#!/usr/bin/env node

/**
 * Find Menu Button
 * Analyzes all buttons to find the three-dots menu
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

async function findMenuButton() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    await page.goto(scraperConfig.urls.songs, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    const firstSong = await page.evaluate((selectors) => {
      const songElement = document.querySelector(selectors.songCard);
      const imageElement = songElement?.querySelector('img[alt]');
      const linkElement = songElement?.querySelector('a[href*="/song/"]');
      return { title: imageElement?.alt, url: linkElement?.href };
    }, scraperConfig.selectors);

    await page.goto(firstSong.url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000);

    console.log(chalk.cyan('\nAnalyzing all buttons...\n'));

    // Analyze all buttons
    const buttonAnalysis = await page.evaluate(() => {
      const buttons = [];
      const allButtons = document.querySelectorAll('button');

      allButtons.forEach((btn, idx) => {
        const rect = btn.getBoundingClientRect();

        // Focus on header buttons (top 300px)
        if (rect.top < 300 && rect.width > 0 && rect.height > 0) {
          const html = btn.innerHTML;
          const text = btn.textContent?.trim();
          const ariaLabel = btn.getAttribute('aria-label');

          // Check for three-dots patterns
          const hasThreeDots = html.includes('...') ||
                             html.includes('•••') ||
                             html.includes('⋯') ||
                             text === '...' ||
                             text === '•••';

          // Check if it's likely a menu button based on SVG patterns
          const svgCount = btn.querySelectorAll('svg').length;
          const hasSVG = svgCount > 0;

          // Check for specific circle patterns in SVG (three dots are often circles)
          const hasCircles = html.includes('<circle') || html.includes('circle');
          const circleCount = (html.match(/<circle/g) || []).length;

          buttons.push({
            index: idx,
            text: text || '(empty)',
            ariaLabel: ariaLabel || '(none)',
            hasThreeDots,
            hasSVG,
            svgCount,
            hasCircles,
            circleCount,
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            top: Math.round(rect.top),
            left: Math.round(rect.left),
            htmlPreview: html.substring(0, 150)
          });
        }
      });

      return buttons;
    });

    console.log(chalk.white(`Found ${buttonAnalysis.length} buttons in header area:\n`));

    buttonAnalysis.forEach(btn => {
      const isLikelyMenu = btn.hasThreeDots || (btn.hasCircles && btn.circleCount >= 3);

      if (isLikelyMenu) {
        console.log(chalk.green(`⭐ Button ${btn.index} - LIKELY MENU BUTTON`));
      } else {
        console.log(chalk.white(`Button ${btn.index}`));
      }

      console.log(chalk.gray(`  Text: "${btn.text}"`));
      console.log(chalk.gray(`  Aria: ${btn.ariaLabel}`));
      console.log(chalk.gray(`  Position: ${btn.left}, ${btn.top} | Size: ${btn.width}x${btn.height}`));
      console.log(chalk.gray(`  Has three dots: ${btn.hasThreeDots}`));
      console.log(chalk.gray(`  SVG count: ${btn.svgCount}, Circles: ${btn.circleCount}`));

      if (isLikelyMenu) {
        console.log(chalk.yellow(`  HTML: ${btn.htmlPreview}...`));
      }
      console.log();
    });

    // Find the rightmost button (likely the menu)
    const rightmost = buttonAnalysis.reduce((max, btn) =>
      btn.left > max.left ? btn : max, buttonAnalysis[0]);

    console.log(chalk.cyan('═══ Analysis ═══\n'));
    console.log(chalk.white('Rightmost button (likely menu):'));
    console.log(chalk.green(`  Button index: ${rightmost.index}`));
    console.log(chalk.gray(`  Position: ${rightmost.left}, ${rightmost.top}`));
    console.log();

    // Suggest selector
    console.log(chalk.yellow('Suggested approach:'));
    console.log(chalk.gray(`  1. Use: page.locator('button').nth(${rightmost.index})`));
    console.log(chalk.gray(`  2. Or position-based: buttons at left > ${rightmost.left - 50}`));
    console.log();

    await page.waitForTimeout(15000);

  } catch (error) {
    console.error(chalk.red('Error:'), error.message);
  } finally {
    if (context) await context.close();
  }
}

findMenuButton();
