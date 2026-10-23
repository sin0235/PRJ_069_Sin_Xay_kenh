#!/usr/bin/env node

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

async function testDownloadIcon() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    const firstSong = await page.evaluate((selectors) => {
      const songElement = document.querySelector(selectors.songCard);
      const imageElement = songElement?.querySelector('img[alt]');
      const linkElement = songElement?.querySelector('a[href*="/song/"]');
      return { title: imageElement?.alt, url: linkElement?.href };
    }, scraperConfig.selectors);

    console.log(chalk.green(`\n✓ Testing song: ${firstSong.title}\n`));

    await page.goto(firstSong.url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    console.log(chalk.yellow('Finding download icon button (second-to-rightmost)...\n'));

    // Find second-to-rightmost button (download icon)
    const downloadIconIndex = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const headerButtons = [];

      buttons.forEach((btn, idx) => {
        const rect = btn.getBoundingClientRect();
        if (rect.top > 150 && rect.top < 350 && rect.width > 20) {
          headerButtons.push({ idx, left: rect.left });
        }
      });

      headerButtons.sort((a, b) => b.left - a.left);
      return headerButtons.length >= 2 ? headerButtons[1].idx : null;
    });

    console.log(chalk.green(`✓ Found download icon at button index ${downloadIconIndex}\n`));
    console.log(chalk.yellow('Clicking download icon button...\n'));

    const downloadIcon = page.locator('button').nth(downloadIconIndex);
    await downloadIcon.click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: 'logs/after-download-icon-click.png' });

    // Check what appeared
    const menuContent = await page.evaluate(() => {
      const items = [];
      const elements = document.querySelectorAll('[role="menuitem"], button, a');

      elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0 && rect.top > 150) {
          const text = el.textContent?.trim();
          if (text && text.length < 100) {
            items.push(text);
          }
        }
      });

      return [...new Set(items)].slice(0, 15);
    });

    console.log(chalk.cyan('═══ Menu Content After Download Icon Click ═══\n'));
    menuContent.forEach((item, idx) => {
      console.log(chalk.white(`${idx + 1}. ${item}`));
    });
    console.log();

    console.log(chalk.yellow('Browser will stay open for 20 seconds.'));
    console.log(chalk.gray('Check logs/after-download-icon-click.png\n'));

    await page.waitForTimeout(20000);

  } catch (error) {
    console.error(chalk.red('Error:'), error.message);
  } finally {
    if (context) await context.close();
  }
}

testDownloadIcon();
