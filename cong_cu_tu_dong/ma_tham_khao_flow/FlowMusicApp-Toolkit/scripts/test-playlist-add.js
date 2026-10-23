#!/usr/bin/env node

/**
 * Test Playlist Add
 * Tests adding a single song to a playlist
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';
import { PlaylistManager } from '../src/utils/playlistManager.js';

async function testPlaylistAdd() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Test Playlist Add                           '));
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
    await page.waitForTimeout(5000); // Wait longer for songs to load

    // Get first song info
    const firstSong = await page.evaluate((selectors) => {
      const element = document.querySelector(selectors.songCard);
      if (!element) {
        console.error('Song card selector failed:', selectors.songCard);
        console.error('Available elements:', document.querySelectorAll('.group').length);
        return null;
      }

      const link = element.querySelector('a[href*="/song/"]');
      const url = link?.href || '';
      const id = url.split('/song/')[1]?.split('?')[0] || '';

      const imageElement = element.querySelector('img[alt]') || element.querySelector('img');
      const title = imageElement?.alt?.trim() || 'Unknown';

      return { id, title, url };
    }, scraperConfig.selectors);

    if (!firstSong) {
      console.log(chalk.red('No songs found!'));
      return;
    }

    console.log(chalk.white(`First song: ${chalk.cyan(firstSong.title)}`));
    console.log(chalk.gray(`Song ID: ${firstSong.id}\n`));

    // Get available playlists
    console.log(chalk.yellow('[2] Getting available playlists...\n'));
    const playlists = await playlistManager.getAvailablePlaylists();

    if (playlists.length === 0) {
      console.log(chalk.red('No playlists found!'));
      return;
    }

    console.log(chalk.white('Available playlists:\n'));
    playlists.forEach((name, idx) => {
      console.log(chalk.gray(`  [${idx}] ${name}`));
    });
    console.log();

    // Use "God Is Water" if available, otherwise use first playlist
    const targetPlaylist = playlists.find(p => p.toLowerCase().includes('god is water')) || playlists[0];

    console.log(chalk.yellow(`[3] Adding song to playlist: ${chalk.cyan(targetPlaylist)}\n`));

    // Add the song
    const result = await playlistManager.addSongToPlaylist(firstSong.id, targetPlaylist, 0);

    if (result.success) {
      console.log(chalk.green('\n✓ Success!\n'));
      console.log(chalk.white('Song added to playlist successfully.\n'));
    } else {
      console.log(chalk.red('\n✗ Failed!\n'));
      console.log(chalk.red(`Error: ${result.error}\n`));
    }

    console.log(chalk.yellow('Browser staying open for verification. Press Ctrl+C when done.\n'));

    // Keep browser open
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

testPlaylistAdd();
