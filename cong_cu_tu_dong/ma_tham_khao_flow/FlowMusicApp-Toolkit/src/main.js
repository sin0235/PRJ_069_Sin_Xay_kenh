#!/usr/bin/env node

/**
 * FlowMusic Music Library Scraper
 * Main orchestration script
 */

import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import chalk from 'chalk';
import dotenv from 'dotenv';

// Import all modules
import { BrowserAuthenticator } from './browser/authenticator.js';
import { SongScraper } from './browser/scraper.js';
import { MetadataExtractor } from './downloaders/metadataExtractor.js';
import { SongDownloader } from './downloaders/songDownloader.js';
import { FileOrganizer } from './utils/fileOrganizer.js';
import { ProgressTracker } from './utils/progressTracker.js';
import { ErrorHandler } from './utils/errorHandler.js';
import { logger, logDivider, createSpinner } from './utils/logger.js';
import scraperConfig from '../config/scraper.config.js';

// Load environment variables
dotenv.config();

/**
 * Main scraper class
 */
class FlowMusicScraper {
  constructor(options) {
    this.options = options;
    this.authenticator = new BrowserAuthenticator();
    this.scraper = null;
    this.metadataExtractor = null;
    this.downloader = null;
    this.fileOrganizer = new FileOrganizer(options.output);
    this.progressTracker = new ProgressTracker();
    this.errorHandler = new ErrorHandler();
    this.page = null;
    this.context = null;
  }

  /**
   * Initialize scraper
   */
  async initialize() {
    try {
      logDivider('INITIALIZATION');
      logger.info('Initializing FlowMusic Scraper...');

      // Initialize browser
      const spinner = await createSpinner('Setting up browser...');
      spinner.start();

      const initialized = await this.authenticator.initialize({
        useProfile: this.options.useProfile,
        profilePath: this.options.profilePath
      });

      if (!initialized) {
        spinner.fail('Failed to initialize browser');
        throw new Error('Browser initialization failed');
      }

      spinner.succeed('Browser initialized');

      // Get page and context
      this.page = this.authenticator.getPage();
      this.context = this.authenticator.getContext();

      // Initialize modules
      this.scraper = new SongScraper(this.page);
      this.metadataExtractor = new MetadataExtractor(this.page);
      this.downloader = new SongDownloader(this.page, this.context);
      await this.downloader.initialize();

      // Initialize file organizer
      await this.fileOrganizer.initialize();

      // Check for resume session
      if (this.options.resume) {
        await this.handleResume();
      }

      logger.info('Scraper initialized successfully');
      return true;

    } catch (error) {
      logger.error('Initialization failed:', error);
      throw error;
    }
  }

  /**
   * Handle resume from checkpoint
   */
  async handleResume() {
    try {
      const sessions = await this.progressTracker.getAvailableSessions();

      if (sessions.length === 0) {
        logger.warn('No previous sessions found to resume');
        return false;
      }

      logger.info('Available sessions to resume:');
      sessions.forEach((session, index) => {
        console.log(`${index + 1}. Session ${session.sessionId}`);
        console.log(`   Started: ${session.startTime}`);
        console.log(`   Progress: ${session.progress}`);
        console.log(`   Status: ${session.status}`);
      });

      // Use most recent session or specified session ID
      const sessionToResume = this.options.sessionId || sessions[0].sessionId;
      logger.info(`Resuming session: ${sessionToResume}`);

      return await this.progressTracker.resumeSession(sessionToResume);

    } catch (error) {
      logger.error('Error handling resume:', error);
      return false;
    }
  }

  /**
   * Authenticate user
   */
  async authenticate() {
    try {
      logDivider('AUTHENTICATION');
      const spinner = await createSpinner('Checking authentication...');
      spinner.start();

      const isAuthenticated = await this.authenticator.checkAuthentication();

      if (isAuthenticated) {
        spinner.succeed('User authenticated');
        return true;
      }

      spinner.fail('Not authenticated');
      logger.warn('User not authenticated, manual login required');

      // Wait for manual login
      await this.authenticator.waitForManualLogin();

      return await this.authenticator.checkAuthentication();

    } catch (error) {
      logger.error('Authentication error:', error);
      throw error;
    }
  }

  /**
   * Get songs to process
   */
  async getSongs() {
    try {
      logDivider('FETCHING SONGS');

      let songs = [];

      if (this.options.playlist) {
        // Get songs from specific playlist
        logger.info(`Fetching songs from playlist: ${this.options.playlist}`);
        songs = await this.scraper.getAllSongs(this.options.playlist);

      } else if (this.options.allSongs) {
        // Get all songs from library
        logger.info('Fetching all songs from library...');
        songs = await this.scraper.getAllSongs();

      } else {
        // Get playlists and let user choose
        const playlists = await this.scraper.getPlaylists();

        if (playlists.length === 0) {
          logger.warn('No playlists found, fetching all songs...');
          songs = await this.scraper.getAllSongs();
        } else {
          logger.info('Available playlists:');
          playlists.forEach((p, i) => {
            console.log(`${i + 1}. ${p.name} (${p.songCount} songs)`);
          });

          // Default to all songs if not interactive
          logger.info('Fetching all songs...');
          songs = await this.scraper.getAllSongs();
        }
      }

      logger.info(`Found ${songs.length} songs`);

      // Filter out already processed songs if resuming
      if (this.progressTracker.state.processedSongs.length > 0) {
        songs = this.progressTracker.getSongsToProcess(songs);
        logger.info(`${songs.length} songs remaining to process`);
      }

      return songs;

    } catch (error) {
      logger.error('Error getting songs:', error);
      throw error;
    }
  }

  /**
   * Process a single song
   */
  async processSong(song, index, total) {
    const startTime = Date.now();

    try {
      // Start tracking
      await this.progressTracker.startSong(song, index);

      logger.info(`\n[${index + 1}/${total}] Processing: ${song.title}`);

      // Create song folder
      const songFolder = await this.fileOrganizer.createSongFolder(
        song,
        this.options.playlist
      );

      // Navigate to song page with retry
      const navigated = await this.errorHandler.withRetry(
        async () => await this.scraper.navigateToSong(song),
        `navigate_${song.title}`,
        song.id
      );

      if (!navigated) {
        throw new Error('Failed to navigate to song page');
      }

      // Extract metadata
      const metadata = await this.errorHandler.withRetry(
        async () => await this.metadataExtractor.extractFullMetadata(),
        `metadata_${song.title}`,
        song.id
      );

      // Download assets
      const downloads = await this.errorHandler.withRetry(
        async () => await this.downloader.downloadSongAssets(song, songFolder),
        `download_${song.title}`,
        song.id
      );

      // Organize files
      const organized = await this.fileOrganizer.organizeFiles(
        song,
        downloads,
        metadata,
        metadata?.lyrics
      );

      // Navigate back to list
      await this.scraper.navigateBack();

      // Mark as completed
      const processingTime = Date.now() - startTime;
      await this.progressTracker.completeSong(song, true, {
        folder: songFolder,
        downloads: Object.keys(organized.files || {}).length,
        processingTime: processingTime
      });

      logger.info(chalk.green(`✓ Completed: ${song.title} (${processingTime}ms)`));
      return { success: true, song, organized };

    } catch (error) {
      logger.error(`Failed to process ${song.title}:`, error);

      // Handle error
      const recovery = await this.errorHandler.handleDownloadError(error, song, this.page);

      // Mark as failed
      await this.progressTracker.completeSong(song, false, {
        error: error.message,
        processingTime: Date.now() - startTime
      });

      // Try to navigate back to list for next song
      try {
        await this.scraper.navigateBack();
      } catch (navError) {
        logger.warn('Failed to navigate back after error');
      }

      return { success: false, song, error: error.message };
    }
  }

  /**
   * Process all songs
   */
  async processAllSongs(songs) {
    try {
      logDivider('PROCESSING SONGS');

      // Initialize progress tracker
      await this.progressTracker.initialize(songs.length, this.options.sessionId);

      const results = [];

      for (let i = 0; i < songs.length; i++) {
        const song = songs[i];

        // Check if already processed (for resume)
        if (this.progressTracker.isProcessed(song)) {
          logger.info(`Skipping already processed: ${song.title}`);
          continue;
        }

        // Process song
        const result = await this.processSong(song, i, songs.length);
        results.push(result);

        // Add delay between songs
        if (i < songs.length - 1) {
          await new Promise(resolve =>
            setTimeout(resolve, scraperConfig.behavior.delays.betweenSongs)
          );
        }

        // Show progress
        const progress = this.progressTracker.getProgress();
        logger.info(
          `Progress: ${progress.percentage}% | ` +
          `Success: ${progress.successful} | ` +
          `Failed: ${progress.failed} | ` +
          `Remaining: ${progress.remaining} | ` +
          `Time: ${progress.elapsedTime}`
        );
      }

      return results;

    } catch (error) {
      logger.error('Error processing songs:', error);
      throw error;
    }
  }

  /**
   * Run the scraper
   */
  async run() {
    try {
      console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
      console.log(chalk.cyan.bold('        FlowMusic Music Library Scraper            '));
      console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

      // Initialize
      await this.initialize();

      // Authenticate
      const authenticated = await this.authenticate();
      if (!authenticated) {
        throw new Error('Authentication failed');
      }

      // Get songs
      const songs = await this.getSongs();
      if (songs.length === 0) {
        logger.warn('No songs found to process');
        return;
      }

      // Process songs
      const results = await this.processAllSongs(songs);

      // Complete session
      await this.progressTracker.complete();

      // Generate reports
      logDivider('GENERATING REPORTS');

      // Create summary report
      await this.fileOrganizer.createSummaryReport(results);

      // Generate error report if there were errors
      if (this.errorHandler.errors.length > 0) {
        await this.errorHandler.generateErrorReport();
      }

      // Get statistics
      const stats = await this.fileOrganizer.getStatistics();
      const progress = this.progressTracker.getProgress();

      // Display final summary
      logDivider('SUMMARY');
      console.log(chalk.green(`✓ Successfully processed: ${progress.successful} songs`));
      if (progress.failed > 0) {
        console.log(chalk.red(`✗ Failed: ${progress.failed} songs`));
      }
      console.log(`Total time: ${progress.elapsedTime}`);
      console.log(`Output directory: ${this.fileOrganizer.baseOutputPath}`);

      if (stats) {
        console.log(`Total size: ${stats.totalSizeFormatted}`);
      }

      logger.info('Scraping completed successfully!');

    } catch (error) {
      logger.error('Scraper failed:', error);
      throw error;

    } finally {
      // Cleanup
      await this.cleanup();
    }
  }

  /**
   * Cleanup resources
   */
  async cleanup() {
    try {
      logger.info('Cleaning up...');

      // Clean up downloader temp files
      if (this.downloader) {
        await this.downloader.cleanup();
      }

      // Clean up empty folders
      await this.fileOrganizer.cleanupEmptyFolders();

      // Close browser
      await this.authenticator.close();
      await this.authenticator.cleanup();

      logger.info('Cleanup completed');

    } catch (error) {
      logger.error('Cleanup error:', error);
    }
  }
}

/**
 * CLI setup
 */
const argv = yargs(hideBin(process.argv))
  .usage('Usage: $0 [options]')
  .option('all-songs', {
    alias: 'a',
    type: 'boolean',
    description: 'Scrape all songs from library'
  })
  .option('playlist', {
    alias: 'p',
    type: 'string',
    description: 'Scrape specific playlist by name'
  })
  .option('output', {
    alias: 'o',
    type: 'string',
    default: './output',
    description: 'Output directory for downloaded files'
  })
  .option('resume', {
    alias: 'r',
    type: 'boolean',
    description: 'Resume from previous session'
  })
  .option('session-id', {
    alias: 's',
    type: 'string',
    description: 'Specific session ID to resume'
  })
  .option('use-profile', {
    type: 'boolean',
    default: true,
    description: 'Use existing browser profile for authentication'
  })
  .option('profile-path', {
    type: 'string',
    description: 'Path to browser profile directory'
  })
  .option('max-retries', {
    type: 'number',
    default: 3,
    description: 'Maximum retry attempts for failed operations'
  })
  .option('debug', {
    alias: 'd',
    type: 'boolean',
    description: 'Enable debug logging'
  })
  .help('h')
  .alias('h', 'help')
  .example('$0 --all-songs', 'Scrape all songs from library')
  .example('$0 --playlist "My Favorites"', 'Scrape specific playlist')
  .example('$0 --resume', 'Resume previous session')
  .epilogue('For more information, visit: https://github.com/yourusername/flowmusic-app-scraper')
  .argv;

// Set debug mode
if (argv.debug) {
  process.env.LOG_LEVEL = 'debug';
}

// Run scraper
async function main() {
  try {
    const scraper = new FlowMusicScraper(argv);
    await scraper.run();
    process.exit(0);

  } catch (error) {
    console.error(chalk.red('\n✗ Scraper failed:'), error.message);
    if (argv.debug) {
      console.error(error.stack);
    }
    process.exit(1);
  }
}

// Handle uncaught errors
process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception:', error);
  process.exit(1);
});

process.on('unhandledRejection', (error) => {
  logger.error('Unhandled rejection:', error);
  process.exit(1);
});

// Handle graceful shutdown
process.on('SIGINT', async () => {
  logger.info('\nReceived interrupt signal, shutting down gracefully...');
  // Save checkpoint before exit
  process.exit(0);
});

// Start the scraper
main();