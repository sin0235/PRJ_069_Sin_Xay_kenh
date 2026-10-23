#!/usr/bin/env node

/**
 * Test Cover Images
 * Downloads 3 songs and verifies each gets a unique cover
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import scraperConfig from '../config/scraper.config.js';
import { CompleteSongDownloader } from '../src/downloaders/completeSongDownloader.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Test Cover Images                          '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testCoverImages() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    const outputDir = path.resolve('./output-test-covers');

    // Clear test directory
    await fs.remove(outputDir);
    await fs.ensureDir(outputDir);

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    // Get first 3 songs from library
    console.log(chalk.yellow('Fetching songs from library...'));
    await page.goto(scraperConfig.urls.songs, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);

    const songs = await page.evaluate((selectors) => {
      const results = [];
      const songElements = document.querySelectorAll(selectors.songCard);

      for (let i = 0; i < Math.min(3, songElements.length); i++) {
        const element = songElements[i];
        const linkElement = element.querySelector('a[href*="/song/"]');
        const url = linkElement?.href || '';

        if (!url) continue;

        const id = url.split('/song/')[1]?.split('?')[0] || '';
        const titleElement = element.querySelector('h3, h2, [class*="title"]');
        const title = titleElement?.textContent?.trim() || 'Unknown';

        results.push({ id, title, url });
      }

      return results;
    }, scraperConfig.selectors);

    if (songs.length < 3) {
      console.log(chalk.red(`Only found ${songs.length} songs (need 3)`));
      return;
    }

    console.log(chalk.white(`\nDownloading ${songs.length} songs:\n`));
    songs.forEach((song, i) => {
      console.log(chalk.gray(`${i + 1}. ${song.title}`));
    });
    console.log();

    // Download each song
    const downloader = new CompleteSongDownloader(page, outputDir);
    const results = [];

    for (let i = 0; i < songs.length; i++) {
      const song = songs[i];
      console.log(chalk.cyan(`\n[${i + 1}/${songs.length}] Downloading: ${song.title}`));

      const result = await downloader.downloadSong(song, { format: 'mp3' });

      if (result.success) {
        // Read the saved metadata to get cover URL
        const metadata = await fs.readJson(result.files.metadata);

        results.push({
          title: song.title,
          coverUrl: metadata.coverUrl,
          coverFile: result.files.cover,
          coverSize: result.files.cover ? (await fs.stat(result.files.cover)).size : 0
        });

        console.log(chalk.green(`✓ Downloaded successfully`));
      } else {
        console.log(chalk.red(`✗ Failed: ${result.error}`));
        results.push({
          title: song.title,
          error: result.error
        });
      }
    }

    // Analyze results
    console.log(chalk.cyan('\n\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Cover Image Analysis                       '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    const coverUrls = new Set();
    const coverSizes = new Set();

    results.forEach((result, i) => {
      console.log(chalk.white(`Song ${i + 1}: ${result.title}`));

      if (result.error) {
        console.log(chalk.red(`  Error: ${result.error}`));
      } else {
        console.log(chalk.gray(`  Cover URL: ${result.coverUrl?.substring(0, 80)}...`));
        console.log(chalk.gray(`  File Size: ${(result.coverSize / 1024).toFixed(2)} KB`));

        coverUrls.add(result.coverUrl);
        coverSizes.add(result.coverSize);

        // Check if it's a default profile image
        if (result.coverUrl?.includes('default-profile-images')) {
          console.log(chalk.red(`  ✗ PROBLEM: Using default profile image!`));
        } else {
          console.log(chalk.green(`  ✓ Unique cover from proper source`));
        }
      }
      console.log();
    });

    // Summary
    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.white('Summary:'));
    console.log(chalk.gray(`  Total songs: ${results.length}`));
    console.log(chalk.gray(`  Unique cover URLs: ${coverUrls.size}`));
    console.log(chalk.gray(`  Unique file sizes: ${coverSizes.size}`));

    if (coverUrls.size === results.length && coverSizes.size === results.length) {
      console.log(chalk.green('\n✓ SUCCESS: All songs have unique cover images!'));
    } else {
      console.log(chalk.red('\n✗ PROBLEM: Some songs share the same cover!'));
    }

    console.log(chalk.gray(`\nTest output saved to: ${outputDir}`));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    process.exit(1);
  } finally {
    if (context) {
      await context.close();
    }
  }
}

testCoverImages();
