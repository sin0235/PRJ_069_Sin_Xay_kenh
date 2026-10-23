#!/usr/bin/env node

/**
 * AI Title Review - Interactive Mode
 * Your AI assistant reviews songs and provides title decisions
 */

import chalk from 'chalk';
import fs from 'fs-extra';
import path from 'path';
import { prepareSongForReview } from '../src/utils/aiTitleReviewer.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     AI Title Review - Decision Mode              '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function reviewSongs() {
  const outputDir = path.resolve('./output');

  // Get all JSON files
  const files = await fs.readdir(outputDir);
  const jsonFiles = files.filter(f => f.endsWith('.json') && !f.includes('checkpoint'));

  if (jsonFiles.length === 0) {
    console.log(chalk.red('No songs found in output directory.'));
    return;
  }

  console.log(chalk.white(`Found ${jsonFiles.length} songs for AI review.\n`));
  console.log(chalk.yellow('Your AI assistant will now review each song and provide title decisions.\n'));
  console.log(chalk.gray('─'.repeat(55)));

  // Prepare all songs for review
  const songsForReview = [];

  for (const jsonFile of jsonFiles.slice(0, 10)) { // Review first 10
    const metadata = await fs.readJson(path.join(outputDir, jsonFile));
    const analysis = prepareSongForReview(metadata);

    songsForReview.push({
      filename: jsonFile,
      metadata,
      analysis
    });
  }

  // Output for AI review
  console.log(chalk.cyan('\n📋 SONGS FOR AI REVIEW:\n'));

  songsForReview.forEach((song, i) => {
    console.log(chalk.cyan(`\n${'═'.repeat(55)}`));
    console.log(chalk.cyan.bold(`Song ${i + 1}: ${song.analysis.cleanedTitle}`));
    console.log(chalk.cyan(`${'═'.repeat(55)}\n`));

    console.log(chalk.yellow('Current Title:'));
    console.log(chalk.white(`  "${song.analysis.cleanedTitle}"\n`));

    console.log(chalk.yellow('Metadata:'));
    console.log(chalk.gray(`  Key: ${song.metadata.key || 'Unknown'} | BPM: ${song.metadata.bpm || 'Unknown'}`));
    console.log(chalk.gray(`  Mood: ${song.metadata.description?.substring(0, 120)}...\n`));

    console.log(chalk.yellow('Lyrics:'));
    const lyricsPreview = song.metadata.lyrics?.split('\n').slice(0, 12).join('\n') || 'No lyrics';
    console.log(chalk.gray(lyricsPreview));
    if (song.metadata.lyrics && song.metadata.lyrics.split('\n').length > 12) {
      console.log(chalk.gray('  [...more lyrics...]'));
    }

    if (song.analysis.potentialHooks.length > 0) {
      console.log(chalk.yellow('\nIdentified Hooks:'));
      song.analysis.potentialHooks.forEach((hook, idx) => {
        const icon = hook.type === 'repeated' ? '🔁 [CHORUS]' :
                     hook.type === 'opening' ? '▶️  [OPENING]' :
                     '❗ [EMPHATIC]';
        console.log(chalk.white(`  ${icon} "${hook.text}"`));
      });
    }

    console.log(chalk.gray('\n─'.repeat(55)));
  });

  console.log(chalk.green('\n\n✨ AI TASK:\n'));
  console.log(chalk.white('Review each song above and respond with your title decisions in this format:\n'));
  console.log(chalk.gray('Song 1: [Your chosen title]'));
  console.log(chalk.gray('Song 2: [Your chosen title]'));
  console.log(chalk.gray('Song 3: [Your chosen title]'));
  console.log(chalk.gray('...etc\n'));

  console.log(chalk.white('For each song, decide:'));
  console.log(chalk.gray('  • Is the current title good? Keep it'));
  console.log(chalk.gray('  • Found a powerful hook? Use that instead'));
  console.log(chalk.gray('  • Need something more evocative? Create a better title\n'));

  console.log(chalk.yellow('Guidelines:'));
  console.log(chalk.gray('  • Keep titles concise (2-5 words preferred)'));
  console.log(chalk.gray('  • Focus on the emotional core or main hook'));
  console.log(chalk.gray('  • Make it memorable and evocative'));
  console.log(chalk.gray('  • No need for key/BPM in the title\n'));

  console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

  // Save the review data for processing
  await fs.writeJson(path.join(outputDir, '_ai-review-pending.json'), {
    songs: songsForReview.map(s => ({
      filename: s.filename,
      currentTitle: s.analysis.cleanedTitle,
      originalTitle: s.analysis.originalTitle
    })),
    createdAt: new Date().toISOString()
  }, { spaces: 2 });

  console.log(chalk.green('✓ Review data saved. After your AI assistant provides titles, run:'));
  console.log(chalk.white('  node scripts/apply-ai-titles.js\n'));
}

reviewSongs().catch(err => {
  console.error(chalk.red('Error:'), err.message);
  process.exit(1);
});
