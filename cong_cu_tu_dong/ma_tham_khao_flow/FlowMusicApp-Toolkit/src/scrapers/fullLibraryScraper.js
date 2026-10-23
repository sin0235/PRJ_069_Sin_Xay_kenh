/**
 * Full Library Scraper
 * Downloads complete library with progress tracking and resume capability
 */

import path from 'path';
import fs from 'fs-extra';
import { logger } from '../utils/logger.js';
import scraperConfig from '../../config/scraper.config.js';
import { CompleteSongDownloader } from '../downloaders/completeSongDownloader.js';

export class FullLibraryScraper {
  constructor(page, outputDir = './output') {
    this.page = page;
    this.outputDir = outputDir;
    this.downloader = new CompleteSongDownloader(page, outputDir);
    this.checkpointFile = path.join(scraperConfig.progress.checkpointDir, 'library-scrape.json');
    this.songs = [];
    this.downloadedSongs = new Set();
    this.failedSongs = [];
  }

  /**
   * Initialize scraper - load checkpoint if exists
   */
  async initialize() {
    await fs.ensureDir(scraperConfig.progress.checkpointDir);

    // Load checkpoint if exists
    if (await fs.pathExists(this.checkpointFile)) {
      try {
        const checkpoint = await fs.readJson(this.checkpointFile);
        this.downloadedSongs = new Set(checkpoint.downloadedSongs || []);
        this.failedSongs = checkpoint.failedSongs || [];
        logger.info(`Loaded checkpoint: ${this.downloadedSongs.size} songs already downloaded`);
      } catch (error) {
        logger.warn('Could not load checkpoint, starting fresh:', error.message);
      }
    }
  }

  /**
   * Save progress checkpoint
   */
  async saveCheckpoint() {
    try {
      await fs.writeJson(this.checkpointFile, {
        downloadedSongs: Array.from(this.downloadedSongs),
        failedSongs: this.failedSongs,
        totalSongs: this.songs.length,
        lastUpdated: new Date().toISOString()
      }, { spaces: 2 });
      logger.debug('Checkpoint saved');
    } catch (error) {
      logger.error('Failed to save checkpoint:', error.message);
    }
  }

  /**
   * Scrape all songs from library with infinite scroll
   */
  async scrapeAllSongs() {
    logger.info('Scraping all songs from library...');

    // Navigate to songs page
    await this.page.goto(scraperConfig.urls.songs, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await this.page.waitForTimeout(3000);

    const selectors = scraperConfig.selectors;
    const discoveredSongs = new Map();
    let previousCount = 0;
    let unchangedCount = 0;
    const maxUnchanged = scraperConfig.behavior.infiniteScroll.noNewContentThreshold;

    logger.info('Starting infinite scroll to load all songs...');

    // Infinite scroll to load all songs
    for (let i = 0; i < scraperConfig.behavior.infiniteScroll.maxScrollAttempts; i++) {
      // Extract current songs
      const currentSongs = await this.page.evaluate((selectors) => {
        const songElements = document.querySelectorAll(selectors.songCard);
        const songs = [];

        songElements.forEach((element, index) => {
          // Get song image which contains title in alt attribute
          const imageElement = element.querySelector('img[alt]') ||
                               element.querySelector('img');
          const title = imageElement?.alt?.trim() || `Song ${index + 1}`;

          // Get song link
          const linkElement = element.querySelector('a[href*="/song/"]');
          const url = linkElement?.href || '';

          // Extract song ID from URL
          let songId = null;
          if (url) {
            const match = url.match(/\/song\/([^\/]+)/);
            songId = match ? match[1] : null;
          }

          // Get duration if available
          const durationElement = element.querySelector('span.w-8.text-xs');
          const duration = durationElement?.textContent?.trim();

          if (songId) {
            songs.push({
              title,
              url,
              id: songId,
              duration
            });
          }
        });

        return songs;
      }, selectors);

      // Merge into cumulative set. The library view can be virtualized and not all
      // cards stay in the DOM at once, so we must preserve previously seen songs.
      currentSongs.forEach(song => {
        if (song.id) {
          discoveredSongs.set(song.id, song);
        }
      });

      this.songs = Array.from(discoveredSongs.values());

      logger.debug(`Scroll ${i + 1}: Found ${this.songs.length} unique songs`);

      // Check if new songs were loaded
      if (this.songs.length === previousCount) {
        unchangedCount++;
        if (unchangedCount >= maxUnchanged) {
          logger.info(`No new songs after ${maxUnchanged} attempts, stopping scroll`);
          break;
        }
      } else {
        unchangedCount = 0;
        previousCount = this.songs.length;
      }

      // Scroll the main container to its bottom to trigger lazy load.
      // The songs list lives inside <main> which has its own scroll context;
      // scrolling window.scrollBy() has no effect on it.
      await this.page.evaluate(() => {
        const main = document.querySelector('main');
        if (main) {
          main.scrollTop = main.scrollHeight;
        } else {
          window.scrollBy(0, window.innerHeight);
        }
      });

      // Wait for the next batch to load (network + render time)
      await this.page.waitForTimeout(scraperConfig.behavior.delays.afterScroll);
    }

    logger.info(`✓ Found ${this.songs.length} total songs in library view`);
    return this.songs;
  }

  /**
   * Scrape all songs from every session via the "Toggle session songs" panel.
   * Sessions are listed in the sidebar nav. Each session panel exposes /song/ links.
   */
  async scrapeAllSessionSongs() {
    logger.info('Collecting session URLs from sidebar...');

    // Collect all session links from the sidebar (any page will have the nav)
    const sessionUrls = await this.page.evaluate(() => {
      const links = document.querySelectorAll('nav a[href*="/session/"]');
      return Array.from(links).map(a => ({ href: a.href, text: a.textContent?.trim() }));
    });

    logger.info(`Found ${sessionUrls.length} sessions in sidebar`);

    const sessionSongs = new Map();

    for (let i = 0; i < sessionUrls.length; i++) {
      const session = sessionUrls[i];
      logger.info(`[${i + 1}/${sessionUrls.length}] Scraping session: ${session.text}`);

      try {
        await this.page.goto(session.href, { waitUntil: 'domcontentloaded', timeout: 60000 });
        await this.page.waitForTimeout(3000);

        // Click "Toggle session songs" button to open the songs panel
        const toggled = await this.page.evaluate(() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const btn = buttons.find(b =>
            b.getAttribute('aria-label')?.toLowerCase().includes('session songs') ||
            b.title?.toLowerCase().includes('session songs')
          );
          if (btn) { btn.click(); return true; }
          return false;
        });

        if (!toggled) {
          // Try by mouse click using coordinates
          const coords = await this.page.evaluate(() => {
            const buttons = Array.from(document.querySelectorAll('main button, header button'));
            // The "Toggle session songs" button is typically the 2nd icon button in the session header
            // It's near a "Toggle compose panel" button
            for (const btn of buttons) {
              const label = btn.getAttribute('aria-label') || btn.getAttribute('title') || '';
              if (label.toLowerCase().includes('song') || label.toLowerCase().includes('list')) {
                const rect = btn.getBoundingClientRect();
                return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
              }
            }
            return null;
          });
          if (coords) {
            await this.page.mouse.click(coords.x, coords.y);
          }
        }

        await this.page.waitForTimeout(2000);

        // Extract song links from the opened panel
        const songs = await this.page.evaluate(() => {
          const links = Array.from(document.querySelectorAll('a[href*="/song/"]'));
          const results = [];
          const seen = new Set();
          for (const a of links) {
            const url = a.href;
            const match = url.match(/\/song\/([a-f0-9-]{36})/);
            if (!match || seen.has(match[1])) continue;
            seen.add(match[1]);

            // Try to get title from heading, alt text, or aria-label
            const heading = a.querySelector('h4, h3, h2, [class*="title"]');
            const img = a.querySelector('img[alt]');
            const title = heading?.textContent?.trim() ||
                          img?.alt?.trim() ||
                          a.textContent?.trim() ||
                          a.getAttribute('aria-label') || '';

            results.push({ url, id: match[1], title: title || `Song ${match[1].slice(0, 8)}` });
          }
          return results;
        });

        logger.info(`  → ${songs.length} songs found in session`);
        songs.forEach(s => sessionSongs.set(s.id, s));

      } catch (err) {
        logger.warn(`  ✗ Failed to scrape session ${session.text}: ${err.message}`);
      }
    }

    const result = Array.from(sessionSongs.values());
    logger.info(`✓ Found ${result.length} unique songs across all sessions`);
    return result;
  }

  /**
   * Scrape all songs from a collection URL (playlist/project).
   * Returns { name, songs } where songs is an array of { id, url, title }.
   */
  async scrapeCollectionByUrl(collectionUrl, collectionType = 'playlist') {
    logger.info(`Navigating to ${collectionType}: ${collectionUrl}`);

    await this.page.goto(collectionUrl, {
      waitUntil: 'domcontentloaded',
      timeout: 60000
    });
    await this.page.waitForTimeout(3000);

    const defaultName = collectionType === 'project' ? 'Project' : 'Playlist';

    // Extract collection name from document.title or page elements.
    const collectionName = await this.page.evaluate((defaultName) => {
      // document.title format: "Name by Creator" or "Name | FlowMusic"
      const rawTitle = document.title?.trim() || '';
      const byStripped = rawTitle.replace(/\s+by\s+.+$/, '').trim();
      const cleaned = byStripped.replace(/\s*[|–—]\s*.*$/, '').trim();
      if (cleaned && cleaned.toLowerCase() !== 'flowmusic' && cleaned.length > 0) {
        return cleaned;
      }

      const main = document.querySelector('main');

      // Use the first heading in DOM order (h1, h2, or h3) — this reliably
      // returns the collection title before any sub-section headings.
      const firstHeading = main?.querySelector('h1, h2, h3')?.textContent?.trim();
      if (firstHeading && firstHeading.toLowerCase() !== 'flowmusic') return firstHeading;

      // Last resort: first non-generic cover art image alt text.
      const genericArtRegex = /^(playlist|project)\s+artwork$/i;
      const images = main ? Array.from(main.querySelectorAll('img[alt]:not([alt=""])')) : [];
      const coverImg = images.find(img => !genericArtRegex.test(img.alt.trim()));
      if (coverImg?.alt) return coverImg.alt.trim();

      return defaultName;
    }, defaultName);
    logger.info(`${collectionType.charAt(0).toUpperCase() + collectionType.slice(1)}: "${collectionName}"`);

    const songs = new Map();
    let previousCount = 0;
    let unchangedCount = 0;
    const maxUnchanged = scraperConfig.behavior.infiniteScroll.noNewContentThreshold;
    const maxScrollAttempts = 200; // Large collections can have 700+ songs

    for (let i = 0; i < maxScrollAttempts; i++) {
      const currentSongs = await this.page.evaluate(() => {
        const links = Array.from(document.querySelectorAll('a[href*="/song/"]'));
        const results = [];
        const seen = new Set();
        for (const a of links) {
          const url = a.href;
          const match = url.match(/\/song\/([a-f0-9-]{36})/);
          if (!match || seen.has(match[1])) continue;
          seen.add(match[1]);
          const heading = a.querySelector('h4, h3, h2, [class*="title"]');
          const img = a.querySelector('img[alt]');
          const title = heading?.textContent?.trim() ||
                        img?.alt?.trim() ||
                        a.textContent?.trim() || '';
          results.push({ url, id: match[1], title: title || `Song ${match[1].slice(0, 8)}` });
        }
        return results;
      });

      currentSongs.forEach(s => songs.set(s.id, s));
      logger.debug(`Scroll ${i + 1}: ${songs.size} unique songs`);

      if (songs.size === previousCount) {
        unchangedCount++;
        if (unchangedCount >= maxUnchanged) {
          logger.info(`No new songs after ${maxUnchanged} attempts, stopping scroll`);
          break;
        }
      } else {
        unchangedCount = 0;
        previousCount = songs.size;
      }

      await this.page.evaluate(() => {
        // On playlist pages <main> scrolls; on project pages a flex div scrolls instead.
        const main = document.querySelector('main');
        const mainStyle = main ? window.getComputedStyle(main).overflowY : '';
        if (main && mainStyle !== 'visible' && mainStyle !== 'hidden') {
          main.scrollTop = main.scrollHeight;
        } else {
          // Find the tallest scrollable container (excludes narrow sidebars)
          const container = Array.from(document.querySelectorAll('div'))
            .filter(el => {
              const s = window.getComputedStyle(el);
              return (s.overflowY === 'auto' || s.overflowY === 'scroll') &&
                     el.scrollHeight > el.clientHeight + 100 &&
                     el.clientWidth > 400;
            })
            .sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
          if (container) {
            container.scrollTop = container.scrollHeight;
          } else {
            window.scrollBy(0, window.innerHeight);
          }
        }
      });

      await this.page.waitForTimeout(scraperConfig.behavior.delays.afterScroll);
    }

    const result = Array.from(songs.values());
    logger.info(`✓ Found ${result.length} songs in ${collectionType} "${collectionName}"`);
    return { name: collectionName, songs: result };
  }

  /**
   * Scrape all songs from a specific playlist URL.
   */
  async scrapePlaylistByUrl(playlistUrl) {
    return this.scrapeCollectionByUrl(playlistUrl, 'playlist');
  }

  /**
   * Scrape all songs from a specific project URL.
   */
  async scrapeProjectByUrl(projectUrl) {
    return this.scrapeCollectionByUrl(projectUrl, 'project');
  }

  /**
   * Download a specific list of songs directly (no scraping step).
   * Accepts an array of { id, url, title } objects (title is optional).
   * Also accepts plain URL strings: extracts id from /song/<uuid> path.
   * Skips songs already in the checkpoint; pass reset=true to force re-download.
   */
  async downloadGivenSongs(songs, options = {}) {
    const { format = 'mp3', includeStems = false, reset = false } = options;

    await this.initialize();

    if (reset) {
      this.downloadedSongs.clear();
      this.failedSongs = [];
    }

    // Normalise entries — accept strings (plain URLs) or objects
    const normalised = songs.map(entry => {
      if (typeof entry === 'string') {
        const match = entry.match(/\/song\/([a-f0-9-]{36})/i);
        const id = match ? match[1] : entry;
        return { id, url: entry, title: id };
      }
      const { id, url, title } = entry;
      const resolvedId = id || (url || '').match(/\/song\/([a-f0-9-]{36})/i)?.[1] || url;
      return { id: resolvedId, url: url || `https://www.flowmusic.app/song/${resolvedId}`, title: title || resolvedId };
    });

    logger.info(`Downloading ${normalised.length} specified songs (${this.downloadedSongs.size} in checkpoint)`);
    logger.info(`Format: ${format.toUpperCase()}`);

    const results = { successful: 0, failed: 0, skipped: 0, total: normalised.length };

    for (let i = 0; i < normalised.length; i++) {
      const song = normalised[i];
      const progress = `[${i + 1}/${normalised.length}]`;

      if (this.downloadedSongs.has(song.id)) {
        logger.info(`${progress} Skipping (already downloaded): ${song.title}`);
        results.skipped++;
        continue;
      }

      logger.info(`${progress} Downloading: ${song.title}`);

      try {
        const result = await this.downloader.downloadSong(song, { format, includeStems });

        if (result.success) {
          this.downloadedSongs.add(song.id);
          if (result.skipped) {
            results.skipped++;
          } else {
            results.successful++;
            logger.info(`${progress} ✓ Success: ${song.title}`);
          }
        } else {
          this.failedSongs.push({ song, error: result.error, timestamp: new Date().toISOString() });
          results.failed++;
          logger.error(`${progress} ✗ Failed: ${song.title} - ${result.error}`);
        }

        await this.saveCheckpoint();
        await this.page.waitForTimeout(scraperConfig.behavior.delays.betweenSongs);

      } catch (error) {
        this.failedSongs.push({ song, error: error.message, timestamp: new Date().toISOString() });
        results.failed++;
        logger.error(`${progress} ✗ Exception: ${song.title}`, error);
        if (scraperConfig.progress.screenshotOnError) {
          await this.page.screenshot({ path: path.join('logs', `error-${song.id}.png`) }).catch(() => {});
        }
      }
    }

    await this.saveCheckpoint();
    return results;
  }

  /**
   * Download all songs from library
   */
  async downloadAllSongs(options = {}) {
    const {
      format = 'mp3',
      includeStems = false,
      startIndex = 0,
      maxSongs = null,
      startId = null,
      endId = null
    } = options;

    await this.initialize();

    // Scrape all songs if not already done
    if (this.songs.length === 0) {
      // Get songs from Library view
      const librarySongs = await this.scrapeAllSongs();

      // Also get songs from all sessions (these are the bulk of the library)
      const sessionSongs = await this.scrapeAllSessionSongs();

      // Merge: sessions may have songs not in Library view
      const merged = new Map();
      librarySongs.forEach(s => merged.set(s.id, s));
      sessionSongs.forEach(s => { if (!merged.has(s.id)) merged.set(s.id, s); });
      this.songs = Array.from(merged.values());
      logger.info(`Total unique songs (library + sessions): ${this.songs.length}`);
    }

    // Filter by ID range if specified
    let songsToDownload = this.songs;

    if (startId || endId) {
      const startIdx = startId ? this.songs.findIndex(s => s.id === startId) : 0;
      const endIdx = endId ? this.songs.findIndex(s => s.id === endId) : this.songs.length - 1;

      if (startId && startIdx === -1) {
        throw new Error(`Start song ID not found: ${startId}`);
      }
      if (endId && endIdx === -1) {
        throw new Error(`End song ID not found: ${endId}`);
      }
      if (startIdx > endIdx) {
        throw new Error(`Invalid range: start ID appears after end ID (${startId} → ${endId})`);
      }

      songsToDownload = this.songs.slice(startIdx, endIdx + 1);
      logger.info(`Filtering by ID range: ${startId || 'start'} → ${endId || 'end'}`);
      logger.info(`Range includes ${songsToDownload.length} songs (positions ${startIdx + 1}-${endIdx + 1})`);
    } else if (maxSongs) {
      songsToDownload = this.songs.slice(startIndex, startIndex + maxSongs);
    } else {
      songsToDownload = this.songs.slice(startIndex);
    }

    logger.info(`Starting download of ${songsToDownload.length} songs...`);
    logger.info(`Format: ${format.toUpperCase()}`);
    logger.info(`Include stems: ${includeStems ? 'Yes' : 'No'}`);
    logger.info(`Already downloaded: ${this.downloadedSongs.size} songs`);

    const results = {
      successful: 0,
      failed: 0,
      skipped: 0,
      total: songsToDownload.length
    };

    // Download each song
    for (let i = 0; i < songsToDownload.length; i++) {
      const song = songsToDownload[i];
      const progress = `[${i + 1}/${songsToDownload.length}]`;

      // Skip if already downloaded
      if (this.downloadedSongs.has(song.id)) {
        logger.info(`${progress} Skipping (already downloaded): ${song.title}`);
        results.skipped++;
        continue;
      }

      logger.info(`${progress} Downloading: ${song.title}`);

      try {
        const result = await this.downloader.downloadSong(song, { format, includeStems });

        if (result.success) {
          this.downloadedSongs.add(song.id);

          if (result.skipped) {
            // Song was skipped (file already exists with same ID)
            results.skipped++;
            // Already logged by downloader
          } else {
            // Song was successfully downloaded
            results.successful++;
            logger.info(`${progress} ✓ Success: ${song.title}`);
          }
        } else {
          this.failedSongs.push({
            song,
            error: result.error,
            timestamp: new Date().toISOString()
          });
          results.failed++;
          logger.error(`${progress} ✗ Failed: ${song.title} - ${result.error}`);
        }

        // Save checkpoint periodically
        if ((i + 1) % scraperConfig.progress.checkpointInterval === 0) {
          await this.saveCheckpoint();
        }

        // Delay between downloads
        await this.page.waitForTimeout(scraperConfig.behavior.delays.betweenSongs);

      } catch (error) {
        this.failedSongs.push({
          song,
          error: error.message,
          timestamp: new Date().toISOString()
        });
        results.failed++;
        logger.error(`${progress} ✗ Exception: ${song.title}`, error);

        // Take error screenshot if enabled
        if (scraperConfig.progress.screenshotOnError) {
          const errorScreenshot = path.join('logs', `error-${song.id}.png`);
          await this.page.screenshot({ path: errorScreenshot }).catch(() => {});
        }
      }
    }

    // Final checkpoint save
    await this.saveCheckpoint();

    return results;
  }

  sanitizeCollectionName(name, fallbackName = 'Collection') {
    const safeName = (name || fallbackName).trim() || fallbackName;
    return safeName
      .replace(/[/\\:*?"<>|]/g, '-')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 100);
  }

  async downloadCollectionByUrl(collectionUrl, options = {}, collectionType = 'playlist') {
    const { format = 'mp3', includeStems = false, reset = false } = options;
    const uuidPattern = new RegExp(`\\/${collectionType}\\/([a-f0-9-]{36})`, 'i');

    // Extract collection UUID for checkpoint filename
    const uuidMatch = collectionUrl.match(uuidPattern);
    if (!uuidMatch) {
      throw new Error(`Invalid ${collectionType} URL: ${collectionUrl}`);
    }
    const collectionUuid = uuidMatch[1];

    // Use per-collection checkpoint file
    this.checkpointFile = path.join(scraperConfig.progress.checkpointDir, `${collectionType}-${collectionUuid}.json`);

    if (reset) {
      if (await fs.pathExists(this.checkpointFile)) {
        await fs.remove(this.checkpointFile);
      }
      this.downloadedSongs.clear();
      this.failedSongs = [];
    }

    await this.initialize();

    const { name: collectionName, songs } = await this.scrapeCollectionByUrl(collectionUrl, collectionType);
    const sanitizedName = this.sanitizeCollectionName(
      collectionName,
      collectionType === 'project' ? 'Project' : 'Playlist'
    );

    // Create collection-specific output subdirectory
    const collectionOutputDir = path.join(this.outputDir, sanitizedName);
    await fs.ensureDir(collectionOutputDir);
    logger.info(`Output directory: ${collectionOutputDir}`);

    // Create a downloader scoped to the collection folder
    const { CompleteSongDownloader } = await import('../downloaders/completeSongDownloader.js');
    const downloader = new CompleteSongDownloader(this.page, collectionOutputDir);

    this.songs = songs;

    logger.info(`Starting download of ${songs.length} songs from ${collectionType} "${collectionName}"...`);
    logger.info(`Format: ${format.toUpperCase()}`);
    logger.info(`Include stems: ${includeStems ? 'Yes' : 'No'}`);
    logger.info(`Already downloaded: ${this.downloadedSongs.size} songs`);

    const results = {
      successful: 0,
      failed: 0,
      skipped: 0,
      total: songs.length,
      collectionType,
      collectionName
    };

    if (collectionType === 'playlist') {
      results.playlistName = collectionName;
    } else if (collectionType === 'project') {
      results.projectName = collectionName;
    }

    for (let i = 0; i < songs.length; i++) {
      const song = songs[i];
      const progress = `[${i + 1}/${songs.length}]`;

      if (this.downloadedSongs.has(song.id)) {
        logger.info(`${progress} Skipping (already downloaded): ${song.title}`);
        results.skipped++;
        continue;
      }

      logger.info(`${progress} Downloading: ${song.title}`);

      try {
        const result = await downloader.downloadSong(song, { format, includeStems });

        if (result.success) {
          this.downloadedSongs.add(song.id);
          if (result.skipped) {
            results.skipped++;
          } else {
            results.successful++;
            logger.info(`${progress} ✓ Success: ${song.title}`);
          }
        } else {
          this.failedSongs.push({ song, error: result.error, timestamp: new Date().toISOString() });
          results.failed++;
          logger.error(`${progress} ✗ Failed: ${song.title} - ${result.error}`);
        }

        if ((i + 1) % scraperConfig.progress.checkpointInterval === 0) {
          await this.saveCheckpoint();
        }

        await this.page.waitForTimeout(scraperConfig.behavior.delays.betweenSongs);

      } catch (error) {
        this.failedSongs.push({ song, error: error.message, timestamp: new Date().toISOString() });
        results.failed++;
        logger.error(`${progress} ✗ Exception: ${song.title}`, error);

        if (scraperConfig.progress.screenshotOnError) {
          const errorScreenshot = path.join('logs', `error-${song.id}.png`);
          await this.page.screenshot({ path: errorScreenshot }).catch(() => {});
        }
      }
    }

    await this.saveCheckpoint();
    return results;
  }

  /**
   * Download all songs from a specific playlist URL.
   * Songs are saved to {outputDir}/{playlistName}/.
   */
  async downloadPlaylist(playlistUrl, options = {}) {
    return this.downloadCollectionByUrl(playlistUrl, options, 'playlist');
  }

  /**
   * Download all songs from a specific project URL.
   * Songs are saved to {outputDir}/{projectName}/.
   */
  async downloadProject(projectUrl, options = {}) {
    return this.downloadCollectionByUrl(projectUrl, options, 'project');
  }

  /**
   * Generate summary report
   */
  async generateReport() {
    const report = {
      totalSongsFound: this.songs.length,
      downloaded: this.downloadedSongs.size,
      failed: this.failedSongs.length,
      remaining: this.songs.length - this.downloadedSongs.size - this.failedSongs.length,
      failedSongs: this.failedSongs,
      timestamp: new Date().toISOString()
    };

    const reportPath = path.join(scraperConfig.progress.checkpointDir, 'scrape-report.json');
    await fs.writeJson(reportPath, report, { spaces: 2 });

    logger.info('\n═══════════════════════════════════════════════════');
    logger.info('            SCRAPING SUMMARY');
    logger.info('═══════════════════════════════════════════════════');
    logger.info(`Total songs found: ${report.totalSongsFound}`);
    logger.info(`✓ Downloaded: ${report.downloaded}`);
    logger.info(`✗ Failed: ${report.failed}`);
    logger.info(`⏳ Remaining: ${report.remaining}`);
    logger.info(`\nReport saved: ${reportPath}`);
    logger.info('═══════════════════════════════════════════════════\n');

    if (this.failedSongs.length > 0) {
      logger.warn('\nFailed songs:');
      this.failedSongs.forEach(({ song, error }) => {
        logger.warn(`  - ${song.title}: ${error}`);
      });
    }

    return report;
  }

  /**
   * Reset checkpoint (start fresh)
   */
  async resetCheckpoint() {
    if (await fs.pathExists(this.checkpointFile)) {
      await fs.remove(this.checkpointFile);
      logger.info('Checkpoint reset');
    }
    this.downloadedSongs.clear();
    this.failedSongs = [];
  }
}

export default FullLibraryScraper;
