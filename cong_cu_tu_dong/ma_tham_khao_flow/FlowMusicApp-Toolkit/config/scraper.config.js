/**
 * Scraper Configuration
 * Settings for FlowMusic scraping behavior
 */

export const scraperConfig = {
  // FlowMusic URLs
  urls: {
    base: 'https://www.flowmusic.app',
    login: 'https://www.flowmusic.app/login',
    songs: 'https://www.flowmusic.app/library/my-songs',
    playlists: 'https://www.flowmusic.app/playlists'
  },

  // Selectors for FlowMusic elements (updated based on actual DOM structure)
  selectors: {
    // Authentication
    loginButton: 'button:has-text("Sign in")',
    userAvatar: '[data-testid="user-avatar"], .user-avatar, img[alt*="Profile"]',
    captcha: 'iframe[src*="recaptcha"], iframe[src*="captcha"], [class*="captcha"], #captcha',

    // Song list (ACTUAL SELECTORS FROM DOM INSPECTION)
    songCard: 'div.cursor-pointer.mb-1',  // Main song container
    songImage: 'img.aspect-square.object-cover',   // Image contains title in alt attribute
    songTitle: 'img[alt]',                         // Title is in image alt text
    songLink: 'a[href*="/song/"]',                 // Link to song detail page
    duration: 'span.text-fg-2.w-8.text-xs.whitespace-nowrap', // Duration element
    playButton: 'button[aria-label*="Play"]',      // Play button
    loadMoreButton: 'button:has-text("Load More"), button:has-text("Show more")',

    // Song detail page - ACTUAL STRUCTURE
    // Step 1: Click three-dots menu (div with aria-haspopup="menu", contains ellipsis SVG)
    menuButton: 'div[aria-haspopup="menu"][data-sentry-element="MenuTrigger"], div[aria-haspopup="menu"]',

    // Step 2: Menu appears with: Remix, Details, Download, Share..., Add to..., Report
    // Click "Download" menu item
    downloadMenuItem: '[class*="flex w-full cursor-pointer items-center rounded-md"]:has-text("Download"), button:has-text("Download")',

    // Step 3: Click format in submenu (appears after clicking Download)
    downloadVideo: 'button:has-text("Download video"), [role="menuitem"]:has-text("Download video")',
    downloadStems: 'button:has-text("Get stems"), [role="menuitem"]:has-text("Get stems")',
    downloadMP3: 'button:has-text("MP3"), [role="menuitem"]:has-text("MP3")',
    downloadM4A: 'button:has-text("M4A"), [role="menuitem"]:has-text("M4A")',
    downloadWAV: 'button:has-text("WAV"), [role="menuitem"]:has-text("WAV")',

    // Note: Cover art needs to be extracted from page image source
    downloadCover: 'img.aspect-square.object-cover, img[alt*="song"], img[alt*="cover"]',
    lyricsSection: '[data-testid="lyrics"], .lyrics-container, div[class*="lyrics"]',
    metadataSection: '.song-metadata, .track-info, div[class*="metadata"]',

    // Metadata fields
    bpm: '[data-testid="bpm"], span:has-text("BPM")',
    key: '[data-testid="key"], span:has-text("Key")',
    genre: '[data-testid="genre"], span:has-text("Genre")',
    durationMeta: '[data-testid="duration"], span:has-text("Duration")',
    createdDate: '[data-testid="created"], span:has-text("Created")'
  },

  // Scraping behavior
  // Tuning guide: Increase delays if you see rate-limit errors or pages not loading fully.
  //               Decrease delays only on fast, stable connections.
  behavior: {
    // Delays (in milliseconds)
    // These are base values. The --speed preset (slow/normal/fast/turbo) applies a multiplier
    // at runtime via applySpeedSettings() in cli.js — editing here changes the normal-speed baseline.
    delays: {
      betweenSongs: 2000,      // Delay between song downloads. Increase if seeing 429/rate-limit errors.
      afterScroll: 3000,       // Wait after each scroll for lazy-loaded content to render.
                               // Increase on slow connections or if scroll-based discovery misses songs.
      afterClick: 1000,        // Wait after UI interactions (menu open, button click).
      afterDownload: 3000,     // Wait after triggering a download before navigating away.
      navigationWait: 5000     // Wait for page navigation to complete.
    },

    // Retry settings
    retries: {
      maxAttempts: 3,          // Retries per song on failure. Increase for flaky connections.
      backoffMultiplier: 2,    // Each retry waits: initialDelay * (backoffMultiplier ^ attempt)
      initialDelay: 1000       // Base delay in ms before first retry.
    },

    // Infinite scroll — used by full library scraping (download --all)
    // Note: playlist and project commands use 200 scroll attempts regardless of this setting.
    infiniteScroll: {
      maxScrollAttempts: 50,         // Increase if your library has more than ~1000 songs.
      scrollDistance: 1000,          // Pixels to scroll each iteration (unused; scrollTop = scrollHeight is used).
      checkInterval: 2000,           // ms between scroll attempts (informational; actual wait is afterScroll).
      noNewContentThreshold: 10      // Stop after this many consecutive scrolls with no new songs found.
                                     // Increase if lazy loading is slow and songs are being missed.
    },

    // Download settings
    downloads: {
      concurrent: 2,           // Concurrent downloads. Currently only 1 is used per run; reserved for future use.
      timeout: 120000,         // Per-song download timeout in ms (2 min). Increase for very large files.
      verifyCompletion: true,  // Verify the download triggered successfully before moving on.
      formats: ['mp3', 'wav', 'm4a', 'stems'], // Supported primary download formats
      assets: ['cover', 'lyrics', 'metadata']
    }
  },

  // File organization
  fileOrganization: {
    outputDir: './output',
    structure: 'BY_SONG', // Options: BY_SONG, BY_PLAYLIST, BY_DATE

    // File naming patterns
    naming: {
      folder: '{songName}', // Can include {songId}, {playlist}, {date}
      audio: 'audio.{ext}',
      cover: 'cover.{ext}',
      lyrics: 'lyrics.txt',
      metadata: 'metadata.json'
    },

    // Sanitization rules
    sanitization: {
      maxLength: 255,
      replaceChars: {
        '/': '-',
        '\\': '-',
        ':': '-',
        '*': '',
        '?': '',
        '"': '',
        '<': '',
        '>': '',
        '|': '-'
      }
    }
  },

  // Metadata defaults
  metadata: {
    defaultArtist: 'Unknown Artist',  // Fallback artist if the page has no author
    defaultAlbum: 'FlowMusic Library', // Default album name (can be overridden per download)
    defaultYear: null,                // null = use current year
    includeOriginalUrl: true,         // Include FlowMusic URL in metadata
    includeLyrics: true,              // Include lyrics in MP3 tags
    includeCoverArt: true             // Embed cover art in MP3
  },

  // Progress tracking
  progress: {
    checkpointInterval: 10, // Save progress every 10 songs
    checkpointDir: './checkpoints',
    enableLogging: true,
    logLevel: 'info', // Options: error, warn, info, debug
    screenshotOnError: true
  },

  // Rate limiting
  rateLimiting: {
    enabled: true,
    requestsPerMinute: 30,
    burstSize: 5
  }
};

export default scraperConfig;
