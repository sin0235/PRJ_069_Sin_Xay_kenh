#!/usr/bin/env node

/**
 * Test Deduplication Logic
 * Tests that the scraper properly handles:
 * 1. Same song re-download (skip)
 * 2. Different song with same title (unique filename)
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import { CompleteSongDownloader } from '../src/downloaders/completeSongDownloader.js';
import { logger } from '../src/utils/logger.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Deduplication Logic Test                   '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testDeduplication() {
  let context = null;

  try {
    const profilePath = path.resolve('./.browser-profile');
    const outputPath = path.resolve('./output-test-dedup');

    // Clean test directory
    await fs.remove(outputPath);
    await fs.ensureDir(outputPath);

    console.log(chalk.yellow(`Profile: ${profilePath}`));
    console.log(chalk.yellow(`Test Output: ${outputPath}\n`));

    context = await chromium.launchPersistentContext(profilePath, {
      headless: false,
      viewport: { width: 1920, height: 1080 },
      acceptDownloads: true
    });

    const page = context.pages()[0] || await context.newPage();

    // Initialize downloader
    const downloader = new CompleteSongDownloader(page, outputPath);

    // Test song
    const testSong = {
      title: 'Test Song',
      url: 'https://www.flowmusic.app/song/c46dc45a-eeae-488c-824f-58a7aed5a96e',
      id: 'c46dc45a-eeae-488c-824f-58a7aed5a96e'
    };

    // Test 1: Download song first time
    console.log(chalk.yellow('Test 1: First download (should succeed)'));
    const result1 = await downloader.downloadSong(testSong);

    if (result1.success && !result1.skipped) {
      console.log(chalk.green('✓ Test 1 PASSED: Song downloaded successfully\n'));
    } else {
      console.log(chalk.red('✗ Test 1 FAILED: Should have downloaded\n'));
    }

    // List files
    const files1 = await fs.readdir(outputPath);
    console.log(chalk.gray(`Files after Test 1: ${files1.length} files`));
    files1.filter(f => f.includes('Test')).forEach(f => console.log(chalk.gray(`  - ${f}`)));
    console.log();

    // Test 2: Download same song again (should skip)
    console.log(chalk.yellow('Test 2: Re-download same song (should skip)'));
    const result2 = await downloader.downloadSong(testSong);

    if (result2.success && result2.skipped) {
      console.log(chalk.green('✓ Test 2 PASSED: Song skipped (already exists)\n'));
    } else {
      console.log(chalk.red('✗ Test 2 FAILED: Should have skipped\n'));
    }

    // Files should be the same
    const files2 = await fs.readdir(outputPath);
    console.log(chalk.gray(`Files after Test 2: ${files2.length} files (should be same as Test 1)`));
    console.log();

    // Test 3: Different song with same title (should add unique suffix)
    console.log(chalk.yellow('Test 3: Different song with same title (should use unique filename)'));
    const differentSong = {
      ...testSong,
      id: 'different-id-12345678', // Different ID, same title
      url: 'https://www.flowmusic.app/song/different-id-12345678'
    };

    const result3 = await downloader.downloadSong(differentSong);

    if (result3.success && !result3.skipped) {
      console.log(chalk.green('✓ Test 3 PASSED: Different song downloaded with unique filename\n'));
    } else {
      console.log(chalk.red('✗ Test 3 FAILED: Should have downloaded with unique name\n'));
    }

    // Should have files with unique suffix
    const files3 = await fs.readdir(outputPath);
    console.log(chalk.gray(`Files after Test 3: ${files3.length} files`));
    files3.filter(f => f.includes('Test')).forEach(f => console.log(chalk.gray(`  - ${f}`)));
    console.log();

    // Check for unique suffix
    const hasUniqueSuffix = files3.some(f => f.includes('different'));
    if (hasUniqueSuffix) {
      console.log(chalk.green('✓ Unique suffix added correctly\n'));
    } else {
      console.log(chalk.red('✗ No unique suffix found\n'));
    }

    // Summary
    console.log(chalk.green('═══════════════════════════════════════════════════'));
    console.log(chalk.green.bold('✓ ALL DEDUPLICATION TESTS COMPLETE'));
    console.log(chalk.green('═══════════════════════════════════════════════════\n'));

    console.log(chalk.white('Test Results:'));
    console.log(chalk.gray(`  Test 1 (First download): ${result1.success && !result1.skipped ? '✓ PASS' : '✗ FAIL'}`));
    console.log(chalk.gray(`  Test 2 (Skip duplicate): ${result2.success && result2.skipped ? '✓ PASS' : '✗ FAIL'}`));
    console.log(chalk.gray(`  Test 3 (Unique filename): ${result3.success && !result3.skipped ? '✓ PASS' : '✗ FAIL'}`));
    console.log(chalk.gray(`  Unique suffix check: ${hasUniqueSuffix ? '✓ PASS' : '✗ FAIL'}`));
    console.log();

    console.log(chalk.yellow('Browser will close in 5 seconds...'));
    await page.waitForTimeout(5000);

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

testDeduplication();
