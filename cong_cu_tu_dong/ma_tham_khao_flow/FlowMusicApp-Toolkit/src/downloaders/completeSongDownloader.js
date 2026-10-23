/**
 * Complete Song Downloader
 * Downloads audio, cover art, and metadata for a song
 */

import path from 'path';
import fs from 'fs-extra';
import sanitize from 'sanitize-filename';
import { logger } from '../utils/logger.js';
import { enhanceTitle } from '../utils/titleEnhancer.js';
import { MetadataTagger } from '../utils/metadataTagger.js';
import scraperConfig from '../../config/scraper.config.js';

export class CompleteSongDownloader {
  constructor(page, outputDir = './output') {
    this.page = page;
    this.outputDir = outputDir;
  }

  /**
   * Download complete song package (audio + cover + metadata)
   */
  async downloadSong(song, options = {}) {
    const {
      format = 'mp3',  // mp3, wav, m4a, stems
      includeStems = false,
      includeVideo = false,
      customAlbum = null,  // Custom album name (overrides default)
      customArtist = null  // Custom artist name (overrides default)
    } = options;

    try {
      logger.info(`Starting download: ${song.title}`);

      // Navigate to song page if needed
      if (this.page.url() !== song.url) {
        await this.page.goto(song.url, {
          waitUntil: 'domcontentloaded',
          timeout: 60000
        });

        // Wait for images to load
        await this.page.waitForTimeout(3000);
      }

      // Extract complete metadata
      logger.debug('Extracting metadata...');
      const metadata = await this.extractMetadata(song);

      // Ensure output directory exists
      await fs.ensureDir(this.outputDir);

      // Get existing files to check for duplicates
      const existingFiles = await fs.readdir(this.outputDir);
      const existingJsonFiles = existingFiles
        .filter(f => f.endsWith('.json'))
        .map(f => f.replace('.json', ''));

      // Enhance and clean the title
      const enhancedTitle = enhanceTitle(metadata.title || song.title, metadata, existingJsonFiles);
      logger.debug(`Enhanced title: "${metadata.title}" → "${enhancedTitle}"`);

      // Create sanitized filename
      let sanitizedTitle = sanitize(enhancedTitle, { replacement: '-' });

      // Check for existing metadata with same file name
      let metadataPath = path.join(this.outputDir, `${sanitizedTitle}.json`);
      let existingMetadata = null;

      if (await fs.pathExists(metadataPath)) {
        // File exists - check if it's the same song
        try {
          const loadedMetadata = await fs.readJson(metadataPath);

          if (loadedMetadata.id === song.id) {
            existingMetadata = loadedMetadata;
          } else {
            // Different song with same title - make unique filename
            logger.debug(`Title collision detected: ${sanitizedTitle}`);

            // Append first 8 chars of song ID to make it unique
            const uniqueSuffix = song.id.substring(0, 8);
            sanitizedTitle = `${sanitizedTitle}-${uniqueSuffix}`;
            metadataPath = path.join(this.outputDir, `${sanitizedTitle}.json`);
            logger.debug(`Using unique filename: ${sanitizedTitle}`);
          }
        } catch (error) {
          // Error reading existing file - continue with original name
          logger.warn(`Could not read existing file: ${error.message}`);
        }
      }

      logger.debug(`Saving to: ${this.outputDir}`);

      const audioTargetPath = format === 'stems'
        ? null
        : path.join(this.outputDir, `${sanitizedTitle}.${format}`);
      const stemsTargetPath = path.join(this.outputDir, `${sanitizedTitle}-stems.zip`);
      const requiresAudio = format !== 'stems';
      const requiresStems = format === 'stems' || includeStems;

      // Reuse existing files when present.
      let audioPath = audioTargetPath && await fs.pathExists(audioTargetPath)
        ? audioTargetPath
        : null;
      let stemsPath = await fs.pathExists(stemsTargetPath)
        ? stemsTargetPath
        : null;
      let coverPath = await this.findExistingCoverPath(this.outputDir, sanitizedTitle, existingMetadata);

      const hasRequiredAudio = !requiresAudio || !!audioPath;
      const hasRequiredStems = !requiresStems || !!stemsPath;
      const hasCover = !!coverPath;

      if (existingMetadata && hasRequiredAudio && hasRequiredStems && hasCover) {
        logger.info(`⊘ Skipping (already downloaded): ${sanitizedTitle}`);
        return {
          success: true,
          title: metadata.title,
          skipped: true,
          files: {
            audio: audioPath,
            stems: stemsPath,
            cover: coverPath,
            metadata: metadataPath
          },
          metadata: existingMetadata
        };
      }

      // Download cover art only when missing.
      if (!coverPath) {
        logger.debug('Downloading cover art...');
        coverPath = await this.downloadCoverArt(this.outputDir, sanitizedTitle, metadata);
      } else {
        logger.debug(`Reusing existing cover art: ${path.basename(coverPath)}`);
      }

      // Download primary asset (audio format or stems ZIP) when missing.
      if (format === 'stems') {
        if (!stemsPath) {
          logger.debug('Downloading stems ZIP...');
          stemsPath = await this.downloadStems(this.outputDir, sanitizedTitle, { required: true });
        } else {
          logger.debug(`Reusing existing stems ZIP: ${path.basename(stemsPath)}`);
        }
      } else {
        if (!audioPath) {
          logger.debug(`Downloading ${format.toUpperCase()} audio...`);
          audioPath = await this.downloadAudio(this.outputDir, sanitizedTitle, format);
        } else {
          logger.debug(`Reusing existing ${format.toUpperCase()} audio: ${path.basename(audioPath)}`);
        }
      }

      // Optional stems add-on for standard audio formats
      if (includeStems && format !== 'stems' && !stemsPath) {
        logger.debug('Downloading optional stems ZIP...');
        stemsPath = await this.downloadStems(this.outputDir, sanitizedTitle, { required: false });
      }

      // Save metadata JSON (directly to output dir)
      const savedMetadata = {
        ...metadata,
        title: enhancedTitle, // Use enhanced title in metadata
        originalTitle: metadata.title, // Keep original for reference
        album: customAlbum || scraperConfig.metadata.defaultAlbum, // Use custom or default album
        artist: customArtist || metadata.author || scraperConfig.metadata.defaultArtist, // Use custom, extracted, or default artist
        files: {
          audio: audioPath ? path.basename(audioPath) : null,
          stems: stemsPath ? path.basename(stemsPath) : null,
          cover: coverPath ? path.basename(coverPath) : null
        },
        downloadedAt: new Date().toISOString()
      };
      await fs.writeJson(metadataPath, savedMetadata, { spaces: 2 });

      // Tag MP3 with metadata
      if (format === 'mp3' && audioPath) {
        logger.debug('Writing ID3 tags to MP3...');
        const tagResult = await MetadataTagger.tagMp3(audioPath, savedMetadata, coverPath);
        if (tagResult.success) {
          logger.debug(`✓ Tagged MP3 with ${tagResult.tagsWritten} metadata fields`);
        } else {
          logger.warn(`Failed to tag MP3: ${tagResult.error}`);
        }
      }

      logger.info(`✓ Complete download: ${sanitizedTitle}`);

      return {
        success: true,
        title: metadata.title,
        files: {
          audio: audioPath,
          stems: stemsPath,
          cover: coverPath,
          metadata: metadataPath
        },
        metadata
      };

    } catch (error) {
      logger.error(`Failed to download song: ${song.title}`, error);
      return {
        success: false,
        title: song.title,
        error: error.message
      };
    }
  }

  /**
   * Extract complete metadata from song page
   */
  async extractMetadata(song) {
    const metadata = await this.page.evaluate(() => {
      const data = {
        title: null,
        author: null,
        description: null,
        bpm: null,
        key: null,
        model: null,
        lyrics: null,
        coverUrl: null,
        duration: null
      };

      // Get page text for pattern matching
      const pageText = document.body.innerText;

      // Get title from heading
      const h1 = document.querySelector('h1');
      const h2Large = document.querySelector('h2.text-2xl, h2.text-3xl, h2.text-xl');
      data.title = (h1 || h2Large)?.textContent?.trim();

      // Fallback: extract title from page text if heading not found or is "Unknown"
      if (!data.title || data.title === 'Unknown' || data.title.length < 3) {
        // Pattern 1: "username time ago TITLE — subtitle, Key, BPM"
        let titleMatch = pageText.match(/ago\s+([^—,\n]+(?:\s*—\s*[^,\n]+)?)\s*,\s*[A-G][#b]?\s*(?:Major|Minor)/i);

        // Pattern 2: Just "TITLE, Key, BPM" (without subtitle)
        if (!titleMatch) {
          titleMatch = pageText.match(/\n([^,\n]{3,50})\s*,\s*[A-G][#b]?\s*(?:Major|Minor)\s*,\s*\d+\s*bpm/i);
        }

        // Pattern 3: Look for text between username and key that looks like a title
        if (!titleMatch) {
          titleMatch = pageText.match(/(?:ago|PUBLISH|REMIX)\s+([A-Z][^,\n]{2,50}?)\s*(?:—[^,\n]+?)?\s*,?\s*[A-G][#b]?\s*(?:Major|Minor)/i);
        }

        if (titleMatch) {
          data.title = titleMatch[1]
            .trim()
            .replace(/\s+/g, ' ')  // Normalize whitespace
            .replace(/^—\s*/, '')  // Remove leading em-dash
            .replace(/\s*—$/, ''); // Remove trailing em-dash
        }
      }

      // Get author (username)
      const authorLink = document.querySelector('a[href*="/profile/"]');
      data.author = authorLink?.textContent?.trim();

      // Extract BPM
      const bpmMatch = pageText.match(/(\d+)\s*bpm/i);
      if (bpmMatch) data.bpm = parseInt(bpmMatch[1]);

      // Extract Key
      const keyMatch = pageText.match(/([A-G][#b]?\s*(?:Major|Minor))/i);
      if (keyMatch) data.key = keyMatch[1];

      // Extract Model
      const modelMatch = pageText.match(/MODEL\s*([A-Z0-9\-\.]+)/i);
      if (modelMatch) data.model = modelMatch[1].trim();

      // Extract Lyrics - FlowMusic splits lyrics into individual word spans
      // Find the lyrics container with data-word-index spans
      const lyricsContainer = document.querySelector('div.mt-1 div.text-base');
      if (lyricsContainer) {
        const lyricsLines = [];
        let currentLine = [];

        // Get all child nodes (spans and br elements)
        const nodes = lyricsContainer.childNodes;

        for (const node of nodes) {
          if (node.nodeType === Node.ELEMENT_NODE) {
            if (node.tagName === 'SPAN' && node.hasAttribute('data-word-index')) {
              // Add the text content of this span
              const text = node.textContent?.trim();
              if (text) {
                currentLine.push(text);
              }
            } else if (node.tagName === 'BR') {
              // Line break - save current line and start new one
              if (currentLine.length > 0) {
                lyricsLines.push(currentLine.join(' '));
                currentLine = [];
              }
            }
          }
        }

        // Don't forget the last line
        if (currentLine.length > 0) {
          lyricsLines.push(currentLine.join(' '));
        }

        data.lyrics = lyricsLines.join('\n').trim();
      }

      // Fallback to regex if container not found
      if (!data.lyrics) {
        const lyricsMatch = pageText.match(/LYRICS\s*([^\n]+(?:\n(?!MODEL|SOUND)[^\n]+)*)/i);
        if (lyricsMatch) {
          data.lyrics = lyricsMatch[1].trim();
        }
      }

      // Get full SOUND description - extract only the actual description text
      // Look for the pattern after "SOUND" and before "MODEL", "LYRICS", or other uppercase headers
      const soundMatch = pageText.match(/SOUND\s+([^]+?)(?=\s+(?:MODEL|LYRICS|VIDEO|PUBLISH|REMIX|Share|Copy|$))/i);
      if (soundMatch) {
        // Clean up the description: remove extra whitespace and trim
        let desc = soundMatch[1]
          .trim()
          .replace(/\s+/g, ' ')  // Normalize whitespace
          .replace(/^\s*—\s*/, '') // Remove leading em-dash
          .replace(/\s*—\s*$/, ''); // Remove trailing em-dash

        // If description seems too long (>500 chars) or contains obvious navigation text,
        // try to extract just the relevant part
        if (desc.length > 500 || /(?:STARTER|UPGRADE|INVITES|ago\s+\w+)/i.test(desc)) {
          // Look for the actual description after common noise patterns
          const cleanMatch = desc.match(/(?:ago\s+[^,]+,\s+[^,]+,\s+\d+\s+bpm\s+\d+\s+\d+\s+)?(.+?)$/i);
          if (cleanMatch && cleanMatch[1].length > 20) {
            desc = cleanMatch[1].trim();
          }
        }

        data.description = desc;
      }

      // Get cover art URL from image
      // The song cover is typically a large square image near the video/player
      // Avoid profile pictures by looking for larger images
      const allImages = Array.from(document.querySelectorAll('img'));

      // Filter to find the song cover:
      // 1. Must be visible and reasonably large (>200px)
      // 2. Must be square or near-square (aspect ratio close to 1:1)
      // 3. Avoid profile images (usually smaller and in different locations)
      const coverCandidates = allImages.filter(img => {
        const rect = img.getBoundingClientRect();
        const width = rect.width;
        const height = rect.height;

        // Must be visible and large enough (song covers are usually 200px+)
        if (width < 200 || height < 200) return false;

        // Should be roughly square (aspect ratio between 0.9 and 1.1)
        const aspectRatio = width / height;
        if (aspectRatio < 0.9 || aspectRatio > 1.1) return false;

        // Avoid default profile images
        if (img.src.includes('default-profile-images')) return false;

        return true;
      });

      // Sort by size (largest first) and take the first one
      coverCandidates.sort((a, b) => {
        const aSize = a.getBoundingClientRect().width * a.getBoundingClientRect().height;
        const bSize = b.getBoundingClientRect().width * b.getBoundingClientRect().height;
        return bSize - aSize;
      });

      if (coverCandidates.length > 0) {
        data.coverUrl = coverCandidates[0].src;
      }

      // Try to get duration from page (populated later from audio file if 0:00)
      const durationSpan = document.querySelector('span.w-8.text-xs');
      const durationText = durationSpan?.textContent?.trim();
      if (durationText && durationText !== '0:00') {
        data.duration = durationText;
      }

      return data;
    });

    // Merge with original song data
    return {
      ...song,
      ...metadata,
      url: song.url,
      id: song.id
    };
  }

  async findExistingCoverPath(songFolder, baseName, existingMetadata = null) {
    const candidates = [];

    if (existingMetadata?.files?.cover) {
      candidates.push(path.join(songFolder, existingMetadata.files.cover));
    }

    for (const ext of ['png', 'jpg', 'jpeg', 'webp']) {
      candidates.push(path.join(songFolder, `${baseName}.${ext}`));
    }

    for (const candidate of candidates) {
      if (await fs.pathExists(candidate)) {
        return candidate;
      }
    }

    return null;
  }

  /**
   * Download cover art image
   */
  async downloadCoverArt(songFolder, baseName, metadata) {
    try {
      if (!metadata.coverUrl) {
        logger.warn('No cover art URL found');
        return null;
      }

      // Download the image
      const response = await this.page.context().request.get(metadata.coverUrl);
      const buffer = await response.body();

      // Determine extension from content-type or URL
      let ext = 'jpg';
      const contentType = response.headers()['content-type'];
      if (contentType?.includes('png')) ext = 'png';
      else if (contentType?.includes('webp')) ext = 'webp';
      else if (metadata.coverUrl.includes('.png')) ext = 'png';

      const coverPath = path.join(songFolder, `${baseName}.${ext}`);
      await fs.writeFile(coverPath, buffer);

      logger.debug(`✓ Cover art saved: ${baseName}.${ext}`);
      return coverPath;

    } catch (error) {
      logger.error('Failed to download cover art:', error);
      return null;
    }
  }

  async findFirstVisible(selectors, timeout = 2000) {
    for (const selector of selectors) {
      try {
        const locator = this.page.locator(selector).first();
        const isVisible = await locator.isVisible({ timeout }).catch(() => false);
        if (isVisible) {
          return locator;
        }
      } catch (error) {
        // Try next selector.
      }
    }
    return null;
  }

  async openDownloadSubmenu() {
    // Step 1: open the three-dots menu near Share.
    const btnCoords = await this.page.evaluate(() => {
      const main = document.querySelector('main');
      if (!main) return null;

      const buttons = Array.from(main.querySelectorAll('button'));
      const shareBtn = buttons.find(b => {
        const txt = b.textContent?.trim();
        const label = b.getAttribute('aria-label') || '';
        return txt === 'Share' || label === 'Share';
      });

      if (!shareBtn) return null;
      const shareIndex = buttons.indexOf(shareBtn);
      if (shareIndex >= 0 && shareIndex + 1 < buttons.length) {
        const moreBtn = buttons[shareIndex + 1];
        const rect = moreBtn.getBoundingClientRect();
        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
      }

      return null;
    });

    if (!btnCoords) {
      throw new Error('Menu button not found');
    }

    await this.page.mouse.click(btnCoords.x, btnCoords.y);
    await this.page.waitForTimeout(1200);

    // Step 2: click Download to open format submenu.
    const downloadItem = await this.findFirstVisible([
      '[role="menuitem"]:has-text("Download")',
      'menuitem:has-text("Download")',
      'button:has-text("Download")',
      'text=Download'
    ]);

    if (!downloadItem) {
      const visibleText = await this.page.evaluate(() => {
        const items = [];
        document.querySelectorAll('*').forEach(el => {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0 && rect.top > 150 && rect.top < 600) {
            const text = el.textContent?.trim();
            if (text && text.length > 2 && text.length < 50) {
              items.push(text);
            }
          }
        });
        return [...new Set(items)].slice(0, 20);
      });
      logger.error('Visible text when looking for Download:', visibleText);
      throw new Error('Download menu item not found');
    }

    await downloadItem.click();
    await this.page.waitForTimeout(1200);
  }

  /**
   * Download audio file (MP3, WAV, M4A)
   */
  async downloadAudio(songFolder, baseName, format) {
    try {
      if (format === 'stems') {
        throw new Error('downloadAudio does not support "stems" format');
      }

      await this.openDownloadSubmenu();

      const formatText = format.toUpperCase();
      const formatButton = await this.findFirstVisible([
        `button:has-text("${formatText}")`,
        `[role="menuitem"]:has-text("${formatText}")`,
        `text=${formatText}`
      ]);

      if (!formatButton) {
        throw new Error(`${formatText} format option not found`);
      }

      const downloadPromise = this.page.waitForEvent('download', { timeout: 60000 });
      await formatButton.click();
      const download = await downloadPromise;

      const audioPath = path.join(songFolder, `${baseName}.${format}`);
      await download.saveAs(audioPath);

      const stats = await fs.stat(audioPath);
      const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
      logger.debug(`✓ Audio saved: ${baseName}.${format} (${sizeMB} MB)`);
      return audioPath;

    } catch (error) {
      logger.error(`Failed to download ${format} audio:`, error);
      throw error;
    }
  }

  /**
   * Download stems ZIP (if available).
   */
  async downloadStems(songFolder, baseName, options = {}) {
    const { required = false } = options;

    try {
      await this.openDownloadSubmenu();

      const stemsButton = await this.findFirstVisible([
        'button:has-text("Get stems")',
        '[role="menuitem"]:has-text("Get stems")',
        'text=Get stems'
      ]);

      if (!stemsButton) {
        if (required) {
          throw new Error('Stems are not available for this song');
        }
        logger.info('Stems not available for this song');
        return null;
      }

      const downloadPromise = this.page.waitForEvent('download', { timeout: 60000 });
      await stemsButton.click();
      const download = await downloadPromise;

      const stemsPath = path.join(songFolder, `${baseName}-stems.zip`);
      await download.saveAs(stemsPath);

      const stats = await fs.stat(stemsPath);
      const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
      logger.debug(`✓ Stems saved: ${baseName}-stems.zip (${sizeMB} MB)`);
      return stemsPath;

    } catch (error) {
      if (required) {
        throw error;
      }
      logger.warn('Failed to download stems:', error.message);
      return null;
    }
  }
}

export default CompleteSongDownloader;
