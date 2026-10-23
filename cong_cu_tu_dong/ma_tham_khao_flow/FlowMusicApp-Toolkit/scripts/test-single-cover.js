#!/usr/bin/env node

/**
 * Test Single Cover Image
 * Debug cover image loading for a specific song
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import { CompleteSongDownloader } from '../src/downloaders/completeSongDownloader.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Test Single Cover Image Debug                '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testSingleCover() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    const outputDir = path.resolve('./output-test-single');

    // Clear test directory
    await fs.remove(outputDir);
    await fs.ensureDir(outputDir);

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 }
    });

    const page = context.pages()[0] || await context.newPage();

    // Test with this specific song
    const song = {
      id: 'c9f13ca5-e6be-4495-bede-b346949c5278',
      title: 'Inner Waters',
      url: 'https://www.flowmusic.app/song/c9f13ca5-e6be-4495-bede-b346949c5278'
    };

    console.log(chalk.yellow(`Testing song: ${song.title}`));
    console.log(chalk.gray(`ID: ${song.id}`));
    console.log(chalk.gray(`URL: ${song.url}\n`));

    const downloader = new CompleteSongDownloader(page, outputDir);
    const result = await downloader.downloadSong(song, { format: 'mp3' });

    if (result.success) {
      console.log(chalk.green('\n✓ Download successful!'));

      const metadata = await fs.readJson(result.files.metadata);
      console.log(chalk.white('\nCover URL from metadata:'));
      console.log(chalk.gray(metadata.coverUrl));

      console.log(chalk.white('\nExpected pattern:'));
      console.log(chalk.gray(`Should contain: ${song.id} or ${song.id.substring(0, 8)}`));

      if (metadata.coverUrl.includes(song.id) || metadata.coverUrl.includes(song.id.substring(0, 8))) {
        console.log(chalk.green('\n✓ Cover URL matches song ID!'));
      } else {
        console.log(chalk.red('\n✗ Cover URL does NOT match song ID!'));
        console.log(chalk.red('This means we extracted the wrong cover image.'));
      }
    } else {
      console.log(chalk.red(`\n✗ Download failed: ${result.error}`));
    }

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    process.exit(1);
  } finally {
    if (context) {
      await context.close();
    }
  }
}

testSingleCover();
