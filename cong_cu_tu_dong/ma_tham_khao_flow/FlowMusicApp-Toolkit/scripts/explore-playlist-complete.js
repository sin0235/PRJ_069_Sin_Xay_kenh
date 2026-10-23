#!/usr/bin/env node

/**
 * Complete Playlist Flow
 * Finds the correct RiffOptionsMenu and navigates to playlists
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import scraperConfig from '../config/scraper.config.js';

async function completePlaylistFlow() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    await fs.ensureDir('./logs');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Complete Playlist Flow                      '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    // Navigate to songs page
    console.log(chalk.yellow('[1] Loading songs list...\n'));
    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    // Hover over first song card
    console.log(chalk.yellow('[2] Hovering over first song...\n'));
    const songCard = page.locator(scraperConfig.selectors.songCard).first();
    await songCard.hover();
    await page.waitForTimeout(1000);

    await page.screenshot({ path: './logs/complete-1-hover.png' });

    // Find the specific RiffOptionsMenu button
    console.log(chalk.yellow('[3] Finding RiffOptionsMenu button...\n'));

    // Use the exact button selector based on the HTML provided
    const menuButtonSelector = `${scraperConfig.selectors.songCard} button[data-sentry-element="MenuTrigger"][data-sentry-source-file="RiffOptionsMenu.tsx"]`;

    let menuButton = page.locator(menuButtonSelector).first();
    const buttonExists = await menuButton.count();

    if (buttonExists === 0) {
      console.log(chalk.red('    ✗ RiffOptionsMenu button not found with data attributes\n'));
      console.log(chalk.yellow('    Trying alternative selector...\n'));

      // Try alternative: button with the specific class and three-circle SVG
      menuButton = page.locator(`${scraperConfig.selectors.songCard} button.text-fg-1:has(svg.lucide-ellipsis)`).first();
      const altExists = await menuButton.count();

      if (altExists === 0) {
        console.log(chalk.red('    ✗ No menu button found!\n'));
        await page.screenshot({ path: './logs/complete-error-no-button.png' });
        console.log(chalk.yellow('    Browser staying open. Press Ctrl+C when done.\n'));
        await new Promise(() => {});
        return;
      }

      console.log(chalk.green('    ✓ Found button with alternative selector\n'));
    } else {
      console.log(chalk.green('    ✓ Found RiffOptionsMenu button\n'));
    }

    // Click the menu button
    console.log(chalk.yellow('[4] Clicking menu button...\n'));
    await menuButton.click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: './logs/complete-2-menu-open.png' });

    // Get ALL visible menu items carefully
    console.log(chalk.yellow('[5] Scanning menu items...\n'));

    const allMenuItems = await page.evaluate(() => {
      const items = [];

      // Look for menu container
      const menuContainers = document.querySelectorAll('[role="menu"], [data-radix-menu-content]');

      menuContainers.forEach(container => {
        const menuItems = container.querySelectorAll('[role="menuitem"], button');
        menuItems.forEach((item, index) => {
          const rect = item.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            const text = item.textContent?.trim() || '';
            items.push({
              index,
              text,
              visible: true,
              tag: item.tagName.toLowerCase(),
              role: item.getAttribute('role'),
              classes: Array.from(item.classList).slice(0, 3).join(' ')
            });
          }
        });
      });

      return items;
    });

    console.log(chalk.white('    Found menu items:\n'));
    allMenuItems.forEach((item, idx) => {
      const isRemix = item.text.toLowerCase().includes('remix');
      const isAddTo = item.text.toLowerCase().includes('add to');

      if (isRemix) {
        console.log(chalk.cyan(`      [${idx}] ⭐ ${item.text} (REMIX - First item)`));
      } else if (isAddTo) {
        console.log(chalk.cyan(`      [${idx}] ⭐ ${item.text} (ADD TO - Target!)`));
      } else {
        console.log(chalk.gray(`      [${idx}] ${item.text}`));
      }
    });
    console.log();

    // Find "Add to" item (should be 5th: index 4)
    const addToItem = allMenuItems.find(item => item.text.toLowerCase().includes('add to'));

    if (!addToItem) {
      console.log(chalk.red('    ✗ "Add to" not found in menu!\n'));
      console.log(chalk.yellow('    Menu might be different than expected.'));
      console.log(chalk.yellow('    Browser staying open. Press Ctrl+C when done.\n'));
      await new Promise(() => {});
      return;
    }

    console.log(chalk.green(`    ✓ Found "Add to" at position ${addToItem.index}\n`));

    // Click "Add to"
    console.log(chalk.yellow('[6] Clicking "Add to"...\n'));
    const addToButton = page.locator('[role="menuitem"]:has-text("Add to")').first();
    await addToButton.click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: './logs/complete-3-add-to-menu.png' });

    // Get submenu items
    const submenuItems = await page.evaluate(() => {
      const items = [];
      const menuContainers = document.querySelectorAll('[role="menu"], [data-radix-menu-content]');

      menuContainers.forEach(container => {
        const menuItems = container.querySelectorAll('[role="menuitem"], button');
        menuItems.forEach((item) => {
          const rect = item.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            const text = item.textContent?.trim() || '';
            if (text && text.length < 100) {
              items.push(text);
            }
          }
        });
      });

      return [...new Set(items)];
    });

    console.log(chalk.white('    Submenu items:\n'));
    submenuItems.forEach((text, idx) => {
      const isPlaylist = text.toLowerCase().includes('playlist');
      if (isPlaylist) {
        console.log(chalk.cyan(`      [${idx}] ⭐ ${text} (Target!)`));
      } else {
        console.log(chalk.gray(`      [${idx}] ${text}`));
      }
    });
    console.log();

    // Click "Playlist"
    console.log(chalk.yellow('[7] Clicking "Playlist"...\n'));
    const playlistButton = page.locator('[role="menuitem"]:has-text("Playlist")').first();
    await playlistButton.click();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: './logs/complete-4-playlists.png' });

    // Get available playlists
    const playlists = await page.evaluate(() => {
      const items = [];
      const menuContainers = document.querySelectorAll('[role="menu"], [data-radix-menu-content]');

      menuContainers.forEach(container => {
        const menuItems = container.querySelectorAll('[role="menuitem"], button, [class*="cursor-pointer"]');
        menuItems.forEach((item) => {
          const rect = item.getBoundingClientRect();
          if (rect.width > 50 && rect.height > 15) {
            const text = item.textContent?.trim() || '';
            if (text && text.length > 0 && text.length < 100) {
              items.push(text);
            }
          }
        });
      });

      return [...new Set(items)];
    });

    console.log(chalk.green('    ✓ Available playlists:\n'));
    playlists.forEach((name, idx) => {
      const isGodIsWater = name.toLowerCase().includes('god is water');
      if (isGodIsWater) {
        console.log(chalk.cyan(`      [${idx}] ⭐⭐ ${name} ⭐⭐ (Your playlist!)`));
      } else {
        console.log(chalk.gray(`      [${idx}] ${name}`));
      }
    });
    console.log();

    console.log(chalk.green('\n═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ Complete flow successful!'));
    console.log(chalk.green('═══════════════════════════════════════════════════\n'));

    console.log(chalk.white('Flow summary:\n'));
    console.log(chalk.gray('  1. Song card → ... button'));
    console.log(chalk.gray('  2. Menu → "Add to" (position ' + addToItem.index + ')'));
    console.log(chalk.gray('  3. Submenu → "Playlist"'));
    console.log(chalk.gray('  4. Select playlist → "God Is Water"\n'));

    console.log(chalk.white('Selectors identified:\n'));
    console.log(chalk.cyan('  Menu button: ') + chalk.gray('button[data-sentry-element="MenuTrigger"]'));
    console.log(chalk.cyan('  Add to: ') + chalk.gray('[role="menuitem"]:has-text("Add to")'));
    console.log(chalk.cyan('  Playlist: ') + chalk.gray('[role="menuitem"]:has-text("Playlist")'));
    console.log(chalk.cyan('  Select: ') + chalk.gray('[role="menuitem"]:has-text("God Is Water")\n'));

    console.log(chalk.yellow('Browser staying open for inspection. Press Ctrl+C when done.\n'));

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

completePlaylistFlow();
