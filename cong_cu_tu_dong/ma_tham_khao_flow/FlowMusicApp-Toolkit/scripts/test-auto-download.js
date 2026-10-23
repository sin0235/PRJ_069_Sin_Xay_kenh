#!/usr/bin/env node

/**
 * Automated Download Test
 * Tests automated clicking through download menus
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Automated Download Test                    '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testAutoDownload() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    const downloadPath = path.resolve('./logs/test-downloads');
    await fs.ensureDir(downloadPath);

    console.log(chalk.yellow(`Loading profile: ${profilePath}`));
    console.log(chalk.yellow(`Download path: ${downloadPath}\n`));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 },
      acceptDownloads: true
    });

    const page = context.pages()[0] || await context.newPage();

    // Navigate to songs page
    console.log(chalk.yellow('Navigating to songs page...'));
    await page.goto(scraperConfig.urls.songs, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);

    // Get first song
    const firstSong = await page.evaluate((selectors) => {
      const songElement = document.querySelector(selectors.songCard);
      if (!songElement) return null;

      const imageElement = songElement.querySelector('img[alt]');
      const linkElement = songElement.querySelector('a[href*="/song/"]');

      return {
        title: imageElement?.alt,
        url: linkElement?.href
      };
    }, scraperConfig.selectors);

    if (!firstSong || !firstSong.url) {
      console.log(chalk.red('✗ Could not find a song to test'));
      return;
    }

    console.log(chalk.green(`✓ Found song: ${firstSong.title}\n`));

    // Navigate to song detail page
    console.log(chalk.yellow('Navigating to song detail page...'));
    await page.goto(firstSong.url, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await page.waitForTimeout(3000);
    console.log(chalk.green('✓ Song page loaded\n'));

    // Extract metadata
    console.log(chalk.yellow('Extracting metadata...\n'));
    const metadata = await page.evaluate(() => {
      const pageText = document.body.innerText;

      // Get title
      const h1 = document.querySelector('h1');
      const h2Large = document.querySelector('h2.text-2xl, h2.text-3xl, h2.text-xl');
      const title = (h1 || h2Large)?.textContent?.trim();

      // Extract from page text
      const bpmMatch = pageText.match(/(\d+)\s*bpm/i);
      const keyMatch = pageText.match(/([A-G][#b]?\s*(?:Major|Minor))/i);
      const modelMatch = pageText.match(/MODEL\s*([A-Z0-9\-\.]+)/i);
      const lyricsMatch = pageText.match(/LYRICS\s*([^\n]+)/i);
      const soundMatch = pageText.match(/SOUND\s*([^M]+?)(?=MODEL|LYRICS|$)/is);

      return {
        title: title || 'Unknown',
        bpm: bpmMatch?.[1],
        key: keyMatch?.[1],
        model: modelMatch?.[1]?.trim(),
        lyrics: lyricsMatch?.[1]?.trim(),
        description: soundMatch?.[1]?.trim()
      };
    });

    console.log(chalk.cyan('═══ Song Metadata ═══\n'));
    Object.entries(metadata).forEach(([key, value]) => {
      if (value && key !== 'description') {
        console.log(chalk.white(`${key}:`), chalk.green(value));
      }
    });
    console.log();

    // Test downloading MP3
    console.log(chalk.yellow('Testing automated download flow...\n'));

    // Step 1: Find and click the three-dots menu (div with aria-haspopup="menu")
    console.log(chalk.gray('Step 1: Finding three-dots menu...'));

    // Use specific attributes from the actual DOM structure
    const menuSelectors = [
      'div[aria-haspopup="menu"][data-sentry-element="MenuTrigger"]',
      'div[aria-haspopup="menu"]',
      'div[data-sentry-element="MenuTrigger"]',
      'div[data-sentry-source-file="RiffOptionsMenu.tsx"]'
    ];

    let menuButton = null;
    for (const selector of menuSelectors) {
      try {
        const locator = page.locator(selector).first();
        const count = await locator.count();
        if (count > 0) {
          const isVisible = await locator.isVisible();
          if (isVisible) {
            menuButton = locator;
            console.log(chalk.green(`✓ Found menu button with selector: ${selector}`));
            break;
          }
        }
      } catch (err) {
        // Try next selector
      }
    }

    if (!menuButton) {
      console.log(chalk.red('✗ Could not find three-dots menu!'));
      await page.screenshot({ path: 'logs/menu-not-found.png' });
      return;
    }

    await menuButton.click();
    await page.waitForTimeout(1500);
    console.log(chalk.green('✓ Clicked three-dots menu\n'));

    // Take screenshot after menu click
    await page.screenshot({ path: 'logs/after-three-dots-click.png' });

    // Step 2: Click "Download" in the menu (with specific class)
    console.log(chalk.gray('Step 2: Looking for "Download" menu item...'));

    // Menu should show: Remix, Details, Download, Share..., Add to..., Report
    // Wait for menu to appear
    await page.waitForTimeout(500);

    // Try specific selector for Download menu item
    const downloadSelectors = [
      '[class*="flex w-full cursor-pointer items-center rounded-md"]:has-text("Download")',
      '[class*="flex"][class*="cursor-pointer"]:has-text("Download")',
      'button:has-text("Download")',
      '[role="menuitem"]:has-text("Download")'
    ];

    let downloadMenuItem = null;
    for (const selector of downloadSelectors) {
      try {
        const locator = page.locator(selector).first();
        const isVisible = await locator.isVisible({ timeout: 2000 }).catch(() => false);
        if (isVisible) {
          downloadMenuItem = locator;
          console.log(chalk.green(`✓ Found "Download" with selector: ${selector}`));
          break;
        }
      } catch (err) {
        // Try next selector
      }
    }

    if (!downloadMenuItem) {
      console.log(chalk.red('✗ "Download" menu item not found!'));

      // List what we see in the menu
      const menuItems = await page.evaluate(() => {
        const items = [];
        const elements = document.querySelectorAll('[role="menuitem"], button, a, div');

        elements.forEach(el => {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0 && rect.top > 180 && rect.top < 600) {
            const text = el.textContent?.trim();
            if (text && text.length < 50) {
              items.push(text);
            }
          }
        });

        return [...new Set(items)].slice(0, 10);
      });

      console.log(chalk.yellow('Visible items in menu area:'));
      menuItems.forEach(item => console.log(chalk.gray(`  - ${item}`)));
      console.log();
      return;
    }

    await downloadMenuItem.click();
    await page.waitForTimeout(1500);
    console.log(chalk.green('✓ Clicked "Download"\n'));

    // Take screenshot after Download click
    await page.screenshot({ path: 'logs/after-download-menu-click.png' });

    // Step 3: Click MP3 format option
    console.log(chalk.gray('Step 3: Looking for "MP3" format option...'));

    const mp3Option = page.locator(scraperConfig.selectors.downloadMP3).first();
    const mp3Exists = await mp3Option.count() > 0;

    if (!mp3Exists) {
      console.log(chalk.red('✗ "MP3" option not found!'));

      // List available format options
      const formatOptions = await page.evaluate(() => {
        const options = [];
        const elements = document.querySelectorAll('[role="menuitem"], button');

        elements.forEach(el => {
          const rect = el.getBoundingClientRect();
          const text = el.textContent?.trim().toLowerCase() || '';

          if (rect.width > 0 && rect.height > 0 &&
              (text.includes('mp3') || text.includes('wav') || text.includes('m4a') ||
               text.includes('stem') || text.includes('video'))) {
            options.push({
              text: el.textContent?.trim(),
              tag: el.tagName
            });
          }
        });

        return options;
      });

      console.log(chalk.yellow('\nAvailable format options:'));
      formatOptions.forEach((opt, idx) => {
        console.log(chalk.gray(`  ${idx + 1}. "${opt.text}" (${opt.tag})`));
      });
      console.log();

      return;
    }

    console.log(chalk.green('✓ Found "MP3" option'));

    // Set up download listener
    const downloadPromise = page.waitForEvent('download', { timeout: 30000 });

    // Click MP3 option
    await mp3Option.click();
    console.log(chalk.green('✓ Clicked "MP3"\n'));

    // Wait for download
    console.log(chalk.yellow('Waiting for download to start...'));

    try {
      const download = await downloadPromise;

      console.log(chalk.green('\n✓ Download started!'));
      console.log(chalk.white('  Filename:'), chalk.cyan(download.suggestedFilename()));
      console.log(chalk.white('  URL:'), chalk.gray(download.url()));

      // Save download
      const savePath = path.join(downloadPath, download.suggestedFilename());
      await download.saveAs(savePath);

      console.log(chalk.green('  ✓ Saved to:'), chalk.gray(savePath));

      // Verify file exists
      const exists = await fs.pathExists(savePath);
      const stats = exists ? await fs.stat(savePath) : null;

      if (exists) {
        const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
        console.log(chalk.green('  ✓ File verified:'), chalk.cyan(`${sizeMB} MB`));
      } else {
        console.log(chalk.red('  ✗ File not found after download'));
      }

    } catch (err) {
      console.log(chalk.red('\n✗ Download timeout or error:'), err.message);
      console.log(chalk.yellow('Check if "preparing to download" modal is still showing'));
    }

    console.log();
    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ Automated download test complete!'));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('Browser will stay open for 10 seconds.'));
    console.log(chalk.gray('Press Ctrl+C to exit early.\n'));

    await page.waitForTimeout(10000);

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(chalk.gray(error.stack));
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

testAutoDownload();
