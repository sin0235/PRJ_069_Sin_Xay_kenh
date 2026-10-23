#!/usr/bin/env node

/**
 * Add Songs to Playlist
 * Batch add songs to a playlist with optional ID range filtering
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import { PlaylistManager } from '../src/utils/playlistManager.js';
import scraperConfig from '../config/scraper.config.js';

async function createBrowserContext(cdpUrl, profilePath) {
  if (cdpUrl) {
    const browser = await chromium.connectOverCDP(cdpUrl);
    const context = browser.contexts()[0];
    const page = context.pages().find(p => !p.isClosed()) || await context.newPage();
    return { browser, context, page, isCDP: true };
  }
  const launchOpts = {
    headless: false,
    viewport: { width: 1920, height: 1080 },
    args: ['--disable-blink-features=AutomationControlled'],
    ignoreDefaultArgs: ['--enable-automation']
  };
  let ctx;
  try {
    ctx = await chromium.launchPersistentContext(profilePath, { ...launchOpts, channel: 'chrome' });
  } catch {
    ctx = await chromium.launchPersistentContext(profilePath, launchOpts);
  }
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.addInitScript(() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); });

  // Restore saved session cookies
  const stateFile = path.join(path.resolve(profilePath), 'session-state.json');
  if (await fs.pathExists(stateFile)) {
    try {
      const state = await fs.readJson(stateFile);
      if (state.cookies?.length > 0) await ctx.addCookies(state.cookies);
    } catch {}
  }

  return { browser: null, context: ctx, page, isCDP: false };
}

async function closeBrowserContext({ browser, context, isCDP }) {
  if (isCDP) {
    await browser.close();
  } else {
    await context.close();
  }
}

async function addToPlaylist() {
  let bc = null;

  try {
    // Parse command line arguments
    const args = process.argv.slice(2);
    let playlistName = null;
    let startId = null;
    let endId = null;
    let listPlaylists = false;
    let cdpUrl = process.env.FLOWMUSIC_CDP_URL || null;

    for (let i = 0; i < args.length; i++) {
      if (args[i] === '--playlist' || args[i] === '-p') {
        playlistName = args[++i];
      } else if (args[i] === '--start-id' || args[i] === '-s') {
        startId = args[++i];
      } else if (args[i] === '--end-id' || args[i] === '-e') {
        endId = args[++i];
      } else if (args[i] === '--list' || args[i] === '-l') {
        listPlaylists = true;
      } else if (args[i] === '--cdp-url') {
        cdpUrl = args[++i];
      }
    }

    // Show usage if no arguments
    if (!listPlaylists && !playlistName) {
      console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
      console.log(chalk.cyan.bold('     Add Songs to Playlist                       '));
      console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));
      console.log(chalk.white('Usage:'));
      console.log(chalk.gray('  node scripts/add-to-playlist.js --list'));
      console.log(chalk.gray('  node scripts/add-to-playlist.js --playlist "God Is Water"'));
      console.log(chalk.gray('  node scripts/add-to-playlist.js -p "God Is Water" -s <start-id> -e <end-id>\n'));
      console.log(chalk.white('Options:'));
      console.log(chalk.gray('  -l, --list                  List available playlists'));
      console.log(chalk.gray('  -p, --playlist <name>       Playlist name (required)'));
      console.log(chalk.gray('  -s, --start-id <id>         Start song ID (optional)'));
      console.log(chalk.gray('  -e, --end-id <id>           End song ID (optional)'));
      console.log(chalk.gray('  --cdp-url <url>             Connect to existing Chrome (e.g. http://localhost:9222)\n'));
      console.log(chalk.white('Examples:'));
      console.log(chalk.gray('  # List all playlists'));
      console.log(chalk.gray('  node scripts/add-to-playlist.js --list\n'));
      console.log(chalk.gray('  # Add all songs to playlist'));
      console.log(chalk.gray('  node scripts/add-to-playlist.js --playlist "God Is Water"\n'));
      console.log(chalk.gray('  # Add songs within ID range'));
      console.log(chalk.gray('  node scripts/add-to-playlist.js -p "God Is Water" -s abc123 -e def456\n'));
      process.exit(0);
    }

    const profilePath = path.resolve('./.browser-profile');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Add Songs to Playlist                       '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    bc = await createBrowserContext(cdpUrl, profilePath);
    const { page } = bc;
    const playlistManager = new PlaylistManager(page);

    // Navigate to library and wait for song cards to render
    console.log(chalk.yellow('[1] Loading library...\n'));
    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    try {
      await page.locator(scraperConfig.selectors.songCard).first().waitFor({ timeout: 15000 });
    } catch {
      await page.waitForTimeout(8000); // fallback fixed wait
    }

    // If listing playlists, show them and exit
    if (listPlaylists) {
      console.log(chalk.yellow('[2] Getting available playlists...\n'));
      const playlists = await playlistManager.getAvailablePlaylists();

      if (playlists.length === 0) {
        console.log(chalk.red('No playlists found!\n'));
      } else {
        console.log(chalk.green(`Found ${playlists.length} playlists:\n`));
        playlists.forEach((name, idx) => {
          console.log(chalk.white(`  [${idx}] ${name}`));
        });
        console.log();
      }

      await closeBrowserContext(bc);
      process.exit(0);
    }

    // Collect songs from /library/my-songs using the same scroll approach as the downloader:
    // scroll <main>, accumulate in a Map (handles virtualized DOM), 3 s between scrolls.
    console.log(chalk.yellow('[2] Extracting song list...\n'));

    const discoveredSongs = new Map();
    const MAX_SCROLL = scraperConfig.behavior.infiniteScroll.maxScrollAttempts;
    const noNewContentThreshold = scraperConfig.behavior.infiniteScroll.noNewContentThreshold;
    let noNewCount = 0;
    let prevCount = 0;

    for (let attempt = 0; attempt < MAX_SCROLL; attempt++) {
      const batch = await page.evaluate((sel) => {
        const cards = document.querySelectorAll(sel);
        const result = [];
        cards.forEach(card => {
          const link = card.querySelector('a[href*="/song/"]');
          const url = link?.href || '';
          const id = url.split('/song/')[1]?.split('?')[0] || '';
          const img = card.querySelector('img[alt]') || card.querySelector('img');
          const title = img?.alt?.trim() || 'Unknown';
          if (id) result.push({ id, title, url });
        });
        return result;
      }, scraperConfig.selectors.songCard);

      batch.forEach(s => { if (s.id) discoveredSongs.set(s.id, s); });

      if (discoveredSongs.size !== prevCount) {
        noNewCount = 0;
        prevCount = discoveredSongs.size;
        process.stdout.write(chalk.gray(`\r  Loaded ${discoveredSongs.size} songs...`));
      } else {
        noNewCount++;
        if (noNewCount >= noNewContentThreshold) break;
      }

      // Stop early if we've found the endId
      if (endId && discoveredSongs.has(endId)) break;

      await page.evaluate(() => {
        // Find the container with the most scrollable overflow — the song list's lazy-load container
        const container = Array.from(document.querySelectorAll('[class*="overflow-y-auto"]'))
          .filter(el => window.getComputedStyle(el).overflowY === 'auto')
          .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight))[0];
        if (container) {
          container.scrollTop = container.scrollHeight;
        } else {
          window.scrollBy(0, window.innerHeight);
        }
      });
      await page.waitForTimeout(4000);
    }
    if (discoveredSongs.size > 0) process.stdout.write('\n');

    let songs = Array.from(discoveredSongs.values());

    console.log(chalk.white(`Found ${songs.length} total songs\n`));

    if (songs.length === 0) {
      console.log(chalk.red('No songs found!\n'));
      await closeBrowserContext(bc);
      process.exit(1);
    }

    // Determine range to add
    const endIdx = endId ? songs.findIndex(s => s.id === endId) : songs.length - 1;
    const startIdx = startId ? songs.findIndex(s => s.id === startId) : 0;
    if (endId && endIdx === -1) {
      console.log(chalk.red(`End song ID not found: ${endId}\n`));
      await closeBrowserContext(bc);
      process.exit(1);
    }
    const songsToAdd = songs.slice(startIdx, endIdx + 1);
    console.log(chalk.white(`Adding ${songsToAdd.length} songs (up to "${songs[endIdx]?.title}") to "${playlistName}"...\n`));

    // Navigate to each song's page URL to add it — avoids card-index issues with virtualized library
    const results = { successful: 0, failed: 0, skipped: 0, total: songsToAdd.length };
    let globalIdx = 0;
    for (const song of songsToAdd) {
      console.log(chalk.white(`  [${++globalIdx}/${results.total}] Adding: ${song.title}`));
      const result = await playlistManager.addSongToPlaylistFromSongPage(song.url, song.id, playlistName);
      if (result.success) {
        if (result.alreadyInPlaylist) {
          results.skipped++;
          console.log(chalk.gray(`    ⊙ Already in playlist`));
        } else {
          results.successful++;
        }
      } else {
        results.failed++;
        console.log(chalk.red(`    ✗ Failed: ${result.error}`));
      }
    }

    // Display results
    console.log(chalk.white('\n═══════════════════════════════════════════════════'));
    console.log(chalk.white('Results:\n'));
    console.log(chalk.green(`✓ Successful: ${results.successful}`));
    console.log(chalk.red(`✗ Failed: ${results.failed}`));
    console.log(chalk.gray(`- Skipped: ${results.skipped}`));
    console.log(chalk.white(`  Total: ${results.total}`));
    console.log(chalk.white('═══════════════════════════════════════════════════\n'));

    await closeBrowserContext(bc);

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
    if (bc) {
      await closeBrowserContext(bc);
    }
    process.exit(1);
  }
}

addToPlaylist();
