#!/usr/bin/env node

/**
 * Fix Existing Metadata Files
 * Updates old JSON files with missing fields and cleans up descriptions
 * Then re-tags the MP3s with corrected metadata
 */

import chalk from 'chalk';
import path from 'path';
import fs from 'fs-extra';
import { MetadataTagger } from '../src/utils/metadataTagger.js';
import { logger } from '../src/utils/logger.js';

/**
 * Clean up description field by removing navigation noise
 */
function cleanDescription(description) {
  if (!description) return null;

  // If description seems to have navigation text at the beginning
  if (/(?:STARTER|UPGRADE|INVITES|Sacred Waters|Quantum)/i.test(description)) {
    // Try to extract just the relevant part after common patterns
    const patterns = [
      // Pattern: after "ago TITLE, Key, BPM numbers SOUND actual-description"
      /ago\s+[^,]+,\s+[^,]+,\s+\d+\s+bpm\s+\d+\s+\d+\s+(?:VIDEO\s+PUBLISH\s+REMIX\s+)?SOUND\s+(.+?)$/i,
      // Pattern: after "SOUND actual-description"
      /SOUND\s+(.+?)$/i,
      // Pattern: Intimate/Vignette at start (common FlowMusic descriptions)
      /((?:Intimate|Vignette|Sacred|Quantum)[^]+)$/i
    ];

    for (const pattern of patterns) {
      const match = description.match(pattern);
      if (match && match[1].length > 20) {
        return match[1].trim();
      }
    }
  }

  return description;
}

async function fixExistingMetadata() {
  try {
    const outputDir = path.resolve('./output');

    console.log(chalk.cyan('\n═══════════════════════════════════════════════════'));
    console.log(chalk.cyan.bold('     Fix Existing Metadata Files                 '));
    console.log(chalk.cyan('═══════════════════════════════════════════════════\n'));

    console.log(chalk.white(`Output directory: ${outputDir}\n`));

    // Get all JSON files
    const files = await fs.readdir(outputDir);
    const jsonFiles = files.filter(f => f.endsWith('.json'));

    console.log(chalk.yellow(`Found ${jsonFiles.length} JSON files to process\n`));

    const results = {
      total: jsonFiles.length,
      updated: 0,
      unchanged: 0,
      retagged: 0,
      errors: 0
    };

    for (const jsonFile of jsonFiles) {
      const jsonPath = path.join(outputDir, jsonFile);
      const baseName = jsonFile.replace('.json', '');

      console.log(chalk.gray(`\nProcessing: ${baseName}`));

      try {
        // Read existing metadata
        const metadata = await fs.readJson(jsonPath);
        let wasUpdated = false;

        // Fix 1: Add title and originalTitle if missing
        if (!metadata.title || !metadata.originalTitle) {
          // Use filename as the title if it's not just "Unknown"
          if (!metadata.title) {
            metadata.title = baseName;
            console.log(chalk.yellow(`  + Added title from filename`));
            wasUpdated = true;
          }

          if (!metadata.originalTitle) {
            metadata.originalTitle = metadata.title;
            console.log(chalk.yellow(`  + Added originalTitle`));
            wasUpdated = true;
          }
        }

        // Fix 2: Clean up description
        if (metadata.description) {
          const cleanedDescription = cleanDescription(metadata.description);
          if (cleanedDescription !== metadata.description) {
            console.log(chalk.yellow(`  + Cleaned description (${metadata.description.length} → ${cleanedDescription.length} chars)`));
            metadata.description = cleanedDescription;
            wasUpdated = true;
          }
        }

        // Fix 3: Add author field if missing (use filename or default)
        if (!metadata.author && !metadata.artist) {
          metadata.author = 'FlowMusic';
          console.log(chalk.yellow(`  + Added default author`));
          wasUpdated = true;
        }

        // Save updated metadata if changed
        if (wasUpdated) {
          await fs.writeJson(jsonPath, metadata, { spaces: 2 });
          results.updated++;
          console.log(chalk.green(`  ✓ Updated JSON`));

          // Re-tag the MP3 with corrected metadata
          const mp3Path = path.join(outputDir, `${baseName}.mp3`);
          if (await fs.pathExists(mp3Path)) {
            // Find cover art
            const coverExtensions = ['.jpg', '.jpeg', '.png', '.webp'];
            let coverPath = null;
            for (const ext of coverExtensions) {
              const candidatePath = path.join(outputDir, `${baseName}${ext}`);
              if (await fs.pathExists(candidatePath)) {
                coverPath = candidatePath;
                break;
              }
            }

            const tagResult = await MetadataTagger.tagMp3(mp3Path, metadata, coverPath);
            if (tagResult.success) {
              results.retagged++;
              console.log(chalk.green(`  ✓ Re-tagged MP3`));
            } else {
              console.log(chalk.red(`  ✗ Failed to re-tag MP3: ${tagResult.error}`));
            }
          }
        } else {
          results.unchanged++;
          console.log(chalk.gray(`  - No changes needed`));
        }

      } catch (error) {
        results.errors++;
        console.log(chalk.red(`  ✗ Error: ${error.message}`));
      }
    }

    // Display results
    console.log(chalk.white('\n═══════════════════════════════════════════════════'));
    console.log(chalk.white('Results:\n'));
    console.log(chalk.green(`  ✓ Updated: ${results.updated}`));
    console.log(chalk.cyan(`  ✓ Re-tagged MP3s: ${results.retagged}`));
    console.log(chalk.gray(`  - Unchanged: ${results.unchanged}`));
    console.log(chalk.red(`  ✗ Errors: ${results.errors}`));
    console.log(chalk.white(`  Total: ${results.total}`));
    console.log(chalk.white('═══════════════════════════════════════════════════\n'));

    if (results.updated > 0) {
      console.log(chalk.green('✓ Metadata fixes complete!\n'));
    } else {
      console.log(chalk.yellow('All files already up to date.\n'));
    }

    process.exit(0);

  } catch (error) {
    console.error(chalk.red('\n✗ Error:'), error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

fixExistingMetadata();
