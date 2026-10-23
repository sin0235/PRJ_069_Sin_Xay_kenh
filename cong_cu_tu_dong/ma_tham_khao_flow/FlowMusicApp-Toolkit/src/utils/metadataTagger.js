/**
 * MP3 Metadata Tagger
 * Writes ID3 tags to MP3 files using metadata from JSON
 */

import NodeID3 from 'node-id3';
import { parseFile as parseAudioFile } from 'music-metadata';
import fs from 'fs-extra';
import path from 'path';
import { logger } from './logger.js';
import scraperConfig from '../../config/scraper.config.js';

export class MetadataTagger {
  /**
   * Write ID3 tags to an MP3 file
   * @param {string} mp3Path - Path to the MP3 file
   * @param {object} metadata - Metadata object from JSON
   * @param {string} [coverPath] - Optional path to cover image
   */
  static async tagMp3(mp3Path, metadata, coverPath = null) {
    try {
      if (!await fs.pathExists(mp3Path)) {
        throw new Error(`MP3 file not found: ${mp3Path}`);
      }

      logger.debug(`Tagging MP3: ${path.basename(mp3Path)}`);

      // Extract filename without extension as fallback title
      const fileNameWithoutExt = path.basename(mp3Path, '.mp3');

      // Prepare ID3 tags with sensible defaults for missing fields
      const defaultYear = scraperConfig.metadata.defaultYear || new Date().getFullYear();

      const tags = {
        title: metadata.title || metadata.originalTitle || fileNameWithoutExt,
        artist: metadata.author || metadata.artist || scraperConfig.metadata.defaultArtist,
        album: metadata.album || scraperConfig.metadata.defaultAlbum,
        year: metadata.year || (metadata.downloadedAt ? new Date(metadata.downloadedAt).getFullYear().toString() : defaultYear.toString()),
        comment: {
          language: 'eng',
          text: this.buildComment(metadata)
        },
        userDefinedText: []
      };

      // Add BPM if available
      if (metadata.bpm) {
        tags.bpm = metadata.bpm.toString();
      }

      // Add key as user-defined text
      if (metadata.key) {
        tags.userDefinedText.push({
          description: 'KEY',
          value: metadata.key
        });
      }

      // Add model as user-defined text
      if (metadata.model) {
        tags.userDefinedText.push({
          description: 'MODEL',
          value: metadata.model
        });
      }

      // Add song ID as user-defined text
      if (metadata.id) {
        tags.userDefinedText.push({
          description: 'SONG_ID',
          value: metadata.id
        });
      }

      // Add URL as user-defined text
      if (metadata.url) {
        tags.userDefinedText.push({
          description: 'URL',
          value: metadata.url
        });
      }

      // Add unsynchronised lyrics if available
      if (metadata.lyrics) {
        tags.unsynchronisedLyrics = {
          language: 'eng',
          text: metadata.lyrics
        };
      }

      // Add cover art if available
      if (coverPath && await fs.pathExists(coverPath)) {
        logger.debug(`Adding cover art: ${path.basename(coverPath)}`);
        const imageBuffer = await fs.readFile(coverPath);

        tags.image = {
          mime: this.getMimeType(coverPath),
          type: {
            id: 3,
            name: 'Front cover'
          },
          description: 'Cover',
          imageBuffer
        };
      }

      // Read duration from the audio file itself (more reliable than scraping the page)
      try {
        const audioMeta = await parseAudioFile(mp3Path, { duration: true });
        const durationSecs = audioMeta.format.duration;
        if (durationSecs && durationSecs > 0) {
          const mins = Math.floor(durationSecs / 60);
          const secs = Math.round(durationSecs % 60);
          tags.length = Math.round(durationSecs * 1000).toString(); // TLEN in ms
          metadata.duration = `${mins}:${secs.toString().padStart(2, '0')}`;
        }
      } catch {
        // Duration unavailable — leave unset rather than error
      }

      // Write tags to MP3
      const success = NodeID3.write(tags, mp3Path);

      if (success) {
        logger.debug(`✓ Tagged: ${path.basename(mp3Path)}`);
        return {
          success: true,
          file: mp3Path,
          tagsWritten: Object.keys(tags).length
        };
      } else {
        throw new Error('NodeID3.write returned false');
      }

    } catch (error) {
      logger.error(`Failed to tag MP3: ${path.basename(mp3Path)}`, error);
      return {
        success: false,
        file: mp3Path,
        error: error.message
      };
    }
  }

  /**
   * Build a descriptive comment from metadata
   */
  static buildComment(metadata) {
    const parts = [];

    if (metadata.key) parts.push(metadata.key);
    if (metadata.bpm) parts.push(`${metadata.bpm} BPM`);
    if (metadata.model) parts.push(`Model: ${metadata.model}`);
    if (metadata.description) {
      // Truncate description to fit in comment (max 30000 chars for ID3v2)
      const desc = metadata.description.substring(0, 500);
      parts.push(desc);
    }

    return parts.join(' | ');
  }

  /**
   * Get MIME type from file extension
   */
  static getMimeType(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes = {
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.png': 'image/png',
      '.webp': 'image/webp'
    };
    return mimeTypes[ext] || 'image/jpeg';
  }

  /**
   * Tag all MP3s in a directory using their corresponding JSON files
   * @param {string} dir - Directory containing MP3 and JSON files
   */
  static async tagDirectory(dir) {
    try {
      logger.info(`Scanning directory for MP3 files: ${dir}`);

      const files = await fs.readdir(dir);
      const mp3Files = files.filter(f => f.endsWith('.mp3'));

      logger.info(`Found ${mp3Files.length} MP3 files`);

      const results = {
        total: mp3Files.length,
        success: 0,
        failed: 0,
        skipped: 0
      };

      for (const mp3File of mp3Files) {
        const mp3Path = path.join(dir, mp3File);
        const baseName = mp3File.replace('.mp3', '');
        const jsonPath = path.join(dir, `${baseName}.json`);

        // Check if JSON exists
        if (!await fs.pathExists(jsonPath)) {
          logger.warn(`No JSON found for: ${mp3File}`);
          results.skipped++;
          continue;
        }

        // Load metadata
        const metadata = await fs.readJson(jsonPath);

        // Find cover art
        const coverExtensions = ['.jpg', '.jpeg', '.png', '.webp'];
        let coverPath = null;
        for (const ext of coverExtensions) {
          const candidatePath = path.join(dir, `${baseName}${ext}`);
          if (await fs.pathExists(candidatePath)) {
            coverPath = candidatePath;
            break;
          }
        }

        // Tag the MP3
        logger.info(`[${results.success + results.failed + 1}/${mp3Files.length}] Tagging: ${mp3File}`);
        const result = await this.tagMp3(mp3Path, metadata, coverPath);

        if (result.success) {
          results.success++;
        } else {
          results.failed++;
        }
      }

      logger.info(`\nTagging complete:`);
      logger.info(`  ✓ Success: ${results.success}`);
      logger.info(`  ✗ Failed: ${results.failed}`);
      logger.info(`  ⊘ Skipped: ${results.skipped}`);

      return results;

    } catch (error) {
      logger.error('Failed to tag directory:', error);
      throw error;
    }
  }
}

export default MetadataTagger;
