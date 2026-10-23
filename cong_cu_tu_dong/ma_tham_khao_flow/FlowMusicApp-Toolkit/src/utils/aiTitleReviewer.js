/**
 * AI Title Reviewer
 * Integration point for any AI assistant to review and decide on song titles
 */

import { logger } from './logger.js';
import { cleanTitle, findPotentialHooks } from './titleEnhancer.js';

/**
 * Prepare song data for AI review
 * Returns a formatted analysis any AI assistant can review
 */
export function prepareSongForReview(metadata) {
  const cleanedTitle = cleanTitle(metadata.title);
  const hooks = findPotentialHooks(metadata.lyrics);

  return {
    originalTitle: metadata.title,
    cleanedTitle,
    metadata: {
      key: metadata.key,
      bpm: metadata.bpm,
      model: metadata.model,
      description: metadata.description
    },
    lyrics: metadata.lyrics,
    potentialHooks: hooks,
    analysisPrompt: generateAnalysisPrompt(metadata, cleanedTitle, hooks)
  };
}

/**
 * Generate a prompt for an AI assistant to analyze and decide on the best title
 */
function generateAnalysisPrompt(metadata, cleanedTitle, hooks) {
  return `
Song Title Analysis:

Current Title: "${cleanedTitle}"
Key: ${metadata.key || 'Unknown'} | BPM: ${metadata.bpm || 'Unknown'}
Mood: ${metadata.description?.substring(0, 200) || 'No description'}

Lyrics:
${metadata.lyrics || 'No lyrics'}

${hooks.length > 0 ? `
Identified Hooks:
${hooks.map((h, i) => `${i + 1}. ${h.type === 'repeated' ? '[CHORUS]' : h.type === 'opening' ? '[OPENING]' : '[EMPHATIC]'} "${h.text}"`).join('\n')}
` : ''}

Task: Review this song and decide on the best title.
- If the current title is good, use it as-is
- If you find a more powerful hook or phrase, use that
- Keep it concise but evocative (2-5 words preferred)
- Consider the emotional core and memorability

What title would you choose?`;
}

/**
 * Apply AI title decision
 * This gets called with the chosen title
 */
export function applyTitleDecision(chosenTitle, metadata) {
  logger.info(`AI-selected title: "${chosenTitle}"`);

  return {
    title: chosenTitle,
    originalTitle: metadata.title,
    aiEnhanced: true,
    enhancedAt: new Date().toISOString()
  };
}

export default {
  prepareSongForReview,
  applyTitleDecision
};
