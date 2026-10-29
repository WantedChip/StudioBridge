import fs from 'node:fs';
import path from 'node:path';

// WCAG 2.2 Relative Luminance and Contrast Ratio calculation
function srgbToLinear(c: number): number {
  const norm = c / 255;
  return norm <= 0.04045 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4);
}

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace(/^#/, '');
  const bigint = parseInt(clean, 16);
  return [(bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255];
}

function relativeLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}

export function contrastRatio(hex1: string, hex2: string): number {
  const l1 = relativeLuminance(hex1);
  const l2 = relativeLuminance(hex2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

interface Palette {
  bg: string;
  surface: string;
  ink: string;
  'ink-muted': string;
  line: string;
  'line-strong': string;
  signal: string;
  'signal-text': string;
  ok: string;
  warn: string;
  err: string;
}

// Canonical token specifications
const EXPECTED_LIGHT: Palette = {
  bg: '#F3F0E8',
  surface: '#FBF9F4',
  ink: '#14130F',
  'ink-muted': '#55524A',
  line: '#CFC9BA',
  'line-strong': '#837E70',
  signal: '#E8461A',
  'signal-text': '#B8330F',
  ok: '#1D7A4A',
  warn: '#8A5A00',
  err: '#B3261E',
};

const EXPECTED_DARK: Palette = {
  bg: '#0F0F0D',
  surface: '#181815',
  ink: '#F1EEE6',
  'ink-muted': '#A9A497',
  line: '#34332C',
  'line-strong': '#74726A',
  signal: '#FF6A2B',
  'signal-text': '#FF6A2B',
  ok: '#5BD08B',
  warn: '#F2B84B',
  err: '#FF7B72',
};

function extractTokensFromCss(cssPath: string): { light: Partial<Palette>; dark: Partial<Palette> } {
  const content = fs.readFileSync(cssPath, 'utf8');

  // Extract root block
  const rootMatch = content.match(/:root\s*\{([^}]+)\}/);
  const darkMatch = content.match(/:root\[data-theme="dark"\]\s*\{([^}]+)\}/);

  const parseBlock = (block: string | undefined): Record<string, string> => {
    if (!block) return {};
    const tokens: Record<string, string> = {};
    const regex = /--([a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})/g;
    let m;
    while ((m = regex.exec(block)) !== null) {
      tokens[m[1]] = m[2].toUpperCase();
    }
    return tokens;
  };

  return {
    light: parseBlock(rootMatch?.[1]) as Partial<Palette>,
    dark: parseBlock(darkMatch?.[1]) as Partial<Palette>,
  };
}

interface CheckResult {
  role: string;
  token1: string;
  token2: string;
  color1: string;
  color2: string;
  ratio: number;
  minRequired: number;
  passed: boolean;
}

function runThemeChecks(palette: Palette): CheckResult[] {
  const results: CheckResult[] = [];

  const textTokens: (keyof Palette)[] = ['ink', 'ink-muted', 'signal-text', 'ok', 'warn', 'err'];
  const backgrounds: (keyof Palette)[] = ['bg', 'surface'];

  // Body text must achieve ≥ 4.5:1 against canvas backgrounds
  for (const textToken of textTokens) {
    for (const bgToken of backgrounds) {
      const c1 = palette[textToken];
      const c2 = palette[bgToken];
      const ratio = contrastRatio(c1, c2);
      results.push({
        role: `Text (${textToken}) on ${bgToken}`,
        token1: textToken,
        token2: bgToken,
        color1: c1,
        color2: c2,
        ratio,
        minRequired: 4.5,
        passed: ratio >= 4.5,
      });
    }
  }

  // UI boundaries / focus rails (line-strong) must achieve ≥ 3.0:1
  for (const bgToken of backgrounds) {
    const c1 = palette['line-strong'];
    const c2 = palette[bgToken];
    const ratio = contrastRatio(c1, c2);
    results.push({
      role: `UI Boundary (line-strong) on ${bgToken}`,
      token1: 'line-strong',
      token2: bgToken,
      color1: c1,
      color2: c2,
      ratio,
      minRequired: 3.0,
      passed: ratio >= 3.0,
    });
  }

  return results;
}

function checkFontBudget(fontsDir: string) {
  if (!fs.existsSync(fontsDir)) {
    throw new Error(`Fonts directory not found: ${fontsDir}`);
  }

  const files = fs.readdirSync(fontsDir).filter((f) => !f.startsWith('.'));
  console.log(`\nVerifying font budget in ${fontsDir}:`);
  console.log(`  Found ${files.length} font files (Budget: ≤ 3 files)`);

  if (files.length === 0) {
    throw new Error('No font files found in public/fonts/');
  }
  if (files.length > 3) {
    throw new Error(`Font file count (${files.length}) exceeds budget of ≤ 3 files`);
  }

  let totalBytes = 0;
  for (const file of files) {
    const filePath = path.join(fontsDir, file);
    const stat = fs.statSync(filePath);
    totalBytes += stat.size;

    // Check extension
    if (!file.endsWith('.woff2')) {
      throw new Error(`Font file ${file} is not a .woff2 file`);
    }

    // Check magic bytes: 'wOF2'
    const buf = Buffer.alloc(4);
    const fd = fs.openSync(filePath, 'r');
    fs.readSync(fd, buf, 0, 4, 0);
    fs.closeSync(fd);
    if (buf.toString('ascii') !== 'wOF2') {
      throw new Error(`Font file ${file} does not have valid wOF2 magic header`);
    }

    console.log(`  - ${file}: ${(stat.size / 1024).toFixed(1)} KB (valid wOF2)`);
  }

  const totalKb = totalBytes / 1024;
  console.log(`  Total font weight: ${totalKb.toFixed(1)} KB (Budget: ≤ 100 KB)`);
  if (totalBytes > 100 * 1024) {
    throw new Error(`Total font weight (${totalKb.toFixed(1)} KB) exceeds 100 KB budget!`);
  }
  console.log(`  [PASS] Font budget and file format verified.`);
}

function main() {
  const siteDir = path.resolve(import.meta.dirname, '..');
  const tokensCssPath = path.join(siteDir, 'src', 'styles', 'tokens.css');
  const fontsDir = path.join(siteDir, 'public', 'fonts');

  console.log('===============================================================');
  console.log(' StudioBridge Design System Contrast & Token Verification');
  console.log('===============================================================');

  // Verify CSS tokens exist on disk
  if (!fs.existsSync(tokensCssPath)) {
    console.error(`ERROR: tokens.css not found at ${tokensCssPath}`);
    process.exit(1);
  }

  const { light, dark } = extractTokensFromCss(tokensCssPath);

  // Validate extracted tokens match canonical spec
  for (const key of Object.keys(EXPECTED_LIGHT) as (keyof Palette)[]) {
    if (light[key] !== EXPECTED_LIGHT[key]) {
      console.error(`Mismatch in Light token --${key}: expected ${EXPECTED_LIGHT[key]}, found ${light[key]}`);
      process.exit(1);
    }
  }

  for (const key of Object.keys(EXPECTED_DARK) as (keyof Palette)[]) {
    if (dark[key] !== EXPECTED_DARK[key]) {
      console.error(`Mismatch in Dark token --${key}: expected ${EXPECTED_DARK[key]}, found ${dark[key]}`);
      process.exit(1);
    }
  }

  console.log('CSS token declarations in tokens.css match specification.\n');

  let allPassed = true;

  console.log('--- Light "Paper" Palette Contrast Ratios ---');
  const lightResults = runThemeChecks(EXPECTED_LIGHT);
  for (const r of lightResults) {
    const status = r.passed ? 'PASS' : 'FAIL';
    if (!r.passed) allPassed = false;
    console.log(
      `  [${status}] ${r.role.padEnd(42)} ${r.ratio.toFixed(2)}:1 (min ${r.minRequired}:1) [${r.color1} on ${r.color2}]`
    );
  }

  console.log('\n--- Dark "Rack" Palette Contrast Ratios ---');
  const darkResults = runThemeChecks(EXPECTED_DARK);
  for (const r of darkResults) {
    const status = r.passed ? 'PASS' : 'FAIL';
    if (!r.passed) allPassed = false;
    console.log(
      `  [${status}] ${r.role.padEnd(42)} ${r.ratio.toFixed(2)}:1 (min ${r.minRequired}:1) [${r.color1} on ${r.color2}]`
    );
  }

  // Accent fills contrast checks
  const lightInkOnSignal = contrastRatio(EXPECTED_LIGHT.ink, EXPECTED_LIGHT.signal);
  console.log(`\n--- Accent Fill Contrast Ratios ---`);
  console.log(
    `  [${lightInkOnSignal >= 4.5 ? 'PASS' : 'FAIL'}] Light ink on signal: ${lightInkOnSignal.toFixed(2)}:1 (min 4.5:1) [${EXPECTED_LIGHT.ink} on ${EXPECTED_LIGHT.signal}]`
  );
  if (lightInkOnSignal < 4.5) allPassed = false;

  const darkBgOnSignal = contrastRatio(EXPECTED_DARK.bg, EXPECTED_DARK.signal);
  console.log(
    `  [${darkBgOnSignal >= 4.5 ? 'PASS' : 'FAIL'}] Dark bg on signal:   ${darkBgOnSignal.toFixed(2)}:1 (min 4.5:1) [${EXPECTED_DARK.bg} on ${EXPECTED_DARK.signal}]`
  );
  if (darkBgOnSignal < 4.5) allPassed = false;

  // Verify Font budget
  checkFontBudget(fontsDir);

  if (!allPassed) {
    console.error('\nERROR: One or more contrast ratio checks failed!');
    process.exit(1);
  }

  console.log('\n===============================================================');
  console.log(' ALL CONTRAST & TYPOGRAPHY CHECKS PASSED (WCAG 2.2 AA)');
  console.log('===============================================================\n');
}

main();
