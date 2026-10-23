#!/usr/bin/env node

/**
 * Test Download Menu
 * Clicks the three-dots menu and explores download options
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Download Menu Test                         '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testDownloadMenu() {
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
    console.log(chalk.yellow('Finding first song...'));
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

    // Extract metadata from the page before clicking menu
    console.log(chalk.yellow('Extracting metadata from page...\n'));

    const metadata = await page.evaluate(() => {
      const data = {
        title: null,
        description: null,
        model: null,
        lyrics: null,
        bpm: null,
        key: null,
        instruments: [],
        style: null
      };

      // Get title from h1 or main heading
      const titleElement = document.querySelector('h1, h2[class*="title"], .song-title');
      data.title = titleElement?.textContent?.trim();

      // Get SOUND section
      const soundSection = Array.from(document.querySelectorAll('div, section')).find(el =>
        el.textContent?.includes('SOUND') && el.textContent?.includes('bpm')
      );

      if (soundSection) {
        const soundText = soundSection.textContent || '';
        data.description = soundText;

        // Extract BPM
        const bpmMatch = soundText.match(/(\d+)\s*bpm/i);
        if (bpmMatch) data.bpm = bpmMatch[1];

        // Extract Key
        const keyMatch = soundText.match(/([A-G][#b]?\s*(?:Major|Minor))/i);
        if (keyMatch) data.key = keyMatch[1];
      }

      // Get MODEL section
      const modelSection = Array.from(document.querySelectorAll('div, section')).find(el => {
        const heading = el.querySelector('h1, h2, h3, h4, strong');
        return heading?.textContent?.includes('MODEL');
      });

      if (modelSection) {
        const modelText = modelSection.textContent || '';
        const modelMatch = modelText.match(/MODEL\s*([^\n]+)/i);
        if (modelMatch) data.model = modelMatch[1].trim();
      }

      // Get LYRICS section
      const lyricsSection = Array.from(document.querySelectorAll('div, section')).find(el => {
        const heading = el.querySelector('h1, h2, h3, h4, strong');
        return heading?.textContent?.includes('LYRICS');
      });

      if (lyricsSection) {
        data.lyrics = lyricsSection.textContent?.replace(/LYRICS/i, '').trim();
      }

      return data;
    });

    console.log(chalk.cyan('═══ Extracted Metadata ═══\n'));
    console.log(chalk.white('Title:'), chalk.gray(metadata.title || 'Not found'));
    console.log(chalk.white('BPM:'), chalk.gray(metadata.bpm || 'Not found'));
    console.log(chalk.white('Key:'), chalk.gray(metadata.key || 'Not found'));
    console.log(chalk.white('Model:'), chalk.gray(metadata.model || 'Not found'));
    console.log(chalk.white('Lyrics:'), chalk.gray(metadata.lyrics || 'Not found'));
    console.log();

    // Look for three-dots menu button
    console.log(chalk.yellow('Looking for menu button...\n'));

    // Try multiple selectors for the menu button
    const menuSelectors = [
      'button:has-text("...")',
      'button[aria-label*="menu"]',
      'button[aria-label*="More"]',
      'button[aria-label*="options"]',
      'button svg',  // SVG icon buttons
      'button[class*="menu"]',
      'button:has(svg)'
    ];

    let menuFound = false;
    let menuSelector = null;

    for (const selector of menuSelectors) {
      try {
        const count = await page.locator(selector).count();
        console.log(chalk.gray(`  Trying: ${selector} - found ${count} elements`));

        if (count > 0) {
          // Look at all buttons to find the right one
          const buttons = await page.locator(selector).all();

          for (let i = 0; i < buttons.length; i++) {
            const isVisible = await buttons[i].isVisible();
            if (isVisible) {
              const text = await buttons[i].textContent();
              const ariaLabel = await buttons[i].getAttribute('aria-label');

              console.log(chalk.gray(`    Button ${i}: text="${text?.trim()}", aria="${ariaLabel}"`));

              // Check if this looks like a menu button
              if (text?.includes('...') || ariaLabel?.toLowerCase().includes('menu') || ariaLabel?.toLowerCase().includes('more')) {
                menuSelector = selector;
                menuFound = true;
                console.log(chalk.green(`\n✓ Found menu button at index ${i}`));

                // Take screenshot before clicking
                await page.screenshot({
                  path: 'logs/before-menu-click.png'
                });

                // Click the menu button
                await buttons[i].click();
                await page.waitForTimeout(2000);

                console.log(chalk.green('✓ Menu clicked\n'));
                break;
              }
            }
          }

          if (menuFound) break;
        }
      } catch (err) {
        // Continue to next selector
      }
    }

    if (!menuFound) {
      console.log(chalk.yellow('⚠ Menu button not found with standard selectors'));
      console.log(chalk.gray('Trying to find any button with three dots...\n'));

      // Try to find button by visual cue
      const allButtons = await page.locator('button').all();
      console.log(chalk.gray(`Found ${allButtons.length} total buttons\n`));

      for (let i = 0; i < Math.min(30, allButtons.length); i++) {
        try {
          const isVisible = await allButtons[i].isVisible();
          if (isVisible) {
            const text = await allButtons[i].textContent();
            const html = await allButtons[i].innerHTML();

            // Look for likely menu indicators
            if (html.includes('...') || html.includes('More') || html.includes('menu')) {
              console.log(chalk.green(`✓ Found potential menu button at index ${i}`));
              console.log(chalk.gray(`  HTML: ${html.substring(0, 100)}`));

              await allButtons[i].click();
              await page.waitForTimeout(2000);
              menuFound = true;
              break;
            }
          }
        } catch (err) {
          // Skip
        }
      }
    }

    // Take screenshot after clicking menu
    await page.screenshot({
      path: 'logs/after-menu-click.png',
      fullPage: true
    });
    console.log(chalk.gray('📷 Screenshot saved: logs/after-menu-click.png\n'));

    // Look for download options
    console.log(chalk.yellow('Looking for download options...\n'));

    const downloadOptions = await page.evaluate(() => {
      const options = [];
      const keywords = ['download', 'export', 'save', 'mp3', 'wav', 'zip', 'stem'];

      // Check all visible elements
      const elements = document.querySelectorAll('button, a, [role="button"], [role="menuitem"]');

      elements.forEach(el => {
        const text = el.textContent?.toLowerCase() || '';
        const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
        const href = el.getAttribute('href') || '';

        const hasKeyword = keywords.some(keyword =>
          text.includes(keyword) || ariaLabel.includes(keyword) || href.includes(keyword)
        );

        if (hasKeyword) {
          const rect = el.getBoundingClientRect();
          // Only include visible elements
          if (rect.width > 0 && rect.height > 0) {
            options.push({
              tag: el.tagName,
              text: el.textContent?.trim(),
              ariaLabel: el.getAttribute('aria-label'),
              href: href,
              classes: el.className,
              isButton: el.tagName === 'BUTTON',
              isLink: el.tagName === 'A'
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
        console.log(chalk.gray(`   Type: ${opt.isButton ? 'Button' : 'Link'}`));
        console.log();
      });
    } else {
      console.log(chalk.red('✗ No download options found'));
      console.log(chalk.yellow('The menu structure may be different than expected.'));
      console.log(chalk.gray('Check the screenshots for manual inspection.\n'));
    }

    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ Test complete!'));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('Browser will stay open for 30 seconds for inspection.'));
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

testDownloadMenu();
