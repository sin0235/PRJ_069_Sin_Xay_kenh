#!/usr/bin/env node

/**
 * Debug Cover Images
 * Shows all images on song page to identify correct cover selector
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Debug Cover Images                         '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function debugCoverImages() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    // Get first song from library
    await page.goto(scraperConfig.urls.songs, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);

    const firstSong = await page.evaluate((selectors) => {
      const songElement = document.querySelector(selectors.songCard);
      if (!songElement) return null;

      const linkElement = songElement.querySelector('a[href*="/song/"]');
      const url = linkElement?.href || '';

      return url ? { url } : null;
    }, scraperConfig.selectors);

    if (!firstSong) {
      console.log(chalk.red('No songs found'));
      return;
    }

    // Navigate to song page
    console.log(chalk.yellow(`Navigating to song page...`));
    await page.goto(firstSong.url, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);

    // Get all images on the page
    const images = await page.evaluate(() => {
      const imgs = Array.from(document.querySelectorAll('img'));

      return imgs.map((img, index) => {
        const rect = img.getBoundingClientRect();

        return {
          index,
          src: img.src,
          alt: img.alt || '',
          width: rect.width,
          height: rect.height,
          classes: img.className,
          visible: rect.width > 0 && rect.height > 0,
          // Get parent element info
          parentTag: img.parentElement?.tagName,
          parentClasses: img.parentElement?.className || ''
        };
      }).filter(img => img.visible); // Only visible images
    });

    console.log(chalk.white(`Found ${images.length} visible images:\n`));

    images.forEach(img => {
      console.log(chalk.cyan(`Image ${img.index}:`));
      console.log(chalk.gray(`  Size: ${Math.round(img.width)}x${Math.round(img.height)}`));
      console.log(chalk.gray(`  Alt: ${img.alt.substring(0, 50)}`));
      console.log(chalk.gray(`  Classes: ${img.classes}`));
      console.log(chalk.gray(`  Parent: <${img.parentTag}> ${img.parentClasses.substring(0, 50)}`));
      console.log(chalk.gray(`  URL: ${img.src.substring(0, 80)}...`));
      console.log();
    });

    // Try current selector
    console.log(chalk.yellow('Testing current selector: img.aspect-square, img[alt*="cover"], img.object-cover'));
    const currentSelector = await page.evaluate(() => {
      const img = document.querySelector('img.aspect-square, img[alt*="cover"], img.object-cover');
      if (!img) return null;

      const rect = img.getBoundingClientRect();
      return {
        src: img.src,
        alt: img.alt,
        width: rect.width,
        height: rect.height,
        classes: img.className
      };
    });

    if (currentSelector) {
      console.log(chalk.green('Current selector found:'));
      console.log(chalk.gray(`  Size: ${Math.round(currentSelector.width)}x${Math.round(currentSelector.height)}`));
      console.log(chalk.gray(`  Alt: ${currentSelector.alt}`));
      console.log(chalk.gray(`  URL: ${currentSelector.src}`));
    } else {
      console.log(chalk.red('Current selector found nothing!'));
    }

    console.log(chalk.yellow('\n\nBrowser will stay open - press Ctrl+C when done inspecting...'));
    await page.waitForTimeout(300000); // 5 minutes

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
  console.log(chalk.cyan('\n\nExiting...\n'));
  process.exit(0);
});

debugCoverImages();
