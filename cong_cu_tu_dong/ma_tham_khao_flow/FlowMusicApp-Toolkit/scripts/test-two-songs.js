#!/usr/bin/env node

/**
 * Test adding first 2 songs to playlist
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import { PlaylistManager } from '../src/utils/playlistManager.js';
import scraperConfig from '../config/scraper.config.js';

async function testTwoSongs() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Test Adding First 2 Songs                  '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

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

    // Get first 2 songs
    console.log(chalk.yellow('[2] Extracting first 2 songs...\n'));
    const songs = await page.evaluate((selectors) => {
      const songCards = document.querySelectorAll(selectors.songCard);
      const songs = [];

      // Only get first 2
      for (let i = 0; i < Math.min(2, songCards.length); i++) {
        const card = songCards[i];
        const link = card.querySelector('a[href*="/song/"]');
        const url = link?.href || '';
        const id = url.split('/song/')[1]?.split('?')[0] || '';
        const imageElement = card.querySelector('img[alt]') || card.querySelector('img');
        const title = imageElement?.alt?.trim() || 'Unknown';

        if (id && title) {
          songs.push({ id, title, url });
        }
      }

      return songs;
    }, scraperConfig.selectors);

    console.log(chalk.white(`Found ${songs.length} songs:\n`));
    songs.forEach((song, idx) => {
      console.log(chalk.gray(`  [${idx}] ${song.title}`));
    });
    console.log();

    // Add songs to playlist
    const playlistName = 'God Is Water';
    console.log(chalk.yellow(`[3] Adding songs to playlist "${playlistName}"...\n`));

    const results = await playlistManager.addSongRangeToPlaylist(
      songs,
      playlistName,
      null,
      null
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

testTwoSongs();
