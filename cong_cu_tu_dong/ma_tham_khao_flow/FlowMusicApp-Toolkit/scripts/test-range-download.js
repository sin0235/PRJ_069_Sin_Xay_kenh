#!/usr/bin/env node

/**
 * Test Range Download
 * Quick test of downloading a specific range of songs by ID
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import { FullLibraryScraper } from '../src/scrapers/fullLibraryScraper.js';

async function testRangeDownload() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    const outputDir = path.resolve('./output-range-test');

    // Clean output directory
    await fs.remove(outputDir);
    await fs.ensureDir(outputDir);

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Range Download Test                         '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('Step 1: Loading songs to get IDs...\n'));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 },
      acceptDownloads: true
    });

    const page = context.pages()[0] || await context.newPage();
    const scraper = new FullLibraryScraper(page, outputDir);

    // Load all songs
    await scraper.scrapeAllSongs();

    if (scraper.songs.length < 3) {
      console.log(chalk.red('Not enough songs in library for range test (need at least 3)'));
      return;
    }

    // Get first 3 song IDs for testing
    const startId = scraper.songs[0].id;
    const endId = scraper.songs[2].id;

    console.log(chalk.white('Test range:'));
    console.log(chalk.gray(`  Start: ${scraper.songs[0].title} (${startId})`));
    console.log(chalk.gray(`  ...`));
    console.log(chalk.gray(`  End:   ${scraper.songs[2].title} (${endId})\n`));

    console.log(chalk.yellow('Step 2: Downloading range...\n'));

    const results = await scraper.downloadAllSongs({
      format: 'mp3',
      startId,
      endId
    });

    console.log(chalk.green('\n✓ Range download test complete!\n'));
    console.log(chalk.white('Results:'));
    console.log(chalk.green(`  ✓ Successful: ${results.successful}`));
    console.log(chalk.yellow(`  ⊘ Skipped: ${results.skipped}`));
    console.log(chalk.red(`  ✗ Failed: ${results.failed}`));
    console.log(chalk.gray(`  Total: ${results.total}\n`));

    console.log(chalk.white('Files saved to: ') + chalk.cyan(outputDir));

    // List downloaded files
    const files = await fs.readdir(outputDir);
    const mp3Files = files.filter(f => f.endsWith('.mp3'));

    console.log(chalk.white('\nDownloaded songs:'));
    mp3Files.forEach(file => {
      console.log(chalk.gray(`  - ${file}`));
    });

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
    process.exit(1);
  } finally {
    if (context) await context.close();
  }
}

testRangeDownload();
