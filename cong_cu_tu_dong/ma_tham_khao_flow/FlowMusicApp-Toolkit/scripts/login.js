#!/usr/bin/env node

/**
 * Login Helper Script
 * Opens a browser for manual login to FlowMusic
 */

import chalk from 'chalk';
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('        FlowMusic Login Helper                    '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function loginHelper() {
  let browser = null;
  let context = null;

  try {
    console.log(chalk.yellow('Starting browser for login...'));
    console.log(chalk.gray('This will open a browser window where you can log in.\n'));

    // Create a profile directory in the project
    const profileDir = path.resolve('./.browser-profile');
    await fs.ensureDir(profileDir);

    console.log(chalk.gray(`Using profile: ${profileDir}\n`));

    // Launch browser with persistent context
    context = await chromium.launchPersistentContext(profileDir, {
      headless: false,
      viewport: { width: 1920, height: 1080 },
      acceptDownloads: true,
      args: [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-setuid-sandbox'
      ]
    });

    const page = context.pages()[0] || await context.newPage();

    // Navigate to FlowMusic
    console.log(chalk.yellow('Navigating to FlowMusic...'));
    await page.goto('https://www.flowmusic.app', {
      waitUntil: 'networkidle',
      timeout: 60000
    });

    console.log(chalk.green('\n✓ Browser opened!'));
    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.white('Please log in to FlowMusic in the browser window.'));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));
    console.log(chalk.yellow('Instructions:'));
    console.log('1. Complete the login process in the browser');
    console.log('2. Navigate to your songs page to verify login');
    console.log('3. Press Ctrl+C in this terminal when done\n');

    console.log(chalk.gray('The browser session will be saved automatically.'));
    console.log(chalk.gray(`Profile location: ${profileDir}\n`));

    // Wait for user avatar or some indication of login
    console.log(chalk.yellow('Waiting for login...'));

    try {
      // Wait for potential login indicators
      await Promise.race([
        page.waitForSelector('[data-testid="user-avatar"], .user-avatar, img[alt*="Profile"]', { timeout: 300000 }),
        page.waitForURL('**/songs', { timeout: 300000 }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 300000))
      ]).then(() => {
        console.log(chalk.green('\n✓ Login detected!'));
      }).catch(() => {
        console.log(chalk.yellow('\n⏱ Timeout - but that\'s okay!'));
        console.log(chalk.gray('Your session should still be saved if you logged in.'));
      });
    } catch (error) {
      // Ignore timeout - user might be manually navigating
      console.log(chalk.gray('\nWaiting for you to finish...'));
    }

    // Keep browser open
    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.green('✓ Browser is ready!'));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));
    console.log(chalk.white('When you\'re done logging in:'));
    console.log('1. Navigate to https://www.flowmusic.app/library/my-songs to verify login');
    console.log('2. Press Ctrl+C in this terminal to close the browser\n');

    console.log(chalk.yellow('To use this profile with the scraper:'));
    console.log(chalk.white(`node cli.js download --all --profile "${profileDir}"\n`));

    // Keep the script running
    await new Promise(() => {});

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);

    if (error.message.includes('DISPLAY')) {
      console.log(chalk.yellow('\n⚠ GUI not available in WSL2'));
      console.log(chalk.white('\nSolutions:'));
      console.log('1. Enable WSLg (Windows 11 with WSL 2.0+):');
      console.log(chalk.gray('   wsl --update'));
      console.log(chalk.gray('   wsl --shutdown'));
      console.log('2. Or use Windows Chrome browser:');
      console.log(chalk.gray('   node cli.js download --all --profile "C:\\Users\\YourName\\AppData\\Local\\Google\\Chrome\\User Data"'));
      console.log('3. Or install X server (VcXsrv, Xming)');
    }

    process.exit(1);
  } finally {
    // Cleanup is handled by Ctrl+C
  }
}

// Handle Ctrl+C gracefully
process.on('SIGINT', async () => {
  console.log(chalk.cyan('\n\n═══════════════════════════════════════════════════'));
  console.log(chalk.green('✓ Browser session saved!'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));
  console.log(chalk.white('You can now run the scraper with:'));
  console.log(chalk.yellow('node cli.js download --all --profile ./.browser-profile\n'));
  process.exit(0);
});

// Run login helper
loginHelper();
