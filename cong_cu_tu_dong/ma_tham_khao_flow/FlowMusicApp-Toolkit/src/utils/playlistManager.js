/**
 * Playlist Manager
 * Handles adding songs to playlists via the UI
 */

import { logger } from './logger.js';
import scraperConfig from '../../config/scraper.config.js';

export class PlaylistManager {
  constructor(page) {
    this.page = page;
  }

  /**
   * Find the nth visible song card on the page, trying multiple selectors
   */
  async getSongCardLocator(index) {
    // Try standard library card selector first
    const libraryCards = this.page.locator(scraperConfig.selectors.songCard);
    if (await libraryCards.count() > index) return libraryCards.nth(index);
    // Fall back to song link parent (session panel cards)
    const songLinks = this.page.locator('a[href*="/song/"]');
    return songLinks.nth(index);
  }

  /**
   * Add a song to a playlist from the songs list page
   * @param {string} songId - The song ID
   * @param {string} playlistName - Name of the playlist to add to
   * @param {number} songIndex - Index of song in the list (0-based)
   */
  async addSongToPlaylist(songId, playlistName, songIndex = 0) {
    try {
      logger.debug(`Adding song ${songId} to playlist "${playlistName}"`);

      const songCard = await this.getSongCardLocator(songIndex);

      // Hover over the song card to reveal buttons
      await songCard.hover();
      await this.page.waitForTimeout(300);

      // Click the "More options" menu button (not the Remix button)
      const menuButton = songCard.locator('button[aria-label^="More options for"]').first();
      const buttonExists = await menuButton.count();
      if (buttonExists === 0) {
        throw new Error('Menu button not found on song card');
      }

      await menuButton.click();
      await this.page.waitForTimeout(800);

      logger.debug('Opened menu');

      // Navigate Down to "Add to..." dynamically, then Right×2 for submenus
      const addToIdx = await this.page.evaluate(() => {
        const items = Array.from(document.querySelectorAll('[role="menuitem"]'))
          .filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
        return items.findIndex(el => el.textContent?.trim() === 'Add to...');
      });
      if (addToIdx === -1) throw new Error('"Add to..." not found in menu');
      for (let i = 0; i < addToIdx + 1; i++) {
        await this.page.keyboard.press('ArrowDown');
        await this.page.waitForTimeout(100);
      }
      await this.page.keyboard.press('ArrowRight');
      await this.page.waitForTimeout(800);
      await this.page.keyboard.press('ArrowRight');
      await this.page.waitForTimeout(1500);

      logger.debug('Playlist list open, finding target...');

      // Find the playlist option (now visible as a menuitem)
      const playlistOption = this.page.locator(`[role="menuitem"]:has-text("${playlistName}")`).first();
      const playlistExists = await playlistOption.count();
      if (playlistExists === 0) {
        throw new Error(`Playlist "${playlistName}" not found`);
      }

      // Check if song is already in the playlist
      const isAlreadyInPlaylist = await playlistOption.locator('svg[data-icon="circle-check"]').count() > 0;

      if (isAlreadyInPlaylist) {
        logger.info(`⊙ Song already in playlist "${playlistName}" - skipping`);
        await this.page.keyboard.press('Escape');
        await this.page.waitForTimeout(300);
        return { success: true, songId, playlistName, alreadyInPlaylist: true };
      }

      await playlistOption.click();
      await this.page.waitForTimeout(500);

      logger.info(`✓ Added song to playlist "${playlistName}"`);
      return { success: true, songId, playlistName, alreadyInPlaylist: false };

    } catch (error) {
      // Try to close any open menu before returning
      try { await this.page.keyboard.press('Escape'); } catch {}
      logger.error(`Failed to add song ${songId} to playlist:`, error);
      return { success: false, songId, playlistName, error: error.message };
    }
  }

  /**
   * Add a song to a playlist by navigating to its song detail page URL.
   * Used for session songs where card-level interaction is unreliable.
   * @param {string} songUrl - Full URL to the song page
   * @param {string} songId - The song ID (for logging)
   * @param {string} playlistName - Playlist to add to
   */
  async addSongToPlaylistFromSongPage(songUrl, songId, playlistName) {
    try {
      logger.debug(`Navigating to song page: ${songUrl}`);
      await this.page.goto(songUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await this.page.waitForTimeout(2500);

      // Song detail page has button[aria-haspopup="menu"] as the options trigger
      const menuButton = this.page.locator('button[aria-haspopup="menu"]').first();
      const buttonExists = await menuButton.count();
      if (buttonExists === 0) {
        throw new Error('Options menu button not found on song page');
      }

      await menuButton.click();
      await this.page.waitForTimeout(800);

      // Navigate Down to "Add to..." (item count varies per song page), then Right×2 for submenus
      const addToIndex = await this.page.evaluate(() => {
        const items = Array.from(document.querySelectorAll('[role="menuitem"]'))
          .filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
        return items.findIndex(el => el.textContent?.trim() === 'Add to...');
      });
      if (addToIndex === -1) throw new Error('"Add to..." not found in menu');
      for (let i = 0; i < addToIndex + 1; i++) {
        await this.page.keyboard.press('ArrowDown');
        await this.page.waitForTimeout(100);
      }
      await this.page.keyboard.press('ArrowRight');
      await this.page.waitForTimeout(800);
      await this.page.keyboard.press('ArrowRight');
      await this.page.waitForTimeout(1500);

      const playlistOption = this.page.locator(`[role="menuitem"]:has-text("${playlistName}")`).first();
      const playlistExists = await playlistOption.count();
      if (playlistExists === 0) {
        throw new Error(`Playlist "${playlistName}" not found`);
      }

      const isAlreadyInPlaylist = await playlistOption.locator('svg[data-icon="circle-check"]').count() > 0;
      if (isAlreadyInPlaylist) {
        logger.info(`⊙ Song already in playlist "${playlistName}" - skipping`);
        await this.page.keyboard.press('Escape');
        await this.page.waitForTimeout(300);
        return { success: true, songId, playlistName, alreadyInPlaylist: true };
      }

      await playlistOption.click();
      await this.page.waitForTimeout(500);

      logger.info(`✓ Added song to playlist "${playlistName}"`);
      return { success: true, songId, playlistName, alreadyInPlaylist: false };

    } catch (error) {
      try { await this.page.keyboard.press('Escape'); } catch {}
      logger.error(`Failed to add song ${songId} via song page:`, error);
      return { success: false, songId, playlistName, error: error.message };
    }
  }

  /**
   * Add multiple songs to a playlist by ID range
   * @param {Array} songs - Array of song objects with { id, title }
   * @param {string} playlistName - Name of the playlist
   * @param {string} startId - Start song ID (inclusive)
   * @param {string} endId - End song ID (inclusive)
   */
  async addSongRangeToPlaylist(songs, playlistName, startId = null, endId = null) {
    const results = {
      successful: 0,
      failed: 0,
      skipped: 0,
      total: 0
    };

    // Filter songs by ID range
    let songsToAdd = songs;
    let startIdx = 0; // Track the starting index in the original array

    if (startId || endId) {
      startIdx = startId ? songs.findIndex(s => s.id === startId) : 0;
      const endIdx = endId ? songs.findIndex(s => s.id === endId) : songs.length - 1;

      if (startId && startIdx === -1) {
        throw new Error(`Start song ID not found: ${startId}`);
      }
      if (endId && endIdx === -1) {
        throw new Error(`End song ID not found: ${endId}`);
      }

      songsToAdd = songs.slice(startIdx, endIdx + 1);
      logger.info(`Adding ${songsToAdd.length} songs (positions ${startIdx + 1}-${endIdx + 1}) to "${playlistName}"`);
    } else {
      logger.info(`Adding ${songsToAdd.length} songs to "${playlistName}"`);
    }

    results.total = songsToAdd.length;

    // Add each song
    for (let i = 0; i < songsToAdd.length; i++) {
      const song = songsToAdd[i];
      const progress = `[${i + 1}/${songsToAdd.length}]`;

      logger.info(`${progress} Adding: ${song.title}`);

      try {
        // Use startIdx + i to get the correct index in the original songs array
        const result = await this.addSongToPlaylist(song.id, playlistName, startIdx + i);

        if (result.success) {
          if (result.alreadyInPlaylist) {
            results.skipped++;
          } else {
            results.successful++;
          }
        } else {
          results.failed++;
          logger.error(`${progress} Failed: ${song.title}`);
        }

        // Small delay between songs to avoid rate limiting
        await this.page.waitForTimeout(500);

      } catch (error) {
        results.failed++;
        logger.error(`${progress} Exception: ${song.title}`, error);
      }
    }

    return results;
  }

  /**
   * Get list of available playlists
   */
  async getAvailablePlaylists() {
    try {
      logger.debug('Getting available playlists...');

      // Wait for song cards to load (library needs ~8s after domcontentloaded)
      const libraryCards = this.page.locator(scraperConfig.selectors.songCard);
      if (await libraryCards.count() === 0) {
        logger.debug('Waiting for song cards to load...');
        try {
          await libraryCards.first().waitFor({ timeout: 15000 });
        } catch {
          logger.error('No song cards found on library page after 15s');
          return [];
        }
      }

      // Open menu on first song card
      const songCard = libraryCards.first();
      await songCard.hover();
      await this.page.waitForTimeout(500);

      logger.debug('Hovered over song card');

      const menuButton = songCard.locator('button[aria-label^="More options for"]').first();
      const buttonExists = await menuButton.count();
      if (buttonExists === 0) {
        logger.error('More options button not found');
        return [];
      }

      await menuButton.click();
      await this.page.waitForTimeout(1000);

      logger.debug('Opened menu');

      // Navigate Down to "Add to..." dynamically, then Right×2 for submenus
      const listAddToIdx = await this.page.evaluate(() => {
        const items = Array.from(document.querySelectorAll('[role="menuitem"]'))
          .filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
        return items.findIndex(el => el.textContent?.trim() === 'Add to...');
      });
      if (listAddToIdx === -1) { logger.error('"Add to..." not found in menu'); return []; }
      for (let i = 0; i < listAddToIdx + 1; i++) {
        await this.page.keyboard.press('ArrowDown');
        await this.page.waitForTimeout(100);
      }
      await this.page.keyboard.press('ArrowRight');
      await this.page.waitForTimeout(800);
      await this.page.keyboard.press('ArrowRight');
      await this.page.waitForTimeout(1500);

      logger.debug('Extracting playlist names...');

      const EXCLUDED = new Set(['Remix', 'Details', 'Download', 'Share...', 'Add to...', 'Report', 'Delete', 'Playlist', 'Queue', 'Create playlist']);

      const playlists = await this.page.evaluate((excluded) => {
        const items = [];
        document.querySelectorAll('[role="menuitem"]').forEach(el => {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            const name = el.textContent?.trim();
            if (name && !excluded.includes(name)) {
              items.push(name);
            }
          }
        });
        return [...new Set(items)];
      }, [...EXCLUDED]);

      logger.debug(`Found ${playlists.length} playlists`);

      // Close menu
      await this.page.keyboard.press('Escape');
      await this.page.waitForTimeout(500);

      return playlists;

    } catch (error) {
      logger.error('Failed to get playlists:', error);

      // Try to close menu if still open
      try {
        await this.page.keyboard.press('Escape');
      } catch (e) {
        // Ignore
      }

      return [];
    }
  }
}

export default PlaylistManager;
