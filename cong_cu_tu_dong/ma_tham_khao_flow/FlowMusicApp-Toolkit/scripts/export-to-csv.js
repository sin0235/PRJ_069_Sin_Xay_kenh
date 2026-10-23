#!/usr/bin/env node

/**
 * Export Tracks to CSV
 * Exports all track metadata from JSON files to a CSV format compatible with WordPress plugins
 */

import chalk from 'chalk';
import path from 'path';
import fs from 'fs-extra';
import { createObjectCsvWriter } from 'csv-writer';

async function exportToCSV() {
  try {
    const outputDir = path.resolve('./output');
    const csvPath = path.join(outputDir, 'tracks.csv');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Export Tracks to CSV                        '));
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

    // Define CSV structure with all possible fields
    const csvWriter = createObjectCsvWriter({
      path: csvPath,
      header: [
        { id: 'title', title: 'Title' },
        { id: 'artist', title: 'Artist' },
        { id: 'album', title: 'Album' },
        { id: 'year', title: 'Year' },
        { id: 'bpm', title: 'BPM' },
        { id: 'key', title: 'Key' },
        { id: 'model', title: 'Model' },
        { id: 'duration', title: 'Duration' },
        { id: 'description', title: 'Description' },
        { id: 'lyrics', title: 'Lyrics' },
        { id: 'audioFile', title: 'Audio File' },
        { id: 'coverFile', title: 'Cover File' },
        { id: 'url', title: 'Original URL' },
        { id: 'songId', title: 'Song ID' },
        { id: 'downloadedAt', title: 'Downloaded At' }
      ]
    });

    // Load all track data
    const tracks = [];
    for (const jsonFile of jsonFiles) {
      try {
        const jsonPath = path.join(outputDir, jsonFile);
        const metadata = await fs.readJson(jsonPath);

        // Extract year from downloadedAt if not present
        let year = metadata.year;
        if (!year && metadata.downloadedAt) {
          year = new Date(metadata.downloadedAt).getFullYear();
        }

        // Clean lyrics (remove line breaks for CSV, or keep them as \n)
        const cleanLyrics = metadata.lyrics ? metadata.lyrics.replace(/\n/g, '\\n') : '';

        tracks.push({
          title: metadata.title || metadata.originalTitle || jsonFile.replace('.json', ''),
          artist: metadata.artist || metadata.author || 'Unknown',
          album: metadata.album || 'FlowMusic Library',
          year: year || new Date().getFullYear(),
          bpm: metadata.bpm || '',
          key: metadata.key || '',
          model: metadata.model || '',
          duration: metadata.duration || '',
          description: metadata.description || '',
          lyrics: cleanLyrics,
          audioFile: metadata.files?.audio || '',
          coverFile: metadata.files?.cover || '',
          url: metadata.url || '',
          songId: metadata.id || '',
          downloadedAt: metadata.downloadedAt || ''
        });
      } catch (error) {
        console.log(chalk.red(`  ✗ Error reading ${jsonFile}: ${error.message}`));
      }
    }

    // Write CSV
    await csvWriter.writeRecords(tracks);

    console.log(chalk.green(`✓ Exported ${tracks.length} tracks to CSV`));
    console.log(chalk.white(`\nCSV file: ${csvPath}\n`));

    // Display sample of first track
    if (tracks.length > 0) {
      console.log(chalk.cyan('Sample track (first entry):'));
      console.log(chalk.gray('─'.repeat(50)));
      console.log(chalk.white(`  Title:  ${tracks[0].title}`));
      console.log(chalk.white(`  Artist: ${tracks[0].artist}`));
      console.log(chalk.white(`  Album:  ${tracks[0].album}`));
      console.log(chalk.white(`  BPM:    ${tracks[0].bpm}`));
      console.log(chalk.white(`  Key:    ${tracks[0].key}`));
      console.log(chalk.gray('─'.repeat(50)));
      console.log();
    }

    console.log(chalk.green('✓ CSV export complete!\n'));
    process.exit(0);

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

exportToCSV();
