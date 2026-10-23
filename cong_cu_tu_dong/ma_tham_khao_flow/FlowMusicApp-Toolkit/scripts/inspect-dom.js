#!/usr/bin/env node

/**
 * Inspect DOM Structure
 * Finds the actual selectors used on FlowMusic
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     FlowMusic DOM Inspector                      '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function inspectDOM() {
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

    // Extract detailed DOM information
    console.log(chalk.yellow('Analyzing DOM structure...\n'));

    const domInfo = await page.evaluate(() => {
      const info = {
        songElements: [],
        possibleContainers: []
      };

      // Look for common container patterns
      const containers = [
        ...document.querySelectorAll('main'),
        ...document.querySelectorAll('[class*="list"]'),
        ...document.querySelectorAll('[class*="grid"]'),
        ...document.querySelectorAll('[class*="container"]')
      ];

      containers.forEach((container, idx) => {
        if (container.children.length > 3) {
          info.possibleContainers.push({
            index: idx,
            tag: container.tagName,
            classes: container.className,
            childCount: container.children.length,
            firstChildTag: container.children[0]?.tagName,
            firstChildClasses: container.children[0]?.className
          });
        }
      });

      // Look for song-like elements (elements with images and text)
      const allElements = document.querySelectorAll('*');
      const songCandidates = [];

      allElements.forEach(el => {
        // Skip if too deep or no children
        if (el.children.length === 0) return;

        // Look for elements that contain an image and text
        const hasImage = el.querySelector('img') !== null;
        const hasText = el.textContent && el.textContent.length > 20;

        if (hasImage && hasText) {
          const rect = el.getBoundingClientRect();

          // Must be visible and reasonably sized
          if (rect.height > 50 && rect.height < 300 && rect.width > 100) {
            songCandidates.push({
              tag: el.tagName,
              classes: el.className,
              id: el.id,
              hasLink: el.querySelector('a') !== null,
              hasButton: el.querySelector('button') !== null,
              textPreview: el.textContent.substring(0, 50).trim(),
              imageCount: el.querySelectorAll('img').length,
              buttonCount: el.querySelectorAll('button').length,
              height: Math.round(rect.height),
              width: Math.round(rect.width)
            });
          }
        }
      });

      // Get unique candidates by classes
      const uniqueCandidates = [];
      const seenClasses = new Set();

      songCandidates.forEach(candidate => {
        if (!seenClasses.has(candidate.classes)) {
          seenClasses.add(candidate.classes);
          uniqueCandidates.push(candidate);
        }
      });

      info.songElements = uniqueCandidates.slice(0, 10);

      return info;
    });

    // Display findings
    console.log(chalk.cyan('═══ Possible Song Containers ═══\n'));
    domInfo.possibleContainers.forEach((container, idx) => {
      console.log(chalk.white(`${idx + 1}. ${container.tag}`));
      console.log(chalk.gray(`   Classes: ${container.classes || '(none)'}`));
      console.log(chalk.gray(`   Children: ${container.childCount}`));
      console.log(chalk.gray(`   First child: ${container.firstChildTag} - ${container.firstChildClasses || '(no class)'}`));
      console.log();
    });

    console.log(chalk.cyan('═══ Possible Song Elements ═══\n'));
    domInfo.songElements.forEach((el, idx) => {
      console.log(chalk.white(`${idx + 1}. ${el.tag}`));
      console.log(chalk.gray(`   Classes: ${el.classes || '(none)'}`));
      console.log(chalk.gray(`   ID: ${el.id || '(none)'}`));
      console.log(chalk.gray(`   Size: ${el.width}x${el.height}px`));
      console.log(chalk.gray(`   Has link: ${el.hasLink}, Has button: ${el.hasButton}`));
      console.log(chalk.gray(`   Images: ${el.imageCount}, Buttons: ${el.buttonCount}`));
      console.log(chalk.gray(`   Text: "${el.textPreview}..."`));
      console.log();
    });

    // Try to get actual song data
    console.log(chalk.cyan('═══ Extracting Song Data ═══\n'));

    const songData = await page.evaluate(() => {
      const songs = [];

      // Look for elements that look like song items
      const candidates = document.querySelectorAll('[class*="song"], [class*="track"], [class*="item"]');

      candidates.forEach(el => {
        const img = el.querySelector('img');
        const title = el.querySelector('h1, h2, h3, h4, h5, h6');
        const duration = el.textContent.match(/\d+:\d+/)?.[0];

        if (img && title) {
          songs.push({
            selector: el.className ? `.${el.className.split(' ')[0]}` : el.tagName,
            title: title.textContent.trim().substring(0, 60),
            hasDuration: !!duration,
            duration: duration
          });
        }
      });

      return songs.slice(0, 5);
    });

    console.log(chalk.yellow('Found potential songs:'));
    songData.forEach((song, idx) => {
      console.log(chalk.white(`${idx + 1}. ${song.title}`));
      console.log(chalk.gray(`   Selector: ${song.selector}`));
      console.log(chalk.gray(`   Duration: ${song.duration || 'N/A'}`));
      console.log();
    });

    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ DOM inspection complete!'));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('Browser will stay open for 30 seconds for manual inspection.'));
    console.log(chalk.gray('Press Ctrl+C to exit early.\n'));

    await page.waitForTimeout(30000);

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
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

inspectDOM();