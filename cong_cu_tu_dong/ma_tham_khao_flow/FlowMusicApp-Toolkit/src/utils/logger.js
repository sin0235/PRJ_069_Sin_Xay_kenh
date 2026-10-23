/**
 * Logger Utility
 * Centralized logging for the scraper with file and console output
 */

import winston from 'winston';
import path from 'path';
import fs from 'fs-extra';
import chalk from 'chalk';

// Ensure logs directory exists
await fs.ensureDir('./logs');

// Custom format for console output with colors
const consoleFormat = winston.format.printf(({ level, message, timestamp, ...metadata }) => {
  let msg = `${timestamp} `;

  // Color-code log levels
  switch (level) {
    case 'error':
      msg += chalk.red(`[ERROR]`);
      break;
    case 'warn':
      msg += chalk.yellow(`[WARN]`);
      break;
    case 'info':
      msg += chalk.blue(`[INFO]`);
      break;
    case 'debug':
      msg += chalk.gray(`[DEBUG]`);
      break;
    default:
      msg += `[${level.toUpperCase()}]`;
  }

  msg += ` ${message}`;

  // Add metadata if present
  if (Object.keys(metadata).length > 0) {
    msg += ` ${JSON.stringify(metadata)}`;
  }

  return msg;
});

// Create logger instance
export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp({
      format: 'YYYY-MM-DD HH:mm:ss'
    }),
    winston.format.errors({ stack: true }),
    winston.format.splat(),
    winston.format.json()
  ),
  transports: [
    // Console output
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.timestamp({
          format: 'HH:mm:ss'
        }),
        consoleFormat
      )
    }),
    // File output - all logs
    new winston.transports.File({
      filename: path.join('logs', 'scraper.log'),
      maxsize: 5242880, // 5MB
      maxFiles: 5
    }),
    // File output - errors only
    new winston.transports.File({
      filename: path.join('logs', 'error.log'),
      level: 'error',
      maxsize: 5242880, // 5MB
      maxFiles: 5
    })
  ]
});

// Add session log for current run
const sessionId = new Date().toISOString().replace(/[:.]/g, '-');
logger.add(new winston.transports.File({
  filename: path.join('logs', `session_${sessionId}.log`),
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  )
}));

/**
 * Progress logger for tracking scraping progress
 */
export class ProgressLogger {
  constructor(total) {
    this.total = total;
    this.current = 0;
    this.successful = 0;
    this.failed = 0;
    this.startTime = Date.now();
  }

  /**
   * Log successful item
   */
  success(item) {
    this.current++;
    this.successful++;
    const percentage = ((this.current / this.total) * 100).toFixed(1);
    const elapsed = this.getElapsedTime();

    logger.info(
      chalk.green(`✓ [${this.current}/${this.total}] (${percentage}%) - ${item} - ${elapsed}`)
    );
  }

  /**
   * Log failed item
   */
  failure(item, error) {
    this.current++;
    this.failed++;
    const percentage = ((this.current / this.total) * 100).toFixed(1);

    logger.error(
      chalk.red(`✗ [${this.current}/${this.total}] (${percentage}%) - ${item}`),
      { error: error.message }
    );
  }

  /**
   * Log progress update
   */
  update(message) {
    const percentage = ((this.current / this.total) * 100).toFixed(1);
    const elapsed = this.getElapsedTime();
    const remaining = this.getEstimatedTimeRemaining();

    logger.info(
      `[${this.current}/${this.total}] (${percentage}%) - ${message} - Elapsed: ${elapsed}, Remaining: ${remaining}`
    );
  }

  /**
   * Get elapsed time
   */
  getElapsedTime() {
    const elapsed = Date.now() - this.startTime;
    return this.formatTime(elapsed);
  }

  /**
   * Get estimated time remaining
   */
  getEstimatedTimeRemaining() {
    if (this.current === 0) return 'N/A';

    const elapsed = Date.now() - this.startTime;
    const averageTime = elapsed / this.current;
    const remaining = averageTime * (this.total - this.current);

    return this.formatTime(remaining);
  }

  /**
   * Format time in human-readable format
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
   * Get summary statistics
   */
  getSummary() {
    const elapsed = this.getElapsedTime();
    const successRate = ((this.successful / this.current) * 100).toFixed(1);

    return {
      total: this.total,
      processed: this.current,
      successful: this.successful,
      failed: this.failed,
      successRate: `${successRate}%`,
      duration: elapsed
    };
  }

  /**
   * Log final summary
   */
  logSummary() {
    const summary = this.getSummary();

    logger.info('═══════════════════════════════════════════');
    logger.info('SCRAPING SUMMARY');
    logger.info('═══════════════════════════════════════════');
    logger.info(`Total Items: ${summary.total}`);
    logger.info(`Processed: ${summary.processed}`);
    logger.info(chalk.green(`✓ Successful: ${summary.successful}`));
    logger.info(chalk.red(`✗ Failed: ${summary.failed}`));
    logger.info(`Success Rate: ${summary.successRate}`);
    logger.info(`Duration: ${summary.duration}`);
    logger.info('═══════════════════════════════════════════');
  }
}

/**
 * Create spinner for console output
 */
export function createSpinner(text) {
  // Import dynamically since ora is ESM only
  return import('ora').then(({ default: ora }) => {
    return ora({
      text,
      spinner: 'dots',
      color: 'cyan'
    });
  });
}

/**
 * Log section divider
 */
export function logDivider(title) {
  const divider = '═'.repeat(50);
  logger.info('');
  logger.info(chalk.cyan(divider));
  if (title) {
    logger.info(chalk.cyan.bold(title.toUpperCase()));
    logger.info(chalk.cyan(divider));
  }
  logger.info('');
}

/**
 * Log error with stack trace
 */
export function logError(error, context = '') {
  logger.error(`Error ${context ? `in ${context}` : ''}: ${error.message}`);

  if (error.stack) {
    logger.debug('Stack trace:', error.stack);
  }

  // Log additional error properties if they exist
  if (error.code) {
    logger.debug(`Error code: ${error.code}`);
  }
  if (error.response) {
    logger.debug(`Response: ${JSON.stringify(error.response)}`);
  }
}

/**
 * Create a child logger with context
 */
export function createLogger(context) {
  return logger.child({ context });
}

export default logger;