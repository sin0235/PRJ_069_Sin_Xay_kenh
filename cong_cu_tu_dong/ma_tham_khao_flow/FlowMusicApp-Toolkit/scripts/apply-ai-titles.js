#!/usr/bin/env node

/**
 * Apply AI Title Decisions
 * Applies AI title choices to the downloaded songs
 */

import chalk from 'chalk';
import fs from 'fs-extra';
import path from 'path';
import sanitize from 'sanitize-filename';
import readline from 'readline';

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

function question(prompt) {
  return new Promise(resolve => rl.question(prompt, resolve));
}

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Apply AI Title Decisions                    '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function applyTitles() {
  const outputDir = path.resolve('./output');
  const reviewFile = path.join(outputDir, '_ai-review-pending.json');

  // Check if review data exists
  if (!await fs.pathExists(reviewFile)) {
    console.log(chalk.red('No pending review found.'));
    console.log(chalk.gray('Run: node scripts/ai-title-review.js first\n'));
    process.exit(1);
  }

  const reviewData = await fs.readJson(reviewFile);

  console.log(chalk.white(`Found ${reviewData.songs.length} songs pending title updates.\n`));
  console.log(chalk.yellow('Enter the AI-provided title decisions:\n'));

  const titleDecisions = [];

  for (let i = 0; i < reviewData.songs.length; i++) {
    const song = reviewData.songs[i];
    console.log(chalk.gray(`${i + 1}. Current: "${song.currentTitle}"`));

    const newTitle = await question(chalk.white(`   New title: `));

    if (newTitle.trim()) {
      titleDecisions.push({
        ...song,
        newTitle: newTitle.trim()
      });
    } else {
      // Keep current title
      titleDecisions.push({
        ...song,
        newTitle: song.currentTitle
      });
    }
  }

  console.log(chalk.cyan('\n\nApplying title changes...\n'));

  // Apply each title change
  for (const decision of titleDecisions) {
    try {
      const oldFilename = decision.filename;
      const oldPath = path.join(outputDir, oldFilename);
      const oldBaseName = oldFilename.replace('.json', '');

      // Sanitize new title
      const sanitizedTitle = sanitize(decision.newTitle, { replacement: '-' });
      const newBaseName = sanitizedTitle;

      if (oldBaseName === newBaseName) {
        console.log(chalk.gray(`⊘ Unchanged: "${decision.newTitle}"`));
        continue;
      }

      // Read metadata
      const metadata = await fs.readJson(oldPath);

      // Find associated files
      const files = await fs.readdir(outputDir);
      const associatedFiles = files.filter(f =>
        f.startsWith(oldBaseName + '.') || f.startsWith(oldBaseName + '-')
      );

      // Rename all associated files
      for (const file of associatedFiles) {
        const ext = path.extname(file);
        const oldFilePath = path.join(outputDir, file);
        const newFilePath = path.join(outputDir, newBaseName + ext);

        await fs.rename(oldFilePath, newFilePath);
      }

      // Update metadata
      const newJsonPath = path.join(outputDir, `${newBaseName}.json`);
      await fs.writeJson(newJsonPath, {
        ...metadata,
        title: decision.newTitle,
        originalTitle: metadata.originalTitle || metadata.title,
        aiEnhanced: true,
        aiEnhancedAt: new Date().toISOString()
      }, { spaces: 2 });

      console.log(chalk.green(`✓ Renamed: "${decision.currentTitle}" → "${decision.newTitle}"`));

    } catch (error) {
      console.log(chalk.red(`✗ Failed: ${decision.filename} - ${error.message}`));
    }
  }

  // Clean up review file
  await fs.remove(reviewFile);

  console.log(chalk.green('\n✓ All title updates applied!'));
  console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

  rl.close();
}

applyTitles().catch(err => {
  console.error(chalk.red('Error:'), err.message);
  rl.close();
  process.exit(1);
});
