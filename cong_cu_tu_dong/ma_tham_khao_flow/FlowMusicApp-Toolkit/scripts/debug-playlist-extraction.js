#!/usr/bin/env node

/**
 * Debug Playlist Extraction
 * Takes screenshots and logs DOM state to understand playlist extraction issue
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

async function debugPlaylistExtraction() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Debug Playlist Extraction                   '));
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

    await page.screenshot({ path: './logs/debug-1-menu-open.png' });

    // Hover over "Add to"
    console.log(chalk.yellow('[4] Hovering over "Add to"...\n'));
    const addToItem = page.locator('[role="menuitem"]:has-text("Add to")').first();
    await addToItem.hover();
    await page.waitForTimeout(2000);

    await page.screenshot({ path: './logs/debug-2-add-to-hover.png' });

    // Hover over "Playlist"
    console.log(chalk.yellow('[5] Hovering over "Playlist"...\n'));
    const playlistItem = page.locator('[role="menuitem"]:has-text("Playlist")').first();
    await playlistItem.hover();
    await page.waitForTimeout(3000);

    await page.screenshot({ path: './logs/debug-3-playlist-hover.png' });

    // Check for various selectors
    console.log(chalk.yellow('[6] Checking DOM for playlist items...\n'));

    const analysis = await page.evaluate(() => {
      const results = {
        playlistItemComponents: [],
        allMenuItems: [],
        visibleMenus: [],
        allPlaylistRelated: []
      };

      // Check for PlaylistItem components
      const playlistItems = document.querySelectorAll('[role="menuitem"][data-sentry-component="PlaylistItem"]');
      playlistItems.forEach(el => {
        const rect = el.getBoundingClientRect();
        const textDiv = el.querySelector('.line-clamp-2');
        results.playlistItemComponents.push({
          visible: rect.width > 0 && rect.height > 0,
          text: textDiv?.textContent?.trim() || el.textContent?.trim() || '',
          rect: { width: rect.width, height: rect.height }
        });
      });

      // Check all menu items
      const allMenuItems = document.querySelectorAll('[role="menuitem"]');
      allMenuItems.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          const component = el.getAttribute('data-sentry-component');
          results.allMenuItems.push({
            text: el.textContent?.trim() || '',
            component: component,
            rect: { width: rect.width, height: rect.height }
          });
        }
      });

      // Check for all visible menu containers
      const menus = document.querySelectorAll('[role="menu"], [data-radix-menu-content]');
      menus.forEach((menu, idx) => {
        const rect = menu.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          results.visibleMenus.push({
            index: idx,
            rect: { width: rect.width, height: rect.height },
            itemCount: menu.querySelectorAll('[role="menuitem"]').length
          });
        }
      });

      // Check for any element containing "God Is Water" or "Playlist"
      const allElements = document.querySelectorAll('*');
      allElements.forEach(el => {
        const text = el.textContent?.trim() || '';
        if (text.toLowerCase().includes('god is water') || (text.toLowerCase().includes('playlist') && text.length < 50)) {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            results.allPlaylistRelated.push({
              tag: el.tagName.toLowerCase(),
              text: text.substring(0, 100),
              role: el.getAttribute('role'),
              component: el.getAttribute('data-sentry-component'),
              classes: Array.from(el.classList).slice(0, 5).join(' ')
            });
          }
        }
      });

      return results;
    });

    console.log(chalk.white('═══════════════════════════════════════════════════'));
    console.log(chalk.white('DOM Analysis Results:\n'));

    console.log(chalk.cyan('1. PlaylistItem components:'));
    if (analysis.playlistItemComponents.length === 0) {
      console.log(chalk.red('   ✗ No PlaylistItem components found!'));
    } else {
      analysis.playlistItemComponents.forEach((item, idx) => {
        console.log(chalk.gray(`   [${idx}] ${item.visible ? '✓' : '✗'} ${item.text}`));
        console.log(chalk.gray(`       Size: ${item.rect.width}x${item.rect.height}`));
      });
    }

    console.log(chalk.cyan('\n2. All visible menu items:'));
    analysis.allMenuItems.forEach((item, idx) => {
      const componentStr = item.component ? ` (${item.component})` : '';
      console.log(chalk.gray(`   [${idx}] ${item.text}${componentStr}`));
    });

    console.log(chalk.cyan('\n3. Visible menu containers:'));
    analysis.visibleMenus.forEach(menu => {
      console.log(chalk.gray(`   Menu ${menu.index}: ${menu.itemCount} items, size: ${menu.rect.width}x${menu.rect.height}`));
    });

    console.log(chalk.cyan('\n4. Playlist-related elements:'));
    if (analysis.allPlaylistRelated.length === 0) {
      console.log(chalk.red('   ✗ No playlist-related elements found!'));
    } else {
      analysis.allPlaylistRelated.forEach((el, idx) => {
        console.log(chalk.gray(`   [${idx}] <${el.tag}> role="${el.role}" component="${el.component}"`));
        console.log(chalk.gray(`       "${el.text}"`));
      });
    }

    console.log(chalk.white('\n═══════════════════════════════════════════════════'));

    console.log(chalk.yellow('\nBrowser staying open for inspection. Press Ctrl+C when done.\n'));

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

debugPlaylistExtraction();
