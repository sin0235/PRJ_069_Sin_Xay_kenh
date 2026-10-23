#!/usr/bin/env node

/**
 * Test Download - Small Sample
 * Downloads 2-3 songs to test title enhancement and cover extraction
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import scraperConfig from '../config/scraper.config.js';
import { CompleteSongDownloader } from '../src/downloaders/completeSongDownloader.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Test Download - Sample Songs                 '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testDownload() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    const outputDir = path.resolve('./output');

    await fs.ensureDir(outputDir);

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    // Get first 3 songs from library
    console.log(chalk.yellow('Fetching songs from your library...\n'));
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

    if (songs.length === 0) {
      console.log(chalk.red('No songs found in library.'));
      console.log(chalk.gray('Make sure you are logged in.\n'));
      return;
    }

    console.log(chalk.white(`Found ${songs.length} songs to download:\n`));
    songs.forEach((song, i) => {
      console.log(chalk.gray(`  ${i + 1}. ${song.title}`));
    });
    console.log();

    // Download each song
    const downloader = new CompleteSongDownloader(page, outputDir);
    const results = [];

    for (let i = 0; i < songs.length; i++) {
      const song = songs[i];
      console.log(chalk.cyan(`\n${'─'.repeat(55)}`));
      console.log(chalk.cyan(`[${i + 1}/${songs.length}] Downloading: ${song.title}`));
      console.log(chalk.cyan(`${'─'.repeat(55)}\n`));

      const result = await downloader.downloadSong(song, { format: 'mp3' });

      if (result.success) {
        console.log(chalk.green(`✓ Success!`));

        // Read metadata to show what we got
        const metadata = await fs.readJson(result.files.metadata);

        console.log(chalk.white('\nSaved as:'));
        console.log(chalk.gray(`  Title: "${metadata.title}"`));
        if (metadata.originalTitle && metadata.originalTitle !== metadata.title) {
          console.log(chalk.gray(`  Original: "${metadata.originalTitle}"`));
        }
        console.log(chalk.gray(`  Files:`));
        console.log(chalk.gray(`    - ${path.basename(result.files.audio)}`));
        console.log(chalk.gray(`    - ${path.basename(result.files.cover)}`));
        console.log(chalk.gray(`    - ${path.basename(result.files.metadata)}`));

        // Show cover info
        if (metadata.coverUrl) {
          const coverIdMatch = metadata.coverUrl.match(/\/image\/([^/.]+)/);
          const coverId = coverIdMatch ? coverIdMatch[1].substring(0, 8) : 'unknown';
          console.log(chalk.gray(`  Cover ID: ${coverId}`));
        }

        results.push({
          title: metadata.title,
          success: true,
          files: result.files
        });
      } else {
        console.log(chalk.red(`✗ Failed: ${result.error}`));
        results.push({
          title: song.title,
          success: false,
          error: result.error
        });
      }
    }

    // Summary
    console.log(chalk.cyan('\n\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Download Summary                            '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;

    console.log(chalk.white(`Total: ${results.length} songs`));
    console.log(chalk.green(`✓ Successful: ${successful}`));
    if (failed > 0) {
      console.log(chalk.red(`✗ Failed: ${failed}`));
    }

    console.log(chalk.white('\nNext steps:'));
    console.log(chalk.gray('  1. Check the files in ./output/'));
    console.log(chalk.gray('  2. Verify titles are clean (no key/BPM)'));
    console.log(chalk.gray('  3. Verify each song has unique cover'));
    console.log(chalk.gray('  4. (Optional) Run AI review: node scripts/ai-title-review.js\n'));

    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
    process.exit(1);
  } finally {
    if (context) {
      await context.close();
    }
  }
}

testDownload();
