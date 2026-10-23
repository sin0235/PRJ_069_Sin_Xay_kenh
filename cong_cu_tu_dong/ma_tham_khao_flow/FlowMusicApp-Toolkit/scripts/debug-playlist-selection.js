#!/usr/bin/env node

/**
 * Debug script to understand playlist selection state
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

async function debugPlaylistSelection() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Debug Playlist Selection State              '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    // Navigate to songs page
    console.log(chalk.yellow('[1] Loading songs list...\n'));
    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);

    // Open menu on first song
    console.log(chalk.yellow('[2] Opening menu on first song...\n'));
    const songCard = page.locator(scraperConfig.selectors.songCard).first();
    await songCard.hover();
    await page.waitForTimeout(300);

    const menuButton = songCard.locator('button[data-sentry-element="MenuTrigger"][data-sentry-source-file="RiffOptionsMenu.tsx"]').first();
    await menuButton.click();
    await page.waitForTimeout(800);

    // Navigate to "Add to" menu
    console.log(chalk.yellow('[3] Navigating to "Add to" submenu...\n'));
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(100);
    }

    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(1000);

    // Open Playlist submenu
    console.log(chalk.yellow('[4] Opening Playlist submenu...\n'));
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(1500);

    // Extract detailed info about playlist items
    console.log(chalk.yellow('[5] Analyzing playlist items...\n'));

    const playlistInfo = await page.evaluate(() => {
      const items = [];
      document.querySelectorAll('[role="menuitem"][data-sentry-component="PlaylistItem"]').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          const textDiv = el.querySelector('.line-clamp-2');
          const name = textDiv?.textContent?.trim();

          if (name && name !== '+ Create Playlist') {
            // Check for various indicators of selection
            const hasCheckmark = !!el.querySelector('svg[data-testid*="check"]') ||
                                 !!el.querySelector('svg[data-icon*="check"]') ||
                                 !!el.querySelector('[aria-checked="true"]');

            const hasCircle = !!el.querySelector('svg circle');
            const hasFilledCircle = !!el.querySelector('svg circle[fill]');

            // Get all classes
            const classes = el.className;

            // Check for aria attributes
            const ariaChecked = el.getAttribute('aria-checked');
            const ariaSelected = el.getAttribute('aria-selected');

            // Get outerHTML for manual inspection
            const html = el.outerHTML;

            items.push({
              name,
              hasCheckmark,
              hasCircle,
              hasFilledCircle,
              classes,
              ariaChecked,
              ariaSelected,
              html: html.substring(0, 500) // First 500 chars
            });
          }
        }
      });
      return items;
    });

    console.log(chalk.white('═══════════════════════════════════════════════════'));
    console.log(chalk.white('Playlist Items Analysis:\n'));

    playlistInfo.forEach((item, idx) => {
      console.log(chalk.cyan(`\n[${idx}] ${item.name}`));
      console.log(chalk.gray(`    Has Checkmark: ${item.hasCheckmark}`));
      console.log(chalk.gray(`    Has Circle: ${item.hasCircle}`));
      console.log(chalk.gray(`    Has Filled Circle: ${item.hasFilledCircle}`));
      console.log(chalk.gray(`    Aria Checked: ${item.ariaChecked}`));
      console.log(chalk.gray(`    Aria Selected: ${item.ariaSelected}`));
      console.log(chalk.gray(`    Classes: ${item.classes}`));
      console.log(chalk.gray(`    HTML Preview: ${item.html.substring(0, 200)}...`));
    });

    console.log(chalk.white('\n═══════════════════════════════════════════════════\n'));
    console.log(chalk.yellow('Browser staying open. Press Ctrl+C when done.\n'));
    await new Promise(() => {});

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
    if (context) {
      console.log(chalk.yellow('\nBrowser staying open. Press Ctrl+C when done.\n'));
      await new Promise(() => {});
    }
  }
}

debugPlaylistSelection();
