#!/usr/bin/env node

/**
 * Test Download Button
 * Finds and clicks the download icon button
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Download Button Test                       '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testDownloadButton() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    console.log(chalk.yellow(`Loading profile: ${profilePath}\n`));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    console.log(chalk.yellow('Navigating to songs page...'));
    await page.goto(scraperConfig.urls.songs, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });

    await page.waitForTimeout(5000);

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

    await page.waitForTimeout(5000);
    console.log(chalk.green('✓ Song detail page loaded\n'));

    // Extract all metadata from the page
    console.log(chalk.yellow('Extracting metadata...\n'));

    const metadata = await page.evaluate(() => {
      const data = {};

      // Get title from the main heading
      const titleEl = document.querySelector('h1, h2.text-2xl, h2.text-3xl');
      data.title = titleEl?.textContent?.trim();

      // Get author
      const authorEl = document.querySelector('[class*="text-sm"]:has(+ h1), [class*="text-sm"]:has(+ h2)');
      data.author = authorEl?.textContent?.trim();

      // Parse SOUND section
      const soundHeading = Array.from(document.querySelectorAll('*')).find(el =>
        el.textContent?.trim().startsWith('SOUND') && el.tagName.match(/^H[1-6]$/)
      );

      if (soundHeading) {
        const soundSection = soundHeading.nextElementSibling || soundHeading.parentElement;
        const soundText = soundSection?.textContent || '';
        data.description = soundText.trim();

        // Extract BPM
        const bpmMatch = soundText.match(/(\d+)\s*bpm/i);
        if (bpmMatch) data.bpm = bpmMatch[1];

        // Extract Key
        const keyMatch = soundText.match(/([A-G][#b]?\s*(?:Major|major|Minor|minor))/);
        if (keyMatch) data.key = keyMatch[1];

        // Extract instruments/style
        data.instruments = soundText;
      }

      // Get MODEL
      const modelHeading = Array.from(document.querySelectorAll('*')).find(el =>
        el.textContent?.trim() === 'MODEL' && el.tagName.match(/^H[1-6]$/)
      );

      if (modelHeading) {
        const modelSection = modelHeading.nextElementSibling || modelHeading.parentElement;
        data.model = modelSection?.textContent?.trim();
      }

      // Get LYRICS
      const lyricsHeading = Array.from(document.querySelectorAll('*')).find(el =>
        el.textContent?.trim() === 'LYRICS' && el.tagName.match(/^H[1-6]$/)
      );

      if (lyricsHeading) {
        const lyricsSection = lyricsHeading.nextElementSibling || lyricsHeading.parentElement;
        data.lyrics = lyricsSection?.textContent?.trim();
      }

      return data;
    });

    console.log(chalk.cyan('═══ Song Metadata ═══\n'));
    console.log(chalk.white('Title:'), chalk.gray(metadata.title || 'Not found'));
    console.log(chalk.white('Author:'), chalk.gray(metadata.author || 'Not found'));
    console.log(chalk.white('BPM:'), chalk.gray(metadata.bpm || 'Not found'));
    console.log(chalk.white('Key:'), chalk.gray(metadata.key || 'Not found'));
    console.log(chalk.white('Model:'), chalk.gray(metadata.model || 'Not found'));
    console.log(chalk.white('Lyrics:'), chalk.gray(metadata.lyrics || 'Not found'));
    console.log();

    // Look for download button
    console.log(chalk.yellow('Looking for download button...\n'));

    // Try to find all buttons near the top
    const buttons = await page.evaluate(() => {
      const buttonInfo = [];
      const allButtons = document.querySelectorAll('button');

      allButtons.forEach((btn, idx) => {
        const rect = btn.getBoundingClientRect();

        // Focus on buttons in the upper part of the page (likely action buttons)
        if (rect.top < 400 && rect.width > 0 && rect.height > 0) {
          const hasDownloadIcon = btn.innerHTML.includes('download') ||
                                 btn.innerHTML.includes('Download') ||
                                 btn.getAttribute('aria-label')?.toLowerCase().includes('download');

          buttonInfo.push({
            index: idx,
            text: btn.textContent?.trim(),
            ariaLabel: btn.getAttribute('aria-label'),
            classes: btn.className,
            top: Math.round(rect.top),
            hasDownloadIcon,
            innerHTML: btn.innerHTML.substring(0, 200)
          });
        }
      });

      return buttonInfo;
    });

    console.log(chalk.cyan(`Found ${buttons.length} buttons in header area:\n`));
    buttons.forEach(btn => {
      console.log(chalk.white(`Button ${btn.index}:`));
      console.log(chalk.gray(`  Text: "${btn.text}"`));
      console.log(chalk.gray(`  Aria: ${btn.ariaLabel || 'none'}`));
      console.log(chalk.gray(`  Has download icon: ${btn.hasDownloadIcon ? 'YES' : 'no'}`));
      if (btn.hasDownloadIcon) {
        console.log(chalk.green(`  ⭐ This looks like the download button!`));
      }
      console.log();
    });

    // Find and click the download button
    const downloadButtonIndex = buttons.findIndex(b => b.hasDownloadIcon);

    if (downloadButtonIndex >= 0) {
      console.log(chalk.green(`✓ Found download button at index ${buttons[downloadButtonIndex].index}\n`));
      console.log(chalk.yellow('Clicking download button...'));

      // Click the button by index
      await page.locator('button').nth(buttons[downloadButtonIndex].index).click();
      await page.waitForTimeout(3000);

      console.log(chalk.green('✓ Download button clicked\n'));

      // Take screenshot
      await page.screenshot({
        path: 'logs/after-download-click.png',
        fullPage: true
      });
      console.log(chalk.gray('📷 Screenshot saved: logs/after-download-click.png\n'));

      // Look for download modal/menu
      console.log(chalk.yellow('Looking for download options...\n'));

      const downloadOptions = await page.evaluate(() => {
        const options = [];
        const keywords = ['mp3', 'wav', 'zip', 'stem', 'audio', 'download'];

        // Look in modals, dialogs, menus
        const containers = document.querySelectorAll(
          'div[role="dialog"], div[role="menu"], [class*="modal"], [class*="popup"], [class*="dropdown"]'
        );

        // Also check all recently visible elements
        const allElements = document.querySelectorAll('button, a, [role="button"], [role="menuitem"]');

        allElements.forEach(el => {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            const text = el.textContent?.toLowerCase() || '';
            const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();

            const hasKeyword = keywords.some(keyword =>
              text.includes(keyword) || ariaLabel.includes(keyword)
            );

            if (hasKeyword) {
              options.push({
                tag: el.tagName,
                text: el.textContent?.trim(),
                ariaLabel: el.getAttribute('aria-label'),
                href: el.getAttribute('href'),
                classes: el.className,
                top: Math.round(rect.top),
                left: Math.round(rect.left)
              });
            }
          }
        });

        return options;
      });

      console.log(chalk.cyan('═══ Download Options ═══\n'));

      if (downloadOptions.length > 0) {
        console.log(chalk.green(`✓ Found ${downloadOptions.length} download options:\n`));

        downloadOptions.forEach((opt, idx) => {
          console.log(chalk.white(`${idx + 1}. ${opt.tag}: "${opt.text}"`));
          if (opt.ariaLabel) console.log(chalk.gray(`   Aria: ${opt.ariaLabel}`));
          if (opt.href) console.log(chalk.gray(`   Href: ${opt.href}`));
          console.log(chalk.gray(`   Position: top ${opt.top}px, left ${opt.left}px`));
          console.log();
        });
      } else {
        console.log(chalk.yellow('⚠ No download options found after clicking'));
        console.log(chalk.gray('Check the screenshot to see what appeared.\n'));
      }

    } else {
      console.log(chalk.red('✗ Download button not found'));
      console.log(chalk.gray('Manual inspection required.\n'));
    }

    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ Test complete!'));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('Browser will stay open for 30 seconds.'));
    console.log(chalk.gray('Press Ctrl+C to exit early.\n'));

    await page.waitForTimeout(30000);

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

testDownloadButton();
