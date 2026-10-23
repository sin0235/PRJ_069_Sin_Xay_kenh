/**
 * Browser Configuration
 * Settings for Playwright browser automation
 */

import path from 'path';
import os from 'os';

export const browserConfig = {
  // Browser type - chromium recommended for best compatibility
  browserType: 'chromium',

  // Launch options
  launchOptions: {
    headless: false, // Keep browser visible for monitoring
    slowMo: 100, // Slow down actions by 100ms for stability
    args: [
      '--disable-blink-features=AutomationControlled',
      '--disable-features=IsolateOrigins,site-per-process',
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--disable-gpu',
      '--window-size=1920,1080'
    ]
  },

  // Context options for persistent browser session
  contextOptions: {
    viewport: { width: 1920, height: 1080 },
    ignoreHTTPSErrors: true,
    acceptDownloads: true,
    // User agent to avoid detection
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  },

  // Browser profile paths for different operating systems
  profilePaths: {
    windows: {
      chrome: path.join(os.homedir(), 'AppData', 'Local', 'Google', 'Chrome', 'User Data'),
      edge: path.join(os.homedir(), 'AppData', 'Local', 'Microsoft', 'Edge', 'User Data')
    },
    mac: {
      chrome: path.join(os.homedir(), 'Library', 'Application Support', 'Google', 'Chrome'),
      edge: path.join(os.homedir(), 'Library', 'Application Support', 'Microsoft Edge')
    },
    linux: {
      chrome: path.join(os.homedir(), '.config', 'google-chrome'),
      chromium: path.join(os.homedir(), '.config', 'chromium'),
      edge: path.join(os.homedir(), '.config', 'microsoft-edge')
    }
  },

  // Get appropriate browser profile path based on OS
  getBrowserProfile() {
    const platform = process.platform;

    // For WSL, we need to access Windows profile
    if (platform === 'linux' && process.env.WSL_DISTRO_NAME) {
      const windowsHome = '/mnt/c/Users/' + process.env.USER;
      return {
        chrome: path.join(windowsHome, 'AppData', 'Local', 'Google', 'Chrome', 'User Data'),
        edge: path.join(windowsHome, 'AppData', 'Local', 'Microsoft', 'Edge', 'User Data')
      };
    }

    switch (platform) {
      case 'win32':
        return this.profilePaths.windows;
      case 'darwin':
        return this.profilePaths.mac;
      case 'linux':
        return this.profilePaths.linux;
      default:
        throw new Error(`Unsupported platform: ${platform}`);
    }
  },

  // Timeouts
  timeouts: {
    navigation: 60000, // 60 seconds for page navigation
    download: 120000,  // 2 minutes for file downloads
    element: 30000,    // 30 seconds for element visibility
    scroll: 5000       // 5 seconds between scroll attempts
  }
};

export default browserConfig;