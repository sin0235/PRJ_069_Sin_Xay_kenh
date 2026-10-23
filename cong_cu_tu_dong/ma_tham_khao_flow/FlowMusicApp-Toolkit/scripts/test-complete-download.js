#!/usr/bin/env node

/**
 * Test Complete Song Download
 * Downloads audio + cover + metadata for one song
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';
import { CompleteSongDownloader } from '../src/downloaders/completeSongDownloader.js';
import { logger } from '../src/utils/logger.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Complete Song Download Test                '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testCompleteDownload() {
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

    // Navigate to songs page
    console.log(chalk.yellow('Getting first song from library...'));
    await page.goto(scraperConfig.urls.songs, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);

    // Get first song
    const firstSong = await page.evaluate((selectors) => {
      const songElement = document.querySelector(selectors.songCard);
      if (!songElement) return null;

      const imageElement = songElement.querySelector('img[alt]');
      const linkElement = songElement.querySelector('a[href*="/song/"]');
      const durationElement = songElement.querySelector('span.text-fg-2.w-8');

      const url = linkElement?.href || '';
      let songId = null;
      if (url) {
        const match = url.match(/\/song\/([^\/]+)/);
        songId = match ? match[1] : null;
      }

      return {
        title: imageElement?.alt,
        url: url,
        id: songId,
        duration: durationElement?.textContent?.trim()
      };
    }, scraperConfig.selectors);

    if (!firstSong) {
      console.log(chalk.red('✗ Could not find any songs'));
      return;
    }

    console.log(chalk.green(`✓ Found song: ${firstSong.title}`));
    console.log(chalk.gray(`  URL: ${firstSong.url}`));
    console.log(chalk.gray(`  Duration: ${firstSong.duration || 'N/A'}\n`));

    // Initialize downloader
    const downloader = new CompleteSongDownloader(page, outputPath);

    // Download complete package
    console.log(chalk.yellow('Starting complete download...\n'));

    const result = await downloader.downloadSong(firstSong, {
      format: 'mp3',
      includeStems: false
    });

    console.log();

    if (result.success) {
      console.log(chalk.green('═══════════════════════════════════════════════════'));
      console.log(chalk.green.bold('✓ COMPLETE DOWNLOAD SUCCESSFUL!'));
      console.log(chalk.green('═══════════════════════════════════════════════════\n'));

      console.log(chalk.white('Song:'), chalk.cyan(result.title));
      console.log(chalk.white('Folder:'), chalk.gray(result.folder));
      console.log();

      console.log(chalk.white('Downloaded Files:'));
      console.log(chalk.green(`  ✓ Audio: ${path.basename(result.files.audio)}`));
      if (result.files.cover) {
        console.log(chalk.green(`  ✓ Cover: ${path.basename(result.files.cover)}`));
      }
      console.log(chalk.green(`  ✓ Metadata: ${path.basename(result.files.metadata)}`));
      console.log();

      console.log(chalk.white('Metadata:'));
      console.log(chalk.gray(`  BPM: ${result.metadata.bpm || 'N/A'}`));
      console.log(chalk.gray(`  Key: ${result.metadata.key || 'N/A'}`));
      console.log(chalk.gray(`  Model: ${result.metadata.model || 'N/A'}`));
      console.log(chalk.gray(`  Duration: ${result.metadata.duration || 'N/A'}`));
      if (result.metadata.lyrics) {
        console.log(chalk.gray(`  Lyrics: ${result.metadata.lyrics.substring(0, 50)}...`));
      }
      console.log();

    } else {
      console.log(chalk.red('✗ Download failed:'), result.error);
    }

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

testCompleteDownload();
