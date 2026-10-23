#!/usr/bin/env node

/**
 * Test Full Library Scraper
 * Downloads first few songs from library with progress tracking
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import { FullLibraryScraper } from '../src/scrapers/fullLibraryScraper.js';
import { logger } from '../src/utils/logger.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Full Library Scraper Test                  '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testFullScraper() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    const outputPath = path.resolve('./output');

    console.log(chalk.yellow(`Profile: ${profilePath}`));
    console.log(chalk.yellow(`Output: ${outputPath}\n`));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 },
      acceptDownloads: true
    });

    const page = context.pages()[0] || await context.newPage();

    // Initialize scraper
    const scraper = new FullLibraryScraper(page, outputPath);

    console.log(chalk.yellow('Scraping library...'));
    const songs = await scraper.scrapeAllSongs();

    console.log(chalk.green(`\n✓ Found ${songs.length} songs in library\n`));

    // Show first 5 songs
    console.log(chalk.white('First 5 songs:'));
    songs.slice(0, 5).forEach((song, i) => {
      console.log(chalk.gray(`  ${i + 1}. ${song.title}`));
      console.log(chalk.gray(`     Duration: ${song.duration || 'N/A'}`));
    });

    // Download first 3 songs
    console.log(chalk.yellow('\n\nDownloading first 3 songs...\n'));

    const results = await scraper.downloadAllSongs({
      format: 'mp3',
      startIndex: 0,
      maxSongs: 3
    });

    console.log();
    console.log(chalk.green('═══════════════════════════════════════════════════'));
    console.log(chalk.green.bold('✓ SCRAPER TEST COMPLETE!'));
    console.log(chalk.green('═══════════════════════════════════════════════════\n'));

    console.log(chalk.white('Results:'));
    console.log(chalk.green(`  ✓ Successful: ${results.successful}`));
    console.log(chalk.yellow(`  ⊘ Skipped: ${results.skipped}`));
    console.log(chalk.red(`  ✗ Failed: ${results.failed}`));
    console.log(chalk.gray(`  Total: ${results.total}\n`));

    // Generate report
    await scraper.generateReport();

    console.log(chalk.yellow('Browser will close in 5 seconds...'));
    await page.waitForTimeout(5000);

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(chalk.gray(error.stack));
    process.exit(1);
  } finally {
    if (context) {
      await context.close();
    }
  }
}

process.on('SIGINT', () => {
  console.log(chalk.cyan('\n\nExiting...\n'));
  process.exit(0);
});

testFullScraper();
