# Proposed Improvements

## 1. Better Handling of Song Variations

### Problem
Producer.AI sometimes creates multiple versions of the same song (remixes, variations, takes) that may share:
- The same cover image
- Similar or identical titles
- Possibly the same song ID

But they have different MP3 files that should be preserved.

### Current Behavior
```javascript
if (existingMetadata.id === song.id) {
  // Same song already downloaded - skip
  return { skipped: true };
}
```

This skips any song with the same ID, potentially missing variations.

### Proposed Solution: Multi-Factor Variation Detection

Check multiple factors to determine if it's truly a duplicate:

```javascript
// 1. Check song ID (primary)
if (existingMetadata.id === song.id) {
  // 2. Check if description/sound fields differ (indicates variation)
  if (existingMetadata.description !== metadata.description) {
    logger.info(`Detected variation of "${sanitizedTitle}"`);
    sanitizedTitle = `${sanitizedTitle}-v${getNextVariationNumber(sanitizedTitle)}`;
  } else {
    // 3. Check if MP3 already exists and compare file size
    const audioPath = path.join(this.outputDir, `${sanitizedTitle}.${format}`);
    if (await fs.pathExists(audioPath)) {
      // Same ID + same description + file exists = true duplicate
      return { skipped: true };
    } else {
      // File doesn't exist, download anyway
      logger.info(`Re-downloading missing audio for: ${sanitizedTitle}`);
    }
  }
}
```

Helper function to find next variation number:
```javascript
function getNextVariationNumber(baseName) {
  const files = fs.readdirSync(this.outputDir);
  const variations = files.filter(f => f.startsWith(baseName)).length;
  return variations + 1;
}
```

---

## 2. Smart Title Generation

### Problem
Many song titles aren't descriptive enough, especially for variations:
- "Unknown" → Need better identification
- "Song Title" → Same title for different variations
- Generic titles → Hard to distinguish in file browser

### Current Behavior
Uses the exact title from Producer.AI's `<h1>` tag.

### Proposed Solution: Intelligent Title Enhancement

Generate better titles based on multiple metadata fields:

```javascript
/**
 * Generate an enhanced title using metadata and lyrics
 */
async generateSmartTitle(metadata) {
  const { title, lyrics, bpm, key, model, description } = metadata;

  // Strategy 1: If title is "Unknown" or generic, extract from lyrics
  if (!title || title === 'Unknown' || title.length < 3) {
    return this.titleFromLyrics(lyrics);
  }

  // Strategy 2: If title is very short, enhance with key/bpm
  if (title.length < 15 && key && bpm) {
    return `${title} (${key} ${bpm}bpm)`;
  }

  // Strategy 3: For variations, extract unique identifier from description
  const variationMatch = description?.match(/(remix|version|take|variation|v\d+)/i);
  if (variationMatch) {
    return `${title} - ${variationMatch[1]}`;
  }

  // Strategy 4: Use original title
  return title;
}

/**
 * Extract a meaningful title from lyrics
 */
titleFromLyrics(lyrics) {
  if (!lyrics || lyrics.length < 10) return 'Untitled';

  // Get first meaningful line (skip "Intro", "Verse 1", etc.)
  const lines = lyrics.split('\n').filter(line => {
    const l = line.trim().toLowerCase();
    return l.length > 5 &&
           !l.match(/^(intro|verse|chorus|bridge|outro|refrain)/i);
  });

  if (lines.length === 0) return 'Untitled';

  // Take first line, clean it up
  let firstLine = lines[0].trim();

  // Limit length
  if (firstLine.length > 50) {
    // Find natural break point
    const lastSpace = firstLine.lastIndexOf(' ', 50);
    firstLine = firstLine.substring(0, lastSpace);
  }

  return firstLine;
}
```

### Alternative: AI-Powered Title Generation

For even smarter titles, we could use an LLM to analyze lyrics + metadata:

```javascript
async generateAITitle(metadata) {
  const prompt = `Generate a concise, descriptive song title based on:

Title: ${metadata.title}
Lyrics excerpt: ${metadata.lyrics?.substring(0, 200)}
Genre/Style: ${metadata.description}
Key: ${metadata.key} | BPM: ${metadata.bpm}

Requirements:
- 3-8 words maximum
- Capture the song's theme/mood
- Make it unique and descriptive
- No quotes or special characters

Title:`;

  // Call LLM API (OpenAI, Claude, local model, etc.)
  const enhancedTitle = await callLLM(prompt);
  return enhancedTitle.trim();
}
```

---

## Configuration

Add options to `scraper.config.js`:

```javascript
export default {
  // ... existing config

  downloads: {
    // Smart title generation
    smartTitles: {
      enabled: true,
      mode: 'enhanced', // 'original', 'enhanced', 'ai'
      minTitleLength: 15, // Enhance titles shorter than this
      includeBpmKey: true, // Add "(Gm 120bpm)" to short titles
      useAI: false, // Use AI for title generation
      aiProvider: 'openai', // 'openai', 'claude', 'local'
    },

    // Variation detection
    variations: {
      detectByDescription: true,
      detectByFileSize: true,
      autoNumber: true, // Auto-add -v1, -v2, etc.
      skipIdenticalFiles: true,
    }
  }
};
```

---

## Implementation Priority

1. **Phase 1** (Quick win): Enhanced title from metadata
   - Extract from lyrics if title is "Unknown"
   - Add key/BPM for short titles
   - Detect variation indicators in description

2. **Phase 2** (Better deduplication): Multi-factor variation detection
   - Check description differences
   - Verify file existence
   - Auto-number variations

3. **Phase 3** (Advanced): AI-powered title generation
   - Optional feature requiring API keys
   - Fallback to Phase 1 if unavailable

---

## Benefits

### Variation Detection
- ✅ Preserve all unique versions of songs
- ✅ Avoid re-downloading identical files
- ✅ Clear naming for variations (v1, v2, etc.)
- ✅ Better deduplication accuracy

### Smart Titles
- ✅ More descriptive filenames
- ✅ Easier to browse in file manager
- ✅ Better for WordPress media library
- ✅ More professional presentation
- ✅ Unique titles for variations

### WordPress Integration
- ✅ Better metadata for imports
- ✅ More searchable content
- ✅ Professional-looking titles
- ✅ Clear identification of variations
