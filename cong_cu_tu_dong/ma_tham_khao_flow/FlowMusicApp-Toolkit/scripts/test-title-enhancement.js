#!/usr/bin/env node

/**
 * Test Title Enhancement
 * Shows how titles are cleaned and made unique
 */

import chalk from 'chalk';
import { enhanceTitle, cleanTitle, findPotentialHooks, selectBestHook } from '../src/utils/titleEnhancer.js';

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.cyan.bold('     Title Enhancement Demo                      '));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

// Test cases
const testCases = [
  {
    title: 'Inner Waters — You Are Water Holding Shape, E Major, 70 bpm',
    lyrics: 'Before I had a name, I floated\nCurled inside a smaller sea\nThe first thing that I ever knew\nWas being held by what holds me',
    description: 'Intimate indie in E Major, 70 bpm: felted piano, soft strings',
    existing: []
  },
  {
    title: 'Ocean Dreams — Waves of Consciousness, G Major, 120 bpm',
    lyrics: 'Verse 1\nDrifting through the endless blue\nEvery wave brings thoughts of you\nFloating in this vast expanse\nLost within a tidal trance',
    description: 'Ambient electronic with ethereal pads and gentle percussion',
    existing: []
  },
  {
    title: 'Ocean Dreams — Waves of Consciousness, G Major, 90 bpm',
    lyrics: 'Verse 1\nDark waters call my name tonight\nPulling me beneath the light\nCold currents wrap around my soul\nDragging down into the hole',
    description: 'Dark ambient with haunting melodies and deep bass',
    existing: ['Ocean Dreams - Waves of Consciousness'] // This one already exists
  },
  {
    title: 'Morning Light — Rise and Shine, C Major, 140 bpm',
    lyrics: 'Intro\nSunrise breaking through the clouds\nNew day calling out loud',
    description: 'Uplifting pop with energetic drums and bright synths',
    existing: []
  },
  {
    title: 'Morning Light — Rise and Shine, C Major, 140 bpm',
    lyrics: 'Verse 1\nGolden rays paint the sky\nBirds take flight and soar up high',
    description: 'Peaceful acoustic with gentle guitar and warm tones',
    existing: ['Morning Light - Rise and Shine']
  }
];

console.log(chalk.white('Testing Title Cleaning:\n'));

testCases.forEach((test, i) => {
  console.log(chalk.cyan(`\nTest ${i + 1}:`));
  console.log(chalk.gray(`Original:  "${test.title}"`));

  const cleaned = cleanTitle(test.title);
  console.log(chalk.yellow(`Cleaned:   "${cleaned}"`));

  // Show hook analysis
  const hooks = findPotentialHooks(test.lyrics);
  if (hooks.length > 0) {
    console.log(chalk.gray(`\n  Found ${hooks.length} potential hooks:`));
    hooks.forEach((hook, idx) => {
      const icon = hook.type === 'repeated' ? '🔁' : hook.type === 'opening' ? '▶️ ' : '❗';
      console.log(chalk.gray(`    ${icon} "${hook.text}" (score: ${hook.score})`));
    });

    if (test.existing.length > 0) {
      const selected = selectBestHook(hooks, cleaned, test);
      console.log(chalk.gray(`  Selected: "${selected?.text}"`));
    }
  }

  const enhanced = enhanceTitle(test.title, {
    lyrics: test.lyrics,
    description: test.description
  }, test.existing);

  console.log(chalk.green(`\nEnhanced:  "${enhanced}"`));

  // Show what was decided
  if (enhanced !== cleaned) {
    const suffix = enhanced.replace(cleaned + ' - ', '');
    console.log(chalk.white(`  → Automatically added: "${suffix}"`));
  }

  if (test.existing.length > 0) {
    console.log(chalk.gray(`  (Avoiding collision with: ${test.existing.join(', ')})`));
  }
});

console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
console.log(chalk.white('\nKey Features:'));
console.log(chalk.gray('  ✓ Preserves subtitles, removes only key/BPM metadata'));
console.log(chalk.gray('  ✓ Finds potential hooks (repeated, opening, emphatic lines)'));
console.log(chalk.gray('  ✓ Automatically selects the best hook for variations'));
console.log(chalk.gray('  ✓ Filters hooks that overlap too much with existing title'));
console.log(chalk.gray('  ✓ Prefers chorus/repeated lines as most memorable'));
console.log(chalk.gray('  ✓ Falls back to mood descriptors or numbered versions'));
console.log(chalk.gray('  ✓ Makes the decision automatically - no user input needed'));
console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));
