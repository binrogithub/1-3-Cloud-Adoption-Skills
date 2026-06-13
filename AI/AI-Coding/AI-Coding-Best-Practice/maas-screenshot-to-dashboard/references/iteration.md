# Iteration & Comparison Reference

## Screenshot Capture

### Using Puppeteer

```javascript
const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto('http://localhost:5173', {
    waitUntil: 'networkidle0',
    timeout: 30000
  });
  // Wait for ECharts to finish rendering
  await new Promise(r => setTimeout(r, 3000));
  await page.screenshot({
    path: 'generated-screenshot.png',
    fullPage: false
  });
  await browser.close();
})();
```

**Important**: Always wait 3+ seconds after `networkidle0` for ECharts async rendering.

## Pixel Comparison

### Using sharp + pixelmatch (Node.js)

```javascript
const sharp = require('sharp');
const fs = require('fs');
const { PNG } = require('pngjs');
const pixelmatch = require('pixelmatch').default;  // NOTE: .default for ESM

async function compare(originalPath, generatedPath, diffPath) {
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

  const mismatch = pixelmatch(
    img1.data, img2.data, diff.data,
    width, height,
    { threshold: 0.1 }
  );

  const total = width * height;
  const similarity = ((1 - mismatch / total) * 100).toFixed(2);

  // Save diff image
  fs.writeFileSync(diffPath, PNG.sync.write(diff));

  return { mismatch, total, similarity: parseFloat(similarity) };
}
```

### Common Issues with pixelmatch

| Issue | Cause | Fix |
|---|---|---|
| `pixelmatch is not a function` | ESM default export | Use `require('pixelmatch').default` |
| `TypeError: object of type 'int' has no len()` | Wrong data format (Python) | Use Node.js version instead |
| `PNG.sync.read` fails on JPEG | pngjs only reads PNG | Convert with `sharp().png()` first |

## Iteration Strategy

### Target: ≥ 85% similarity

### Iteration Loop (max 5 rounds)

```
Round 1: Initial implementation → compare → typically 65-75%
Round 2: Fix layout proportions → compare → typically 75-82%
Round 3: Fix chart sizes/data → compare → typically 80-85%
Round 4: Fine-tune colors/spacing → compare → typically 85-90%
Round 5: Polish details → compare → typically 88-95%
```

### What to Fix Each Round

**Round 1→2 (Layout)**:
- Check `grid-template-columns` proportions
- Check gap/spacing values
- Check KPI card grid (repeat(N, 1fr))
- Check column heights and flex behavior

**Round 2→3 (Charts)**:
- Verify chart data matches screenshot values
- Adjust chart heights (minHeight)
- Fix chart padding/margins inside cards
- Verify legend position and style

**Round 3→4 (Colors & Typography)**:
- Compare background colors with extract_colors.py output
- Adjust text opacity tiers
- Fix border colors and radii
- Verify font sizes match design.md

**Round 4→5 (Details)**:
- Table row height and padding
- KPI ring stroke width and size
- Tooltip style consistency
- Card header padding

### Analyzing the Diff Image

The diff image highlights mismatched pixels in red. Use it to identify:

1. **Large red blocks** → layout/position issues (wrong column width, missing component)
2. **Red outlines** → sizing issues (component too large/small)
3. **Scattered red pixels** → color/spacing differences (close but not exact)
4. **Red in chart areas** → data or chart config differences

## Dev Server Management

```bash
# Start
npx vite --port 5173 --host 0.0.0.0 &

# Find running port (Vite may use 5174 if 5173 is taken)
# Check output for "Local: http://localhost:XXXX/"

# Kill when done
pkill -f "vite"
```

## Git Workflow

After each successful iteration:

```bash
git add -A
git commit -m "Iteration N: <what changed>. Similarity: XX.XX%"
```

After reaching target similarity:

```bash
git add -A
git commit -m "Dashboard reconstruction complete. Similarity: XX.XX% (target: ≥85%)"
```
