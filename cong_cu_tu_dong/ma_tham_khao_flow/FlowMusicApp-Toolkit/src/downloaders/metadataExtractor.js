/**
 * Metadata Extractor
 * Extracts and formats song metadata, lyrics, and other information
 */

import * as cheerio from 'cheerio';
import fs from 'fs-extra';
import path from 'path';
import { logger } from '../utils/logger.js';

export class MetadataExtractor {
  constructor(page) {
    this.page = page;
  }

  /**
   * Extract all metadata from the current song page
   */
  async extractFullMetadata() {
    try {
      logger.debug('Extracting full metadata from song page...');

      // Get page HTML for detailed parsing
      const html = await this.page.content();
      const $ = cheerio.load(html);

      // Extract basic metadata
      const basicMetadata = await this.extractBasicMetadata($);

      // Extract technical metadata
      const technicalMetadata = await this.extractTechnicalMetadata($);

      // Extract lyrics
      const lyrics = await this.extractLyrics($);

      // Extract cover image URL
      const coverUrl = await this.extractCoverUrl($);

      // Extract social/engagement data
      const socialData = await this.extractSocialData($);

      // Extract creation/remix data
      const creationData = await this.extractCreationData($);

      // Combine all metadata
      const fullMetadata = {
        ...basicMetadata,
        technical: technicalMetadata,
        lyrics: lyrics,
        coverUrl: coverUrl,
        social: socialData,
        creation: creationData,
        extractedAt: new Date().toISOString(),
        pageUrl: this.page.url()
      };

      logger.debug('Metadata extraction complete');
      return fullMetadata;

    } catch (error) {
      logger.error('Error extracting metadata:', error);
      return null;
    }
  }

  /**
   * Extract basic song information
   */
  async extractBasicMetadata($) {
    try {
      const metadata = {};

      // Title variations
      metadata.title = $('h1.song-title').text().trim() ||
                      $('h1').first().text().trim() ||
                      $('[data-testid="song-title"]').text().trim() ||
                      $('.track-name').text().trim();

      // Artist/Creator
      metadata.artist = $('.artist-name').text().trim() ||
                       $('[data-testid="artist"]').text().trim() ||
                       $('.creator-name').text().trim() ||
                       $('.by-line').text().replace('by', '').trim();

      // Description
      metadata.description = $('.song-description').text().trim() ||
                           $('[data-testid="description"]').text().trim() ||
                           $('.track-description').text().trim();

      // Song ID
      metadata.songId = $('[data-song-id]').attr('data-song-id') ||
                       this.extractIdFromUrl(this.page.url());

      // Clean up empty values
      Object.keys(metadata).forEach(key => {
        if (!metadata[key] || metadata[key] === '') {
          delete metadata[key];
        }
      });

      return metadata;

    } catch (error) {
      logger.error('Error extracting basic metadata:', error);
      return {};
    }
  }

  /**
   * Extract technical music metadata
   */
  async extractTechnicalMetadata($) {
    try {
      const technical = {};

      // BPM (Beats Per Minute)
      const bpmText = $('[data-testid="bpm"]').text() ||
                     $('.bpm').text() ||
                     $('span:contains("BPM")').parent().text();
      technical.bpm = this.extractNumber(bpmText);

      // Key
      technical.key = $('[data-testid="key"]').text().trim() ||
                     $('.key').text().trim() ||
                     $('span:contains("Key")').next().text().trim();

      // Genre
      technical.genre = $('[data-testid="genre"]').text().trim() ||
                       $('.genre').text().trim() ||
                       $('span:contains("Genre")').next().text().trim();

      // Duration
      const durationText = $('[data-testid="duration"]').text() ||
                          $('.duration').text() ||
                          $('span:contains("Duration")').next().text();
      technical.duration = this.parseDuration(durationText);

      // Mood/Vibe
      technical.mood = $('.mood').text().trim() ||
                      $('[data-testid="mood"]').text().trim();

      // Instruments (if listed)
      const instruments = [];
      $('.instrument-tag, [data-testid="instrument"]').each((i, el) => {
        instruments.push($(el).text().trim());
      });
      if (instruments.length > 0) {
        technical.instruments = instruments;
      }

      // Clean up empty values
      Object.keys(technical).forEach(key => {
        if (!technical[key] || technical[key] === '') {
          delete technical[key];
        }
      });

      return technical;

    } catch (error) {
      logger.error('Error extracting technical metadata:', error);
      return {};
    }
  }

  /**
   * Extract lyrics from the page
   */
  async extractLyrics($) {
    try {
      // Multiple strategies for finding lyrics
      let lyrics = '';

      // Strategy 1: Direct lyrics container
      lyrics = $('.lyrics-container').text().trim() ||
              $('[data-testid="lyrics"]').text().trim() ||
              $('.song-lyrics').text().trim();

      // Strategy 2: Look for lyrics section
      if (!lyrics) {
        const lyricsSection = $('section:has(h2:contains("Lyrics"))').text();
        if (lyricsSection) {
          lyrics = lyricsSection.replace(/^.*?Lyrics/i, '').trim();
        }
      }

      // Strategy 3: Line-by-line lyrics
      if (!lyrics) {
        const lines = [];
        $('.lyrics-line, .lyric-line').each((i, el) => {
          lines.push($(el).text().trim());
        });
        if (lines.length > 0) {
          lyrics = lines.join('\n');
        }
      }

      // Clean up lyrics
      if (lyrics) {
        lyrics = lyrics
          .replace(/\s+/g, ' ')  // Normalize whitespace
          .replace(/\n{3,}/g, '\n\n')  // Max 2 newlines
          .trim();
      }

      return lyrics;

    } catch (error) {
      logger.error('Error extracting lyrics:', error);
      return '';
    }
  }

  /**
   * Extract cover image URL
   */
  async extractCoverUrl($) {
    try {
      // Try multiple selectors for cover image
      const coverUrl = $('img.song-cover').attr('src') ||
                      $('img.album-art').attr('src') ||
                      $('[data-testid="cover-image"]').attr('src') ||
                      $('.song-image img').attr('src') ||
                      $('meta[property="og:image"]').attr('content');

      // Convert relative URLs to absolute
      if (coverUrl && !coverUrl.startsWith('http')) {
        const baseUrl = new URL(this.page.url()).origin;
        return new URL(coverUrl, baseUrl).href;
      }

      return coverUrl || null;

    } catch (error) {
      logger.error('Error extracting cover URL:', error);
      return null;
    }
  }

  /**
   * Extract social/engagement data
   */
  async extractSocialData($) {
    try {
      const social = {};

      // Play count
      const playsText = $('.play-count').text() ||
                       $('[data-testid="plays"]').text() ||
                       $('span:contains("plays")').parent().text();
      social.plays = this.extractNumber(playsText);

      // Likes
      const likesText = $('.like-count').text() ||
                       $('[data-testid="likes"]').text() ||
                       $('span:contains("likes")').parent().text();
      social.likes = this.extractNumber(likesText);

      // Comments
      const commentsText = $('.comment-count').text() ||
                          $('[data-testid="comments"]').text();
      social.comments = this.extractNumber(commentsText);

      // Shares
      const sharesText = $('.share-count').text() ||
                        $('[data-testid="shares"]').text();
      social.shares = this.extractNumber(sharesText);

      // Clean up
      Object.keys(social).forEach(key => {
        if (!social[key] || social[key] === 0) {
          delete social[key];
        }
      });

      return social;

    } catch (error) {
      logger.error('Error extracting social data:', error);
      return {};
    }
  }

  /**
   * Extract creation and remix data
   */
  async extractCreationData($) {
    try {
      const creation = {};

      // Creation date
      const dateText = $('.created-date').text() ||
                      $('[data-testid="created"]').text() ||
                      $('span:contains("Created")').next().text();
      creation.createdAt = this.parseDate(dateText);

      // Remix information
      const remixOf = $('.remix-of').text().trim() ||
                     $('[data-testid="remix-source"]').text().trim();
      if (remixOf) {
        creation.remixOf = remixOf;
      }

      // AI model used (if displayed)
      const model = $('.ai-model').text().trim() ||
                   $('[data-testid="model"]').text().trim();
      if (model) {
        creation.aiModel = model;
      }

      // Prompt (if available)
      const prompt = $('.song-prompt').text().trim() ||
                    $('[data-testid="prompt"]').text().trim();
      if (prompt) {
        creation.prompt = prompt;
      }

      // Tags
      const tags = [];
      $('.tag, [data-testid="tag"]').each((i, el) => {
        const tag = $(el).text().trim();
        if (tag) tags.push(tag);
      });
      if (tags.length > 0) {
        creation.tags = tags;
      }

      return creation;

    } catch (error) {
      logger.error('Error extracting creation data:', error);
      return {};
    }
  }

  /**
   * Extract number from text
   */
  extractNumber(text) {
    if (!text) return null;
    const match = text.match(/[\d,]+/);
    if (match) {
      return parseInt(match[0].replace(/,/g, ''));
    }
    return null;
  }

  /**
   * Parse duration text to seconds
   */
  parseDuration(text) {
    if (!text) return null;

    // Match patterns like "3:45", "03:45", "3m 45s"
    const colonMatch = text.match(/(\d+):(\d+)/);
    if (colonMatch) {
      const minutes = parseInt(colonMatch[1]);
      const seconds = parseInt(colonMatch[2]);
      return {
        formatted: text.trim(),
        seconds: minutes * 60 + seconds
      };
    }

    const verboseMatch = text.match(/(\d+)m?\s*(\d+)s?/);
    if (verboseMatch) {
      const minutes = parseInt(verboseMatch[1]) || 0;
      const seconds = parseInt(verboseMatch[2]) || 0;
      return {
        formatted: `${minutes}:${seconds.toString().padStart(2, '0')}`,
        seconds: minutes * 60 + seconds
      };
    }

    return null;
  }

  /**
   * Parse date text
   */
  parseDate(text) {
    if (!text) return null;

    try {
      // Remove extra text like "Created on"
      const cleanText = text.replace(/created|on|at/gi, '').trim();
      const date = new Date(cleanText);

      if (!isNaN(date.getTime())) {
        return date.toISOString();
      }
    } catch (error) {
      logger.debug('Could not parse date:', text);
    }

    return text; // Return original text if parsing fails
  }

  /**
   * Extract ID from URL
   */
  extractIdFromUrl(url) {
    const match = url.match(/\/song\/([^\/\?]+)/);
    return match ? match[1] : null;
  }

  /**
   * Save metadata to JSON file
   */
  async saveMetadata(metadata, outputPath) {
    try {
      const metadataPath = path.join(outputPath, 'metadata.json');
      await fs.ensureDir(outputPath);
      await fs.writeJson(metadataPath, metadata, { spaces: 2 });
      logger.debug(`Metadata saved to: ${metadataPath}`);
      return true;

    } catch (error) {
      logger.error('Error saving metadata:', error);
      return false;
    }
  }

  /**
   * Save lyrics to text file
   */
  async saveLyrics(lyrics, outputPath) {
    try {
      if (!lyrics || lyrics.trim() === '') {
        logger.debug('No lyrics to save');
        return false;
      }

      const lyricsPath = path.join(outputPath, 'lyrics.txt');
      await fs.ensureDir(outputPath);
      await fs.writeFile(lyricsPath, lyrics, 'utf8');
      logger.debug(`Lyrics saved to: ${lyricsPath}`);
      return true;

    } catch (error) {
      logger.error('Error saving lyrics:', error);
      return false;
    }
  }
}

export default MetadataExtractor;