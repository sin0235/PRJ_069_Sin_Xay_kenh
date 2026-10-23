/**
 * Browser Authentication Handler
 * Manages browser sessions and authentication for FlowMusic
 */

import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs-extra';
import browserConfig from '../../config/browser.config.js';
import scraperConfig from '../../config/scraper.config.js';
import { logger } from '../utils/logger.js';

export class BrowserAuthenticator {
  constructor() {
    this.browser = null;
    this.context = null;
    this.page = null;
    this.isAuthenticated = false;
  }

  /**
   * Initialize browser with existing profile or create new session
   */
  async initialize(options = {}) {
    try {
      logger.info('Initializing browser session...');

      const { useProfile = true, profilePath = null } = options;

      if (useProfile) {
        // Try to use existing browser profile
        const profile = profilePath || this.detectBrowserProfile();
        if (profile && await fs.pathExists(profile)) {
          logger.info(`Using browser profile: ${profile}`);
          return await this.launchWithProfile(profile);
        }
      }

      // Fall back to new browser session
      logger.info('Launching new browser session...');
      return await this.launchNewSession();

    } catch (error) {
      logger.error('Failed to initialize browser:', error);
      throw error;
    }
  }

  /**
   * Detect existing browser profile path
   */
  detectBrowserProfile() {
    try {
      const profiles = browserConfig.getBrowserProfile();

      // Check for Chrome profile first
      if (profiles.chrome && fs.existsSync(profiles.chrome)) {
        logger.info('Chrome profile detected');
        return profiles.chrome;
      }

      // Check for Edge profile
      if (profiles.edge && fs.existsSync(profiles.edge)) {
        logger.info('Edge profile detected');
        return profiles.edge;
      }

      // Check for Chromium (Linux)
      if (profiles.chromium && fs.existsSync(profiles.chromium)) {
        logger.info('Chromium profile detected');
        return profiles.chromium;
      }

      logger.warn('No existing browser profile found');
      return null;

    } catch (error) {
      logger.error('Error detecting browser profile:', error);
      return null;
    }
  }

  /**
   * Launch browser with existing profile
   */
  async launchWithProfile(profilePath) {
    try {
      // Launch with persistent context using existing profile
      this.context = await chromium.launchPersistentContext(
        profilePath,
        {
          ...browserConfig.launchOptions,
          ...browserConfig.contextOptions,
          // Override headless to false for profile mode
          headless: false
        }
      );

      // Get the first page or create new one
      const pages = this.context.pages();
      this.page = pages.length > 0 ? pages[0] : await this.context.newPage();

      // Set default timeouts
      this.page.setDefaultTimeout(browserConfig.timeouts.element);
      this.page.setDefaultNavigationTimeout(browserConfig.timeouts.navigation);

      logger.info('Browser launched with existing profile');
      return true;

    } catch (error) {
      logger.error('Failed to launch with profile:', error);

      // Try alternative approach - copy profile to temp location
      if (error.message.includes('already in use')) {
        logger.info('Profile in use, attempting to copy profile...');
        return await this.launchWithProfileCopy(profilePath);
      }

      throw error;
    }
  }

  /**
   * Launch browser with copy of existing profile
   */
  async launchWithProfileCopy(originalProfilePath) {
    try {
      // Create temporary profile directory
      const tempDir = path.join(process.cwd(), '.temp-profile');
      await fs.ensureDir(tempDir);

      // Copy essential profile files (cookies, local storage)
      const filesToCopy = ['Default/Cookies', 'Default/Local Storage', 'Default/Preferences'];

      for (const file of filesToCopy) {
        const src = path.join(originalProfilePath, file);
        const dest = path.join(tempDir, file);

        if (await fs.pathExists(src)) {
          await fs.ensureDir(path.dirname(dest));
          await fs.copy(src, dest);
        }
      }

      logger.info('Profile copied to temporary location');

      // Launch with copied profile
      this.context = await chromium.launchPersistentContext(
        tempDir,
        {
          ...browserConfig.launchOptions,
          ...browserConfig.contextOptions,
          headless: false
        }
      );

      this.page = await this.context.newPage();
      this.page.setDefaultTimeout(browserConfig.timeouts.element);
      this.page.setDefaultNavigationTimeout(browserConfig.timeouts.navigation);

      logger.info('Browser launched with copied profile');
      return true;

    } catch (error) {
      logger.error('Failed to launch with profile copy:', error);
      throw error;
    }
  }

  /**
   * Launch new browser session
   */
  async launchNewSession() {
    try {
      this.browser = await chromium.launch(browserConfig.launchOptions);
      this.context = await this.browser.newContext(browserConfig.contextOptions);
      this.page = await this.context.newPage();

      // Set timeouts
      this.page.setDefaultTimeout(browserConfig.timeouts.element);
      this.page.setDefaultNavigationTimeout(browserConfig.timeouts.navigation);

      logger.info('New browser session created');
      return true;

    } catch (error) {
      logger.error('Failed to launch new session:', error);
      throw error;
    }
  }

  /**
   * Check if user is authenticated on FlowMusic
   */
  async checkAuthentication() {
    try {
      logger.info('Checking authentication status...');

      // Navigate to songs page
      await this.page.goto(scraperConfig.urls.songs, {
        waitUntil: 'networkidle',
        timeout: browserConfig.timeouts.navigation
      });

      // Check for CAPTCHA first
      await this.checkForCaptcha();

      // Check for user avatar or login button
      const isLoggedIn = await this.page.locator(scraperConfig.selectors.userAvatar).count() > 0;

      if (isLoggedIn) {
        logger.info('User is authenticated');
        this.isAuthenticated = true;

        // Take screenshot for verification
        await this.page.screenshot({
          path: path.join('logs', 'authenticated.png'),
          fullPage: false
        });

        return true;
      }

      logger.warn('User is not authenticated');
      this.isAuthenticated = false;
      return false;

    } catch (error) {
      logger.error('Error checking authentication:', error);

      // Take error screenshot
      await this.page.screenshot({
        path: path.join('logs', 'auth-check-error.png'),
        fullPage: true
      });

      return false;
    }
  }

  /**
   * Check for and handle CAPTCHA
   */
  async checkForCaptcha() {
    try {
      logger.debug('Checking for CAPTCHA...');

      const captchaExists = await this.page.locator(scraperConfig.selectors.captcha).count() > 0;

      if (captchaExists) {
        logger.warn('CAPTCHA detected!');
        console.log('\n⚠️  CAPTCHA DETECTED');
        console.log('Please solve the CAPTCHA in the browser window.');
        console.log('The script will continue automatically once solved.\n');

        // Take screenshot
        await this.takeScreenshot('captcha-detected');

        // Wait for CAPTCHA to disappear (user solves it)
        await this.page.waitForSelector(scraperConfig.selectors.captcha, {
          state: 'hidden',
          timeout: 300000 // 5 minutes for user to solve CAPTCHA
        }).catch(() => {
          logger.warn('CAPTCHA wait timeout - continuing anyway');
        });

        // Wait a bit after CAPTCHA is solved
        await this.page.waitForTimeout(3000);

        logger.info('CAPTCHA appears to be solved, continuing...');
        return true;
      }

      logger.debug('No CAPTCHA detected');
      return false;

    } catch (error) {
      logger.error('Error checking for CAPTCHA:', error);
      return false;
    }
  }

  /**
   * Wait for manual login
   */
  async waitForManualLogin() {
    try {
      logger.info('Waiting for manual login...');
      console.log('\n⚠️  Please log in to FlowMusic in the browser window');
      console.log('The script will continue automatically once you are logged in.\n');

      // Navigate to login page
      await this.page.goto(scraperConfig.urls.login, {
        waitUntil: 'networkidle'
      });

      // Wait for user avatar to appear (indicates successful login)
      await this.page.waitForSelector(scraperConfig.selectors.userAvatar, {
        timeout: 300000 // 5 minutes timeout for manual login
      });

      logger.info('Manual login successful');
      this.isAuthenticated = true;

      // Save cookies for future use
      await this.saveCookies();

      return true;

    } catch (error) {
      logger.error('Manual login timeout or error:', error);
      return false;
    }
  }

  /**
   * Save cookies to file for future sessions
   */
  async saveCookies() {
    try {
      const cookies = await this.context.cookies();
      const cookiesPath = path.join('config', 'cookies.json');

      await fs.ensureDir('config');
      await fs.writeJson(cookiesPath, cookies, { spaces: 2 });

      logger.info('Cookies saved for future sessions');
      return true;

    } catch (error) {
      logger.error('Failed to save cookies:', error);
      return false;
    }
  }

  /**
   * Load cookies from file
   */
  async loadCookies() {
    try {
      const cookiesPath = path.join('config', 'cookies.json');

      if (await fs.pathExists(cookiesPath)) {
        const cookies = await fs.readJson(cookiesPath);
        await this.context.addCookies(cookies);
        logger.info('Cookies loaded from file');
        return true;
      }

      logger.info('No saved cookies found');
      return false;

    } catch (error) {
      logger.error('Failed to load cookies:', error);
      return false;
    }
  }

  /**
   * Get current page instance
   */
  getPage() {
    if (!this.page) {
      throw new Error('Browser page not initialized');
    }
    return this.page;
  }

  /**
   * Get browser context
   */
  getContext() {
    if (!this.context) {
      throw new Error('Browser context not initialized');
    }
    return this.context;
  }

  /**
   * Take screenshot for debugging
   */
  async takeScreenshot(name = 'screenshot') {
    try {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `${name}_${timestamp}.png`;
      const filepath = path.join('logs', filename);

      await fs.ensureDir('logs');
      await this.page.screenshot({
        path: filepath,
        fullPage: true
      });

      logger.debug(`Screenshot saved: ${filepath}`);
      return filepath;

    } catch (error) {
      logger.error('Failed to take screenshot:', error);
      return null;
    }
  }

  /**
   * Close browser session
   */
  async close() {
    try {
      if (this.context) {
        await this.context.close();
      }
      if (this.browser) {
        await this.browser.close();
      }

      logger.info('Browser session closed');
      return true;

    } catch (error) {
      logger.error('Error closing browser:', error);
      return false;
    }
  }

  /**
   * Clean up temporary files
   */
  async cleanup() {
    try {
      const tempProfile = path.join(process.cwd(), '.temp-profile');
      if (await fs.pathExists(tempProfile)) {
        await fs.remove(tempProfile);
        logger.info('Temporary profile removed');
      }
      return true;

    } catch (error) {
      logger.error('Cleanup error:', error);
      return false;
    }
  }
}

export default BrowserAuthenticator;