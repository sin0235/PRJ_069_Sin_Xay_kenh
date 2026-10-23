#!/usr/bin/env node

/**
 * List Song IDs
 * Shows all songs in your library with their IDs for range download
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

async function listSongIds() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Song ID List                                '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    console.log(chalk.yellow('Loading songs page...\n'));
    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    const selectors = scraperConfig.selectors;
    const songs = [];
    let previousCount = 0;
    let unchangedCount = 0;

    console.log(chalk.yellow('Scrolling to load all songs...\n'));

    // Infinite scroll to load all songs
    for (let i = 0; i < scraperConfig.behavior.infiniteScroll.maxScrollAttempts; i++) {
      const currentSongs = await page.evaluate((selectors) => {
        const songElements = document.querySelectorAll(selectors.songCard);
        const songs = [];

        songElements.forEach((element, index) => {
          const imageElement = element.querySelector('img[alt]') || element.querySelector('img');
          const title = imageElement?.alt?.trim() || `Song ${index + 1}`;

          const linkElement = element.querySelector('a[href*="/song/"]');
          const url = linkElement?.href || '';

          let songId = null;
          if (url) {
            const match = url.match(/\/song\/([^\/]+)/);
            songId = match ? match[1] : null;
          }

          if (songId) {
            songs.push({ title, id: songId });
          }
        });

        return songs;
      }, selectors);

      // Update songs list (use Map to avoid duplicates)
      const uniqueSongs = new Map();
      currentSongs.forEach(song => {
        if (song.id) {
          uniqueSongs.set(song.id, song);
        }
      });

      songs.length = 0;
      songs.push(...Array.from(uniqueSongs.values()));

      process.stdout.write(`\r${chalk.gray(`Found ${songs.length} songs...`)}`);

      if (songs.length === previousCount) {
        unchangedCount++;
        if (unchangedCount >= scraperConfig.behavior.infiniteScroll.noNewContentThreshold) {
          break;
        }
      } else {
        unchangedCount = 0;
        previousCount = songs.length;
      }

      await page.evaluate(() => window.scrollBy(0, 1000));
      await page.waitForTimeout(scraperConfig.behavior.delays.afterScroll);
    }

    console.log(chalk.green(`\n✓ Found ${songs.length} total songs\n`));

    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Song List with IDs                         '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    songs.forEach((song, index) => {
      const position = chalk.gray(`[${String(index + 1).padStart(3, ' ')}]`);
      const id = chalk.yellow(song.id);
      const title = chalk.white(song.title);
      console.log(`${position} ${id} - ${title}`);
    });

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.white('\nUsage examples:\n'));
    console.log(chalk.gray('Download songs 1-10:'));
    console.log(chalk.cyan(`  node cli.js download --start-id ${songs[0]?.id} --end-id ${songs[9]?.id}\n`));
    console.log(chalk.gray('Download songs 5-15:'));
    console.log(chalk.cyan(`  node cli.js download --start-id ${songs[4]?.id} --end-id ${songs[14]?.id}\n`));
    console.log(chalk.gray('Download from song 20 to end:'));
    console.log(chalk.cyan(`  node cli.js download --start-id ${songs[19]?.id}\n`));
    console.log(chalk.gray('Download from beginning to song 30:'));
    console.log(chalk.cyan(`  node cli.js download --end-id ${songs[29]?.id}\n`));

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    process.exit(1);
  } finally {
    if (context) await context.close();
  }
}

listSongIds();
