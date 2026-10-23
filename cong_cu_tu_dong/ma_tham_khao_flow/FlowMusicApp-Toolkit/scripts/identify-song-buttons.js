#!/usr/bin/env node

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

async function identifyButtons() {
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

    console.log(chalk.cyan('═══ All Buttons in Song Header Area ═══\n'));

    // Get detailed info about all buttons near the song title
    const buttons = await page.evaluate(() => {
      const buttonInfo = [];
      const allButtons = document.querySelectorAll('button, div[role="button"]');

      allButtons.forEach((btn, idx) => {
        const rect = btn.getBoundingClientRect();

        // Focus on song header area (y: 150-400)
        if (rect.top > 150 && rect.top < 400 && rect.width > 20 && rect.height > 15) {
          buttonInfo.push({
            index: idx,
            text: btn.textContent?.trim().substring(0, 30) || '(empty)',
            className: btn.className.substring(0, 100),
            top: Math.round(rect.top),
            left: Math.round(rect.left),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            innerHTML: btn.innerHTML.substring(0, 200)
          });
        }
      });

      // Sort by position (top to bottom, then left to right)
      buttonInfo.sort((a, b) => {
        if (Math.abs(a.top - b.top) < 10) {
          return a.left - b.left;
        }
        return a.top - b.top;
      });

      return buttonInfo;
    });

    console.log(chalk.yellow(`Found ${buttons.length} buttons in song header area:\n`));

    buttons.forEach((btn, i) => {
      console.log(chalk.white(`${i + 1}. Button Index ${btn.index}`));
      console.log(chalk.gray(`   Text: "${btn.text}"`));
      console.log(chalk.gray(`   Position: (${btn.left}, ${btn.top}) | Size: ${btn.width}x${btn.height}`));
      console.log(chalk.gray(`   Class: ${btn.className}`));

      // Highlight likely candidates
      if (btn.innerHTML.includes('...') || btn.className.includes('...')) {
        console.log(chalk.green(`   ⭐ Contains "..." - LIKELY MENU BUTTON`));
      }
      if (btn.text === '...' || btn.innerHTML.includes('dots') || btn.innerHTML.includes('more')) {
        console.log(chalk.green(`   ⭐ Three-dots pattern detected`));
      }

      console.log();
    });

    console.log(chalk.yellow('Browser will stay open for 30 seconds.'));
    console.log(chalk.gray('Please try clicking the three-dots menu manually\n'));
    console.log(chalk.gray('and note which button number (position) it is from the list above.\n'));

    await page.waitForTimeout(30000);

  } catch (error) {
    console.error(chalk.red('Error:'), error.message);
  } finally {
    if (context) await context.close();
  }
}

identifyButtons();
