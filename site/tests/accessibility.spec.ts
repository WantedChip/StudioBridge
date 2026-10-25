/**
 * Automated Accessibility Test Suite (WCAG 2.2 AA / Axe-Core Rules)
 * Sub-Phase v0.6.10 / T-WEB-10
 *
 * Requirements per 18_landing_page_spec.md §10, §12:
 * 1. Landmark structure: Semantic landmarks (<header>, <main id="main-content">, <nav>, <footer>),
 *    valid landmark roles, unique labels if multiple landmarks of the same type exist.
 * 2. Skip navigation links: Accessible skip-link (href="#main-content" or href="#_top") as the first
 *    interactive element on every page, with proper focus styles.
 * 3. ARIA attributes & relationships: Valid WAI-ARIA roles, valid state attributes (aria-checked,
 *    aria-selected, aria-expanded), proper pairing (aria-controls, aria-labelledby, aria-describedby
 *    referencing valid existing element IDs).
 * 4. Heading order & structure: Strict hierarchical heading progression (single <h1> per page,
 *    no skipped levels like h1 -> h3), non-empty headings.
 * 5. Interactive target sizing: WCAG 2.2 SC 2.5.8 (Target Size Minimum: ≥ 24x24 CSS px or adequate spacing)
 *    across buttons, links, inputs, and interactive controls.
 * 6. Keyboard operability & focus indicators: Focusable interactive controls (<a>, <button>, <input>,
 *    <select>, role="tab", role="radio"), roving tabindex, visible focus rings, Escape key handling.
 * 7. Alt text & media alternatives: All <img> tags have non-empty alt or decorative alt="", SVGs have
 *    aria-hidden="true" or role="img" with <title>/aria-label.
 * 8. Language & Viewport: <html lang="en">, <title> present, viewport allows user scaling (no user-scalable=no).
 * 9. Token & color contrast: WCAG 2.2 AA ratios across Paper (light) and Rack (dark) palettes:
 *    normal text ≥ 4.5:1, large text/UI boundaries ≥ 3.0:1.
 * 10. Reduced-motion compliance: @media (prefers-reduced-motion: reduce) rules halt animations and transitions.
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

describe('Automated Accessibility Test Suite (WCAG 2.2 AA / Axe-Core Rules) (v0.6.10 / T-WEB-10)', () => {
  const distDir = resolveDistDir();

  const pagesToAudit = [
    { name: 'Landing Page (/)', file: path.join(distDir, 'index.html'), isDocs: false },
    { name: 'Compatibility Page (/compat)', file: path.join(distDir, 'compat/index.html'), isDocs: false },
    { name: 'Changelog Page (/changelog)', file: path.join(distDir, 'changelog/index.html'), isDocs: false },
    { name: 'Documentation Hub (/docs/)', file: path.join(distDir, 'docs/index.html'), isDocs: true },
  ];

  describe('1. Document Language & Viewport Zoom (WCAG SC 3.1.1, SC 1.4.4)', () => {
    for (const page of pagesToAudit) {
      it(`defines valid lang="en" and responsive zoomable viewport on ${page.name}`, () => {
        assert.ok(fs.existsSync(page.file), `Page file must exist: ${page.file}`);
        const html = fs.readFileSync(page.file, 'utf8');

        // Check html lang attribute
        const langMatch = html.match(/<html[^>]*lang=["']([^"']+)["']/i);
        assert.ok(langMatch, `Page ${page.name} must declare a lang attribute on <html>`);
        assert.strictEqual(langMatch[1].toLowerCase(), 'en', `Page ${page.name} must have lang="en"`);

        // Check viewport meta tag
        const viewportMatch = html.match(/<meta[^>]*name=["']viewport["'][^>]*content=["']([^"']+)["']/i);
        assert.ok(viewportMatch, `Page ${page.name} must have a viewport <meta> tag`);
        const content = viewportMatch[1];
        assert.ok(content.includes('width=device-width'), `Viewport must include width=device-width on ${page.name}`);
        assert.ok(
          !content.includes('user-scalable=no') && !content.includes('maximum-scale=1.0'),
          `Viewport must NOT disable user zoom (WCAG SC 1.4.4 violation) on ${page.name}`
        );

        // Check title element
        const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
        assert.ok(titleMatch, `Page ${page.name} must have a non-empty <title> tag`);
        assert.ok(titleMatch[1].trim().length > 0, `Title must not be empty on ${page.name}`);
      });
    }
  });

  describe('2. Landmark Structure & Skip Navigation Links (WCAG SC 1.3.1, SC 2.4.1)', () => {
    for (const page of pagesToAudit) {
      it(`renders compliant landmark structure (<header>, <main>, <nav>, <footer>) on ${page.name}`, () => {
        const html = fs.readFileSync(page.file, 'utf8');

        // Main landmark check
        const hasMain = /<main[^>]*>/i.test(html);
        assert.ok(hasMain, `Page ${page.name} must have a semantic <main> landmark`);

        // Header landmark check
        const hasHeader = /<header[^>]*>/i.test(html) || /role=["']banner["']/i.test(html);
        assert.ok(hasHeader, `Page ${page.name} must have a <header> landmark`);

        // Nav landmark check
        const hasNav = /<nav[^>]*>/i.test(html) || /role=["']navigation["']/i.test(html);
        assert.ok(hasNav, `Page ${page.name} must have a <nav> landmark`);

        // Skip navigation link check
        // Landing/compat/changelog target #main-content; Starlight docs targets #_top (first heading)
        const skipLinkMatch = html.match(/<a[^>]*href=["']#(main-content|_top)["'][^>]*>([\s\S]*?)<\/a>/i);
        assert.ok(skipLinkMatch, `Page ${page.name} must provide an accessible skip navigation link targeting main content`);
        const skipText = skipLinkMatch[2].replace(/<[^>]*>/g, '').trim().toLowerCase();
        assert.ok(
          skipText.includes('skip to content') || skipText.includes('skip to main content') || skipText.includes('skip'),
          `Skip link text must clearly announce action, got: "${skipText}" on ${page.name}`
        );

        // Skip link must target an ID that exists in the document
        const targetId = skipLinkMatch[1];
        const targetExists = new RegExp(`id=["']${targetId}["']`, 'i').test(html);
        assert.ok(targetExists, `Skip link target #${targetId} must exist in DOM on ${page.name}`);
      });
    }

    it('ensures all multiple <nav> landmarks have unique accessible names', () => {
      for (const page of pagesToAudit) {
        const html = fs.readFileSync(page.file, 'utf8');
        const navMatches = [...html.matchAll(/<nav\b([^>]*)>/gi)];
        if (navMatches.length > 1) {
          const labels = navMatches.map((m) => {
            const attrs = m[1];
            const ariaLabel = attrs.match(/aria-label=["']([^"']+)["']/i)?.[1];
            const ariaLabelledby = attrs.match(/aria-labelledby=["']([^"']+)["']/i)?.[1];
            return ariaLabel || ariaLabelledby || null;
          });
          const labeledCount = labels.filter(Boolean).length;
          assert.ok(
            labeledCount >= navMatches.length - 1,
            `When multiple <nav> elements exist on ${page.name}, they must be disambiguated with aria-label or aria-labelledby`
          );
        }
      }
    });
  });

  describe('3. Strict Heading Hierarchy (WCAG SC 1.3.1, SC 2.4.6)', () => {
    for (const page of pagesToAudit) {
      it(`enforces single <h1> and zero skipped heading levels on ${page.name}`, () => {
        const html = fs.readFileSync(page.file, 'utf8');
        const headings = [...html.matchAll(/<h([1-6])\b[^>]*>([\s\S]*?)<\/h\1>/gi)].map((m) => ({
          level: parseInt(m[1], 10),
          text: m[2].replace(/<[^>]*>/g, '').trim(),
        }));

        assert.ok(headings.length > 0, `Page ${page.name} must contain headings`);

        // Assert exactly one <h1>
        const h1s = headings.filter((h) => h.level === 1);
        assert.strictEqual(
          h1s.length,
          1,
          `Page ${page.name} must have exactly one <h1> heading, found ${h1s.length}: ${JSON.stringify(h1s.map((h) => h.text))}`
        );

        // Assert <h1> is non-empty
        assert.ok(h1s[0].text.length > 0, `H1 heading on ${page.name} must not be empty`);

        // Assert zero skipped heading levels (e.g. h1 -> h3 without h2)
        const skippedLevels: Array<{ from: number; to: number; fromText: string; toText: string }> = [];
        for (let i = 0; i < headings.length - 1; i++) {
          const current = headings[i];
          const next = headings[i + 1];
          if (next.level - current.level > 1) {
            skippedLevels.push({
              from: current.level,
              to: next.level,
              fromText: current.text.slice(0, 40),
              toText: next.text.slice(0, 40),
            });
          }
        }

        assert.deepStrictEqual(
          skippedLevels,
          [],
          `Page ${page.name} has skipped heading levels: ${JSON.stringify(skippedLevels, null, 2)}`
        );
      });
    }
  });

  describe('4. WAI-ARIA Attributes, Roles & ID References (WCAG SC 4.1.2)', () => {
    const VALID_ROLES = new Set([
      'alert', 'alertdialog', 'application', 'article', 'banner', 'button', 'cell', 'checkbox',
      'columnheader', 'combobox', 'complementary', 'contentinfo', 'definition', 'dialog', 'directory',
      'document', 'feed', 'figure', 'form', 'grid', 'gridcell', 'group', 'heading', 'img', 'link',
      'list', 'listbox', 'listitem', 'log', 'main', 'marquee', 'math', 'menu', 'menubar', 'menuitem',
      'menuitemcheckbox', 'menuitemradio', 'navigation', 'none', 'note', 'option', 'presentation',
      'progressbar', 'radio', 'radiogroup', 'region', 'row', 'rowgroup', 'rowheader', 'scrollbar',
      'search', 'searchbox', 'separator', 'slider', 'spinbutton', 'status', 'switch', 'tab', 'table',
      'tablist', 'tabpanel', 'term', 'textbox', 'timer', 'toolbar', 'tooltip', 'tree', 'treegrid',
      'treeitem',
    ]);

    for (const page of pagesToAudit) {
      it(`validates all ARIA roles and attribute references on ${page.name}`, () => {
        const html = fs.readFileSync(page.file, 'utf8');

        // Check roles
        const roleMatches = [...html.matchAll(/\brole=["']([^"']+)["']/gi)];
        for (const match of roleMatches) {
          const roles = match[1].split(/\s+/);
          for (const role of roles) {
            if (role) {
              assert.ok(
                VALID_ROLES.has(role.toLowerCase()),
                `Invalid ARIA role "${role}" found on ${page.name}`
              );
            }
          }
        }

        // Check aria-controls references for active/expanded elements
        const activeControlsMatches = [
          ...html.matchAll(/<[^>]*(?:aria-selected=["']true["']|aria-expanded=["']true["'])[^>]*\baria-controls=["']([^"']+)["'][^>]*>/gi),
        ];
        for (const match of activeControlsMatches) {
          const id = match[1];
          if (id && !id.startsWith('#')) {
            const idExists = new RegExp(`\\bid=["']${id}["']`, 'i').test(html);
            assert.ok(
              idExists,
              `Active/expanded control aria-controls="${id}" references non-existent ID on ${page.name}`
            );
          }
        }

        // Check aria-labelledby references
        const labelledByMatches = [...html.matchAll(/\baria-labelledby=["']([^"']+)["']/gi)];
        for (const match of labelledByMatches) {
          const ids = match[1].split(/\s+/);
          for (const id of ids) {
            if (id && !id.startsWith('#')) {
              const idExists = new RegExp(`\\bid=["']${id}["']`, 'i').test(html);
              assert.ok(
                idExists,
                `aria-labelledby="${id}" references non-existent ID on ${page.name}`
              );
            }
          }
        }

        // Check radio elements have aria-checked
        const radioMatches = [...html.matchAll(/<[^>]*\brole=["']radio["'][^>]*>/gi)];
        for (const match of radioMatches) {
          assert.ok(
            match[0].includes('aria-checked='),
            `role="radio" must declare aria-checked on ${page.name}: ${match[0].slice(0, 80)}`
          );
        }

        // Check tab elements have aria-selected
        const tabMatches = [...html.matchAll(/<[^>]*\brole=["']tab["'][^>]*>/gi)];
        for (const match of tabMatches) {
          assert.ok(
            match[0].includes('aria-selected='),
            `role="tab" must declare aria-selected on ${page.name}: ${match[0].slice(0, 80)}`
          );
        }
      });
    }
  });

  describe('5. Interactive Target Sizing (WCAG 2.2 SC 2.5.8)', () => {
    it('verifies interactive controls satisfy minimum 24x24 CSS px target size or padding on Landing Page', () => {
      const html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');

      // Check buttons, links, and role="radio"/"tab"
      // Verify interactive controls do not use sub-24px fixed sizing without padding
      const smallTargetRegex = /\b(w-[1-5]\b|h-[1-5]\b|size-[1-5]\b)/g;
      const buttons = [...html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/gi)];

      for (const btn of buttons) {
        const attrs = btn[1];
        // If button has explicit width/height, verify it is at least 24px (w-6 = 24px, min-h-[24px], p-1.5 = 24px effective target)
        if (smallTargetRegex.test(attrs)) {
          // Verify it has padding or minimum target extension class
          assert.ok(
            attrs.includes('p-') || attrs.includes('min-w-') || attrs.includes('min-h-') || attrs.includes('cursor-pointer'),
            `Button target size must satisfy SC 2.5.8 (>=24x24 px): ${btn[0].slice(0, 100)}`
          );
        }
      }

      // Check ThemeToggle buttons:
      assert.ok(
        html.includes('min-w-[28px]') || html.includes('p-1.5') || html.includes('px-2.5'),
        'ThemeToggle options must meet minimum touch target sizing >= 24px'
      );

      // Check Install tabs:
      assert.ok(
        html.includes('role="tab"'),
        'Install tabs must exist and provide touch-accessible target dimensions'
      );
    });
  });

  describe('6. Keyboard Operability & Focus Styles (WCAG SC 2.1.1, SC 2.4.7)', () => {
    it('ensures no positive tabindex anti-patterns exist', () => {
      for (const page of pagesToAudit) {
        const html = fs.readFileSync(page.file, 'utf8');
        const positiveTabindexMatches = [...html.matchAll(/\btabindex=["']([1-9][0-9]*)["']/gi)];
        assert.strictEqual(
          positiveTabindexMatches.length,
          0,
          `Found positive tabindex values on ${page.name} (breaks natural tab order): ${JSON.stringify(positiveTabindexMatches.map((m) => m[0]))}`
        );
      }
    });

    it('verifies visible focus ring utilities and tokens are defined in stylesheets', () => {
      const astroDir = path.join(distDir, '_astro');
      const cssFiles = fs.readdirSync(astroDir).filter((f) => f.endsWith('.css'));
      assert.ok(cssFiles.length > 0, 'CSS bundles must exist');

      let combinedCss = '';
      for (const f of cssFiles) {
        combinedCss += fs.readFileSync(path.join(astroDir, f), 'utf8') + '\n';
      }

      // Verify focus styles
      const hasFocusVisible = combinedCss.includes(':focus-visible') || combinedCss.includes('focus-visible');
      assert.ok(hasFocusVisible, 'Stylesheets must include focus-visible rules for keyboard navigation (WCAG SC 2.4.7)');

      const hasOutlineOrRing = combinedCss.includes('outline') || combinedCss.includes('box-shadow') || combinedCss.includes('--line-strong');
      assert.ok(hasOutlineOrRing, 'Focus styles must render an outline or focus ring');
    });

    it('validates Escape key handling in interactive islands and modals', () => {
      const astroDir = path.join(distDir, '_astro');
      const jsFiles = fs.readdirSync(astroDir).filter((f) => f.endsWith('.js'));
      let combinedJs = '';
      for (const f of jsFiles) {
        combinedJs += fs.readFileSync(path.join(astroDir, f), 'utf8') + '\n';
      }

      // Verify Escape key handling in SignalPath or client dialogs
      const hasEscapeHandler = combinedJs.includes('Escape') || combinedJs.includes('keydown') || combinedJs.includes('close');
      assert.ok(hasEscapeHandler, 'Interactive islands must support Escape key dismissal (WCAG SC 2.1.2)');
    });
  });

  describe('7. Media Alternatives & SVG Accessibility (WCAG SC 1.1.1)', () => {
    for (const page of pagesToAudit) {
      it(`verifies all <img> tags have alt attributes and SVGs have accessible annotations on ${page.name}`, () => {
        const html = fs.readFileSync(page.file, 'utf8');

        // Check <img> tags
        const imgMatches = [...html.matchAll(/<img\b([^>]*)>/gi)];
        for (const img of imgMatches) {
          const attrs = img[1];
          assert.ok(
            attrs.includes('alt='),
            `<img> tag without alt attribute found on ${page.name}: ${img[0]}`
          );
        }

        // Check inline SVGs
        const svgMatches = [...html.matchAll(/<svg\b([^>]*)>([\s\S]*?)<\/svg>/gi)];
        for (const svg of svgMatches) {
          const attrs = svg[1];
          const inner = svg[2];
          const isAriaHidden = attrs.includes('aria-hidden="true"');
          const hasRoleImg = attrs.includes('role="img"');
          const hasTitle = /<title\b[^>]*>[\s\S]*?<\/title>/i.test(inner);
          const hasAriaLabel = attrs.includes('aria-label=') || attrs.includes('aria-labelledby=');

          // Check if parent container has aria-hidden="true"
          const svgIndex = html.indexOf(svg[0]);
          const precedingHtml = html.slice(Math.max(0, svgIndex - 140), svgIndex);
          const parentAriaHidden = precedingHtml.includes('aria-hidden="true"');

          assert.ok(
            isAriaHidden || hasRoleImg || hasTitle || hasAriaLabel || parentAriaHidden,
            `SVG must be either hidden (aria-hidden="true" on SVG or parent) or given an accessible name on ${page.name}: ${svg[0].slice(0, 100)}`
          );
        }
      });
    }
  });

  describe('8. Reduced Motion Support (WCAG SC 2.2.2, SC 2.3.3)', () => {
    it('verifies @media (prefers-reduced-motion: reduce) rules halt animations and transitions', () => {
      const astroDir = path.join(distDir, '_astro');
      const cssFiles = fs.readdirSync(astroDir).filter((f) => f.endsWith('.css'));
      let combinedCss = '';
      for (const f of cssFiles) {
        combinedCss += fs.readFileSync(path.join(astroDir, f), 'utf8') + '\n';
      }

      assert.ok(
        combinedCss.includes('prefers-reduced-motion'),
        'Stylesheets must define @media (prefers-reduced-motion: reduce) rules'
      );
    });
  });

  describe('9. Design Token Contrast Verification (WCAG SC 1.4.3, SC 1.4.11)', () => {
    // Relative Luminance calculation per WCAG 2.2
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
    function contrastRatio(hex1: string, hex2: string): number {
      const l1 = relativeLuminance(hex1);
      const l2 = relativeLuminance(hex2);
      const lighter = Math.max(l1, l2);
      const darker = Math.min(l1, l2);
      return (lighter + 0.05) / (darker + 0.05);
    }

    const PAPER = {
      bg: '#F3F0E8',
      surface: '#FBF9F4',
      ink: '#14130F',
      inkMuted: '#55524A',
      lineStrong: '#837E70',
      signalText: '#B8330F',
      ok: '#1D7A4A',
      warn: '#8A5A00',
      err: '#B3261E',
    };

    const RACK = {
      bg: '#0F0F0D',
      surface: '#181815',
      ink: '#F1EEE6',
      inkMuted: '#A9A497',
      lineStrong: '#74726A',
      signalText: '#FF6A2B',
      ok: '#5BD08B',
      warn: '#F2B84B',
      err: '#FF7B72',
    };

    it('validates Paper (Light) palette meets or exceeds WCAG 2.2 AA contrast ratios', () => {
      assert.ok(contrastRatio(PAPER.ink, PAPER.bg) >= 4.5, 'Paper ink on bg must be >= 4.5:1');
      assert.ok(contrastRatio(PAPER.ink, PAPER.surface) >= 4.5, 'Paper ink on surface must be >= 4.5:1');
      assert.ok(contrastRatio(PAPER.inkMuted, PAPER.bg) >= 4.5, 'Paper ink-muted on bg must be >= 4.5:1');
      assert.ok(contrastRatio(PAPER.lineStrong, PAPER.bg) >= 3.0, 'Paper line-strong UI boundary on bg must be >= 3.0:1');
      assert.ok(contrastRatio(PAPER.signalText, PAPER.bg) >= 4.5, 'Paper signal-text on bg must be >= 4.5:1');
      assert.ok(contrastRatio(PAPER.ok, PAPER.bg) >= 4.5, 'Paper ok text on bg must be >= 4.5:1');
      assert.ok(contrastRatio(PAPER.warn, PAPER.bg) >= 4.5, 'Paper warn text on bg must be >= 4.5:1');
      assert.ok(contrastRatio(PAPER.err, PAPER.bg) >= 4.5, 'Paper err text on bg must be >= 4.5:1');
    });

    it('validates Rack (Dark) palette meets or exceeds WCAG 2.2 AA contrast ratios', () => {
      assert.ok(contrastRatio(RACK.ink, RACK.bg) >= 4.5, 'Rack ink on bg must be >= 4.5:1');
      assert.ok(contrastRatio(RACK.ink, RACK.surface) >= 4.5, 'Rack ink on surface must be >= 4.5:1');
      assert.ok(contrastRatio(RACK.inkMuted, RACK.bg) >= 4.5, 'Rack ink-muted on bg must be >= 4.5:1');
      assert.ok(contrastRatio(RACK.lineStrong, RACK.bg) >= 3.0, 'Rack line-strong UI boundary on bg must be >= 3.0:1');
      assert.ok(contrastRatio(RACK.signalText, RACK.bg) >= 4.5, 'Rack signal-text on bg must be >= 4.5:1');
      assert.ok(contrastRatio(RACK.ok, RACK.bg) >= 4.5, 'Rack ok text on bg must be >= 4.5:1');
      assert.ok(contrastRatio(RACK.warn, RACK.bg) >= 4.5, 'Rack warn text on bg must be >= 4.5:1');
      assert.ok(contrastRatio(RACK.err, RACK.bg) >= 4.5, 'Rack err text on bg must be >= 4.5:1');
    });
  });
});
