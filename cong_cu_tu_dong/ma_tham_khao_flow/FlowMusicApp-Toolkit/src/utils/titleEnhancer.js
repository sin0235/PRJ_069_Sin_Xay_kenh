/**
 * Title Enhancer
 * Cleans up and enhances song titles for better file naming
 */

/**
 * Clean up title by removing FlowMusic's automatic key/BPM suffix
 * Preserves the subtitle part (after the dash)
 * Example: "Ocean Dreams — You Are Water, E Major, 70 bpm" → "Ocean Dreams - You Are Water"
 */
export function cleanTitle(title) {
  if (!title) return 'Untitled';

  // Remove the metadata suffix: ", Key, BPM" at the end
  let cleaned = title.replace(/,\s*[A-G][#b]?\s*(?:Major|Minor|m)?,?\s*\d+\s*bpm\s*$/i, '');

  // Convert em-dash (—) to regular dash for consistency
  cleaned = cleaned.replace(/\s*—\s*/g, ' - ');

  // Clean up any trailing commas or spaces
  cleaned = cleaned.replace(/,\s*$/, '');

  return cleaned.trim();
}

/**
 * Find potential hooks in lyrics
 * Looks for repeated phrases, powerful imagery, or memorable lines
 * Returns multiple candidates for human review
 */
export function findPotentialHooks(lyrics) {
  if (!lyrics || lyrics.length < 20) return [];

  const lines = lyrics.split('\n')
    .map(l => l.trim())
    .filter(l => {
      const lower = l.toLowerCase();
      return l.length > 5 &&
        !lower.match(/^(intro|verse|chorus|bridge|outro|refrain|pre-chorus|verse \d+)/i) &&
        !lower.match(/^\[.*\]$/) &&
        !lower.match(/^[\d\s]+$/);
    });

  if (lines.length === 0) return [];

  const hooks = [];
  const seenLines = new Map(); // Track repeated lines

  // Find repeated lines (likely chorus/hook)
  lines.forEach(line => {
    const normalized = line.toLowerCase().trim();
    seenLines.set(normalized, (seenLines.get(normalized) || 0) + 1);
  });

  // Add repeated lines as candidates
  seenLines.forEach((count, line) => {
    if (count >= 2 && line.length > 10 && line.length < 80) {
      hooks.push({
        text: lines.find(l => l.toLowerCase().trim() === line),
        type: 'repeated',
        score: count * 2
      });
    }
  });

  // Add first substantial line
  if (lines.length > 0 && lines[0].length > 10) {
    hooks.push({
      text: lines[0],
      type: 'opening',
      score: 1
    });
  }

  // Look for lines with strong imagery (questions, exclamations, vivid words)
  lines.forEach(line => {
    if (line.includes('?') || line.includes('!')) {
      hooks.push({
        text: line.replace(/[?!]/g, '').trim(),
        type: 'emphatic',
        score: 1.5
      });
    }
  });

  // Sort by score and return unique hooks
  const unique = Array.from(new Set(hooks.map(h => h.text)))
    .map(text => hooks.find(h => h.text === text))
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);

  return unique;
}

/**
 * Extract a meaningful descriptor from lyrics to make title unique
 * Looks for thematic words, emotions, or key phrases
 */
export function extractLyricDescriptor(lyrics) {
  if (!lyrics || lyrics.length < 20) return null;

  // Find hooks and use the best one
  const hooks = findPotentialHooks(lyrics);

  if (hooks.length > 0) {
    // Take the top hook and extract a 2-4 word phrase
    const hookText = hooks[0].text;
    const words = hookText.split(/\s+/).filter(w => w.length > 2);
    const filtered = words.filter(w => !['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at'].includes(w.toLowerCase()));

    if (filtered.length >= 2) {
      return filtered.slice(0, 3).join(' ');
    }

    return words.slice(0, Math.min(3, words.length)).join(' ');
  }

  return null;
}

/**
 * Extract mood or theme words from description
 */
export function extractMoodFromDescription(description) {
  if (!description) return null;

  // Common mood/style descriptors in FlowMusic descriptions
  const moodWords = [
    'intimate', 'epic', 'ambient', 'energetic', 'melancholic', 'uplifting',
    'dark', 'bright', 'haunting', 'peaceful', 'dramatic', 'gentle', 'powerful',
    'dreamy', 'mystical', 'ethereal', 'cinematic', 'raw', 'polished', 'experimental',
    'minimal', 'lush', 'sparse', 'dense', 'floating', 'driving', 'meditative',
    'contemplative', 'euphoric', 'somber', 'joyful', 'tender', 'fierce'
  ];

  const lowerDesc = description.toLowerCase();

  // Find the first mood word that appears
  for (const mood of moodWords) {
    if (lowerDesc.includes(mood)) {
      return mood.charAt(0).toUpperCase() + mood.slice(1);
    }
  }

  return null;
}

/**
 * Intelligently select the best hook for a variation title
 * Makes the decision automatically based on quality and relevance
 */
export function selectBestHook(hooks, existingTitle, metadata) {
  if (!hooks || hooks.length === 0) return null;

  // Filter out hooks that are too similar to the existing title
  const titleWords = existingTitle.toLowerCase().split(/\s+/);
  const distinctHooks = hooks.filter(hook => {
    const hookWords = hook.text.toLowerCase().split(/\s+/);
    const overlap = hookWords.filter(w => titleWords.includes(w)).length;
    // Less than 50% overlap with title
    return overlap < hookWords.length * 0.5;
  });

  if (distinctHooks.length === 0) {
    // If all hooks overlap, use the highest scored one anyway
    return hooks[0];
  }

  // Prefer repeated hooks (chorus) over others
  const repeatedHooks = distinctHooks.filter(h => h.type === 'repeated');
  if (repeatedHooks.length > 0) {
    return repeatedHooks[0];
  }

  // Use the highest scored distinct hook
  return distinctHooks[0];
}

/**
 * Generate a unique variation suffix for duplicate titles
 * Makes intelligent decisions about what makes the best subtitle
 */
export function generateVariationSuffix(existingTitle, metadata, existingVariations = []) {
  const { lyrics, description, key, bpm, model } = metadata;

  // Strategy 1: Find the best hook from lyrics
  const hooks = findPotentialHooks(lyrics);
  if (hooks.length > 0) {
    const bestHook = selectBestHook(hooks, existingTitle, metadata);
    if (bestHook) {
      // Extract 2-4 meaningful words from the hook
      const words = bestHook.text.split(/\s+/).filter(w => w.length > 2);
      const filtered = words.filter(w =>
        !['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from'].includes(w.toLowerCase())
      );

      if (filtered.length >= 2) {
        const phrase = filtered.slice(0, 3).join(' ').replace(/[^\w\s]/g, '').trim();
        if (phrase.length > 0 && phrase.length <= 40) {
          const proposed = `${existingTitle} - ${phrase}`;
          if (!existingVariations.includes(proposed)) {
            return phrase;
          }
        }
      }
    }
  }

  // Strategy 2: Use mood from description (combine with context)
  const mood = extractMoodFromDescription(description);
  if (mood) {
    const proposed = `${existingTitle} - ${mood}`;
    if (!existingVariations.includes(proposed)) {
      return mood;
    }

    // Try mood + key combination
    if (key) {
      const moodKey = `${mood} ${key}`;
      const proposed2 = `${existingTitle} - ${moodKey}`;
      if (!existingVariations.includes(proposed2)) {
        return moodKey;
      }
    }
  }

  // Strategy 3: Use key alone (only if nothing else worked)
  if (key) {
    const proposed = `${existingTitle} - ${key}`;
    if (!existingVariations.includes(proposed)) {
      return key;
    }
  }

  // Fallback: Numbered version (simple and clear)
  const versionNum = existingVariations.length + 2; // +2 because original is v1
  return `v${versionNum}`;
}

/**
 * Main function: Enhance a song title
 * Cleans it and makes it unique if needed
 */
export function enhanceTitle(title, metadata, existingFiles = []) {
  // Step 1: Clean the title
  const cleanedTitle = cleanTitle(title);

  // Step 2: Check if this exact title already exists
  const exactMatch = existingFiles.includes(cleanedTitle);

  if (!exactMatch) {
    // No exact duplicate, use cleaned title
    return cleanedTitle;
  }

  // Step 3: Find all existing variations of this title
  const existingWithSameBase = existingFiles.filter(f =>
    f === cleanedTitle || f.startsWith(cleanedTitle + ' - ')
  );

  // Step 4: Generate a unique variation
  const suffix = generateVariationSuffix(cleanedTitle, metadata, existingWithSameBase);

  return `${cleanedTitle} - ${suffix}`;
}

export default {
  cleanTitle,
  extractLyricDescriptor,
  extractMoodFromDescription,
  generateVariationSuffix,
  enhanceTitle
};
