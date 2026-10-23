/**
 * File Organization System
 * Manages folder structure and file naming for downloaded content
 */

import path from 'path';
import fs from 'fs-extra';
import sanitize from 'sanitize-filename';
import scraperConfig from '../../config/scraper.config.js';
import { logger } from './logger.js';

export class FileOrganizer {
  constructor(baseOutputPath = './output') {
    this.baseOutputPath = path.resolve(baseOutputPath);
    this.config = scraperConfig.fileOrganization;
    this.songFolders = new Map();
    this.duplicateCounter = new Map();
  }

  /**
   * Initialize file organizer
   */
  async initialize() {
    try {
      // Ensure base output directory exists
      await fs.ensureDir(this.baseOutputPath);

      // Create subdirectories based on organization structure
      if (this.config.structure === 'BY_DATE') {
        const dateFolder = new Date().toISOString().split('T')[0];
        this.baseOutputPath = path.join(this.baseOutputPath, dateFolder);
        await fs.ensureDir(this.baseOutputPath);
      }

      logger.info(`File organizer initialized. Output path: ${this.baseOutputPath}`);
      return true;

    } catch (error) {
      logger.error('Failed to initialize file organizer:', error);
      return false;
    }
  }

  /**
   * Create folder structure for a song
   */
  async createSongFolder(song, playlist = null) {
    try {
      // Generate folder name
      const folderName = this.generateFolderName(song, playlist);

      // Create full path
      let songPath;
      if (this.config.structure === 'BY_PLAYLIST' && playlist) {
        const playlistFolder = this.sanitizeName(playlist);
        songPath = path.join(this.baseOutputPath, playlistFolder, folderName);
      } else {
        songPath = path.join(this.baseOutputPath, folderName);
      }

      // Ensure folder exists
      await fs.ensureDir(songPath);

      // Store folder mapping
      this.songFolders.set(song.id || song.title, songPath);

      logger.debug(`Created folder for song: ${songPath}`);
      return songPath;

    } catch (error) {
      logger.error('Error creating song folder:', error);
      throw error;
    }
  }

  /**
   * Generate folder name for a song
   */
  generateFolderName(song, playlist = null) {
    let folderName = this.config.naming.folder;

    // Replace placeholders
    folderName = folderName.replace('{songName}', song.title || 'Unknown Song');
    folderName = folderName.replace('{songId}', song.id || '');
    folderName = folderName.replace('{playlist}', playlist || '');

    // Add date if included in pattern
    if (folderName.includes('{date}')) {
      const date = new Date().toISOString().split('T')[0];
      folderName = folderName.replace('{date}', date);
    }

    // Sanitize folder name
    folderName = this.sanitizeName(folderName);

    // Handle duplicates
    folderName = this.handleDuplicateName(folderName);

    return folderName;
  }

  /**
   * Sanitize file/folder name
   */
  sanitizeName(name) {
    // Use sanitize-filename library
    let sanitized = sanitize(name, { replacement: '-' });

    // Apply custom replacements
    if (this.config.sanitization.replaceChars) {
      for (const [char, replacement] of Object.entries(this.config.sanitization.replaceChars)) {
        sanitized = sanitized.replace(new RegExp(`\\${char}`, 'g'), replacement);
      }
    }

    // Trim to max length
    if (sanitized.length > this.config.sanitization.maxLength) {
      const extension = path.extname(sanitized);
      const baseName = path.basename(sanitized, extension);
      const truncated = baseName.substring(0, this.config.sanitization.maxLength - extension.length - 3);
      sanitized = truncated + '...' + extension;
    }

    // Remove leading/trailing dots and spaces
    sanitized = sanitized.replace(/^[. ]+|[. ]+$/g, '');

    // Ensure name is not empty
    if (!sanitized || sanitized === '') {
      sanitized = 'unnamed';
    }

    return sanitized;
  }

  /**
   * Handle duplicate names by appending counter
   */
  handleDuplicateName(name) {
    const basePath = path.join(this.baseOutputPath, name);

    if (!fs.existsSync(basePath)) {
      return name;
    }

    // Track duplicates
    if (!this.duplicateCounter.has(name)) {
      this.duplicateCounter.set(name, 1);
    }

    let counter = this.duplicateCounter.get(name);
    let newName = `${name}_${counter}`;
    let newPath = path.join(this.baseOutputPath, newName);

    while (fs.existsSync(newPath)) {
      counter++;
      newName = `${name}_${counter}`;
      newPath = path.join(this.baseOutputPath, newName);
    }

    this.duplicateCounter.set(name, counter);
    logger.debug(`Duplicate name detected. Using: ${newName}`);

    return newName;
  }

  /**
   * Organize downloaded files
   */
  async organizeFiles(song, downloads, metadata, lyrics) {
    try {
      const songFolder = this.songFolders.get(song.id || song.title);

      if (!songFolder) {
        throw new Error('Song folder not created');
      }

      const organized = {
        folder: songFolder,
        files: {}
      };

      // Move/copy audio file
      if (downloads.audio) {
        const audioPath = await this.organizeAudioFile(downloads.audio, songFolder);
        organized.files.audio = audioPath;
      }

      // Move/copy cover file
      if (downloads.cover) {
        const coverPath = await this.organizeCoverFile(downloads.cover, songFolder);
        organized.files.cover = coverPath;
      }

      // Save metadata
      if (metadata) {
        const metadataPath = await this.saveMetadata(metadata, songFolder);
        organized.files.metadata = metadataPath;
      }

      // Save lyrics
      if (lyrics) {
        const lyricsPath = await this.saveLyrics(lyrics, songFolder);
        organized.files.lyrics = lyricsPath;
      }

      // Create info file with all details
      await this.createInfoFile(song, organized, songFolder);

      logger.debug(`Files organized for: ${song.title}`);
      return organized;

    } catch (error) {
      logger.error(`Error organizing files for ${song.title}:`, error);
      throw error;
    }
  }

  /**
   * Organize audio file
   */
  async organizeAudioFile(sourcePath, targetFolder) {
    try {
      if (!await fs.pathExists(sourcePath)) {
        throw new Error('Audio file not found');
      }

      const extension = path.extname(sourcePath);
      const targetName = this.config.naming.audio.replace('{ext}', extension.substring(1));
      const targetPath = path.join(targetFolder, targetName);

      await fs.move(sourcePath, targetPath, { overwrite: true });
      logger.debug(`Audio file organized: ${targetPath}`);

      return targetPath;

    } catch (error) {
      logger.error('Error organizing audio file:', error);
      return null;
    }
  }

  /**
   * Organize cover file
   */
  async organizeCoverFile(sourcePath, targetFolder) {
    try {
      if (!await fs.pathExists(sourcePath)) {
        throw new Error('Cover file not found');
      }

      const extension = path.extname(sourcePath);
      const targetName = this.config.naming.cover.replace('{ext}', extension.substring(1));
      const targetPath = path.join(targetFolder, targetName);

      await fs.move(sourcePath, targetPath, { overwrite: true });
      logger.debug(`Cover file organized: ${targetPath}`);

      return targetPath;

    } catch (error) {
      logger.error('Error organizing cover file:', error);
      return null;
    }
  }

  /**
   * Save metadata to JSON file
   */
  async saveMetadata(metadata, targetFolder) {
    try {
      const targetPath = path.join(targetFolder, this.config.naming.metadata);

      await fs.writeJson(targetPath, metadata, { spaces: 2 });
      logger.debug(`Metadata saved: ${targetPath}`);

      return targetPath;

    } catch (error) {
      logger.error('Error saving metadata:', error);
      return null;
    }
  }

  /**
   * Save lyrics to text file
   */
  async saveLyrics(lyrics, targetFolder) {
    try {
      if (!lyrics || lyrics.trim() === '') {
        logger.debug('No lyrics to save');
        return null;
      }

      const targetPath = path.join(targetFolder, this.config.naming.lyrics);

      await fs.writeFile(targetPath, lyrics, 'utf8');
      logger.debug(`Lyrics saved: ${targetPath}`);

      return targetPath;

    } catch (error) {
      logger.error('Error saving lyrics:', error);
      return null;
    }
  }

  /**
   * Create info file with all song details
   */
  async createInfoFile(song, organized, targetFolder) {
    try {
      const info = {
        song: {
          id: song.id,
          title: song.title,
          url: song.url
        },
        files: organized.files,
        downloadedAt: new Date().toISOString(),
        folder: targetFolder
      };

      const infoPath = path.join(targetFolder, 'info.json');
      await fs.writeJson(infoPath, info, { spaces: 2 });

      logger.debug(`Info file created: ${infoPath}`);
      return infoPath;

    } catch (error) {
      logger.error('Error creating info file:', error);
      return null;
    }
  }

  /**
   * Create summary report
   */
  async createSummaryReport(results) {
    try {
      const reportPath = path.join(this.baseOutputPath, 'export-summary.json');

      const summary = {
        exportDate: new Date().toISOString(),
        totalSongs: results.length,
        successful: results.filter(r => r.success).length,
        failed: results.filter(r => !r.success).length,
        songs: results.map(r => ({
          title: r.song.title,
          success: r.success,
          folder: r.folder,
          files: r.files,
          errors: r.errors
        }))
      };

      await fs.writeJson(reportPath, summary, { spaces: 2 });
      logger.info(`Summary report saved: ${reportPath}`);

      return reportPath;

    } catch (error) {
      logger.error('Error creating summary report:', error);
      return null;
    }
  }

  /**
   * Clean up empty folders
   */
  async cleanupEmptyFolders() {
    try {
      const folders = await this.getAllFolders(this.baseOutputPath);

      for (const folder of folders) {
        const files = await fs.readdir(folder);
        if (files.length === 0) {
          await fs.remove(folder);
          logger.debug(`Removed empty folder: ${folder}`);
        }
      }

      return true;

    } catch (error) {
      logger.error('Error cleaning up empty folders:', error);
      return false;
    }
  }

  /**
   * Get all folders recursively
   */
  async getAllFolders(dir, folders = []) {
    const items = await fs.readdir(dir, { withFileTypes: true });

    for (const item of items) {
      if (item.isDirectory()) {
        const fullPath = path.join(dir, item.name);
        folders.push(fullPath);
        await this.getAllFolders(fullPath, folders);
      }
    }

    return folders;
  }

  /**
   * Get organization statistics
   */
  async getStatistics() {
    try {
      const stats = {
        totalFolders: this.songFolders.size,
        totalSize: 0,
        fileTypes: {},
        duplicates: Array.from(this.duplicateCounter.entries())
      };

      // Calculate total size and file types
      for (const folder of this.songFolders.values()) {
        const files = await fs.readdir(folder);

        for (const file of files) {
          const filePath = path.join(folder, file);
          const stat = await fs.stat(filePath);

          stats.totalSize += stat.size;

          const ext = path.extname(file);
          stats.fileTypes[ext] = (stats.fileTypes[ext] || 0) + 1;
        }
      }

      // Convert size to human-readable format
      stats.totalSizeFormatted = this.formatFileSize(stats.totalSize);

      return stats;

    } catch (error) {
      logger.error('Error getting statistics:', error);
      return null;
    }
  }

  /**
   * Format file size to human-readable
   */
  formatFileSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }

    return `${size.toFixed(2)} ${units[unitIndex]}`;
  }
}

export default FileOrganizer;