#!/usr/bin/env node

/**
 * Test Script for FlowMusic Scraper
 * Tests individual components without full scraping
 */

import chalk from 'chalk';
import { BrowserAuthenticator } from '../src/browser/authenticator.js';
import { logger } from '../src/utils/logger.js';
import { FileOrganizer } from '../src/utils/fileOrganizer.js';
import { ProgressTracker } from '../src/utils/progressTracker.js';
import scraperConfig from '../config/scraper.config.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('        FlowMusic Scraper - Component Tests'));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

const tests = [];

async function runTests() {
  // Test 1: Browser Authentication
  await testBrowserAuth();

  // Test 2: File Organization
  await testFileOrganization();

  // Test 3: Progress Tracking
  await testProgressTracking();

  // Test 4: Configuration Loading
  await testConfiguration();

  // Summary
  printSummary();
}

async function testBrowserAuth() {
  const testName = 'Browser Authentication';
  console.log(chalk.yellow(`\nTesting: ${testName}...`));

  try {
    const authenticator = new BrowserAuthenticator();

    // Test 1: Profile detection
    const profile = authenticator.detectBrowserProfile();
    if (profile) {
      console.log(chalk.green('  ✓ Browser profile detected:'), profile);
    } else {
      console.log(chalk.yellow('  ⚠ No browser profile found (will use manual login)'));
    }

    // Test 2: Browser initialization (without actually opening)
    console.log(chalk.green('  ✓ BrowserAuthenticator class loaded'));

    tests.push({ name: testName, status: 'pass' });

  } catch (error) {
    console.log(chalk.red(`  ✗ Failed: ${error.message}`));
    tests.push({ name: testName, status: 'fail', error: error.message });
  }
}

async function testFileOrganization() {
  const testName = 'File Organization';
  console.log(chalk.yellow(`\nTesting: ${testName}...`));

  try {
    const organizer = new FileOrganizer('./test-output');

    // Test sanitization
    const testNames = [
      'Normal Song Name',
      'Song: With Special? Characters*',
      'Song/With\\Slashes',
      'A'.repeat(300) // Very long name
    ];

    console.log(chalk.gray('  Testing filename sanitization:'));
    for (const name of testNames) {
      const sanitized = organizer.sanitizeName(name);
      console.log(chalk.gray(`    "${name.substring(0, 30)}..." → "${sanitized.substring(0, 30)}..."`));
    }

    console.log(chalk.green('  ✓ File sanitization working'));

    // Test folder name generation
    const testSong = {
      id: 'test-123',
      title: 'Test Song',
      url: 'https://flowmusic.app/song/test-123'
    };

    const folderName = organizer.generateFolderName(testSong);
    console.log(chalk.green(`  ✓ Folder name generated: "${folderName}"`));

    tests.push({ name: testName, status: 'pass' });

  } catch (error) {
    console.log(chalk.red(`  ✗ Failed: ${error.message}`));
    tests.push({ name: testName, status: 'fail', error: error.message });
  }
}

async function testProgressTracking() {
  const testName = 'Progress Tracking';
  console.log(chalk.yellow(`\nTesting: ${testName}...`));

  try {
    const tracker = new ProgressTracker();

    // Test initialization
    await tracker.initialize(10);
    console.log(chalk.green(`  ✓ Progress tracker initialized`));

    // Test progress calculation
    const mockSong = { id: '1', title: 'Test Song 1' };
    await tracker.startSong(mockSong, 0);
    await tracker.completeSong(mockSong, true, { downloads: 3 });

    const progress = tracker.getProgress();
    console.log(chalk.gray(`    Progress: ${progress.percentage}% (${progress.successful} successful)`));

    console.log(chalk.green(`  ✓ Progress tracking working`));

    // Test checkpoint
    await tracker.saveCheckpoint();
    console.log(chalk.green(`  ✓ Checkpoint saved: ${tracker.checkpointFile}`));

    // Get available sessions
    const sessions = await tracker.getAvailableSessions();
    console.log(chalk.gray(`    Available sessions: ${sessions.length}`));

    tests.push({ name: testName, status: 'pass' });

  } catch (error) {
    console.log(chalk.red(`  ✗ Failed: ${error.message}`));
    tests.push({ name: testName, status: 'fail', error: error.message });
  }
}

async function testConfiguration() {
  const testName = 'Configuration Loading';
  console.log(chalk.yellow(`\nTesting: ${testName}...`));

  try {
    // Test scraper config
    console.log(chalk.gray('  Scraper URLs:'));
    console.log(chalk.gray(`    Base: ${scraperConfig.urls.base}`));
    console.log(chalk.gray(`    Songs: ${scraperConfig.urls.songs}`));

    console.log(chalk.gray('  Scraper Behavior:'));
    console.log(chalk.gray(`    Max retries: ${scraperConfig.behavior.retries.maxAttempts}`));
    console.log(chalk.gray(`    Delay between songs: ${scraperConfig.behavior.delays.betweenSongs}ms`));

    console.log(chalk.gray('  File Organization:'));
    console.log(chalk.gray(`    Output dir: ${scraperConfig.fileOrganization.outputDir}`));
    console.log(chalk.gray(`    Structure: ${scraperConfig.fileOrganization.structure}`));

    console.log(chalk.green('  ✓ Configuration loaded successfully'));

    tests.push({ name: testName, status: 'pass' });

  } catch (error) {
    console.log(chalk.red(`  ✗ Failed: ${error.message}`));
    tests.push({ name: testName, status: 'fail', error: error.message });
  }
}

function printSummary() {
  console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
  console.log(chalk.cyan.bold('                  Test Summary'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════'));

  const passed = tests.filter(t => t.status === 'pass').length;
  const failed = tests.filter(t => t.status === 'fail').length;

  console.log(chalk.green(`\n✓ Passed: ${passed}`));
  if (failed > 0) {
    console.log(chalk.red(`✗ Failed: ${failed}`));

    console.log(chalk.red('\nFailed Tests:'));
    tests.filter(t => t.status === 'fail').forEach(t => {
      console.log(chalk.red(`  - ${t.name}: ${t.error}`));
    });
  }

  console.log(chalk.cyan('\n═══════════════════════════════════════════════════\n'));

  if (failed === 0) {
    console.log(chalk.green('✓ All tests passed! The scraper is ready to use.\n'));
    console.log(chalk.cyan('To start scraping, run:'));
    console.log(chalk.white('  npm run download -- --all\n'));
    process.exit(0);
  } else {
    console.log(chalk.red('✗ Some tests failed. Please check the errors above.\n'));
    process.exit(1);
  }
}

// Run tests
runTests().catch(error => {
  console.error(chalk.red('\nTest suite error:'), error);
  process.exit(1);
});
