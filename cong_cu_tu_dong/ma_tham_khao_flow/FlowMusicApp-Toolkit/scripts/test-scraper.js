#!/usr/bin/env node

/**
 * Test Song Scraper
 * Verifies song extraction with updated selectors
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Song Scraper Test                          '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testScraper() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    console.log(chalk.yellow(`Loading profile: ${profilePath}\n`));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    console.log(chalk.yellow('Navigating to FlowMusic...'));
    await page.goto(scraperConfig.urls.songs, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });

    await page.waitForTimeout(5000);
    console.log(chalk.green('✓ Page loaded\n'));

    // Test song extraction
    console.log(chalk.yellow('Testing song extraction with updated selectors...\n'));

    const songs = await page.evaluate((selectors) => {
      const songElements = document.querySelectorAll(selectors.songCard);
      console.log(`Found ${songElements.length} song card elements`);

      const songList = [];

      // Extract first 5 songs as test
      for (let i = 0; i < Math.min(5, songElements.length); i++) {
        const element = songElements[i];

        try {
          // Extract title from image alt
          const imageElement = element.querySelector(selectors.songImage) ||
                             element.querySelector('img[alt]') ||
                             element.querySelector('img');
          const title = imageElement?.alt?.trim() || `Song ${i + 1}`;

          // Extract URL
          const linkElement = element.querySelector(selectors.songLink) ||
                            element.querySelector('a[href*="/song"]');
          const url = linkElement?.href || '';

          // Extract song ID
          let songId = null;
          if (url) {
            const match = url.match(/\/song\/([^\/]+)/);
            songId = match ? match[1] : null;
          }

          // Extract duration
          const durationElement = element.querySelector(selectors.duration) ||
                                element.querySelector('span.text-fg-2.w-8');
          const duration = durationElement?.innerText?.trim();

          // Extract image URL
          const imageUrl = imageElement?.src;

          songList.push({
            index: i + 1,
            id: songId,
            title: title,
            url: url,
            duration: duration,
            imageUrl: imageUrl ? imageUrl.substring(0, 80) + '...' : null,
            hasImage: !!imageElement,
            hasLink: !!linkElement,
            hasDuration: !!durationElement
          });

        } catch (err) {
          console.error(`Error extracting song ${i}:`, err);
          songList.push({
            index: i + 1,
            error: err.message
          });
        }
      }

      return songList;
    }, scraperConfig.selectors);

    // Display results
    console.log(chalk.cyan('═══ Extracted Songs ═══\n'));

    if (songs.length === 0) {
      console.log(chalk.red('✗ No songs extracted!'));
      console.log(chalk.yellow('The selectors may still be incorrect.\n'));
    } else {
      console.log(chalk.green(`✓ Successfully extracted ${songs.length} songs\n`));

      songs.forEach(song => {
        if (song.error) {
          console.log(chalk.red(`${song.index}. ERROR: ${song.error}`));
        } else {
          console.log(chalk.white(`${song.index}. ${song.title}`));
          console.log(chalk.gray(`   ID: ${song.id || 'N/A'}`));
          console.log(chalk.gray(`   Duration: ${song.duration || 'N/A'}`));
          console.log(chalk.gray(`   URL: ${song.url ? song.url.substring(0, 70) + '...' : 'N/A'}`));
          console.log(chalk.gray(`   Has Image: ${song.hasImage ? '✓' : '✗'}`));
          console.log(chalk.gray(`   Has Link: ${song.hasLink ? '✓' : '✗'}`));
          console.log(chalk.gray(`   Has Duration: ${song.hasDuration ? '✓' : '✗'}`));
          console.log();
        }
      });

      // Validation check
      const validSongs = songs.filter(s => !s.error && s.title && s.id);
      const validPercentage = (validSongs.length / songs.length * 100).toFixed(0);

      console.log(chalk.cyan('═══ Validation Summary ═══\n'));
      console.log(chalk.white(`Valid songs: ${validSongs.length}/${songs.length} (${validPercentage}%)`));

      if (validPercentage >= 80) {
        console.log(chalk.green('✓ Selectors are working well!'));
      } else if (validPercentage >= 50) {
        console.log(chalk.yellow('⚠ Selectors working but may need refinement'));
      } else {
        console.log(chalk.red('✗ Selectors need significant adjustment'));
      }
      console.log();
    }

    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ Scraper test complete!'));
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

testScraper();
