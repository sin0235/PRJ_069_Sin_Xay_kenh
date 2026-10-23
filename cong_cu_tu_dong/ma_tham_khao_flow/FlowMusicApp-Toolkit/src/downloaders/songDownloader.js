/**
 * Song Download Manager
 * Handles downloading of MP3, WAV, and cover art files
 */

import path from 'path';
import fs from 'fs-extra';
import { PQueue } from 'p-queue';
import scraperConfig from '../../config/scraper.config.js';
import browserConfig from '../../config/browser.config.js';
import { logger } from '../utils/logger.js';

export class SongDownloader {
  constructor(page, context) {
    this.page = page;
    this.context = context;
    this.downloadQueue = new PQueue({
      concurrency: scraperConfig.behavior.downloads.concurrent
    });
    this.downloads = new Map();
    this.downloadPath = path.resolve('./downloads-temp');
  }

  /**
   * Initialize download handler
   */
  async initialize() {
    try {
      // Ensure download directory exists
      await fs.ensureDir(this.downloadPath);

      // Set up download path for the browser context
      await this.page._client().send('Page.setDownloadBehavior', {
        behavior: 'allow',
        downloadPath: this.downloadPath
      });

      // Listen for download events
      this.page.on('download', this.handleDownload.bind(this));

      logger.debug('Download manager initialized');
      return true;

    } catch (error) {
      logger.error('Failed to initialize download manager:', error);
      return false;
    }
  }

  /**
   * Download all assets for a song
   */
  async downloadSongAssets(song, outputPath) {
    try {
      logger.info(`Downloading assets for: ${song.title}`);

      const results = {
        song: song,
        audio: null,
        cover: null,
        success: false,
        errors: []
      };

      // Ensure output directory exists
      await fs.ensureDir(outputPath);

      // Open song menu
      const menuOpened = await this.openMenu();
      if (!menuOpened) {
        throw new Error('Failed to open song menu');
      }

      // Download audio (MP3 or WAV)
      const audioResult = await this.downloadAudio(outputPath);
      if (audioResult.success) {
        results.audio = audioResult.file;
      } else {
        results.errors.push(audioResult.error);
      }

      // Close and reopen menu for next action
      await this.closeMenu();
      await this.page.waitForTimeout(1000);
      await this.openMenu();

      // Download cover art
      const coverResult = await this.downloadCover(outputPath);
      if (coverResult.success) {
        results.cover = coverResult.file;
      } else {
        results.errors.push(coverResult.error);
      }

      // Close menu
      await this.closeMenu();

      results.success = results.audio !== null;
      return results;

    } catch (error) {
      logger.error(`Failed to download assets for ${song.title}:`, error);
      return {
        song: song,
        audio: null,
        cover: null,
        success: false,
        errors: [error.message]
      };
    }
  }

  /**
   * Download audio file (MP3 or WAV)
   */
  async downloadAudio(outputPath) {
    try {
      logger.debug('Downloading audio file...');

      // Try MP3 first
      let downloadStarted = await this.clickDownloadOption('MP3');

      // If MP3 not available, try WAV
      if (!downloadStarted) {
        logger.debug('MP3 not available, trying WAV...');
        downloadStarted = await this.clickDownloadOption('WAV');
      }

      if (!downloadStarted) {
        throw new Error('No audio download option available');
      }

      // Wait for download to complete
      const downloadedFile = await this.waitForDownload('audio', 120000);

      if (downloadedFile) {
        // Move and rename file
        const extension = path.extname(downloadedFile);
        const newFileName = `audio${extension}`;
        const newPath = path.join(outputPath, newFileName);

        await fs.move(downloadedFile, newPath, { overwrite: true });
        logger.debug(`Audio saved: ${newPath}`);

        return {
          success: true,
          file: newPath
        };
      }

      throw new Error('Audio download failed - timeout');

    } catch (error) {
      logger.error('Failed to download audio:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Download cover art
   */
  async downloadCover(outputPath) {
    try {
      logger.debug('Downloading cover art...');

      // First try to get cover URL directly from page
      const coverUrl = await this.getCoverUrlFromPage();

      if (coverUrl) {
        // Direct download from URL
        return await this.downloadFromUrl(coverUrl, outputPath, 'cover');
      }

      // Try menu option
      const downloadStarted = await this.clickDownloadOption('cover');

      if (!downloadStarted) {
        logger.warn('Cover download option not available');
        // Try to extract and save cover from page
        return await this.extractAndSaveCover(outputPath);
      }

      // Wait for download to complete
      const downloadedFile = await this.waitForDownload('image', 30000);

      if (downloadedFile) {
        // Move and rename file
        const extension = path.extname(downloadedFile);
        const newFileName = `cover${extension}`;
        const newPath = path.join(outputPath, newFileName);

        await fs.move(downloadedFile, newPath, { overwrite: true });
        logger.debug(`Cover saved: ${newPath}`);

        return {
          success: true,
          file: newPath
        };
      }

      throw new Error('Cover download failed - timeout');

    } catch (error) {
      logger.error('Failed to download cover:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Click a download option in the menu
   */
  async clickDownloadOption(type) {
    try {
      const selectors = {
        'MP3': [
          scraperConfig.selectors.downloadMP3,
          'button:has-text("Download MP3")',
          'a:has-text("Download MP3")',
          'button:has-text("MP3")'
        ],
        'WAV': [
          scraperConfig.selectors.downloadWAV,
          'button:has-text("Download WAV")',
          'a:has-text("Download WAV")',
          'button:has-text("WAV")'
        ],
        'cover': [
          scraperConfig.selectors.downloadCover,
          'button:has-text("Download cover")',
          'button:has-text("Download artwork")',
          'a:has-text("Download cover")',
          'button:has-text("Cover")'
        ]
      };

      const optionSelectors = selectors[type] || [];

      for (const selector of optionSelectors) {
        const element = await this.page.locator(selector).first();
        const exists = await element.count() > 0;

        if (exists && await element.isVisible()) {
          // Set up download promise before clicking
          const downloadPromise = this.page.waitForEvent('download', { timeout: 5000 })
            .catch(() => null);

          await element.click();
          await this.page.waitForTimeout(1000);

          // Check if download started
          const download = await downloadPromise;
          if (download) {
            // Store download reference
            this.downloads.set(type, download);
            logger.debug(`Download started for: ${type}`);
            return true;
          }
        }
      }

      logger.debug(`${type} download option not found`);
      return false;

    } catch (error) {
      logger.error(`Error clicking download option for ${type}:`, error);
      return false;
    }
  }

  /**
   * Wait for a download to complete
   */
  async waitForDownload(type, timeout = 60000) {
    try {
      const startTime = Date.now();

      // Check if we have a download reference
      const download = this.downloads.get(type);

      if (download) {
        // Wait for download to complete
        const filePath = await download.path();
        this.downloads.delete(type);
        return filePath;
      }

      // Poll download directory for new files
      while (Date.now() - startTime < timeout) {
        const files = await fs.readdir(this.downloadPath);

        // Look for files matching the type
        const matchingFiles = files.filter(file => {
          if (type === 'audio') {
            return file.endsWith('.mp3') || file.endsWith('.wav');
          } else if (type === 'image') {
            return file.endsWith('.png') || file.endsWith('.jpg') || file.endsWith('.jpeg');
          }
          return false;
        });

        if (matchingFiles.length > 0) {
          // Get the most recent file
          const filePaths = matchingFiles.map(f => path.join(this.downloadPath, f));
          const stats = await Promise.all(filePaths.map(f => fs.stat(f)));
          const mostRecent = filePaths.reduce((prev, curr, i) => {
            return stats[i].mtimeMs > (prev.mtime || 0)
              ? { path: curr, mtime: stats[i].mtimeMs }
              : prev;
          }, {});

          if (mostRecent.path) {
            // Check if file size is stable (download complete)
            const size1 = (await fs.stat(mostRecent.path)).size;
            await new Promise(resolve => setTimeout(resolve, 1000));
            const size2 = (await fs.stat(mostRecent.path)).size;

            if (size1 === size2 && size1 > 0) {
              return mostRecent.path;
            }
          }
        }

        await new Promise(resolve => setTimeout(resolve, 2000));
      }

      logger.warn(`Download timeout for ${type}`);
      return null;

    } catch (error) {
      logger.error(`Error waiting for download:`, error);
      return null;
    }
  }

  /**
   * Handle download event
   */
  handleDownload(download) {
    logger.debug('Download started:', download.url());

    // Track the download
    download.saveAs(path.join(this.downloadPath, download.suggestedFilename()))
      .then(() => {
        logger.debug('Download saved:', download.suggestedFilename());
      })
      .catch(error => {
        logger.error('Download save error:', error);
      });
  }

  /**
   * Get cover URL from page
   */
  async getCoverUrlFromPage() {
    try {
      const coverUrl = await this.page.evaluate(() => {
        const img = document.querySelector('img.song-cover, img.album-art, .song-image img');
        return img ? img.src : null;
      });

      return coverUrl;

    } catch (error) {
      logger.error('Error getting cover URL:', error);
      return null;
    }
  }

  /**
   * Download file from URL
   */
  async downloadFromUrl(url, outputPath, filename) {
    try {
      // Use page to download the image
      const response = await this.page.evaluate(async (imageUrl) => {
        const res = await fetch(imageUrl);
        const blob = await res.blob();
        return {
          data: Array.from(new Uint8Array(await blob.arrayBuffer())),
          contentType: res.headers.get('content-type')
        };
      }, url);

      // Determine file extension
      const extension = response.contentType?.includes('png') ? '.png' : '.jpg';
      const filePath = path.join(outputPath, `${filename}${extension}`);

      // Save file
      await fs.writeFile(filePath, Buffer.from(response.data));
      logger.debug(`File saved from URL: ${filePath}`);

      return {
        success: true,
        file: filePath
      };

    } catch (error) {
      logger.error('Failed to download from URL:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Extract and save cover image from page
   */
  async extractAndSaveCover(outputPath) {
    try {
      const coverData = await this.page.evaluate(() => {
        const img = document.querySelector('img.song-cover, img.album-art, .song-image img');
        if (!img || !img.src) return null;

        // If it's a data URL, return it directly
        if (img.src.startsWith('data:')) {
          return { dataUrl: img.src };
        }

        // Otherwise return the URL to fetch
        return { url: img.src };
      });

      if (!coverData) {
        throw new Error('No cover image found on page');
      }

      if (coverData.dataUrl) {
        // Save data URL directly
        const matches = coverData.dataUrl.match(/^data:image\/([a-z]+);base64,(.+)$/);
        if (matches) {
          const extension = matches[1];
          const data = matches[2];
          const filePath = path.join(outputPath, `cover.${extension}`);

          await fs.writeFile(filePath, Buffer.from(data, 'base64'));
          logger.debug(`Cover saved from data URL: ${filePath}`);

          return {
            success: true,
            file: filePath
          };
        }
      } else if (coverData.url) {
        // Download from URL
        return await this.downloadFromUrl(coverData.url, outputPath, 'cover');
      }

      throw new Error('Could not extract cover image');

    } catch (error) {
      logger.error('Failed to extract and save cover:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Open song menu
   */
  async openMenu() {
    try {
      const menuSelectors = [
        scraperConfig.selectors.menuButton,
        'button[aria-label*="menu"]',
        'button[aria-label*="More"]',
        'button:has-text("...")',
        'button.menu-button'
      ];

      for (const selector of menuSelectors) {
        const element = await this.page.locator(selector).first();
        if (await element.count() > 0 && await element.isVisible()) {
          await element.click();
          await this.page.waitForTimeout(1000);
          return true;
        }
      }

      return false;

    } catch (error) {
      logger.error('Error opening menu:', error);
      return false;
    }
  }

  /**
   * Close menu
   */
  async closeMenu() {
    try {
      // Click outside menu or press Escape
      await this.page.keyboard.press('Escape');
      await this.page.waitForTimeout(500);
      return true;

    } catch (error) {
      logger.error('Error closing menu:', error);
      return false;
    }
  }

  /**
   * Clean up temporary download directory
   */
  async cleanup() {
    try {
      await fs.remove(this.downloadPath);
      logger.debug('Download temp directory cleaned up');
      return true;

    } catch (error) {
      logger.error('Error cleaning up downloads:', error);
      return false;
    }
  }
}

export default SongDownloader;