/**
 * Infinite Scroll Handler
 * Manages automatic scrolling and dynamic content loading
 */

import scraperConfig from '../../config/scraper.config.js';
import { logger } from './logger.js';

export class InfiniteScrollHandler {
  constructor(page) {
    this.page = page;
    this.config = scraperConfig.behavior.infiniteScroll;
    this.previousHeight = 0;
    this.noNewContentCount = 0;
    this.scrollCount = 0;
    this.allItems = new Set();
  }

  /**
   * Main scroll method - scrolls until no new content loads
   */
  async scrollToEnd(itemSelector = null) {
    logger.info('Starting infinite scroll...');

    try {
      // Get initial page height
      this.previousHeight = await this.getPageHeight();

      // Initial item count if selector provided
      if (itemSelector) {
        const initialItems = await this.getUniqueItems(itemSelector);
        logger.info(`Initial items found: ${initialItems.size}`);
      }

      while (this.shouldContinueScrolling()) {
        await this.performScroll();

        // Check for new content
        const hasNewContent = await this.checkForNewContent(itemSelector);

        if (!hasNewContent) {
          this.noNewContentCount++;
          logger.debug(`No new content detected (attempt ${this.noNewContentCount}/${this.config.noNewContentThreshold})`);

          // Check for "Load More" button
          const loadMoreClicked = await this.checkAndClickLoadMore();
          if (loadMoreClicked) {
            this.noNewContentCount = 0; // Reset counter if button was clicked
            continue;
          }

        } else {
          this.noNewContentCount = 0; // Reset counter if new content found
        }

        // Stop if we've reached the threshold for no new content
        if (this.noNewContentCount >= this.config.noNewContentThreshold) {
          logger.info('Reached end of scrollable content');
          break;
        }

        // Wait between scrolls
        await this.page.waitForTimeout(this.config.checkInterval);
      }

      // Final item count
      if (itemSelector) {
        logger.info(`Total unique items found: ${this.allItems.size}`);
      }

      logger.info(`Scrolling completed after ${this.scrollCount} scrolls`);
      return Array.from(this.allItems);

    } catch (error) {
      logger.error('Error during infinite scroll:', error);
      throw error;
    }
  }

  /**
   * Perform a single scroll action
   */
  async performScroll() {
    try {
      this.scrollCount++;

      // Multiple scroll strategies for better compatibility
      await this.page.evaluate((distance) => {
        // Strategy 1: Scroll to bottom
        window.scrollTo(0, document.body.scrollHeight);

        // Strategy 2: Scroll by specific distance
        window.scrollBy(0, distance);

        // Strategy 3: Scroll element if it exists
        const scrollContainer = document.querySelector('.scroll-container, [data-infinite-scroll], main');
        if (scrollContainer) {
          scrollContainer.scrollTop = scrollContainer.scrollHeight;
        }
      }, this.config.scrollDistance);

      logger.debug(`Performed scroll #${this.scrollCount}`);

      // Wait for content to load
      await this.page.waitForTimeout(scraperConfig.behavior.delays.afterScroll);

    } catch (error) {
      logger.error('Error performing scroll:', error);
      throw error;
    }
  }

  /**
   * Check if new content has loaded
   */
  async checkForNewContent(itemSelector) {
    try {
      // Method 1: Check page height change
      const currentHeight = await this.getPageHeight();
      const heightChanged = currentHeight > this.previousHeight;

      if (heightChanged) {
        logger.debug(`Page height increased: ${this.previousHeight} -> ${currentHeight}`);
        this.previousHeight = currentHeight;
      }

      // Method 2: Check for new items if selector provided
      if (itemSelector) {
        const currentItems = await this.getUniqueItems(itemSelector);
        const newItemsCount = currentItems.size - this.allItems.size;

        if (newItemsCount > 0) {
          logger.debug(`Found ${newItemsCount} new items`);
          this.allItems = currentItems;
          return true;
        }
      }

      return heightChanged;

    } catch (error) {
      logger.error('Error checking for new content:', error);
      return false;
    }
  }

  /**
   * Get current page height
   */
  async getPageHeight() {
    try {
      return await this.page.evaluate(() => {
        return Math.max(
          document.body.scrollHeight,
          document.body.offsetHeight,
          document.documentElement.clientHeight,
          document.documentElement.scrollHeight,
          document.documentElement.offsetHeight
        );
      });
    } catch (error) {
      logger.error('Error getting page height:', error);
      return this.previousHeight;
    }
  }

  /**
   * Get unique items on the page
   */
  async getUniqueItems(selector) {
    try {
      const items = await this.page.evaluate((sel) => {
        const elements = document.querySelectorAll(sel);
        const uniqueItems = new Set();

        elements.forEach(el => {
          // Try to get unique identifier
          const id = el.dataset.id ||
                    el.getAttribute('href') ||
                    el.innerText?.trim() ||
                    el.innerHTML;
          if (id) {
            uniqueItems.add(id);
          }
        });

        return Array.from(uniqueItems);
      }, selector);

      return new Set(items);

    } catch (error) {
      logger.error('Error getting unique items:', error);
      return this.allItems;
    }
  }

  /**
   * Check for and click "Load More" button
   */
  async checkAndClickLoadMore() {
    try {
      const loadMoreSelector = scraperConfig.selectors.loadMoreButton;

      // Check if button exists and is visible
      const buttonExists = await this.page.locator(loadMoreSelector).count() > 0;

      if (buttonExists) {
        const button = this.page.locator(loadMoreSelector).first();
        const isVisible = await button.isVisible();

        if (isVisible) {
          logger.info('Found "Load More" button, clicking...');

          await button.click();
          await this.page.waitForTimeout(scraperConfig.behavior.delays.afterClick);

          // Wait for new content to start loading
          await this.page.waitForLoadState('networkidle', {
            timeout: 10000
          }).catch(() => {
            // Ignore timeout, content might load dynamically
          });

          return true;
        }
      }

      return false;

    } catch (error) {
      logger.debug('No load more button found or clickable');
      return false;
    }
  }

  /**
   * Check if we should continue scrolling
   */
  shouldContinueScrolling() {
    return this.scrollCount < this.config.maxScrollAttempts &&
           this.noNewContentCount < this.config.noNewContentThreshold;
  }

  /**
   * Scroll to a specific element
   */
  async scrollToElement(selector) {
    try {
      await this.page.evaluate((sel) => {
        const element = document.querySelector(sel);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, selector);

      await this.page.waitForTimeout(1000);
      logger.debug(`Scrolled to element: ${selector}`);

    } catch (error) {
      logger.error('Error scrolling to element:', error);
    }
  }

  /**
   * Get all loaded items after scrolling
   */
  async getAllItems(selector) {
    try {
      // Perform infinite scroll first
      await this.scrollToEnd(selector);

      // Get all items from the page
      const items = await this.page.evaluate((sel) => {
        const elements = document.querySelectorAll(sel);
        return Array.from(elements).map(el => {
          // Extract relevant data from each element
          return {
            text: el.innerText?.trim(),
            href: el.getAttribute('href') || el.querySelector('a')?.getAttribute('href'),
            id: el.dataset.id || el.id,
            html: el.outerHTML
          };
        });
      }, selector);

      logger.info(`Retrieved ${items.length} items after scrolling`);
      return items;

    } catch (error) {
      logger.error('Error getting all items:', error);
      return [];
    }
  }

  /**
   * Reset scroll handler state
   */
  reset() {
    this.previousHeight = 0;
    this.noNewContentCount = 0;
    this.scrollCount = 0;
    this.allItems = new Set();
    logger.debug('Scroll handler reset');
  }

  /**
   * Get scroll statistics
   */
  getStats() {
    return {
      scrollCount: this.scrollCount,
      itemsFound: this.allItems.size,
      currentHeight: this.previousHeight,
      noNewContentCount: this.noNewContentCount
    };
  }
}

/**
 * Factory function to create scroll handler
 */
export function createScrollHandler(page) {
  return new InfiniteScrollHandler(page);
}

/**
 * Utility function for simple infinite scroll
 */
export async function infiniteScroll(page, options = {}) {
  const handler = new InfiniteScrollHandler(page);
  return await handler.scrollToEnd(options.itemSelector);
}

export default InfiniteScrollHandler;