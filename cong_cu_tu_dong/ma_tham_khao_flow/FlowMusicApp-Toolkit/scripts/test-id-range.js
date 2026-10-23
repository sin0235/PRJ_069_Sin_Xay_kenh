#!/usr/bin/env node

/**
 * Test adding songs by ID range
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import { PlaylistManager } from '../src/utils/playlistManager.js';
import scraperConfig from '../config/scraper.config.js';

async function testIdRange() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');

    const startId = '5c624602-9ee8-4356-a648-e12836a56458';
    const endId = '535b1b67-bc23-41dc-82b1-700b521515a9';

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Test ID Range Selection                    '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));
    console.log(chalk.white(`Start ID: ${startId}`));
    console.log(chalk.white(`End ID: ${endId}\n`));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();
    const playlistManager = new PlaylistManager(page);

    // Navigate to songs page
    console.log(chalk.yellow('[1] Loading songs list...\n'));
    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);

    // Get all songs
    console.log(chalk.yellow('[2] Extracting all songs...\n'));
    const songs = await page.evaluate((selectors) => {
      const songCards = document.querySelectorAll(selectors.songCard);
      const songs = [];

      songCards.forEach(card => {
        const link = card.querySelector('a[href*="/song/"]');
        const url = link?.href || '';
        const id = url.split('/song/')[1]?.split('?')[0] || '';
        const imageElement = card.querySelector('img[alt]') || card.querySelector('img');
        const title = imageElement?.alt?.trim() || 'Unknown';

        if (id && title) {
          songs.push({ id, title, url });
        }
      });

      return songs;
    }, scraperConfig.selectors);

    console.log(chalk.white(`Total songs on page: ${songs.length}\n`));

    // Find start and end indices
    const startIdx = songs.findIndex(s => s.id === startId);
    const endIdx = songs.findIndex(s => s.id === endId);

    console.log(chalk.white(`Start ID found at index: ${startIdx}`));
    console.log(chalk.white(`End ID found at index: ${endIdx}\n`));

    if (startIdx === -1) {
      console.log(chalk.red('Start ID not found!\n'));
      await context.close();
      process.exit(1);
    }

    if (endIdx === -1) {
      console.log(chalk.red('End ID not found!\n'));
      await context.close();
      process.exit(1);
    }

    const songsInRange = songs.slice(startIdx, endIdx + 1);
    console.log(chalk.green(`Songs in range: ${songsInRange.length}\n`));
    songsInRange.forEach((song, idx) => {
      console.log(chalk.gray(`  [${idx}] ${song.title}`));
      console.log(chalk.gray(`      ID: ${song.id}`));
    });
    console.log();

    // Add songs to playlist
    const playlistName = 'God Is Water';
    console.log(chalk.yellow(`[3] Adding songs to playlist "${playlistName}"...\n`));

    const results = await playlistManager.addSongRangeToPlaylist(
      songs,
      playlistName,
      startId,
      endId
    );

    // Display results
    console.log(chalk.white('\n═══════════════════════════════════════════════════'));
    console.log(chalk.white('Results:\n'));
    console.log(chalk.green(`✓ Successful: ${results.successful}`));
    console.log(chalk.red(`✗ Failed: ${results.failed}`));
    console.log(chalk.gray(`- Skipped: ${results.skipped}`));
    console.log(chalk.white(`  Total: ${results.total}`));
    console.log(chalk.white('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('Browser staying open. Press Ctrl+C when done.\n'));
    await new Promise(() => {});

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
    if (context) {
      console.log(chalk.yellow('\nBrowser staying open. Press Ctrl+C when done.\n'));
      await new Promise(() => {});
    }
  }
}

testIdRange();
