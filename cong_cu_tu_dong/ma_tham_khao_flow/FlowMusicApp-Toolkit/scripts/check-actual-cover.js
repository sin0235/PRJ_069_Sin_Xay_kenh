#!/usr/bin/env node

/**
 * Check Actual Cover
 * Take screenshots of two song pages to see what covers are actually shown
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Check Actual Covers on FlowMusic             '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function checkActualCovers() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    const logsDir = path.resolve('./logs');
    await fs.ensureDir(logsDir);

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    const songs = [
      {
        id: 'c9f13ca5-e6be-4495-bede-b346949c5278',
        title: 'Song 1 (c9f13ca5)',
        url: 'https://www.flowmusic.app/song/c9f13ca5-e6be-4495-bede-b346949c5278'
      },
      {
        id: '30c2d062-3f80-4cb9-8e67-47db694743c8',
        title: 'Song 2 (30c2d062)',
        url: 'https://www.flowmusic.app/song/30c2d062-3f80-4cb9-8e67-47db694743c8'
      }
    ];

    for (const song of songs) {
      console.log(chalk.yellow(`\nNavigating to: ${song.title}`));
      console.log(chalk.gray(song.url));

      await page.goto(song.url, {
        waitUntil: 'domcontentloaded',
        timeout: 60000
      });

      // Wait for page to load
      await page.waitForTimeout(5000);

      // Take screenshot
      const screenshotPath = path.join(logsDir, `cover-check-${song.id.substring(0, 8)}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: false });

      console.log(chalk.green(`Screenshot saved: ${screenshotPath}`));

      // Get cover image info
      const coverInfo = await page.evaluate(() => {
        const images = Array.from(document.querySelectorAll('img'));
        const largeImages = images.filter(img => {
          const rect = img.getBoundingClientRect();
          return rect.width > 200 && rect.height > 200;
        });

        return largeImages.map(img => {
          const match = img.src.match(/\/image\/([^/.]+)/);
          const imageId = match ? match[1].substring(0, 8) : 'unknown';
          const rect = img.getBoundingClientRect();

          return {
            imageId,
            size: `${Math.round(rect.width)}x${Math.round(rect.height)}`,
            src: img.src
          };
        });
      });

      console.log(chalk.white('  Cover images found:'));
      coverInfo.forEach((img, i) => {
        console.log(chalk.gray(`    [${i+1}] ${img.size} - ID: ${img.imageId}`));
      });
    }

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.white('Check the screenshots in the logs directory to see'));
    console.log(chalk.white('if FlowMusic actually shows different covers for'));
    console.log(chalk.white('these two songs.'));
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

checkActualCovers();
