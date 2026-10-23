#!/usr/bin/env node

/**
 * Setup Script for FlowMusic Scraper
 * Helps users configure and verify installation
 */

import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import { execSync } from 'child_process';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('    FlowMusic Scraper Setup                        '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function setup() {
  const steps = [
    checkNodeVersion,
    createDirectories,
    setupEnvFile,
    verifyDependencies,
    installPlaywright,
    checkBrowserProfile,
    testImports
  ];

  for (const step of steps) {
    try {
      await step();
    } catch (error) {
      console.error(chalk.red(`✗ Setup failed: ${error.message}`));
      process.exit(1);
    }
  }

  console.log(chalk.green('\n✓ Setup completed successfully!'));
  console.log(chalk.cyan('\nNext steps:'));
  console.log('1. Run: npm run login');
  console.log('2. Run: npm run download -- --all');
  console.log('\nFor help, run: node cli.js --help\n');
}

async function checkNodeVersion() {
  console.log(chalk.yellow('Checking Node.js version...'));

  const nodeVersion = process.version;
  const major = parseInt(nodeVersion.split('.')[0].substring(1));

  if (major < 18) {
    throw new Error(`Node.js 18+ required. Current version: ${nodeVersion}`);
  }

  console.log(chalk.green(`✓ Node.js ${nodeVersion} detected\n`));
}

async function createDirectories() {
  console.log(chalk.yellow('Creating directories...'));

  const dirs = ['output', 'logs', 'checkpoints', 'config'];

  for (const dir of dirs) {
    await fs.ensureDir(dir);
    console.log(chalk.gray(`  Created: ${dir}/`));
  }

  console.log(chalk.green('✓ Directories created\n'));
}

async function setupEnvFile() {
  console.log(chalk.yellow('Setting up environment file...'));

  const envPath = '.env';
  const envExamplePath = '.env.example';

  if (!await fs.pathExists(envPath) && await fs.pathExists(envExamplePath)) {
    await fs.copy(envExamplePath, envPath);
    console.log(chalk.green('✓ Created .env from .env.example'));
  } else if (await fs.pathExists(envPath)) {
    console.log(chalk.gray('  .env already exists'));
  } else {
    // Create basic .env
    const envContent = `# FlowMusic Scraper Configuration
LOG_LEVEL=info
MAX_CONCURRENT_DOWNLOADS=2
MAX_RETRIES=3
CHECKPOINT_INTERVAL=10
`;
    await fs.writeFile(envPath, envContent);
    console.log(chalk.green('✓ Created default .env file'));
  }

  console.log();
}

async function verifyDependencies() {
  console.log(chalk.yellow('Verifying dependencies...'));

  try {
    execSync('npm list --depth=0', { stdio: 'ignore' });
    console.log(chalk.green('✓ All dependencies installed\n'));
  } catch (error) {
    console.log(chalk.yellow('  Some dependencies missing, installing...'));
    execSync('npm install', { stdio: 'inherit' });
    console.log(chalk.green('✓ Dependencies installed\n'));
  }
}

async function installPlaywright() {
  console.log(chalk.yellow('Checking Playwright browsers...'));

  try {
    // Check if Playwright browsers are installed
    const playwrightPath = path.join(process.env.HOME || process.env.USERPROFILE, '.cache', 'ms-playwright');

    if (!await fs.pathExists(playwrightPath)) {
      console.log(chalk.yellow('  Installing Playwright browsers...'));
      execSync('npx playwright install chromium', { stdio: 'inherit' });
    }

    console.log(chalk.green('✓ Playwright browsers ready\n'));
  } catch (error) {
    console.warn(chalk.yellow('⚠ Could not verify Playwright browsers'));
    console.log(chalk.gray('  Run manually: npx playwright install chromium\n'));
  }
}

async function checkBrowserProfile() {
  console.log(chalk.yellow('Checking browser profiles...'));

  const profiles = [];

  // Check common browser profile locations
  const profilePaths = {
    'Chrome (Windows)': path.join(process.env.LOCALAPPDATA || '', 'Google', 'Chrome', 'User Data'),
    'Chrome (Mac)': path.join(process.env.HOME || '', 'Library', 'Application Support', 'Google', 'Chrome'),
    'Chrome (Linux)': path.join(process.env.HOME || '', '.config', 'google-chrome'),
    'Edge (Windows)': path.join(process.env.LOCALAPPDATA || '', 'Microsoft', 'Edge', 'User Data'),
  };

  for (const [name, profilePath] of Object.entries(profilePaths)) {
    if (await fs.pathExists(profilePath)) {
      profiles.push({ name, path: profilePath });
    }
  }

  if (profiles.length > 0) {
    console.log(chalk.green('✓ Browser profiles found:'));
    profiles.forEach(p => console.log(chalk.gray(`  - ${p.name}: ${p.path}`)));
  } else {
    console.log(chalk.yellow('⚠ No browser profiles found'));
    console.log(chalk.gray('  The scraper will prompt for manual login'));
  }

  console.log();
}

async function testImports() {
  console.log(chalk.yellow('Testing module imports...'));

  try {
    // Test critical imports
    await import('../src/browser/authenticator.js');
    await import('../src/browser/scraper.js');
    await import('../src/utils/logger.js');

    console.log(chalk.green('✓ All modules load correctly\n'));
  } catch (error) {
    throw new Error(`Module import failed: ${error.message}`);
  }
}

// Run setup
setup().catch(error => {
  console.error(chalk.red('\n✗ Setup error:'), error);
  process.exit(1);
});
