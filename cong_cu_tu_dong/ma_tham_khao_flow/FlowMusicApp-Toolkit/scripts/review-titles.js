#!/usr/bin/env node

/**
 * Interactive Title Review
 * Analyzes downloaded songs and suggests better titles based on lyrics and mood
 */

import chalk from 'chalk';
import fs from 'fs-extra';
import path from 'path';
import { findPotentialHooks, cleanTitle } from '../src/utils/titleEnhancer.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Interactive Title Review                    '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

async function reviewTitles() {
  const outputDir = path.resolve('./output');

  // Get all JSON files
  const files = await fs.readdir(outputDir);
  const jsonFiles = files.filter(f => f.endsWith('.json'));

  if (jsonFiles.length === 0) {
    console.log(chalk.red('No songs found in output directory.'));
    console.log(chalk.gray('Run a download first, then use this tool to review titles.\n'));
    return;
  }

  console.log(chalk.white(`Found ${jsonFiles.length} songs to review.\n`));

  // Review each song
  for (let i = 0; i < Math.min(5, jsonFiles.length); i++) {
    const jsonFile = jsonFiles[i];
    const metadata = await fs.readJson(path.join(outputDir, jsonFile));

    console.log(chalk.cyan(`\n${'═'.repeat(55)}`));
    console.log(chalk.cyan.bold(`Song ${i + 1}: ${metadata.originalTitle || metadata.title}`));
    console.log(chalk.cyan(`${'═'.repeat(55)}\n`));

    console.log(chalk.yellow('Current Title:'));
    console.log(chalk.white(`  ${metadata.title}\n`));

    if (metadata.originalTitle && metadata.originalTitle !== metadata.title) {
      console.log(chalk.gray('Original from FlowMusic:'));
      console.log(chalk.gray(`  ${metadata.originalTitle}\n`));
    }

    console.log(chalk.yellow('Metadata:'));
    console.log(chalk.gray(`  Key: ${metadata.key || 'Unknown'} | BPM: ${metadata.bpm || 'Unknown'}`));
    console.log(chalk.gray(`  Model: ${metadata.model || 'Unknown'}`));
    console.log(chalk.gray(`  Description: ${metadata.description?.substring(0, 100)}...\n`));

    console.log(chalk.yellow('Lyrics Preview:'));
    const lyricsPreview = metadata.lyrics?.split('\n').slice(0, 8).join('\n') || 'No lyrics';
    console.log(chalk.gray(lyricsPreview));
    if (metadata.lyrics && metadata.lyrics.split('\n').length > 8) {
      console.log(chalk.gray('  ...'));
    }
    console.log();

    // Find potential hooks
    const hooks = findPotentialHooks(metadata.lyrics);

    if (hooks.length > 0) {
      console.log(chalk.yellow('Potential Hooks/Memorable Lines:'));
      hooks.forEach((hook, idx) => {
        const typeLabel = {
          'repeated': '🔁 Chorus',
          'opening': '▶️  Opening',
          'emphatic': '❗ Emphatic'
        }[hook.type] || '✨ Hook';

        console.log(chalk.white(`  ${idx + 1}. ${typeLabel}: "${hook.text}"`));
      });
      console.log();
    }

    console.log(chalk.green('═══════════════════════════════════════════════════'));
    console.log(chalk.green('Paste this into your AI assistant to get title suggestions:'));
    console.log(chalk.gray('─────────────────────────────────────────────────────'));
    console.log(chalk.white(`
Please analyze this song and suggest 2-3 better title options:

Title: ${metadata.title}
${metadata.originalTitle && metadata.originalTitle !== metadata.title ? `Original: ${metadata.originalTitle}` : ''}
Key: ${metadata.key || 'Unknown'} | BPM: ${metadata.bpm || 'Unknown'}
Mood: ${metadata.description?.substring(0, 150)}

Lyrics:
${metadata.lyrics || 'No lyrics'}

Based on the lyrics and mood, what would be a powerful, memorable title?
Consider:
- The strongest hook or repeated phrase
- The emotional core of the song
- Keep it concise but evocative
- If the current title is good, say so!
`));
    console.log(chalk.gray('─────────────────────────────────────────────────────\n'));
  }

  if (jsonFiles.length > 5) {
    console.log(chalk.gray(`\nShowing first 5 songs. Total: ${jsonFiles.length}\n`));
  }
}

reviewTitles().catch(err => {
  console.error(chalk.red('Error:'), err.message);
  process.exit(1);
});
