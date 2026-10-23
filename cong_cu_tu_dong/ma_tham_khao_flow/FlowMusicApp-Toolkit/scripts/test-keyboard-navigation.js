#!/usr/bin/env node

/**
 * Test Keyboard Navigation for Playlist Menu
 * Uses arrow keys to navigate menus without mouse movement
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

async function testKeyboardNavigation() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Test Keyboard Navigation                    '));
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

    // Hover over first song card
    console.log(chalk.yellow('[2] Hovering over song card...\n'));
    const songCard = page.locator(scraperConfig.selectors.songCard).first();
    await songCard.hover();
    await page.waitForTimeout(500);

    // Click menu button
    console.log(chalk.yellow('[3] Opening menu...\n'));
    const menuButton = songCard.locator('button[data-sentry-element="MenuTrigger"][data-sentry-source-file="RiffOptionsMenu.tsx"]').first();
    await menuButton.click();
    await page.waitForTimeout(2000);

    // Use keyboard to navigate to "Add to" (position 4, so press Down 4 times)
    console.log(chalk.yellow('[4] Navigating to "Add to" with keyboard...\n'));
    for (let i = 0; i < 4; i++) {
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(200);
    }

    // Press Right to open "Add to" submenu
    console.log(chalk.yellow('[5] Opening "Add to" submenu with Right arrow...\n'));
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(2000);

    await page.screenshot({ path: './logs/keyboard-1-add-to-submenu.png' });

    // Navigate to "Playlist" (should be first item)
    console.log(chalk.yellow('[6] Navigating to "Playlist"...\n'));
    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(500);

    // Press Right to open Playlist submenu
    console.log(chalk.yellow('[7] Opening Playlist submenu with Right arrow...\n'));
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(3000);

    await page.screenshot({ path: './logs/keyboard-2-playlist-submenu.png' });

    // Extract playlists
    const playlists = await page.evaluate(() => {
      const items = [];
      document.querySelectorAll('[role="menuitem"][data-sentry-component="PlaylistItem"]').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          const textDiv = el.querySelector('.line-clamp-2');
          const name = textDiv?.textContent?.trim();
          if (name && name !== '+ Create Playlist') {
            items.push(name);
          }
        }
      });
      return items;
    });

    console.log(chalk.white('\n═══════════════════════════════════════════════════'));
    if (playlists.length === 0) {
      console.log(chalk.red('✗ No playlists found'));
    } else {
      console.log(chalk.green(`✓ Found ${playlists.length} playlists:\n`));
      playlists.forEach((name, idx) => {
        console.log(chalk.gray(`  [${idx}] ${name}`));
      });
    }
    console.log(chalk.white('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('Browser staying open. Press Ctrl+C when done.\n'));

    // Keep browser open
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

testKeyboardNavigation();
