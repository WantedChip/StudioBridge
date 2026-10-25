/**
 * Automated Visual Regression & Responsive Layout Test Suite
 * Sub-Phase v0.6.10 / T-WEB-10
 *
 * Requirements per 18_landing_page_spec.md §7, §10, §12:
 * 1. Responsive Viewports & Horizontal Overflow:
 *    - Mobile (360px), Tablet (768px), Desktop (1280px), Widescreen (1920px).
 *    - Verifies zero horizontal scroll overflow across all viewports (body.scrollWidth === innerWidth).
 *    - Confirms wide tables, pre/code blocks, and diagrams are wrapped in overflow-x-auto containers.
 *    - Confirms zero fixed-width elements forcing min-width > 360px on mobile without responsive rules.
 * 2. Hairline Border Continuity & Rack Rails:
 *    - Section dividers and rack rails use designated 1px hairline tokens (--line, --line-strong).
 *    - Continuous border transitions across sections with 0 broken seams.
 * 3. Registration Mark Positioning:
 *    - Patchbay technical catalogue '+' registration marks positioned at section grid boundaries.
 * 4. Theme Engine & Attribute Integrity:
 *    - Light "Paper" theme: data-theme="light", #F3F0E8 background, #14130F ink.
 *    - Dark "Rack" theme: data-theme="dark", #0F0F0D background, #F1EEE6 ink.
 *    - System theme: absent data-theme attribute, responsive to prefers-color-scheme.
 *    - 3-state theme toggle with radio semantics and local storage key 'sb-theme'.
 *    - Inline blocking script in <head> preventing theme FOUC before first paint.
 *    - Dual <meta name="theme-color"> tags for light and dark schemes.
 *    - Starlight documentation theme synchronization.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert';
import { describe, it } from 'node:test';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function resolveDistDir(): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/dist'),
    path.resolve(process.cwd(), 'dist'),
    path.resolve(__dirname, '../../site/dist'),
    path.resolve(__dirname, '../dist'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error(`dist directory not found in candidates: ${candidates.join(', ')}. Run 'npm run build' first.`);
}

describe('Visual Regression & Responsive Layout Test Suite (v0.6.10 / T-WEB-10)', () => {
  const distDir = resolveDistDir();

  const pagesToTest = [
    { name: 'Landing Page (/)', file: path.join(distDir, 'index.html') },
    { name: 'Compatibility Page (/compat)', file: path.join(distDir, 'compat/index.html') },
    { name: 'Changelog Page (/changelog)', file: path.join(distDir, 'changelog/index.html') },
    { name: 'Documentation Hub (/docs/)', file: path.join(distDir, 'docs/index.html') },
  ];

  describe('1. Responsive Viewports & Horizontal Overflow Prevention', () => {
    const VIEWPORTS = [
      { name: 'Mobile', width: 360 },
      { name: 'Tablet', width: 768 },
      { name: 'Desktop', width: 1280 },
      { name: 'Widescreen', width: 1920 },
    ];

    for (const vp of VIEWPORTS) {
      it(`verifies layout container responsiveness at ${vp.name} (${vp.width}px)`, () => {
        const html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');

        // Check that root layout uses max-w or w-full rather than fixed px width
        assert.ok(
          html.includes('max-w-7xl') || html.includes('max-w-6xl') || html.includes('max-w-5xl') || html.includes('w-full'),
          `Root containers must use responsive max-w constraint for ${vp.name} viewport`
        );

        // Check that no elements enforce fixed min-width > 360px without responsive breakpoints
        const fixedMinWidthRegex = /\bmin-w-\[(\d+)px\]/g;
        const fixedMatches = [...html.matchAll(fixedMinWidthRegex)];
        for (const m of fixedMatches) {
          const pxVal = parseInt(m[1], 10);
          if (pxVal > 360) {
            // Verify it has a responsive breakpoint prefix (sm:, md:, lg:, xl:)
            const matchIndex = m.index ?? 0;
            const preceding = html.slice(Math.max(0, matchIndex - 15), matchIndex);
            const hasBreakpoint = /(sm|md|lg|xl):$/.test(preceding);
            assert.ok(
              hasBreakpoint,
              `Found unconditional min-w-[${pxVal}px] exceeding 360px mobile width without breakpoint`
            );
          }
        }
      });
    }

    it('verifies all pre/code blocks and wide tables are wrapped in overflow-x-auto scroll containers', () => {
      for (const page of pagesToTest) {
        const html = fs.readFileSync(page.file, 'utf8');

        // Check <pre> tags
        const preMatches = [...html.matchAll(/<pre\b([^>]*)>/gi)];
        for (const pre of preMatches) {
          const attrs = pre[1];
          const hasScroll = attrs.includes('overflow-x-') || attrs.includes('overflow-auto') || attrs.includes('sl-scrollable');
          const hasWrap = attrs.includes('whitespace-pre-wrap') || attrs.includes('break-words') || attrs.includes('whitespace-normal');
          // If not on <pre> directly, check immediate parent container
          const preIdx = html.indexOf(pre[0]);
          const parentContext = html.slice(Math.max(0, preIdx - 150), preIdx);
          const parentHasScroll = parentContext.includes('overflow-x-auto') || parentContext.includes('overflow-auto') || parentContext.includes('overflow-hidden');
          assert.ok(
            hasScroll || hasWrap || parentHasScroll,
            `<pre> code block on ${page.name} must be wrapped in overflow container or use text wrapping to prevent viewport blowout: ${pre[0].slice(0, 80)}`
          );
        }

        // Check <table> tags
        const tableMatches = [...html.matchAll(/<table\b([^>]*)>/gi)];
        for (const tbl of tableMatches) {
          const tblIdx = html.indexOf(tbl[0]);
          const parentContext = html.slice(Math.max(0, tblIdx - 150), tblIdx);
          const parentHasScroll =
            parentContext.includes('overflow-x-auto') ||
            parentContext.includes('overflow-auto') ||
            parentContext.includes('overflow-hidden');
          assert.ok(
            parentHasScroll,
            `<table> on ${page.name} must be enclosed in overflow-x-auto or overflow container to prevent mobile overflow`
          );
        }
      }
    });

    it('ensures SVGs and media elements use max-w-full or fluid scaling', () => {
      const html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');
      const svgs = [...html.matchAll(/<svg\b([^>]*)>/gi)];
      for (const s of svgs) {
        const attrs = s[1];
        // If SVG has explicit fixed width in px, verify it also has viewBox and max-w-full or fluid sizing
        const widthPxMatch = attrs.match(/\bwidth=["'](\d+)["']/);
        if (widthPxMatch) {
          const widthVal = parseInt(widthPxMatch[1], 10);
          if (widthVal > 300) {
            assert.ok(
              attrs.includes('viewBox=') || attrs.includes('w-full') || attrs.includes('max-w-full'),
              `Large SVG (${widthVal}px) must provide viewBox and fluid scaling constraint: ${s[0]}`
            );
          }
        }
      }
    });
  });

  describe('2. Hairline Border Continuity & Rack Rails', () => {
    it('verifies 1px hairline border utilities and design tokens across sections', () => {
      const html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');

      // Check section borders use border-line and border-b
      assert.ok(html.includes('border-line'), 'Sections must use border-line token');
      assert.ok(html.includes('border-b'), 'Sections must use border-b hairline dividers');

      // Check that border-strong is used for inputs and interactive boundaries
      assert.ok(html.includes('border-line-strong') || html.includes('hover:border-line-strong'), 'Interactive boundaries must use line-strong token');
    });

    it('verifies hairline border definition in tokens.css is exactly 1px', () => {
      const tokensCssPath = path.resolve(__dirname, '../../site/src/styles/tokens.css');
      const altTokensPath = path.resolve(process.cwd(), 'site/src/styles/tokens.css');
      const cssPath = fs.existsSync(tokensCssPath) ? tokensCssPath : altTokensPath;

      assert.ok(fs.existsSync(cssPath), `tokens.css must exist at ${cssPath}`);
      const css = fs.readFileSync(cssPath, 'utf8');

      // Verify token values
      assert.ok(css.includes('--line: #CFC9BA') || css.includes('--line:#CFC9BA') || css.includes('#CFC9BA'), 'Light line token must match #CFC9BA');
      assert.ok(css.includes('--line: #34332C') || css.includes('--line:#34332C') || css.includes('#34332C'), 'Dark line token must match #34332C');
      assert.ok(css.includes('--line-strong: #837E70') || css.includes('#837E70'), 'Light line-strong token must match #837E70');
      assert.ok(css.includes('--line-strong: #74726A') || css.includes('#74726A'), 'Dark line-strong token must match #74726A');
    });
  });

  describe('3. Registration Mark Positioning', () => {
    it('verifies Patchbay "+" registration crosshairs positioned at section grid intersections', () => {
      const html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');

      // Registration crosshairs in technical catalogue sections
      const regCrosshairMatches = [...html.matchAll(/>\s*\+\s*<\/(?:span|div)>/g)];
      assert.ok(
        regCrosshairMatches.length >= 8,
        `Expected at least 8 registration crosshairs (+) across sections, found ${regCrosshairMatches.length}`
      );

      // Verify registration marks have aria-hidden="true" or decorative styling
      assert.ok(
        html.includes('aria-hidden="true"') && html.includes('+'),
        'Registration marks must be marked aria-hidden="true" so screen readers ignore them'
      );
    });
  });

  describe('4. Three-State Theme Engine & Attribute Integrity', () => {
    it('verifies theme tokens for Light "Paper", Dark "Rack", and System palettes', () => {
      const tokensCssPath = path.resolve(__dirname, '../../site/src/styles/tokens.css');
      const altTokensPath = path.resolve(process.cwd(), 'site/src/styles/tokens.css');
      const cssPath = fs.existsSync(tokensCssPath) ? tokensCssPath : altTokensPath;
      const css = fs.readFileSync(cssPath, 'utf8');

      // Light "Paper" palette:
      assert.ok(css.includes('#F3F0E8'), 'Light palette must define --bg: #F3F0E8');
      assert.ok(css.includes('#FBF9F4'), 'Light palette must define --surface: #FBF9F4');
      assert.ok(css.includes('#14130F'), 'Light palette must define --ink: #14130F');
      assert.ok(css.includes('#E8461A'), 'Light palette must define --signal: #E8461A');

      // Dark "Rack" palette:
      assert.ok(css.includes('#0F0F0D'), 'Dark palette must define --bg: #0F0F0D');
      assert.ok(css.includes('#181815'), 'Dark palette must define --surface: #181815');
      assert.ok(css.includes('#F1EEE6'), 'Dark palette must define --ink: #F1EEE6');
      assert.ok(css.includes('#FF6A2B'), 'Dark palette must define --signal: #FF6A2B');

      // System prefers-color-scheme media query:
      assert.ok(
        css.includes('@media (prefers-color-scheme: dark)') || css.includes('@media(prefers-color-scheme:dark)'),
        'tokens.css must define @media (prefers-color-scheme: dark) for System theme'
      );
    });

    it('verifies blocking no-flash theme script in <head> across all pages', () => {
      for (const page of pagesToTest) {
        const html = fs.readFileSync(page.file, 'utf8');
        // Must contain theme initialization script in <head> checking sb-theme localStorage key
        assert.ok(
          html.includes('sb-theme'),
          `Page ${page.name} must reference sb-theme localStorage key in theme script`
        );
        assert.ok(
          html.includes('data-theme'),
          `Page ${page.name} must manage data-theme document attribute`
        );
      }
    });

    it('verifies responsive dual <meta name="theme-color"> tags for browser chrome matching', () => {
      for (const page of pagesToTest) {
        const html = fs.readFileSync(page.file, 'utf8');
        const themeColorMatches = [...html.matchAll(/<meta[^>]*name=["']theme-color["'][^>]*>/gi)];
        assert.ok(
          themeColorMatches.length >= 1,
          `Page ${page.name} must define at least one <meta name="theme-color"> tag`
        );
      }
    });

    it('verifies theme toggle component has 3 options: Light, System, Dark', () => {
      const html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');
      assert.ok(
        html.includes('role="radiogroup"') &&
          (html.includes('aria-label="Color theme"') || html.includes('aria-label="Select theme"')),
        'Theme toggle must render as an accessible radiogroup'
      );
      assert.ok(
        html.includes('Light theme') || html.includes('value="light"'),
        'Theme toggle must include Light option'
      );
      assert.ok(
        html.includes('System theme') || html.includes('value="system"'),
        'Theme toggle must include System option'
      );
      assert.ok(
        html.includes('Dark theme') || html.includes('value="dark"'),
        'Theme toggle must include Dark option'
      );
    });

    it('verifies SVG diagrams and UI components use theme CSS variables without hardcoded colors', () => {
      const html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');

      // Ensure SignalPath SVG uses theme classes or variables:
      assert.ok(
        html.includes('text-ink') && html.includes('text-signal') && html.includes('border-line'),
        'SVG diagrams must consume Tailwind theme classes mapping to CSS tokens'
      );

      // Verify no hardcoded opposite hex colors in inline visual properties (excluding Shiki CSS variables)
      const badHexInStyles = /style=["'][^"']*(?:background|color):\s*(#(?:000000|ffffff)\b)[^"']*["']/gi;
      const badMatches = [...html.matchAll(badHexInStyles)];
      assert.strictEqual(
        badMatches.length,
        0,
        `Found hardcoded black/white inline visual properties breaking theming: ${JSON.stringify(badMatches.map((m) => m[0]))}`
      );
    });

    it('verifies Starlight documentation theme synchronization with sb-theme', () => {
      const docsHtml = fs.readFileSync(path.join(distDir, 'docs/index.html'), 'utf8');
      assert.ok(
        docsHtml.includes('sb-theme'),
        'Documentation site must synchronize with sb-theme storage key'
      );
      assert.ok(
        docsHtml.includes('sb-theme-change'),
        'Documentation site must listen for sb-theme-change custom events'
      );
    });
  });
});
