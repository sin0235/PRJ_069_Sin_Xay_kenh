#!/usr/bin/env node

/**
 * Detailed DOM Inspection
 * Extracts exact selectors for all song elements
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Detailed Song Element Inspector            '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function detailedInspect() {
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

    // Extract detailed selector information
    console.log(chalk.yellow('Analyzing song elements in detail...\n'));

    const selectorInfo = await page.evaluate(() => {
      const info = {
        songCards: [],
        sampleElements: {}
      };

      // Find the song card elements (based on our initial inspection)
      const songElements = document.querySelectorAll('.group.mb-1.flex.cursor-pointer');

      console.log(`Found ${songElements.length} song elements`);

      // Analyze first 3 songs in detail
      for (let i = 0; i < Math.min(3, songElements.length); i++) {
        const song = songElements[i];

        // Get all child elements
        const img = song.querySelector('img');
        const allLinks = song.querySelectorAll('a');
        const allButtons = song.querySelectorAll('button');
        const allSpans = song.querySelectorAll('span');
        const allDivs = song.querySelectorAll('div');

        // Try to find title
        let titleElement = null;
        let titleSelector = null;
        for (const span of allSpans) {
          const text = span.textContent.trim();
          if (text.length > 10 && text.length < 100 && !text.includes('BPM') && !text.match(/^\d+:\d+$/)) {
            titleElement = span;
            titleSelector = {
              tag: span.tagName,
              classes: span.className,
              text: text.substring(0, 60)
            };
            break;
          }
        }

        // Try to find duration
        let durationElement = null;
        let durationSelector = null;
        for (const span of allSpans) {
          const text = span.textContent.trim();
          if (text.match(/^\d+:\d+$/)) {
            durationElement = span;
            durationSelector = {
              tag: span.tagName,
              classes: span.className,
              text: text
            };
            break;
          }
        }

        // Get main link (usually the first one or largest one)
        const mainLink = allLinks[0];

        info.songCards.push({
          index: i,
          mainClasses: song.className,
          imageSelector: img ? {
            tag: img.tagName,
            classes: img.className,
            src: img.src.substring(0, 80),
            alt: img.alt
          } : null,
          titleSelector: titleSelector,
          durationSelector: durationSelector,
          linkSelector: mainLink ? {
            tag: mainLink.tagName,
            classes: mainLink.className,
            href: mainLink.href.substring(0, 80)
          } : null,
          buttonCount: allButtons.length,
          firstButtonClasses: allButtons[0]?.className,
          spanCount: allSpans.length,
          divCount: allDivs.length
        });
      }

      // Get unique button types by analyzing aria-labels and titles
      const allButtons = document.querySelectorAll('button');
      const buttonTypes = new Set();

      allButtons.forEach(btn => {
        const ariaLabel = btn.getAttribute('aria-label') || '';
        const title = btn.getAttribute('title') || '';
        const text = btn.textContent?.trim() || '';

        if (ariaLabel) buttonTypes.add(`aria-label: ${ariaLabel}`);
        if (title) buttonTypes.add(`title: ${title}`);
        if (text && text.length < 30) buttonTypes.add(`text: ${text}`);
      });

      info.sampleElements.buttonTypes = Array.from(buttonTypes).slice(0, 15);

      return info;
    });

    // Display findings
    console.log(chalk.cyan('═══ Song Card Structure ═══\n'));

    selectorInfo.songCards.forEach((card, idx) => {
      console.log(chalk.white(`Song ${idx + 1}:`));
      console.log(chalk.gray(`  Main container classes: ${card.mainClasses}`));
      console.log();

      if (card.imageSelector) {
        console.log(chalk.yellow('  Image:'));
        console.log(chalk.gray(`    Classes: ${card.imageSelector.classes || '(none)'}`));
        console.log(chalk.gray(`    Alt: ${card.imageSelector.alt}`));
        console.log(chalk.gray(`    Src: ${card.imageSelector.src}...`));
        console.log();
      }

      if (card.titleSelector) {
        console.log(chalk.yellow('  Title:'));
        console.log(chalk.gray(`    Tag: ${card.titleSelector.tag}`));
        console.log(chalk.gray(`    Classes: ${card.titleSelector.classes || '(none)'}`));
        console.log(chalk.gray(`    Text: "${card.titleSelector.text}"`));
        console.log();
      }

      if (card.durationSelector) {
        console.log(chalk.yellow('  Duration:'));
        console.log(chalk.gray(`    Tag: ${card.durationSelector.tag}`));
        console.log(chalk.gray(`    Classes: ${card.durationSelector.classes || '(none)'}`));
        console.log(chalk.gray(`    Text: ${card.durationSelector.text}`));
        console.log();
      }

      if (card.linkSelector) {
        console.log(chalk.yellow('  Link:'));
        console.log(chalk.gray(`    Classes: ${card.linkSelector.classes || '(none)'}`));
        console.log(chalk.gray(`    Href: ${card.linkSelector.href}...`));
        console.log();
      }

      console.log(chalk.gray(`  Buttons: ${card.buttonCount}`));
      console.log(chalk.gray(`  First button classes: ${card.firstButtonClasses}`));
      console.log();
      console.log(chalk.cyan('─────────────────────────────────────────────────'));
      console.log();
    });

    console.log(chalk.cyan('═══ Button Types Found ═══\n'));
    selectorInfo.sampleElements.buttonTypes.forEach(type => {
      console.log(chalk.gray(`  • ${type}`));
    });
    console.log();

    console.log(chalk.cyan('═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ Detailed inspection complete!'));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    // Generate suggested config
    console.log(chalk.yellow('Suggested Selector Configuration:\n'));

    const firstCard = selectorInfo.songCards[0];
    if (firstCard) {
      console.log(chalk.white('selectors: {'));
      console.log(chalk.gray(`  songCard: '.group.mb-1.flex.cursor-pointer',`));

      if (firstCard.titleSelector) {
        const titleClass = firstCard.titleSelector.classes.split(' ')[0];
        console.log(chalk.gray(`  songTitle: 'span.${titleClass}',`));
      }

      if (firstCard.linkSelector) {
        console.log(chalk.gray(`  songLink: 'a',`));
      }

      if (firstCard.durationSelector) {
        console.log(chalk.gray(`  duration: 'span:has-text(/\\\\d+:\\\\d+/)',`));
      }

      console.log(chalk.white('}'));
    }
    console.log();

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

detailedInspect();
