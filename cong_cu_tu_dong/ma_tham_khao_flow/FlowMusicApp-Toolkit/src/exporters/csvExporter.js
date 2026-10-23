/**
 * CSV Exporter
 * Generates CSV file from downloaded songs for WordPress import
 */

import path from 'path';
import fs from 'fs-extra';
import { parse } from 'json2csv';
import { logger } from '../utils/logger.js';

export class CSVExporter {
  constructor(outputDir = './output') {
    this.outputDir = outputDir;
  }

  toPosixPath(filePath) {
    return filePath ? filePath.split(path.sep).join('/') : filePath;
  }

  async collectMetadataFiles(dir, collected = []) {
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);

      if (entry.isDirectory()) {
        await this.collectMetadataFiles(fullPath, collected);
        continue;
      }

      const isMetadataJson = entry.name.endsWith('.json')
        && !entry.name.includes('checkpoint')
        && !entry.name.includes('report')
        && entry.name !== '_ai-review-pending.json';

      if (isMetadataJson) {
        collected.push(fullPath);
      }
    }

    return collected;
  }

  async findSiblingByExtensions(dir, baseName, extensions) {
    for (const ext of extensions) {
      const candidate = path.join(dir, `${baseName}${ext}`);
      if (await fs.pathExists(candidate)) {
        return candidate;
      }
    }

    return null;
  }

  /**
   * Scan output directory and collect all song metadata.
   * Supports both flat output and playlist subdirectories.
   */
  async collectSongsMetadata() {
    const songs = [];

    try {
      if (!await fs.pathExists(this.outputDir)) {
        logger.warn(`Output directory does not exist: ${this.outputDir}`);
        return songs;
      }

      const metadataFiles = await this.collectMetadataFiles(this.outputDir);

      for (const jsonPath of metadataFiles) {
        const jsonFile = path.basename(jsonPath);
        const songDir = path.dirname(jsonPath);
        const baseName = path.basename(jsonFile, '.json');

        // Read metadata
        const metadata = await fs.readJson(jsonPath);

        // Find matching audio and cover files with the same base name in the same directory.
        const audioFile = await this.findSiblingByExtensions(songDir, baseName, ['.mp3', '.wav', '.m4a', '.zip']);
        const coverFile = await this.findSiblingByExtensions(songDir, baseName, ['.png', '.jpg', '.jpeg', '.webp']);
        const relativeDir = path.relative(this.outputDir, songDir) || '.';

        songs.push({
          ...metadata,
          audioFilePath: audioFile ? this.toPosixPath(path.relative(this.outputDir, audioFile)) : null,
          coverFilePath: coverFile ? this.toPosixPath(path.relative(this.outputDir, coverFile)) : null,
          folder: this.toPosixPath(relativeDir)
        });
      }

      logger.info(`Collected metadata from ${songs.length} songs`);
      return songs;

    } catch (error) {
      logger.error('Failed to collect songs metadata:', error);
      throw error;
    }
  }

  /**
   * Transform song metadata to WordPress-compatible format
   */
  transformForWordPress(songs) {
    return songs.map(song => ({
      // Basic Info
      'Title': song.title || 'Untitled',
      'Artist': song.author || 'Unknown',
      'Album': song.album || 'FlowMusic Library',

      // Technical Details
      'BPM': song.bpm || '',
      'Key': song.key || '',
      'Duration': song.duration || '',
      'Model': song.model || '',

      // Content
      'Description': song.description || '',
      'Lyrics': song.lyrics || '',

      // Files (filenames for WordPress media library)
      'Audio File': song.audioFilePath || '',
      'Cover Image': song.coverFilePath || '',

      // URLs
      'FlowMusic URL': song.url || '',
      'Song ID': song.id || '',

      // Metadata
      'Download Date': song.downloadedAt || '',
      'Folder': song.folder || '.',

      // WordPress Categories/Tags (can be customized)
      'Categories': this.generateCategories(song),
      'Tags': this.generateTags(song)
    }));
  }

  /**
   * Generate WordPress categories based on song metadata
   */
  generateCategories(song) {
    const categories = ['AI Music'];

    if (song.model) {
      categories.push(`Model: ${song.model}`);
    }

    return categories.join(', ');
  }

  /**
   * Generate WordPress tags based on song metadata
   */
  generateTags(song) {
    const tags = [];

    if (song.key) tags.push(song.key);
    if (song.bpm) tags.push(`${song.bpm} BPM`);
    if (song.model) tags.push(song.model);

    // Add genre tags based on description (simple keyword matching)
    const description = (song.description || '').toLowerCase();
    const genreKeywords = [
      'ambient', 'orchestral', 'electronic', 'jazz', 'rock', 'pop',
      'classical', 'hip-hop', 'techno', 'house', 'folk', 'blues',
      'metal', 'indie', 'acoustic', 'cinematic', 'experimental'
    ];

    genreKeywords.forEach(genre => {
      if (description.includes(genre)) {
        tags.push(genre.charAt(0).toUpperCase() + genre.slice(1));
      }
    });

    return tags.join(', ');
  }

  /**
   * Export songs to CSV file
   */
  async exportToCSV(outputPath = null) {
    try {
      // Default path if not specified
      if (!outputPath) {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        outputPath = path.join(this.outputDir, `flowmusic-library-${timestamp}.csv`);
      }

      // Collect and transform data
      logger.info('Collecting songs metadata...');
      const songs = await this.collectSongsMetadata();

      if (songs.length === 0) {
        logger.warn('No songs found to export');
        return null;
      }

      logger.info('Transforming data for WordPress...');
      const wordpressData = this.transformForWordPress(songs);

      // Generate CSV
      logger.info('Generating CSV...');
      const csv = parse(wordpressData, {
        quote: '"',
        escapedQuote: '""',
        delimiter: ',',
        header: true,
        withBOM: true // UTF-8 BOM for Excel compatibility
      });

      // Write to file
      await fs.writeFile(outputPath, csv, 'utf8');

      logger.info(`✓ CSV exported: ${outputPath}`);
      logger.info(`  Songs: ${songs.length}`);
      logger.info(`  Size: ${(Buffer.byteLength(csv) / 1024).toFixed(2)} KB`);

      return {
        path: outputPath,
        songCount: songs.length,
        size: Buffer.byteLength(csv)
      };

    } catch (error) {
      logger.error('Failed to export CSV:', error);
      throw error;
    }
  }

  /**
   * Export with custom field mapping
   */
  async exportWithCustomFields(fieldMapping, outputPath = null) {
    try {
      const songs = await this.collectSongsMetadata();

      if (songs.length === 0) {
        logger.warn('No songs found to export');
        return null;
      }

      // Transform using custom field mapping
      const customData = songs.map(song => {
        const row = {};

        for (const [csvColumn, songField] of Object.entries(fieldMapping)) {
          // Support nested field access with dot notation
          const value = songField.split('.').reduce((obj, key) => obj?.[key], song);
          row[csvColumn] = value || '';
        }

        return row;
      });

      // Generate CSV
      const csv = parse(customData, {
        quote: '"',
        escapedQuote: '""',
        delimiter: ',',
        header: true,
        withBOM: true
      });

      // Default path if not specified
      if (!outputPath) {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        outputPath = path.join(this.outputDir, `flowmusic-custom-${timestamp}.csv`);
      }

      await fs.writeFile(outputPath, csv, 'utf8');

      logger.info(`✓ Custom CSV exported: ${outputPath}`);
      return {
        path: outputPath,
        songCount: songs.length,
        size: Buffer.byteLength(csv)
      };

    } catch (error) {
      logger.error('Failed to export custom CSV:', error);
      throw error;
    }
  }
}

export default CSVExporter;
