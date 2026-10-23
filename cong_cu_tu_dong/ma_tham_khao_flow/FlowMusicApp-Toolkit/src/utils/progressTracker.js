/**
 * Progress Tracker and Checkpoint System
 * Manages scraping progress and enables resume capability
 */

import path from 'path';
import fs from 'fs-extra';
import { logger, ProgressLogger } from './logger.js';
import scraperConfig from '../../config/scraper.config.js';

export class ProgressTracker {
  constructor(options = {}) {
    this.checkpointDir = options.checkpointDir || './checkpoints';
    this.checkpointInterval = options.checkpointInterval || scraperConfig.progress.checkpointInterval;
    this.sessionId = options.sessionId || this.generateSessionId();
    this.checkpointFile = path.join(this.checkpointDir, `checkpoint_${this.sessionId}.json`);

    // Progress state
    this.state = {
      sessionId: this.sessionId,
      startTime: null,
      endTime: null,
      status: 'initializing',
      totalSongs: 0,
      processedSongs: [],
      failedSongs: [],
      currentSongIndex: 0,
      lastCheckpoint: null,
      statistics: {
        successful: 0,
        failed: 0,
        skipped: 0,
        totalDownloads: 0,
        totalSize: 0
      }
    };

    // Progress logger for console output
    this.progressLogger = null;
  }

  /**
   * Initialize progress tracker
   */
  async initialize(totalSongs = 0, resumeSession = null) {
    try {
      // Ensure checkpoint directory exists
      await fs.ensureDir(this.checkpointDir);

      if (resumeSession) {
        // Resume from existing session
        const resumed = await this.resumeSession(resumeSession);
        if (resumed) {
          logger.info(`Resumed session: ${resumeSession}`);
          return true;
        }
      }

      // Start new session
      this.state.startTime = new Date().toISOString();
      this.state.totalSongs = totalSongs;
      this.state.status = 'initialized';

      // Create progress logger
      this.progressLogger = new ProgressLogger(totalSongs);

      // Save initial checkpoint
      await this.saveCheckpoint();

      logger.info(`Progress tracker initialized. Session: ${this.sessionId}`);
      return true;

    } catch (error) {
      logger.error('Failed to initialize progress tracker:', error);
      return false;
    }
  }

  /**
   * Generate unique session ID
   */
  generateSessionId() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const random = Math.random().toString(36).substring(2, 8);
    return `${timestamp}_${random}`;
  }

  /**
   * Resume from existing session
   */
  async resumeSession(sessionId) {
    try {
      const checkpointFile = path.join(this.checkpointDir, `checkpoint_${sessionId}.json`);

      if (!await fs.pathExists(checkpointFile)) {
        logger.warn(`Checkpoint file not found: ${sessionId}`);
        return false;
      }

      // Load checkpoint
      const checkpoint = await fs.readJson(checkpointFile);
      this.state = checkpoint;
      this.sessionId = sessionId;
      this.checkpointFile = checkpointFile;

      // Update status
      this.state.status = 'resumed';
      this.state.resumedAt = new Date().toISOString();

      // Recreate progress logger
      this.progressLogger = new ProgressLogger(this.state.totalSongs);
      this.progressLogger.current = this.state.processedSongs.length;
      this.progressLogger.successful = this.state.statistics.successful;
      this.progressLogger.failed = this.state.statistics.failed;

      logger.info(`Session resumed from checkpoint: ${this.state.currentSongIndex}/${this.state.totalSongs} songs processed`);
      return true;

    } catch (error) {
      logger.error('Failed to resume session:', error);
      return false;
    }
  }

  /**
   * Get list of available sessions
   */
  async getAvailableSessions() {
    try {
      const files = await fs.readdir(this.checkpointDir);
      const sessions = [];

      for (const file of files) {
        if (file.startsWith('checkpoint_') && file.endsWith('.json')) {
          const filepath = path.join(this.checkpointDir, file);
          const checkpoint = await fs.readJson(filepath);

          sessions.push({
            sessionId: checkpoint.sessionId,
            startTime: checkpoint.startTime,
            status: checkpoint.status,
            progress: `${checkpoint.processedSongs.length}/${checkpoint.totalSongs}`,
            lastCheckpoint: checkpoint.lastCheckpoint
          });
        }
      }

      return sessions.sort((a, b) => new Date(b.startTime) - new Date(a.startTime));

    } catch (error) {
      logger.error('Error getting available sessions:', error);
      return [];
    }
  }

  /**
   * Mark song as started
   */
  async startSong(song, index) {
    try {
      this.state.status = 'processing';
      this.state.currentSongIndex = index;
      this.state.currentSong = {
        id: song.id,
        title: song.title,
        startedAt: new Date().toISOString()
      };

      logger.debug(`Started processing: ${song.title} (${index + 1}/${this.state.totalSongs})`);

      // Save checkpoint if interval reached
      if (this.shouldSaveCheckpoint()) {
        await this.saveCheckpoint();
      }

      return true;

    } catch (error) {
      logger.error('Error marking song start:', error);
      return false;
    }
  }

  /**
   * Mark song as completed
   */
  async completeSong(song, success = true, details = {}) {
    try {
      const processedSong = {
        id: song.id,
        title: song.title,
        success: success,
        processedAt: new Date().toISOString(),
        ...details
      };

      if (success) {
        this.state.processedSongs.push(processedSong);
        this.state.statistics.successful++;
        this.progressLogger?.success(song.title);
      } else {
        this.state.failedSongs.push(processedSong);
        this.state.statistics.failed++;
        this.progressLogger?.failure(song.title, new Error(details.error || 'Unknown error'));
      }

      // Update statistics
      if (details.downloads) {
        this.state.statistics.totalDownloads += details.downloads;
      }
      if (details.size) {
        this.state.statistics.totalSize += details.size;
      }

      // Clear current song
      delete this.state.currentSong;

      // Save checkpoint if needed
      if (this.shouldSaveCheckpoint()) {
        await this.saveCheckpoint();
      }

      return true;

    } catch (error) {
      logger.error('Error marking song completion:', error);
      return false;
    }
  }

  /**
   * Check if song was already processed
   */
  isProcessed(song) {
    const songId = song.id || song.title;
    return this.state.processedSongs.some(s => s.id === songId || s.title === song.title);
  }

  /**
   * Get songs to process (excluding already processed)
   */
  getSongsToProcess(allSongs) {
    const processedIds = new Set(this.state.processedSongs.map(s => s.id || s.title));
    const failedIds = new Set(this.state.failedSongs.map(s => s.id || s.title));

    return allSongs.filter(song => {
      const songId = song.id || song.title;
      return !processedIds.has(songId) && !failedIds.has(songId);
    });
  }

  /**
   * Should save checkpoint
   */
  shouldSaveCheckpoint() {
    const processed = this.state.processedSongs.length + this.state.failedSongs.length;
    return processed % this.checkpointInterval === 0;
  }

  /**
   * Save checkpoint
   */
  async saveCheckpoint() {
    try {
      this.state.lastCheckpoint = new Date().toISOString();
      await fs.writeJson(this.checkpointFile, this.state, { spaces: 2 });
      logger.debug(`Checkpoint saved: ${this.checkpointFile}`);
      return true;

    } catch (error) {
      logger.error('Failed to save checkpoint:', error);
      return false;
    }
  }

  /**
   * Update progress status
   */
  updateStatus(status) {
    this.state.status = status;
    logger.debug(`Status updated: ${status}`);
  }

  /**
   * Log progress update
   */
  logProgress(message) {
    const processed = this.state.processedSongs.length;
    const total = this.state.totalSongs;
    const percentage = total > 0 ? ((processed / total) * 100).toFixed(1) : 0;

    logger.info(`[${processed}/${total}] (${percentage}%) - ${message}`);
  }

  /**
   * Get current progress
   */
  getProgress() {
    const processed = this.state.processedSongs.length + this.state.failedSongs.length;
    const remaining = this.state.totalSongs - processed;
    const percentage = this.state.totalSongs > 0
      ? ((processed / this.state.totalSongs) * 100).toFixed(1)
      : 0;

    return {
      sessionId: this.sessionId,
      status: this.state.status,
      total: this.state.totalSongs,
      processed: processed,
      successful: this.state.statistics.successful,
      failed: this.state.statistics.failed,
      remaining: remaining,
      percentage: percentage,
      currentSong: this.state.currentSong,
      elapsedTime: this.getElapsedTime(),
      estimatedTimeRemaining: this.getEstimatedTimeRemaining()
    };
  }

  /**
   * Get elapsed time
   */
  getElapsedTime() {
    if (!this.state.startTime) return 'N/A';

    const start = new Date(this.state.startTime);
    const now = this.state.endTime ? new Date(this.state.endTime) : new Date();
    const elapsed = now - start;

    return this.formatTime(elapsed);
  }

  /**
   * Get estimated time remaining
   */
  getEstimatedTimeRemaining() {
    const processed = this.state.processedSongs.length;
    if (processed === 0) return 'N/A';

    const start = new Date(this.state.startTime);
    const now = new Date();
    const elapsed = now - start;
    const averageTime = elapsed / processed;
    const remaining = this.state.totalSongs - processed;
    const estimatedRemaining = averageTime * remaining;

    return this.formatTime(estimatedRemaining);
  }

  /**
   * Format time duration
   */
  formatTime(milliseconds) {
    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  }

  /**
   * Complete session
   */
  async complete() {
    try {
      this.state.status = 'completed';
      this.state.endTime = new Date().toISOString();

      // Save final checkpoint
      await this.saveCheckpoint();

      // Log summary
      this.progressLogger?.logSummary();

      // Create final report
      await this.createFinalReport();

      logger.info('Session completed successfully');
      return true;

    } catch (error) {
      logger.error('Error completing session:', error);
      return false;
    }
  }

  /**
   * Create final report
   */
  async createFinalReport() {
    try {
      const report = {
        sessionId: this.sessionId,
        startTime: this.state.startTime,
        endTime: this.state.endTime,
        duration: this.getElapsedTime(),
        totalSongs: this.state.totalSongs,
        processedSongs: this.state.processedSongs.length,
        successfulSongs: this.state.statistics.successful,
        failedSongs: this.state.statistics.failed,
        successRate: ((this.state.statistics.successful / this.state.totalSongs) * 100).toFixed(1) + '%',
        totalDownloads: this.state.statistics.totalDownloads,
        totalSize: this.formatFileSize(this.state.statistics.totalSize),
        processedList: this.state.processedSongs,
        failedList: this.state.failedSongs
      };

      const reportPath = path.join(this.checkpointDir, `report_${this.sessionId}.json`);
      await fs.writeJson(reportPath, report, { spaces: 2 });

      logger.info(`Final report saved: ${reportPath}`);
      return reportPath;

    } catch (error) {
      logger.error('Error creating final report:', error);
      return null;
    }
  }

  /**
   * Format file size
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

  /**
   * Clean up old checkpoints
   */
  async cleanupOldCheckpoints(daysToKeep = 7) {
    try {
      const files = await fs.readdir(this.checkpointDir);
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - daysToKeep);

      for (const file of files) {
        if (file.startsWith('checkpoint_') && file.endsWith('.json')) {
          const filepath = path.join(this.checkpointDir, file);
          const stat = await fs.stat(filepath);

          if (stat.mtime < cutoffDate) {
            await fs.remove(filepath);
            logger.debug(`Removed old checkpoint: ${file}`);
          }
        }
      }

      return true;

    } catch (error) {
      logger.error('Error cleaning up checkpoints:', error);
      return false;
    }
  }
}

export default ProgressTracker;