/**
 * Song List Scraper and Navigator
 * Handles song list extraction and navigation
 */

import * as cheerio from 'cheerio';
import scraperConfig from '../../config/scraper.config.js';
import { logger } from '../utils/logger.js';
import { InfiniteScrollHandler } from '../utils/infiniteScroll.js';

export class SongScraper {
  constructor(page) {
    this.page = page;
    this.songs = [];
    this.scrollHandler = new InfiniteScrollHandler(page);
  }

  /**
   * Get all songs from the library or playlist
   */
  async getAllSongs(playlistName = null) {
    try {
      logger.info(`Fetching songs${playlistName ? ` from playlist: ${playlistName}` : ' from library'}`);

      // Navigate to appropriate page
      const url = playlistName
        ? `${scraperConfig.urls.playlists}/${encodeURIComponent(playlistName)}`
        : scraperConfig.urls.songs;

      await this.page.goto(url, {
        waitUntil: 'networkidle',
        timeout: 60000
      });

      // Wait for initial content to load
      await this.page.waitForSelector(scraperConfig.selectors.songCard, {
        timeout: 30000
      }).catch(() => {
        logger.warn('No song cards found immediately, will try scrolling...');
      });

      // Perform infinite scroll to load all songs
      await this.scrollHandler.scrollToEnd(scraperConfig.selectors.songCard);

      // Extract song data
      this.songs = await this.extractSongList();

      logger.info(`Found ${this.songs.length} songs`);
      return this.songs;

    } catch (error) {
      logger.error('Error getting songs:', error);
      throw error;
    }
  }

  /**
   * Extract song list from the current page
   */
  async extractSongList() {
    try {
      const songs = await this.page.evaluate((selectors) => {
        const songElements = document.querySelectorAll(selectors.songCard);
        const songList = [];

        songElements.forEach((element, index) => {
          try {
            // Extract song title from image alt attribute (FlowMusic stores title there)
            const imageElement = element.querySelector(selectors.songImage) ||
                               element.querySelector('img[alt]') ||
                               element.querySelector('img');
            const title = imageElement?.alt?.trim() || `Song ${index + 1}`;

            // Extract song URL
            const linkElement = element.querySelector(selectors.songLink) ||
                              element.querySelector('a[href*="/song"]') ||
                              element.querySelector('a');
            const url = linkElement?.href || '';

            // Extract song ID from URL or data attribute
            let songId = element.dataset.songId ||
                        element.dataset.id ||
                        element.id;

            if (!songId && url) {
              const match = url.match(/\/song\/([^\/]+)/);
              songId = match ? match[1] : null;
            }

            // Extract additional metadata if available using actual selectors
            const durationElement = element.querySelector(selectors.duration) ||
                                  element.querySelector('span.text-fg-2.w-8');

            const metadata = {
              duration: durationElement?.innerText?.trim(),
              date: element.querySelector('.date, .created')?.innerText?.trim(),
              plays: element.querySelector('.plays, .play-count')?.innerText?.trim(),
              likes: element.querySelector('.likes, .like-count')?.innerText?.trim(),
              bpm: element.querySelector('.bpm')?.innerText?.trim(),
              key: element.querySelector('.key')?.innerText?.trim(),
              genre: element.querySelector('.genre')?.innerText?.trim()
            };

            // Clean up undefined values
            Object.keys(metadata).forEach(key => {
              if (!metadata[key]) delete metadata[key];
            });

            songList.push({
              id: songId || `song-${index}`,
              title: title,
              url: url,
              index: index,
              metadata: metadata,
              elementHtml: element.outerHTML // For debugging
            });

          } catch (err) {
            console.error('Error extracting song:', err);
          }
        });

        return songList;
      }, scraperConfig.selectors);

      // Filter out invalid songs
      const validSongs = songs.filter(song => song.title && (song.url || song.id));

      logger.info(`Extracted ${validSongs.length} valid songs from ${songs.length} elements`);
      return validSongs;

    } catch (error) {
      logger.error('Error extracting song list:', error);
      return [];
    }
  }

  /**
   * Navigate to a specific song page
   */
  async navigateToSong(song) {
    try {
      logger.debug(`Navigating to song: ${song.title}`);

      if (song.url) {
        // Direct navigation using URL
        await this.page.goto(song.url, {
          waitUntil: 'networkidle',
          timeout: 30000
        });
      } else {
        // Click on song element
        const selector = `[data-id="${song.id}"], #${song.id}`;
        await this.page.click(selector);
        await this.page.waitForLoadState('networkidle');
      }

      // Wait for song page to load
      await this.waitForSongPage();

      logger.debug(`Successfully navigated to: ${song.title}`);
      return true;

    } catch (error) {
      logger.error(`Failed to navigate to song: ${song.title}`, error);
      return false;
    }
  }

  /**
   * Wait for song detail page to load
   */
  async waitForSongPage() {
    try {
      // Wait for menu button or other song page indicators
      await Promise.race([
        this.page.waitForSelector(scraperConfig.selectors.menuButton, { timeout: 10000 }),
        this.page.waitForSelector('.song-details, .track-details', { timeout: 10000 }),
        this.page.waitForSelector('[data-testid="song-page"]', { timeout: 10000 })
      ]);

      // Additional wait for dynamic content
      await this.page.waitForTimeout(2000);

    } catch (error) {
      logger.warn('Song page indicators not found, continuing anyway');
    }
  }

  /**
   * Get song details from current page
   */
  async getSongDetails() {
    try {
      const details = await this.page.evaluate((selectors) => {
        const data = {};

        // Get song title
        const titleElement = document.querySelector('h1, h2, .song-title, .track-title');
        data.title = titleElement?.innerText?.trim();

        // Get metadata
        const metadataSelectors = {
          bpm: selectors.bpm,
          key: selectors.key,
          genre: selectors.genre,
          duration: selectors.duration,
          createdDate: selectors.createdDate
        };

        for (const [field, selector] of Object.entries(metadataSelectors)) {
          const element = document.querySelector(selector);
          if (element) {
            // Try to get the value part if it's a label-value pair
            const text = element.innerText?.trim();
            const match = text.match(/:\s*(.+)/) || text.match(/\s+(.+)/);
            data[field] = match ? match[1] : text;
          }
        }

        // Get lyrics
        const lyricsElement = document.querySelector(selectors.lyricsSection);
        data.lyrics = lyricsElement?.innerText?.trim();

        // Get image URL
        const imageElement = document.querySelector('img.song-cover, img.album-art, .song-image img');
        data.coverUrl = imageElement?.src;

        // Get any additional data attributes
        const songContainer = document.querySelector('[data-song-id], .song-container');
        if (songContainer) {
          data.songId = songContainer.dataset.songId;
          data.attributes = { ...songContainer.dataset };
        }

        return data;
      }, scraperConfig.selectors);

      logger.debug(`Extracted song details: ${details.title}`);
      return details;

    } catch (error) {
      logger.error('Error getting song details:', error);
      return null;
    }
  }

  /**
   * Open song menu (three dots)
   */
  async openSongMenu() {
    try {
      logger.debug('Opening song menu...');

      // Try multiple selector strategies
      const menuSelectors = [
        scraperConfig.selectors.menuButton,
        'button[aria-label*="menu"]',
        'button[aria-label*="More"]',
        'button[aria-label*="options"]',
        'button:has-text("...")',
        'button.menu-button',
        'button.dropdown-toggle',
        '[data-testid="more-button"]'
      ];

      for (const selector of menuSelectors) {
        const menuButton = await this.page.locator(selector).first();
        const exists = await menuButton.count() > 0;

        if (exists) {
          const isVisible = await menuButton.isVisible();
          if (isVisible) {
            await menuButton.click();
            await this.page.waitForTimeout(1000);
            logger.debug('Menu opened successfully');
            return true;
          }
        }
      }

      logger.error('Menu button not found');
      return false;

    } catch (error) {
      logger.error('Error opening menu:', error);
      return false;
    }
  }

  /**
   * Get download options from menu
   */
  async getDownloadOptions() {
    try {
      const options = await this.page.evaluate((selectors) => {
        const downloadOptions = {};

        // Check for MP3 download
        const mp3Element = document.querySelector(selectors.downloadMP3) ||
                          document.querySelector('button:has-text("Download MP3")') ||
                          document.querySelector('a:has-text("Download MP3")');
        downloadOptions.mp3 = !!mp3Element;

        // Check for WAV download
        const wavElement = document.querySelector(selectors.downloadWAV) ||
                          document.querySelector('button:has-text("Download WAV")') ||
                          document.querySelector('a:has-text("Download WAV")');
        downloadOptions.wav = !!wavElement;

        // Check for cover download
        const coverElement = document.querySelector(selectors.downloadCover) ||
                           document.querySelector('button:has-text("Download cover")') ||
                           document.querySelector('a:has-text("Download artwork")');
        downloadOptions.cover = !!coverElement;

        return downloadOptions;
      }, scraperConfig.selectors);

      logger.debug('Available download options:', options);
      return options;

    } catch (error) {
      logger.error('Error getting download options:', error);
      return { mp3: false, wav: false, cover: false };
    }
  }

  /**
   * Navigate back to song list
   */
  async navigateBack() {
    try {
      await this.page.goBack({
        waitUntil: 'networkidle',
        timeout: 30000
      });

      // Wait for song list to be visible again
      await this.page.waitForSelector(scraperConfig.selectors.songCard, {
        timeout: 10000
      }).catch(() => {
        logger.warn('Song cards not immediately visible after navigation');
      });

      return true;

    } catch (error) {
      logger.error('Error navigating back:', error);
      return false;
    }
  }

  /**
   * Get playlists available
   */
  async getPlaylists() {
    try {
      logger.info('Fetching playlists...');

      await this.page.goto(scraperConfig.urls.playlists, {
        waitUntil: 'networkidle'
      });

      const playlists = await this.page.evaluate(() => {
        const playlistElements = document.querySelectorAll('.playlist-card, [data-testid="playlist"], .playlist-item');
        return Array.from(playlistElements).map(el => {
          const nameElement = el.querySelector('.playlist-name, h3, h4, .title');
          const countElement = el.querySelector('.song-count, .count, .tracks');
          const linkElement = el.querySelector('a');

          return {
            name: nameElement?.innerText?.trim(),
            songCount: countElement?.innerText?.trim(),
            url: linkElement?.href
          };
        });
      });

      logger.info(`Found ${playlists.length} playlists`);
      return playlists;

    } catch (error) {
      logger.error('Error getting playlists:', error);
      return [];
    }
  }

  /**
   * Search for specific songs
   */
  async searchSongs(query) {
    try {
      logger.info(`Searching for: ${query}`);

      // Look for search input
      const searchInput = await this.page.locator('input[type="search"], input[placeholder*="Search"]').first();

      if (await searchInput.count() > 0) {
        await searchInput.fill(query);
        await searchInput.press('Enter');
        await this.page.waitForTimeout(2000);

        // Extract filtered results
        return await this.extractSongList();
      }

      logger.warn('Search input not found');
      return [];

    } catch (error) {
      logger.error('Error searching songs:', error);
      return [];
    }
  }

  /**
   * Get statistics about scraped songs
   */
  getStatistics() {
    return {
      totalSongs: this.songs.length,
      songsWithUrls: this.songs.filter(s => s.url).length,
      songsWithMetadata: this.songs.filter(s => Object.keys(s.metadata || {}).length > 0).length
    };
  }
}

export default SongScraper;