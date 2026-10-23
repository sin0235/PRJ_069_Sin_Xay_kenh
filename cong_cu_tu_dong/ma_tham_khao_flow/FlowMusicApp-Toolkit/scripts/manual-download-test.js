#!/usr/bin/env node

/**
 * Manual Download Test
 * Opens song page and waits for you to manually click download
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Manual Download Test                       '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function manualDownloadTest() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    console.log(chalk.yellow(`Loading profile: ${profilePath}\n`));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 },
      acceptDownloads: true
    });

    const page = context.pages()[0] || await context.newPage();

    console.log(chalk.yellow('Navigating to songs page...'));
    await page.goto(scraperConfig.urls.songs, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });

    await page.waitForTimeout(5000);

    // Get first song
    const firstSong = await page.evaluate((selectors) => {
      const songElement = document.querySelector(selectors.songCard);
      if (!songElement) return null;

      const imageElement = songElement.querySelector('img[alt]');
      const linkElement = songElement.querySelector('a[href*="/song/"]');

      return {
        title: imageElement?.alt,
        url: linkElement?.href
      };
    }, scraperConfig.selectors);

    console.log(chalk.green(`✓ Found song: ${firstSong.title}\n`));

    // Navigate to song detail page
    console.log(chalk.yellow('Navigating to song detail page...'));
    await page.goto(firstSong.url, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });

    await page.waitForTimeout(5000);
    console.log(chalk.green('✓ Song detail page loaded\n'));

    // Extract metadata using more robust method
    console.log(chalk.yellow('Extracting metadata...\n'));

    const metadata = await page.evaluate(() => {
      const data = {};

      // Get everything as text
      const pageText = document.body.innerText;

      // Find title - it's the large heading
      const h1 = document.querySelector('h1');
      const h2Large = document.querySelector('h2.text-2xl, h2.text-3xl, h2.text-xl');
      data.title = (h1 || h2Large)?.textContent?.trim();

      // Extract BPM from page text
      const bpmMatch = pageText.match(/(\d+)\s*bpm/i);
      if (bpmMatch) data.bpm = bpmMatch[1];

      // Extract Key from page text
      const keyMatch = pageText.match(/([A-G][#b]?\s*(?:Major|Minor))/i);
      if (keyMatch) data.key = keyMatch[1];

      // Extract Model
      const modelMatch = pageText.match(/MODEL\s*([A-Z0-9\-\.]+)/i);
      if (modelMatch) data.model = modelMatch[1].trim();

      // Extract Lyrics
      const lyricsMatch = pageText.match(/LYRICS\s*([^\n]+)/i);
      if (lyricsMatch) data.lyrics = lyricsMatch[1].trim();

      // Get full SOUND description
      const soundMatch = pageText.match(/SOUND\s*([^M]+?)(?=MODEL|LYRICS|$)/is);
      if (soundMatch) data.description = soundMatch[1].trim();

      return data;
    });

    console.log(chalk.cyan('═══ Extracted Metadata ═══\n'));
    console.log(chalk.white('Title:'), chalk.green(metadata.title || 'Not found'));
    console.log(chalk.white('BPM:'), chalk.green(metadata.bpm || 'Not found'));
    console.log(chalk.white('Key:'), chalk.green(metadata.key || 'Not found'));
    console.log(chalk.white('Model:'), chalk.green(metadata.model || 'Not found'));
    console.log(chalk.white('Lyrics:'), chalk.green(metadata.lyrics || 'Not found'));
    if (metadata.description) {
      console.log(chalk.white('Description:'), chalk.gray(metadata.description.substring(0, 100) + '...'));
    }
    console.log();

    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.yellow.bold('         MANUAL TEST INSTRUCTIONS                  '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));
    console.log(chalk.white('Please manually test the download functionality:\n'));
    console.log(chalk.yellow('1. Click the DOWNLOAD icon button (down arrow)'));
    console.log(chalk.yellow('2. Check what modal/menu appears'));
    console.log(chalk.yellow('3. Try clicking download options (MP3, WAV, Stems, etc.)'));
    console.log(chalk.yellow('4. Note what happens (direct download, new page, etc.)\n'));
    console.log(chalk.white('The browser will stay open for 5 minutes.'));
    console.log(chalk.gray('Press Ctrl+C when done.\n'));

    // Listen for downloads
    page.on('download', async download => {
      console.log(chalk.green('\n✓ Download started!'));
      console.log(chalk.white('  Filename:'), chalk.cyan(download.suggestedFilename()));
      console.log(chalk.white('  URL:'), chalk.gray(download.url()));

      try {
        const downloadPath = path.join(process.cwd(), 'logs', 'test-downloads', download.suggestedFilename());
        await download.saveAs(downloadPath);
        console.log(chalk.green('  ✓ Saved to:'), chalk.gray(downloadPath));
      } catch (err) {
        console.log(chalk.yellow('  Note: Download detected but not saved'));
      }
      console.log();
    });

    // Wait 5 minutes
    await page.waitForTimeout(300000);

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    process.exit(1);
  } finally {
    if (context) {
      await context.close();
    }
  }
}

process.on('SIGINT', () => {
  console.log(chalk.cyan('\n\n═══════════════════════════════════════════════════'));
  console.log(chalk.green('Thanks for testing!'));
  console.log(chalk.white('Please share your findings so I can automate this.'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));
  process.exit(0);
});

manualDownloadTest();
