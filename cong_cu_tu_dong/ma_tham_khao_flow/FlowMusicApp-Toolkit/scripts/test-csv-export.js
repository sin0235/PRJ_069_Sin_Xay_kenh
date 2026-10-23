#!/usr/bin/env node

/**
 * Test CSV Export
 * Generates WordPress-compatible CSV from downloaded songs
 */

import chalk from 'chalk';
import path from 'path';
import fs from 'fs-extra';
import { CSVExporter } from '../src/exporters/csvExporter.js';
import { logger } from '../src/utils/logger.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     CSV Export Test                            '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function testCSVExport() {
  try {
    const outputPath = path.resolve('./output');

    console.log(chalk.yellow(`Output directory: ${outputPath}\n`));

    // Initialize exporter
    const exporter = new CSVExporter(outputPath);

    // Test 1: Standard WordPress export
    console.log(chalk.yellow('Generating WordPress CSV...\n'));

    const result = await exporter.exportToCSV();

    if (result) {
      console.log(chalk.green('═══════════════════════════════════════════════════'));
      console.log(chalk.green.bold('✓ CSV EXPORT SUCCESSFUL!'));
      console.log(chalk.green('═══════════════════════════════════════════════════\n'));

      console.log(chalk.white('Export Details:'));
      console.log(chalk.gray(`  File: ${result.path}`));
      console.log(chalk.gray(`  Songs: ${result.songCount}`));
      console.log(chalk.gray(`  Size: ${(result.size / 1024).toFixed(2)} KB\n`));

      // Show preview of CSV
      console.log(chalk.white('CSV Preview (first 500 chars):'));
      const csvContent = await fs.readFile(result.path, 'utf8');
      console.log(chalk.gray(csvContent.substring(0, 500) + '...\n'));

      // Test 2: Custom field mapping example
      console.log(chalk.yellow('Generating custom CSV with selected fields...\n'));

      const customMapping = {
        'Track Name': 'title',
        'Artist Name': 'author',
        'Tempo (BPM)': 'bpm',
        'Musical Key': 'key',
        'AI Model': 'model',
        'Audio File': 'audioFilePath',
        'Album Art': 'coverFilePath',
        'Original URL': 'url'
      };

      const customResult = await exporter.exportWithCustomFields(
        customMapping,
        path.join(outputPath, 'flowmusic-custom.csv')
      );

      if (customResult) {
        console.log(chalk.green(`✓ Custom CSV exported: ${customResult.path}`));
        console.log(chalk.gray(`  Songs: ${customResult.songCount}\n`));
      }

      console.log(chalk.white('Import Instructions:'));
      console.log(chalk.gray('1. Upload this CSV to your WordPress site'));
      console.log(chalk.gray('2. Use a CSV import plugin (e.g., WP All Import)'));
      console.log(chalk.gray('3. Map CSV columns to your custom post type fields'));
      console.log(chalk.gray('4. Import audio files and cover images to WordPress Media Library'));
      console.log(chalk.gray('5. Update file paths in WordPress to match your media URLs\n'));

    } else {
      console.log(chalk.yellow('No songs found to export'));
    }

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(chalk.gray(error.stack));
    process.exit(1);
  }
}

testCSVExport();
