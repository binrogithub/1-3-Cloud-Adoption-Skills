#!/usr/bin/env node
/**
 * Compare two screenshots using sharp + pixelmatch.
 *
 * Usage:
 *   node compare-screenshots.js <original> <generated> [diff-output]
 *
 * Example:
 *   node compare-screenshots.js original.jpeg generated.png diff.png
 */

const sharp = require('sharp');
const fs = require('fs');
const { PNG } = require('pngjs');
const pixelmatch = require('pixelmatch').default;

async function compare(originalPath, generatedPath, diffPath = 'diff-image.png') {
  // Convert original to PNG (handles JPEG)
  const buf1 = await sharp(originalPath).png().toBuffer();
  const img1 = PNG.sync.read(buf1);

  // Resize generated to match original dimensions
  const buf2 = await sharp(generatedPath)
    .resize(img1.width, img1.height)
    .png()
    .toBuffer();
  const img2 = PNG.sync.read(buf2);

  const { width, height } = img1;
  const diff = new PNG({ width, height });

  const mismatch = pixelmatch(img1.data, img2.data, diff.data, width, height, {
    threshold: 0.1,
  });

  const total = width * height;
  const similarity = ((1 - mismatch / total) * 100).toFixed(2);

  // Save diff image
  fs.writeFileSync(diffPath, PNG.sync.write(diff));

  console.log(`Original: ${width} x ${height}`);
  console.log(`Mismatched pixels: ${mismatch.toLocaleString()} / ${total.toLocaleString()}`);
  console.log(`Similarity: ${similarity}%`);

  return { mismatch, total, similarity: parseFloat(similarity) };
}

const [,, original, generated, diff] = process.argv;
if (!original || !generated) {
  console.error('Usage: node compare-screenshots.js <original> <generated> [diff-output]');
  process.exit(1);
}

compare(original, generated, diff).catch((error) => {
  console.error(error);
  process.exit(1);
});
