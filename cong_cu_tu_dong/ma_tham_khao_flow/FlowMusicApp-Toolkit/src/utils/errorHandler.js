/**
 * Error Handler and Retry Logic
 * Manages error recovery and retry strategies
 */

import path from 'path';
import fs from 'fs-extra';
import { logger } from './logger.js';
import scraperConfig from '../../config/scraper.config.js';

export class ErrorHandler {
  constructor(options = {}) {
    this.maxRetries = options.maxRetries || scraperConfig.behavior.retries.maxAttempts;
    this.backoffMultiplier = options.backoffMultiplier || scraperConfig.behavior.retries.backoffMultiplier;
    this.initialDelay = options.initialDelay || scraperConfig.behavior.retries.initialDelay;
    this.screenshotOnError = options.screenshotOnError ?? scraperConfig.progress.screenshotOnError;

    // Error tracking
    this.errors = [];
    this.retryCount = new Map();
  }

  /**
   * Execute function with retry logic
   */
  async withRetry(fn, context = 'operation', identifier = null) {
    const retryKey = identifier || context;
    let attempts = 0;
    let lastError = null;

    while (attempts < this.maxRetries) {
      attempts++;

      try {
        logger.debug(`Attempting ${context} (attempt ${attempts}/${this.maxRetries})`);
        const result = await fn();

        // Reset retry count on success
        this.retryCount.delete(retryKey);

        return result;

      } catch (error) {
        lastError = error;
        logger.warn(`${context} failed (attempt ${attempts}/${this.maxRetries}):`, error.message);

        // Record error
        await this.recordError(context, error, attempts);

        // Check if we should retry
        if (attempts >= this.maxRetries) {
          logger.error(`${context} failed after ${attempts} attempts`);
          break;
        }

        // Check if error is retryable
        if (!this.isRetryableError(error)) {
          logger.error(`${context} failed with non-retryable error`);
          break;
        }

        // Calculate delay with exponential backoff
        const delay = this.calculateBackoff(attempts);
        logger.debug(`Waiting ${delay}ms before retry...`);
        await this.sleep(delay);
      }
    }

    // All retries exhausted
    throw new RetryError(`${context} failed after ${attempts} attempts`, lastError, attempts);
  }

  /**
   * Check if error is retryable
   */
  isRetryableError(error) {
    // Non-retryable errors
    const nonRetryablePatterns = [
      /not found/i,
      /invalid credentials/i,
      /unauthorized/i,
      /forbidden/i,
      /not authenticated/i,
      /invalid session/i
    ];

    const errorMessage = error.message || error.toString();

    for (const pattern of nonRetryablePatterns) {
      if (pattern.test(errorMessage)) {
        return false;
      }
    }

    // Retryable error patterns
    const retryablePatterns = [
      /timeout/i,
      /network/i,
      /connection/i,
      /ECONNRESET/i,
      /ETIMEDOUT/i,
      /socket hang up/i,
      /navigation failed/i,
      /page crashed/i,
      /target closed/i
    ];

    for (const pattern of retryablePatterns) {
      if (pattern.test(errorMessage)) {
        return true;
      }
    }

    // Default to retryable for unknown errors
    return true;
  }

  /**
   * Calculate backoff delay
   */
  calculateBackoff(attempt) {
    return this.initialDelay * Math.pow(this.backoffMultiplier, attempt - 1);
  }

  /**
   * Sleep for specified milliseconds
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Record error for tracking
   */
  async recordError(context, error, attempt) {
    const errorRecord = {
      timestamp: new Date().toISOString(),
      context: context,
      message: error.message,
      stack: error.stack,
      attempt: attempt,
      code: error.code
    };

    this.errors.push(errorRecord);

    // Log to error file
    await this.logErrorToFile(errorRecord);
  }

  /**
   * Log error to file
   */
  async logErrorToFile(errorRecord) {
    try {
      const errorLogPath = path.join('logs', 'errors.jsonl');
      await fs.ensureDir('logs');

      const logLine = JSON.stringify(errorRecord) + '\n';
      await fs.appendFile(errorLogPath, logLine);

    } catch (err) {
      logger.error('Failed to write error log:', err);
    }
  }

  /**
   * Take screenshot on error
   */
  async captureErrorScreenshot(page, context) {
    if (!this.screenshotOnError || !page) return null;

    try {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `error_${context}_${timestamp}.png`;
      const filepath = path.join('logs', 'screenshots', filename);

      await fs.ensureDir(path.dirname(filepath));
      await page.screenshot({
        path: filepath,
        fullPage: true
      });

      logger.debug(`Error screenshot saved: ${filepath}`);
      return filepath;

    } catch (error) {
      logger.error('Failed to capture error screenshot:', error);
      return null;
    }
  }

  /**
   * Handle download error
   */
  async handleDownloadError(error, song, page = null) {
    const context = `download_${song.title}`;

    // Take screenshot
    if (page) {
      await this.captureErrorScreenshot(page, context);
    }

    // Determine error type and recovery strategy
    const errorType = this.classifyDownloadError(error);

    switch (errorType) {
      case 'timeout':
        logger.warn(`Download timeout for ${song.title}`);
        return { retry: true, delay: 5000 };

      case 'menu_not_found':
        logger.warn(`Menu not found for ${song.title}`);
        return { retry: true, refreshPage: true };

      case 'file_not_found':
        logger.error(`Download file not found for ${song.title}`);
        return { retry: false, skip: true };

      case 'network':
        logger.warn(`Network error for ${song.title}`);
        return { retry: true, delay: 10000 };

      default:
        logger.error(`Unknown download error for ${song.title}`);
        return { retry: true, delay: 3000 };
    }
  }

  /**
   * Classify download error type
   */
  classifyDownloadError(error) {
    const message = error.message || error.toString();

    if (/timeout/i.test(message)) return 'timeout';
    if (/menu.*not.*found/i.test(message)) return 'menu_not_found';
    if (/file.*not.*found/i.test(message)) return 'file_not_found';
    if (/network|connection/i.test(message)) return 'network';

    return 'unknown';
  }

  /**
   * Handle navigation error
   */
  async handleNavigationError(error, url, page = null) {
    logger.error(`Navigation error for ${url}:`, error.message);

    if (page) {
      await this.captureErrorScreenshot(page, 'navigation');
    }

    // Check for specific navigation issues
    if (/timeout/i.test(error.message)) {
      return { retry: true, increasedTimeout: true };
    }

    if (/refused|blocked/i.test(error.message)) {
      return { retry: false, blocked: true };
    }

    return { retry: true, delay: 5000 };
  }

  /**
   * Handle authentication error
   */
  async handleAuthenticationError(error, page = null) {
    logger.error('Authentication error:', error.message);

    if (page) {
      await this.captureErrorScreenshot(page, 'authentication');
    }

    return {
      retry: false,
      requiresManualLogin: true,
      message: 'Session expired or authentication required. Please log in manually.'
    };
  }

  /**
   * Generate error report
   */
  async generateErrorReport() {
    try {
      const reportPath = path.join('logs', `error_report_${new Date().toISOString().split('T')[0]}.json`);

      const report = {
        generatedAt: new Date().toISOString(),
        totalErrors: this.errors.length,
        errorsByContext: this.groupErrorsByContext(),
        errorsByType: this.groupErrorsByType(),
        retryStatistics: this.getRetryStatistics(),
        errors: this.errors
      };

      await fs.writeJson(reportPath, report, { spaces: 2 });
      logger.info(`Error report generated: ${reportPath}`);

      return report;

    } catch (error) {
      logger.error('Failed to generate error report:', error);
      return null;
    }
  }

  /**
   * Group errors by context
   */
  groupErrorsByContext() {
    const grouped = {};

    for (const error of this.errors) {
      if (!grouped[error.context]) {
        grouped[error.context] = [];
      }
      grouped[error.context].push(error);
    }

    return grouped;
  }

  /**
   * Group errors by type
   */
  groupErrorsByType() {
    const grouped = {};

    for (const error of this.errors) {
      const type = this.classifyError(error);
      if (!grouped[type]) {
        grouped[type] = 0;
      }
      grouped[type]++;
    }

    return grouped;
  }

  /**
   * Classify error type
   */
  classifyError(error) {
    const message = error.message || '';

    if (/timeout/i.test(message)) return 'timeout';
    if (/network|connection/i.test(message)) return 'network';
    if (/auth|login|session/i.test(message)) return 'authentication';
    if (/not.*found/i.test(message)) return 'not_found';
    if (/navigation/i.test(message)) return 'navigation';

    return 'unknown';
  }

  /**
   * Get retry statistics
   */
  getRetryStatistics() {
    const stats = {
      totalRetries: 0,
      successfulRetries: 0,
      failedRetries: 0,
      averageRetriesPerOperation: 0
    };

    for (const [key, count] of this.retryCount.entries()) {
      stats.totalRetries += count;
    }

    if (this.retryCount.size > 0) {
      stats.averageRetriesPerOperation = stats.totalRetries / this.retryCount.size;
    }

    return stats;
  }

  /**
   * Clear error history
   */
  clearErrors() {
    this.errors = [];
    this.retryCount.clear();
    logger.debug('Error history cleared');
  }

  /**
   * Get recent errors
   */
  getRecentErrors(count = 10) {
    return this.errors.slice(-count);
  }
}

/**
 * Custom retry error class
 */
export class RetryError extends Error {
  constructor(message, originalError, attempts) {
    super(message);
    this.name = 'RetryError';
    this.originalError = originalError;
    this.attempts = attempts;
  }
}

/**
 * Create error handler instance
 */
export function createErrorHandler(options) {
  return new ErrorHandler(options);
}

export default ErrorHandler;