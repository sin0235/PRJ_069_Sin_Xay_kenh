#!/usr/bin/env node

/**
 * Test Single Download
 * Quick test of title extraction fix
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import scraperConfig from '../config/scraper.config.js';
import { CompleteSongDownloader } from '../src/downloaders/completeSongDownloader.js';

async function test() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    const outputDir = path.resolve('./output-test');

    await fs.remove(outputDir);
    await fs.ensureDir(outputDir);

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    console.log(chalk.yellow('Fetching a song...\n'));
    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    const songs = await page.evaluate((selectors) => {
      const element = document.querySelector(selectors.songCard);
      if (!element) return null;

      const link = element.querySelector('a[href*="/song/"]');
      const url = link?.href || '';
      const id = url.split('/song/')[1]?.split('?')[0] || '';
      const title = element.querySelector('h3, h2')?.textContent?.trim() || 'Unknown';

      return [{ id, title, url }];
    }, scraperConfig.selectors);

    if (!songs || songs.length === 0) {
      console.log(chalk.red('No songs found'));
      return;
    }

    const downloader = new CompleteSongDownloader(page, outputDir);
    const result = await downloader.downloadSong(songs[0], { format: 'mp3' });

    if (result.success) {
      const metadata = await fs.readJson(result.files.metadata);
      console.log(chalk.green('\n✓ Downloaded successfully!\n'));
      console.log(chalk.white('Title: ') + chalk.cyan(metadata.title));
      console.log(chalk.white('Original: ') + chalk.gray(metadata.originalTitle));
      console.log(chalk.white('BPM: ') + chalk.gray(metadata.bpm));
      console.log(chalk.white('Key: ') + chalk.gray(metadata.key));
      console.log(chalk.white('\nLyrics preview:'));
      console.log(chalk.gray(metadata.lyrics?.split('\n').slice(0, 4).join('\n')));
    } else {
      console.log(chalk.red(`Failed: ${result.error}`));
    }

  } catch (error) {
    console.error(chalk.red('Error:'), error.message);
  } finally {
    if (context) await context.close();
  }
}

test();
