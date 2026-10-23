#!/usr/bin/env node

/**
 * Retroactively Tag MP3 Files
 * Tags all MP3 files in the output directory with metadata from their JSON files
 */

import chalk from 'chalk';
import path from 'path';
import { MetadataTagger } from '../src/utils/metadataTagger.js';
import { logger } from '../src/utils/logger.js';

async function tagExistingMp3s() {
  try {
    const outputDir = path.resolve('./output');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Retroactive MP3 Metadata Tagging          '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.white(`Output directory: ${outputDir}\n`));
    console.log(chalk.yellow('Starting metadata tagging process...\n'));

    // Tag all MP3s in the output directory
    const results = await MetadataTagger.tagDirectory(outputDir);

    // Display results
    console.log(chalk.white('\n═══════════════════════════════════════════════════'));
    console.log(chalk.white('Tagging Results:\n'));
    console.log(chalk.green(`  ✓ Successfully tagged: ${results.success}`));
    console.log(chalk.red(`  ✗ Failed: ${results.failed}`));
    console.log(chalk.gray(`  ⊘ Skipped (no JSON): ${results.skipped}`));
    console.log(chalk.white(`  Total MP3 files: ${results.total}`));
    console.log(chalk.white('═══════════════════════════════════════════════════\n'));

    if (results.success > 0) {
      console.log(chalk.green('✓ MP3 metadata tagging complete!\n'));
    } else if (results.total === 0) {
      console.log(chalk.yellow('⚠ No MP3 files found in output directory.\n'));
    } else {
      console.log(chalk.yellow('⚠ Some files could not be tagged. Check logs for details.\n'));
    }

    process.exit(0);

  } catch (error) {
    console.error(chalk.red('\n✗ Error during tagging:'), error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

// Run the tagging process
tagExistingMp3s();
