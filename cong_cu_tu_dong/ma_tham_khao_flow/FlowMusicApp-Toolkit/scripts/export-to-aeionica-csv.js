#!/usr/bin/env node

/**
 * Export to Aeionica CSV Format
 * Exports all track metadata to Aeionica-compatible CSV for ZIP import
 */

import chalk from 'chalk';
import path from 'path';
import fs from 'fs-extra';
import { createObjectCsvWriter } from 'csv-writer';
import scraperConfig from '../config/scraper.config.js';

async function exportToAeionicaCSV() {
  try {
    const outputDir = path.resolve('./output');
    const csvPath = path.join(outputDir, 'aeionica-tracks.csv');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Export to Aeionica CSV Format                 '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.white(`Source directory: ${outputDir}`));
    console.log(chalk.white(`Output CSV: ${csvPath}\n`));

    // Get all JSON files
    const files = await fs.readdir(outputDir);
    const jsonFiles = files.filter(f => f.endsWith('.json'));

    console.log(chalk.yellow(`Found ${jsonFiles.length} tracks to export\n`));

    if (jsonFiles.length === 0) {
      console.log(chalk.red('No JSON metadata files found!'));
      process.exit(1);
    }

    // Define CSV structure matching Aeionica ZIP import format
    const csvWriter = createObjectCsvWriter({
      path: csvPath,
      header: [
        // Required fields
        { id: 'title', title: 'title' },
        { id: 'artist', title: 'artist' },
        { id: 'audio_file', title: 'audio_file' },

        // Basic information
        { id: 'album', title: 'album' },
        { id: 'track_number', title: 'track_number' },

        // Musical properties
        { id: 'genre', title: 'genre' },
        { id: 'bpm', title: 'bpm' },
        { id: 'key', title: 'key' },
        { id: 'mood', title: 'mood' },

        // Content
        { id: 'duration', title: 'duration' },
        { id: 'lyrics', title: 'lyrics' },
        { id: 'description', title: 'description' },
        { id: 'tags', title: 'tags' },

        // Media files
        { id: 'image_file', title: 'image_file' },

        // Dates
        { id: 'release_date', title: 'release_date' },

        // Content flags
        { id: 'explicit', title: 'explicit' },
        { id: 'instrumental', title: 'instrumental' },

        // Pricing (optional - can be left empty)
        { id: 'streaming_price', title: 'streaming_price' },
        { id: 'download_price', title: 'download_price' }
      ]
    });

    // Load all track data
    const tracks = [];
    let trackNumber = 1;

    for (const jsonFile of jsonFiles) {
      try {
        const jsonPath = path.join(outputDir, jsonFile);
        const metadata = await fs.readJson(jsonPath);

        // Extract year from downloadedAt for release_date
        let releaseDate = '';
        if (metadata.downloadedAt) {
          const date = new Date(metadata.downloadedAt);
          releaseDate = date.toISOString().split('T')[0]; // YYYY-MM-DD
        }

        // Clean lyrics for CSV (escape newlines)
        const cleanLyrics = metadata.lyrics ? metadata.lyrics.replace(/\n/g, '\\n') : '';

        // Create tags from available metadata
        const tagsList = [];
        if (metadata.model) tagsList.push(metadata.model);
        if (metadata.key) tagsList.push(metadata.key.replace(' ', '-').toLowerCase());
        if (metadata.bpm) tagsList.push(`${metadata.bpm}bpm`);
        tagsList.push('ai-generated', 'flowmusic');
        const tags = tagsList.join(',');

        // Determine mood from description (simple heuristic)
        let mood = '';
        if (metadata.description) {
          const desc = metadata.description.toLowerCase();
          if (desc.includes('energetic') || desc.includes('upbeat')) mood = 'energetic';
          else if (desc.includes('calm') || desc.includes('peaceful') || desc.includes('ambient')) mood = 'calm';
          else if (desc.includes('dark') || desc.includes('intense')) mood = 'intense';
          else if (desc.includes('melancholic') || desc.includes('sad')) mood = 'melancholic';
          else if (desc.includes('happy') || desc.includes('joyful')) mood = 'happy';
          else mood = 'atmospheric';
        }

        tracks.push({
          // Required
          title: metadata.title || metadata.originalTitle || jsonFile.replace('.json', ''),
          artist: metadata.artist || metadata.author || scraperConfig.metadata.defaultArtist,
          audio_file: metadata.files?.audio || '',

          // Basic info
          album: metadata.album || scraperConfig.metadata.defaultAlbum,
          track_number: trackNumber++,

          // Musical properties
          genre: 'AI-Generated',
          bpm: metadata.bpm || '',
          key: metadata.key || '',
          mood: mood,

          // Content
          duration: metadata.duration || '',
          lyrics: cleanLyrics,
          description: metadata.description || '',
          tags: tags,

          // Media
          image_file: metadata.files?.cover || '',

          // Dates
          release_date: releaseDate,

          // Flags
          explicit: 'false',
          instrumental: metadata.lyrics ? 'false' : 'true',

          // Pricing (leave empty for now)
          streaming_price: '',
          download_price: ''
        });
      } catch (error) {
        console.log(chalk.red(`  ✗ Error reading ${jsonFile}: ${error.message}`));
      }
    }

    // Write CSV
    await csvWriter.writeRecords(tracks);

    console.log(chalk.green(`✓ Exported ${tracks.length} tracks to Aeionica CSV format`));
    console.log(chalk.white(`\nCSV file: ${csvPath}\n`));

    // Display sample of first track
    if (tracks.length > 0) {
      console.log(chalk.cyan('Sample track (first entry):'));
      console.log(chalk.gray('─'.repeat(50)));
      console.log(chalk.white(`  Title:      ${tracks[0].title}`));
      console.log(chalk.white(`  Artist:     ${tracks[0].artist}`));
      console.log(chalk.white(`  Album:      ${tracks[0].album}`));
      console.log(chalk.white(`  Track #:    ${tracks[0].track_number}`));
      console.log(chalk.white(`  BPM:        ${tracks[0].bpm}`));
      console.log(chalk.white(`  Key:        ${tracks[0].key}`));
      console.log(chalk.white(`  Mood:       ${tracks[0].mood}`));
      console.log(chalk.white(`  Tags:       ${tracks[0].tags}`));
      console.log(chalk.white(`  Audio:      ${tracks[0].audio_file}`));
      console.log(chalk.white(`  Image:      ${tracks[0].image_file}`));
      console.log(chalk.gray('─'.repeat(50)));
      console.log();
    }

    console.log(chalk.yellow('Next steps:'));
    console.log(chalk.white('  1. Create a ZIP file containing:'));
    console.log(chalk.white(`     - aeionica-tracks.csv`));
    console.log(chalk.white(`     - All MP3 files`));
    console.log(chalk.white(`     - All cover image files`));
    console.log(chalk.white('  2. Upload the ZIP to Aeionica import'));
    console.log();

    console.log(chalk.green('✓ CSV export complete!\n'));
    process.exit(0);

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

exportToAeionicaCSV();
