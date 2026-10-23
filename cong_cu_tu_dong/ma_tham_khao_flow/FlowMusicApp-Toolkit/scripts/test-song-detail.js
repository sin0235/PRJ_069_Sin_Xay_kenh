#!/usr/bin/env node

/**
 * Test Song Detail Page
 * Clicks into a song and inspects available elements
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Song Detail Page Test                      '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testSongDetail() {
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
    console.log(chalk.green('✓ Page loaded\n'));

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

    console.log(chalk.green(`✓ Found song: ${firstSong.title}`));
    console.log(chalk.gray(`  URL: ${firstSong.url}\n`));

    // Navigate to song detail page
    console.log(chalk.yellow('Navigating to song detail page...'));
    await page.goto(firstSong.url, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });

    await page.waitForTimeout(5000);
    console.log(chalk.green('✓ Song detail page loaded\n'));

    // Take screenshot
    await page.screenshot({
      path: 'logs/song-detail-page.png',
      fullPage: true
    });
    console.log(chalk.gray('📷 Screenshot saved: logs/song-detail-page.png\n'));

    // Analyze the page
    console.log(chalk.yellow('Analyzing song detail page...\n'));

    const pageAnalysis = await page.evaluate(() => {
      const analysis = {
        title: null,
        buttons: [],
        downloadOptions: [],
        metadata: {},
        images: [],
        links: [],
        textElements: []
      };

      // Find title
      const titleElements = [
        document.querySelector('h1'),
        document.querySelector('h2'),
        document.querySelector('.song-title'),
        document.querySelector('[data-testid="song-title"]')
      ].filter(Boolean);

      if (titleElements.length > 0) {
        analysis.title = titleElements[0].textContent.trim();
      }

      // Find all buttons
      const buttons = document.querySelectorAll('button');
      buttons.forEach(btn => {
        const text = btn.textContent?.trim() || '';
        const ariaLabel = btn.getAttribute('aria-label') || '';
        const title = btn.getAttribute('title') || '';

        if (text || ariaLabel || title) {
          analysis.buttons.push({
            text: text.substring(0, 50),
            ariaLabel: ariaLabel.substring(0, 50),
            title: title.substring(0, 50),
            classes: btn.className
          });
        }
      });

      // Look for download-related buttons/links
      const downloadKeywords = ['download', 'export', 'save', 'stem', 'mp3', 'wav', 'zip'];
      const allElements = document.querySelectorAll('button, a, [role="button"]');

      allElements.forEach(el => {
        const text = el.textContent?.toLowerCase() || '';
        const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
        const href = el.getAttribute('href') || '';

        const hasDownloadKeyword = downloadKeywords.some(keyword =>
          text.includes(keyword) || ariaLabel.includes(keyword) || href.includes(keyword)
        );

        if (hasDownloadKeyword) {
          analysis.downloadOptions.push({
            tag: el.tagName,
            text: el.textContent?.trim().substring(0, 60),
            ariaLabel: el.getAttribute('aria-label'),
            href: href.substring(0, 80),
            classes: el.className
          });
        }
      });

      // Look for metadata sections
      const metadataKeywords = ['bpm', 'key', 'tempo', 'genre', 'duration', 'created', 'date', 'mood', 'instrument'];

      const allSpans = document.querySelectorAll('span, div[class*="meta"], p');
      allSpans.forEach(el => {
        const text = el.textContent?.toLowerCase() || '';

        metadataKeywords.forEach(keyword => {
          if (text.includes(keyword) && text.length < 100) {
            analysis.metadata[keyword] = el.textContent.trim();
          }
        });
      });

      // Find all images
      const images = document.querySelectorAll('img');
      images.forEach(img => {
        if (img.src && !img.src.includes('icon') && !img.src.includes('logo')) {
          analysis.images.push({
            src: img.src.substring(0, 80),
            alt: img.alt,
            classes: img.className
          });
        }
      });

      // Look for lyrics section
      const lyricsKeywords = ['lyric', 'verse', 'chorus', 'words'];
      const textSections = document.querySelectorAll('div, section, article, pre');

      textSections.forEach(section => {
        const text = section.textContent || '';
        const classes = section.className.toLowerCase();

        const hasLyricsKeyword = lyricsKeywords.some(keyword =>
          classes.includes(keyword) || section.getAttribute('data-testid')?.includes('lyric')
        );

        if (hasLyricsKeyword && text.length > 50) {
          analysis.textElements.push({
            type: 'lyrics',
            preview: text.trim().substring(0, 100),
            classes: section.className,
            length: text.length
          });
        }
      });

      return analysis;
    });

    // Display results
    console.log(chalk.cyan('═══ Page Analysis ═══\n'));

    console.log(chalk.white('Title:'));
    console.log(chalk.gray(`  ${pageAnalysis.title || 'Not found'}\n`));

    console.log(chalk.white(`Buttons Found: ${pageAnalysis.buttons.length}`));
    pageAnalysis.buttons.slice(0, 10).forEach((btn, idx) => {
      console.log(chalk.gray(`  ${idx + 1}. Text: "${btn.text}"`));
      if (btn.ariaLabel) console.log(chalk.gray(`     Aria: "${btn.ariaLabel}"`));
    });
    console.log();

    console.log(chalk.white(`Download Options: ${pageAnalysis.downloadOptions.length}`));
    if (pageAnalysis.downloadOptions.length > 0) {
      pageAnalysis.downloadOptions.forEach((opt, idx) => {
        console.log(chalk.green(`  ${idx + 1}. ${opt.tag}: "${opt.text}"`));
        if (opt.ariaLabel) console.log(chalk.gray(`     Aria: ${opt.ariaLabel}`));
        if (opt.href) console.log(chalk.gray(`     Href: ${opt.href}`));
      });
    } else {
      console.log(chalk.yellow('  ⚠ No download options found'));
      console.log(chalk.gray('     May need to click a menu or button first'));
    }
    console.log();

    console.log(chalk.white('Metadata Found:'));
    if (Object.keys(pageAnalysis.metadata).length > 0) {
      Object.entries(pageAnalysis.metadata).forEach(([key, value]) => {
        console.log(chalk.gray(`  ${key}: ${value}`));
      });
    } else {
      console.log(chalk.yellow('  ⚠ No metadata found'));
    }
    console.log();

    console.log(chalk.white(`Images Found: ${pageAnalysis.images.length}`));
    pageAnalysis.images.slice(0, 3).forEach((img, idx) => {
      console.log(chalk.gray(`  ${idx + 1}. Alt: "${img.alt}"`));
      console.log(chalk.gray(`     Src: ${img.src}...`));
    });
    console.log();

    console.log(chalk.white(`Lyrics Sections: ${pageAnalysis.textElements.length}`));
    if (pageAnalysis.textElements.length > 0) {
      pageAnalysis.textElements.forEach((section, idx) => {
        console.log(chalk.gray(`  ${idx + 1}. Length: ${section.length} chars`));
        console.log(chalk.gray(`     Preview: ${section.preview}...`));
      });
    }
    console.log();

    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ Analysis complete!'));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.yellow('Browser will stay open for 30 seconds for inspection.'));
    console.log(chalk.gray('Check the screenshot at logs/song-detail-page.png'));
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

testSongDetail();
