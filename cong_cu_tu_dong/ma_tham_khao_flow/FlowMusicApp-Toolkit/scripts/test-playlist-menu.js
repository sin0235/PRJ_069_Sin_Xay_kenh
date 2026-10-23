#!/usr/bin/env node

/**
 * Test Playlist Menu Flow
 * Interactive script to explore the "Add to Playlist" menu structure
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import scraperConfig from '../config/scraper.config.js';
import readline from 'readline';

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

function prompt(question) {
  return new Promise((resolve) => {
    rl.question(question, resolve);
  });
}

async function testPlaylistMenu() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    await fs.ensureDir('./logs');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Playlist Menu Flow Test                     '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('This script will help us explore the playlist menu structure.\n'));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    // Navigate to songs page
    console.log(chalk.yellow('Step 1: Loading songs page...\n'));
    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    // Get first song
    const firstSong = await page.evaluate((selectors) => {
      const element = document.querySelector(selectors.songCard);
      if (!element) return null;

      const link = element.querySelector('a[href*="/song/"]');
      const url = link?.href || '';
      const id = url.split('/song/')[1]?.split('?')[0] || '';
      const imageElement = element.querySelector('img[alt]') || element.querySelector('img');
      const title = imageElement?.alt?.trim() || 'Unknown';

      return { id, title, url };
    }, scraperConfig.selectors);

    if (!firstSong) {
      console.log(chalk.red('No songs found!'));
      return;
    }

    console.log(chalk.white(`Found song: ${chalk.cyan(firstSong.title)}\n`));

    // Navigate to song detail page
    console.log(chalk.yellow('Step 2: Opening song detail page...\n'));
    await page.goto(firstSong.url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    await page.screenshot({ path: './logs/playlist-test-1-song-page.png' });
    console.log(chalk.gray('Screenshot saved: playlist-test-1-song-page.png\n'));

    // Find and click three-dots menu
    console.log(chalk.yellow('Step 3: Looking for three-dots menu...\n'));

    const menuSelectors = [
      'div[aria-haspopup="menu"][data-sentry-element="MenuTrigger"]',
      'div[aria-haspopup="menu"]',
      'button[aria-haspopup="menu"]',
      '[aria-haspopup="menu"]'
    ];

    let menuButton = null;
    for (const selector of menuSelectors) {
      try {
        const locator = page.locator(selector).first();
        const isVisible = await locator.isVisible({ timeout: 2000 }).catch(() => false);
        if (isVisible) {
          menuButton = locator;
          console.log(chalk.green(`✓ Found menu button with: ${selector}\n`));
          break;
        }
      } catch (err) {
        // Try next selector
      }
    }

    if (!menuButton) {
      console.log(chalk.red('✗ Menu button not found!\n'));
      await prompt(chalk.yellow('Press Enter to close...'));
      return;
    }

    await prompt(chalk.yellow('Press Enter to click the menu button...'));

    // Click menu
    await menuButton.click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: './logs/playlist-test-2-menu-open.png' });
    console.log(chalk.gray('Screenshot saved: playlist-test-2-menu-open.png\n'));

    // Show visible menu items
    const menuItems = await page.evaluate(() => {
      const items = [];
      document.querySelectorAll('*').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0 && rect.top > 100 && rect.top < 600) {
          const text = el.textContent?.trim();
          if (text && text.length > 2 && text.length < 50 && !text.includes('\n')) {
            const tagName = el.tagName.toLowerCase();
            const className = el.className;
            items.push({ text, tagName, className });
          }
        }
      });
      return items.slice(0, 30);
    });

    console.log(chalk.white('Visible menu items:'));
    menuItems.forEach(item => {
      console.log(chalk.gray(`  - "${item.text}" (${item.tagName})`));
    });
    console.log();

    await prompt(chalk.yellow('Press Enter to look for "Add to..." option...'));

    // Try to find and click "Add to..."
    const addToSelectors = [
      'text="Add to"',
      'text="Add to..."',
      ':has-text("Add to")',
      '[class*="flex w-full cursor-pointer"]:has-text("Add to")',
      '[role="menuitem"]:has-text("Add to")'
    ];

    let addToButton = null;
    for (const selector of addToSelectors) {
      try {
        const locator = page.locator(selector).first();
        const isVisible = await locator.isVisible({ timeout: 2000 }).catch(() => false);
        if (isVisible) {
          addToButton = locator;
          console.log(chalk.green(`✓ Found "Add to" with: ${selector}\n`));
          break;
        }
      } catch (err) {
        // Try next selector
      }
    }

    if (!addToButton) {
      console.log(chalk.red('✗ "Add to" option not found!\n'));
      console.log(chalk.yellow('Looking for alternatives...\n'));

      // List all clickable items
      const clickableItems = await page.evaluate(() => {
        const items = [];
        document.querySelectorAll('[role="menuitem"], button, [class*="cursor-pointer"]').forEach(el => {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            const text = el.textContent?.trim();
            if (text && text.length < 100) {
              items.push(text);
            }
          }
        });
        return [...new Set(items)].slice(0, 20);
      });

      console.log(chalk.white('Clickable items found:'));
      clickableItems.forEach(text => {
        console.log(chalk.gray(`  - ${text}`));
      });
      console.log();

      await prompt(chalk.yellow('Press Enter to close...'));
      return;
    }

    await prompt(chalk.yellow('Press Enter to click "Add to..."...'));

    // Click "Add to..."
    await addToButton.click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: './logs/playlist-test-3-add-to-menu.png' });
    console.log(chalk.gray('Screenshot saved: playlist-test-3-add-to-menu.png\n'));

    // Show visible items after "Add to..." click
    const addToMenuItems = await page.evaluate(() => {
      const items = [];
      document.querySelectorAll('*').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0 && rect.top > 100 && rect.top < 600) {
          const text = el.textContent?.trim();
          if (text && text.length > 2 && text.length < 50 && !text.includes('\n')) {
            items.push(text);
          }
        }
      });
      return [...new Set(items)].slice(0, 30);
    });

    console.log(chalk.white('Visible items after "Add to...":'));
    addToMenuItems.forEach(text => {
      console.log(chalk.gray(`  - ${text}`));
    });
    console.log();

    await prompt(chalk.yellow('Press Enter to look for "Playlist" option...'));

    // Try to find and click "Playlist"
    const playlistSelectors = [
      'text="Playlist"',
      ':has-text("Playlist")',
      '[role="menuitem"]:has-text("Playlist")',
      'button:has-text("Playlist")'
    ];

    let playlistButton = null;
    for (const selector of playlistSelectors) {
      try {
        const locator = page.locator(selector).first();
        const isVisible = await locator.isVisible({ timeout: 2000 }).catch(() => false);
        if (isVisible) {
          playlistButton = locator;
          console.log(chalk.green(`✓ Found "Playlist" with: ${selector}\n`));
          break;
        }
      } catch (err) {
        // Try next selector
      }
    }

    if (!playlistButton) {
      console.log(chalk.red('✗ "Playlist" option not found!\n'));
      await prompt(chalk.yellow('Press Enter to close...'));
      return;
    }

    await prompt(chalk.yellow('Press Enter to click "Playlist"...'));

    // Click "Playlist"
    await playlistButton.click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: './logs/playlist-test-4-playlist-menu.png' });
    console.log(chalk.gray('Screenshot saved: playlist-test-4-playlist-menu.png\n'));

    // Show available playlists
    const playlists = await page.evaluate(() => {
      const items = [];
      document.querySelectorAll('*').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 50 && rect.height > 20 && rect.top > 100 && rect.top < 800) {
          const text = el.textContent?.trim();
          if (text && text.length > 2 && text.length < 100 && !text.includes('\n\n')) {
            items.push(text);
          }
        }
      });
      return [...new Set(items)].slice(0, 40);
    });

    console.log(chalk.white('Available playlists and options:'));
    playlists.forEach(text => {
      console.log(chalk.gray(`  - ${text}`));
    });
    console.log();

    console.log(chalk.green('\n✓ Test complete!\n'));
    console.log(chalk.white('Check the screenshots in ./logs/ to see the menu flow.\n'));
    console.log(chalk.yellow('Next steps:'));
    console.log(chalk.gray('1. Review the screenshots to understand the UI'));
    console.log(chalk.gray('2. Identify your playlist name in the list above'));
    console.log(chalk.gray('3. We can now build selectors for the automation\n'));

    await prompt(chalk.yellow('Press Enter to close the browser...'));

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
  } finally {
    if (context) await context.close();
    rl.close();
  }
}

testPlaylistMenu();
