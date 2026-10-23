#!/usr/bin/env node

/**
 * Explore Playlist Flow
 * Automatically walks through the playlist add flow and keeps browser open
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import scraperConfig from '../config/scraper.config.js';

async function explorePlaylistFlow() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    await fs.ensureDir('./logs');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Playlist Flow Explorer                      '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('Exploring playlist menu flow from songs list...\n'));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    // Navigate to songs page
    console.log(chalk.yellow('[1] Loading songs list page...\n'));
    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    await page.screenshot({ path: './logs/flow-1-songs-list.png' });
    console.log(chalk.gray('    Screenshot: flow-1-songs-list.png\n'));

    // Get first song info
    const firstSong = await page.evaluate((selectors) => {
      const element = document.querySelector(selectors.songCard);
      if (!element) return null;

      const imageElement = element.querySelector('img[alt]') || element.querySelector('img');
      const title = imageElement?.alt?.trim() || 'Unknown';

      return { title };
    }, scraperConfig.selectors);

    if (!firstSong) {
      console.log(chalk.red('No songs found!'));
      return;
    }

    console.log(chalk.white(`    First song: ${chalk.cyan(firstSong.title)}\n`));

    // Inspect song card elements
    console.log(chalk.yellow('[2] Inspecting song card elements...\n'));

    const cardStructure = await page.evaluate((selectors) => {
      const card = document.querySelector(selectors.songCard);
      if (!card) return null;

      const structure = {
        buttons: [],
        menus: [],
        svgs: []
      };

      // Find all potential menu triggers
      card.querySelectorAll('[aria-haspopup="menu"], button, [role="button"], svg').forEach(el => {
        const rect = el.getBoundingClientRect();
        const info = {
          tag: el.tagName.toLowerCase(),
          classes: Array.from(el.classList).join(' '),
          ariaLabel: el.getAttribute('aria-label'),
          ariaHaspopup: el.getAttribute('aria-haspopup'),
          visible: rect.width > 0 && rect.height > 0,
          position: `(${rect.left.toFixed(0)}, ${rect.top.toFixed(0)})`,
          size: `${rect.width.toFixed(0)}x${rect.height.toFixed(0)}`
        };

        if (info.ariaHaspopup === 'menu') {
          structure.menus.push(info);
        } else if (info.tag === 'svg') {
          structure.svgs.push(info);
        } else {
          structure.buttons.push(info);
        }
      });

      return structure;
    }, scraperConfig.selectors);

    if (cardStructure.menus.length > 0) {
      console.log(chalk.green('    ✓ Found menu triggers:\n'));
      cardStructure.menus.forEach((menu, idx) => {
        console.log(chalk.gray(`      [${idx}] <${menu.tag}>`));
        console.log(chalk.gray(`          classes: ${menu.classes || '(none)'}`));
        console.log(chalk.gray(`          aria-label: ${menu.ariaLabel || '(none)'}`));
        console.log(chalk.gray(`          visible: ${menu.visible}, pos: ${menu.position}, size: ${menu.size}\n`));
      });
    } else {
      console.log(chalk.yellow('    ⚠ No [aria-haspopup="menu"] elements found\n'));
    }

    console.log(chalk.yellow('[3] Hovering over first song card...\n'));

    // Hover to reveal menu button
    const songCard = page.locator(scraperConfig.selectors.songCard).first();
    await songCard.hover();
    await page.waitForTimeout(1000);

    await page.screenshot({ path: './logs/flow-2-hover-card.png' });
    console.log(chalk.gray('    Screenshot: flow-2-hover-card.png\n'));

    // Try to find menu button
    console.log(chalk.yellow('[4] Looking for menu button...\n'));

    const menuSelectors = [
      `${scraperConfig.selectors.songCard} [aria-haspopup="menu"]`,
      `${scraperConfig.selectors.songCard} button[aria-haspopup="menu"]`,
      `${scraperConfig.selectors.songCard} div[aria-haspopup="menu"]`
    ];

    let menuButton = null;
    let usedSelector = null;

    for (const selector of menuSelectors) {
      try {
        const locator = page.locator(selector).first();
        const isVisible = await locator.isVisible({ timeout: 2000 }).catch(() => false);
        if (isVisible) {
          menuButton = locator;
          usedSelector = selector;
          break;
        }
      } catch (err) {
        // Try next selector
      }
    }

    if (!menuButton) {
      console.log(chalk.red('    ✗ Menu button not found!\n'));
      console.log(chalk.yellow('    Browser will stay open for manual inspection.'));
      console.log(chalk.yellow('    Check logs/flow-*.png screenshots.'));
      console.log(chalk.yellow('    Press Ctrl+C when done.\n'));
      await new Promise(() => {}); // Keep alive
      return;
    }

    console.log(chalk.green(`    ✓ Found menu button: ${usedSelector}\n`));

    // Click menu button
    console.log(chalk.yellow('[5] Clicking menu button...\n'));
    await menuButton.click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: './logs/flow-3-menu-open.png' });
    console.log(chalk.gray('    Screenshot: flow-3-menu-open.png\n'));

    // List menu options
    const menuOptions = await page.evaluate(() => {
      const options = [];

      // Look for menu items that are currently visible
      document.querySelectorAll('[role="menuitem"], [class*="menu-item"]').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0 && rect.top > 50 && rect.top < 900) {
          const text = el.textContent?.trim();
          if (text && text.length > 0 && text.length < 100) {
            options.push({
              text,
              tag: el.tagName.toLowerCase(),
              classes: Array.from(el.classList).slice(0, 3).join(' ')
            });
          }
        }
      });

      return options;
    });

    console.log(chalk.white('    Menu options found:\n'));
    menuOptions.forEach((opt, idx) => {
      console.log(chalk.gray(`      [${idx}] ${opt.text}`));
    });
    console.log();

    // Try to find "Add to" option
    console.log(chalk.yellow('[6] Looking for "Add to" option...\n'));

    const addToSelectors = [
      'text="Add to"',
      ':text("Add to")',
      '[role="menuitem"]:has-text("Add to")'
    ];

    let addToButton = null;
    for (const selector of addToSelectors) {
      try {
        const locator = page.locator(selector).first();
        const isVisible = await locator.isVisible({ timeout: 2000 }).catch(() => false);
        if (isVisible) {
          addToButton = locator;
          console.log(chalk.green(`    ✓ Found "Add to": ${selector}\n`));
          break;
        }
      } catch (err) {
        // Try next
      }
    }

    if (!addToButton) {
      console.log(chalk.red('    ✗ "Add to" not found!\n'));
      console.log(chalk.yellow('    Browser will stay open. Check the screenshots.'));
      console.log(chalk.yellow('    Press Ctrl+C when done.\n'));
      await new Promise(() => {}); // Keep alive
      return;
    }

    // Click "Add to"
    console.log(chalk.yellow('[7] Clicking "Add to"...\n'));
    await addToButton.click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: './logs/flow-4-add-to-menu.png' });
    console.log(chalk.gray('    Screenshot: flow-4-add-to-menu.png\n'));

    // Try to find "Playlist" option
    console.log(chalk.yellow('[8] Looking for "Playlist" option...\n'));

    const playlistSelectors = [
      'text="Playlist"',
      ':text("Playlist")',
      '[role="menuitem"]:has-text("Playlist")'
    ];

    let playlistButton = null;
    for (const selector of playlistSelectors) {
      try {
        const locator = page.locator(selector).first();
        const isVisible = await locator.isVisible({ timeout: 2000 }).catch(() => false);
        if (isVisible) {
          playlistButton = locator;
          console.log(chalk.green(`    ✓ Found "Playlist": ${selector}\n`));
          break;
        }
      } catch (err) {
        // Try next
      }
    }

    if (!playlistButton) {
      console.log(chalk.red('    ✗ "Playlist" not found!\n'));
      console.log(chalk.yellow('    Browser will stay open. Check the screenshots.'));
      console.log(chalk.yellow('    Press Ctrl+C when done.\n'));
      await new Promise(() => {}); // Keep alive
      return;
    }

    // Click "Playlist"
    console.log(chalk.yellow('[9] Clicking "Playlist"...\n'));
    await playlistButton.click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: './logs/flow-5-playlists.png' });
    console.log(chalk.gray('    Screenshot: flow-5-playlists.png\n'));

    // List available playlists
    const playlists = await page.evaluate(() => {
      const items = [];

      // Look for playlist items
      document.querySelectorAll('[role="menuitem"], button, [class*="cursor-pointer"]').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 50 && rect.height > 15 && rect.top > 50 && rect.top < 900) {
          const text = el.textContent?.trim();
          if (text && text.length > 0 && text.length < 100) {
            items.push({
              text,
              classes: Array.from(el.classList).slice(0, 3).join(' ')
            });
          }
        }
      });

      return items;
    });

    console.log(chalk.green('    ✓ Available playlists:\n'));
    playlists.forEach((pl, idx) => {
      const isGodIsWater = pl.text.toLowerCase().includes('god is water');
      if (isGodIsWater) {
        console.log(chalk.cyan(`      [${idx}] ⭐ ${pl.text} ⭐`));
      } else {
        console.log(chalk.gray(`      [${idx}] ${pl.text}`));
      }
    });
    console.log();

    console.log(chalk.green('\n═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ Flow exploration complete!'));
    console.log(chalk.green('═══════════════════════════════════════════════════\n'));

    console.log(chalk.white('Summary:\n'));
    console.log(chalk.gray('  Flow: Song card → ... menu → Add to → Playlist → [Select playlist]'));
    console.log(chalk.gray(`  Playlists found: ${playlists.length}`));
    console.log(chalk.gray('  Screenshots saved to: ./logs/flow-*.png\n'));

    console.log(chalk.yellow('Browser will stay open for manual inspection.'));
    console.log(chalk.yellow('Press Ctrl+C when done.\n'));

    // Keep browser open indefinitely
    await new Promise(() => {});

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
    if (context) {
      console.log(chalk.yellow('\nBrowser will stay open. Press Ctrl+C when done.\n'));
      await new Promise(() => {});
    }
  }
}

explorePlaylistFlow();
