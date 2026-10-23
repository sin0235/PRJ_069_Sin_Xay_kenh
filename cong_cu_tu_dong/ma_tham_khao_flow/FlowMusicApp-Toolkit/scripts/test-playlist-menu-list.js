#!/usr/bin/env node

/**
 * Test Playlist Menu from Songs List
 * Interactive script to explore adding songs to playlist from the list view
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

async function testPlaylistMenuFromList() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    await fs.ensureDir('./logs');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Playlist Menu Test (List View)              '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('This script will explore adding songs to playlists from the list view.\n'));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    // Navigate to songs page
    console.log(chalk.yellow('Step 1: Loading songs list page...\n'));
    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    await page.screenshot({ path: './logs/playlist-list-1-songs-page.png' });
    console.log(chalk.gray('Screenshot saved: playlist-list-1-songs-page.png\n'));

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

    console.log(chalk.white(`Found song: ${chalk.cyan(firstSong.title)}\n`));

    await prompt(chalk.yellow('Press Enter to look for the three-dots menu on the first song card...'));

    // Find three-dots menu on the song card
    console.log(chalk.yellow('\nStep 2: Looking for three-dots menu on song card...\n'));

    // Try different selectors for the menu button on the song card
    const menuSelectors = [
      `${scraperConfig.selectors.songCard} [aria-haspopup="menu"]`,
      `${scraperConfig.selectors.songCard} button[aria-haspopup="menu"]`,
      `${scraperConfig.selectors.songCard} div[aria-haspopup="menu"]`,
      `${scraperConfig.selectors.songCard} svg[class*="lucide"]`,
      `${scraperConfig.selectors.songCard} [data-sentry-element="MenuTrigger"]`,
    ];

    // First, let's see what elements are in the song card
    const songCardElements = await page.evaluate((selectors) => {
      const card = document.querySelector(selectors.songCard);
      if (!card) return [];

      const elements = [];
      card.querySelectorAll('*').forEach(el => {
        const tagName = el.tagName.toLowerCase();
        const className = el.className;
        const ariaLabel = el.getAttribute('aria-label');
        const ariaHaspopup = el.getAttribute('aria-haspopup');
        const role = el.getAttribute('role');

        if (ariaHaspopup || ariaLabel || role === 'button' || tagName === 'button' || tagName === 'svg') {
          elements.push({
            tagName,
            className: typeof className === 'string' ? className : '',
            ariaLabel,
            ariaHaspopup,
            role,
            innerText: el.innerText?.substring(0, 50)
          });
        }
      });

      return elements;
    }, scraperConfig.selectors);

    console.log(chalk.white('Elements in first song card:'));
    songCardElements.forEach((el, idx) => {
      console.log(chalk.gray(`  [${idx}] <${el.tagName}> ${el.className}`));
      if (el.ariaLabel) console.log(chalk.gray(`      aria-label: "${el.ariaLabel}"`));
      if (el.ariaHaspopup) console.log(chalk.gray(`      aria-haspopup: "${el.ariaHaspopup}"`));
      if (el.role) console.log(chalk.gray(`      role: "${el.role}"`));
      if (el.innerText) console.log(chalk.gray(`      text: "${el.innerText}"`));
    });
    console.log();

    await prompt(chalk.yellow('Press Enter to try clicking the menu button...'));

    // Try to find the menu button
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
      console.log(chalk.red('✗ Menu button not found with standard selectors!\n'));
      console.log(chalk.yellow('Let me try to find clickable elements on the song card...\n'));

      // Find all clickable elements
      const clickableInfo = await page.evaluate((selectors) => {
        const card = document.querySelector(selectors.songCard);
        if (!card) return null;

        const clickables = [];
        card.querySelectorAll('button, [role="button"], [aria-haspopup], svg').forEach((el, idx) => {
          const rect = el.getBoundingClientRect();
          clickables.push({
            index: idx,
            tagName: el.tagName.toLowerCase(),
            className: el.className,
            visible: rect.width > 0 && rect.height > 0,
            position: `${rect.left.toFixed(0)}, ${rect.top.toFixed(0)}`,
            size: `${rect.width.toFixed(0)}x${rect.height.toFixed(0)}`
          });
        });

        return clickables;
      }, scraperConfig.selectors);

      console.log(chalk.white('Clickable elements found:'));
      clickableInfo.forEach(el => {
        console.log(chalk.gray(`  [${el.index}] <${el.tagName}>`));
        console.log(chalk.gray(`      class: ${el.className}`));
        console.log(chalk.gray(`      visible: ${el.visible}, pos: ${el.position}, size: ${el.size}`));
      });
      console.log();

      await prompt(chalk.yellow('Review the elements above. Press Enter to close...'));
      return;
    }

    // Hover over the song card first to ensure menu button is visible
    const songCard = page.locator(scraperConfig.selectors.songCard).first();
    await songCard.hover();
    await page.waitForTimeout(500);

    await page.screenshot({ path: './logs/playlist-list-2-hover-card.png' });
    console.log(chalk.gray('Screenshot saved: playlist-list-2-hover-card.png\n'));

    // Click menu button
    await menuButton.click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: './logs/playlist-list-3-menu-open.png' });
    console.log(chalk.gray('Screenshot saved: playlist-list-3-menu-open.png\n'));

    // Show visible menu items
    const menuItems = await page.evaluate(() => {
      const items = [];
      document.querySelectorAll('*').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 50 && rect.height > 10 && rect.top > 100 && rect.top < 800) {
          const text = el.textContent?.trim();
          if (text && text.length > 2 && text.length < 50 && !text.includes('\n\n')) {
            items.push(text);
          }
        }
      });
      return [...new Set(items)].slice(0, 30);
    });

    console.log(chalk.white('Visible menu items:'));
    menuItems.forEach(text => {
      console.log(chalk.gray(`  - ${text}`));
    });
    console.log();

    await prompt(chalk.yellow('Press Enter to look for "Add to" option...'));

    // Try to find and click "Add to"
    const addToSelectors = [
      'text="Add to"',
      'text="Add to..."',
      ':text("Add to")',
      '[role="menuitem"]:has-text("Add to")',
      'button:has-text("Add to")'
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
      await prompt(chalk.yellow('Press Enter to close...'));
      return;
    }

    // Click "Add to"
    await addToButton.click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: './logs/playlist-list-4-add-to-menu.png' });
    console.log(chalk.gray('Screenshot saved: playlist-list-4-add-to-menu.png\n'));

    await prompt(chalk.yellow('Press Enter to look for "Playlist" option...'));

    // Try to find and click "Playlist"
    const playlistSelectors = [
      'text="Playlist"',
      ':text("Playlist")',
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

    // Click "Playlist"
    await playlistButton.click();
    await page.waitForTimeout(1500);

    await page.screenshot({ path: './logs/playlist-list-5-playlists.png' });
    console.log(chalk.gray('Screenshot saved: playlist-list-5-playlists.png\n'));

    // Show available playlists
    const playlists = await page.evaluate(() => {
      const items = [];

      // Look for playlist items - they're usually in a scrollable container
      document.querySelectorAll('[role="menuitem"], button, [class*="cursor-pointer"]').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 50 && rect.height > 20 && rect.top > 100 && rect.top < 800) {
          const text = el.textContent?.trim();
          if (text && text.length > 2 && text.length < 100) {
            items.push({
              text,
              className: el.className,
              tagName: el.tagName.toLowerCase()
            });
          }
        }
      });

      return items;
    });

    console.log(chalk.white('Available playlists and options:'));
    playlists.forEach(item => {
      console.log(chalk.gray(`  - ${item.text}`));
    });
    console.log();

    console.log(chalk.green('\n✓ Test complete!\n'));
    console.log(chalk.white('Check the screenshots in ./logs/ to see the menu flow.\n'));
    console.log(chalk.yellow('Findings:'));
    console.log(chalk.gray('1. Confirmed menu structure from song list view'));
    console.log(chalk.gray('2. Flow: ... → Add to → Playlist → [Your Playlist]'));
    console.log(chalk.gray('3. Ready to build automation\n'));

    await prompt(chalk.yellow('Press Enter to close the browser...'));

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
  } finally {
    if (context) await context.close();
    rl.close();
  }
}

testPlaylistMenuFromList();
