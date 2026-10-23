#!/usr/bin/env node
/**
 * One-off recovery script for songs that fail with ERR_ABORTED on navigation.
 * These songs may serve the audio file directly from the song URL.
 *
 * Usage: node scripts/recover-song.js <song-url> [output-dir] [profile-path]
 */

import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';

const songUrl = process.argv[2];
const outputDir = path.resolve(process.argv[3] || './output');
const profilePath = path.resolve(process.argv[4] || './.browser-profile');

if (!songUrl) {
  console.error('Usage: node scripts/recover-song.js <song-url> [output-dir] [profile-path]');
  process.exit(1);
}

console.log('Song URL:', songUrl);
console.log('Output:', outputDir);
console.log('Profile:', profilePath);
console.log();

const context = await chromium.launchPersistentContext(profilePath, {
  headless: false,
  viewport: { width: 1920, height: 1080 },
  acceptDownloads: true
});

const page = context.pages()[0] || await context.newPage();

// Set up download listener BEFORE navigating
let capturedDownload = null;
page.on('download', d => {
  console.log('Download triggered:', d.suggestedFilename());
  capturedDownload = d;
});

console.log('Navigating to song page...');
try {
  await page.goto(songUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  console.log('Page loaded normally — checking for page title...');
  const title = await page.title();
  console.log('Page title:', title);
  // Wait to see if the page triggers a download
  await page.waitForTimeout(5000);
} catch (err) {
  if (err.message.includes('ERR_ABORTED')) {
    console.log('Navigation aborted (expected if page triggers direct download) — waiting for download...');
    await page.waitForTimeout(5000);
  } else {
    console.error('Navigation error:', err.message);
  }
}

if (capturedDownload) {
  await fs.ensureDir(outputDir);
  const filename = capturedDownload.suggestedFilename() || 'recovered-song.mp3';
  const destPath = path.join(outputDir, filename);
  await capturedDownload.saveAs(destPath);
  console.log('✓ Saved download to:', destPath);
} else {
  console.log('No download captured. Song may be unavailable.');
  console.log('Check the browser window for clues.');
  // Wait a bit so the user can see the page
  await page.waitForTimeout(10000);
}

await context.close();
