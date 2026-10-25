# StudioBridge Web & Documentation Workspace (`site/`)

Welcome to the `site/` workspace of StudioBridge. This directory contains the authoritative landing page, interactive technical showcases, and Astro Starlight documentation hub for the StudioBridge platform.

Hosted statically on Cloudflare Workers with zero server dependencies, zero client tracking, zero external blocking network requests, and zero-JS baseline rendering.

---

## 1. Architecture Overview

| Layer | Technology | Purpose |
|---|---|---|
| **Core Framework** | **Astro 5 / 7** (`output: "static"`) | Static-first HTML generation. Zero client-side JavaScript shipped by default. |
| **Documentation Hub** | **Astro Starlight** (`/docs/*`) | Deep documentation site sharing tokens, fonts, and theme synchronization with the landing page. Built-in Pagefind search. |
| **Design System** | **Patchbay** ("Technical Catalogue") | Industrial technical hardware catalogue language: 1px hairlines, rack rails, registration marks (`+`), status LEDs, tabular numerals, mono labels. |
| **Interactive Islands** | **React 19** (`@astrojs/react`) | Selective hydration with `client:visible` for heavy interactive tools and `client:load` for persistent header controls. |
| **Styling** | **Tailwind CSS v4** + `tokens.css` | CSS-first custom design tokens. No generic third-party UI framework themes. |
| **Edge Hosting** | **Cloudflare Workers** (Static Assets) | Global low-latency CDN asset serving with immutable caching for hashed chunks. |

### Three-State Theme Engine (`[THM-01]` – `[THM-07]`)
- **Light ("Paper"):** `#F3F0E8` ground, `#FBF9F4` surface, `#14130F` ink, `#E8461A` signal accent.
- **Dark ("Rack"):** `#0F0F0D` ground, `#181815` surface, `#F1EEE6` ink, `#FF6A2B` signal accent.
- **System (Default):** Evaluates `prefers-color-scheme` live without flash of wrong theme (`[THM-01]` head script).
- **Synchronized State:** Persisted under `localStorage` key `sb-theme` (`light` | `dark` | `system`). Bidirectionally synced between landing page and Starlight docs via custom `sb-theme-change` events.

---

## 2. Directory Structure

```
site/
├── astro.config.mjs        # Astro & Starlight configuration (routes, sidebar, theme overrides)
├── wrangler.jsonc          # Cloudflare Workers static assets deployment manifest
├── package.json            # Node.js workspace dependencies and audit scripts
├── public/
│   ├── _headers            # Cloudflare security headers (strict CSP, nosniff, frame-ancestors)
│   ├── _redirects          # Canonical 301/302 edge redirects
│   ├── fonts/              # Self-hosted WOFF2 variable fonts (Bricolage, Inter Tight, JetBrains Mono)
│   ├── llms.txt            # Machine-readable LLM architectural summary
│   ├── llms-full.txt       # Consolidated documentation suite (235KB+ Markdown)
│   ├── og.png & og.svg     # Pre-rendered 1200x630 OpenGraph social preview cards
│   └── robots.txt          # Crawler policy pointing to sitemap and RSS feeds
├── scripts/
│   ├── check-contrast.ts   # WCAG 2.2 contrast ratio validator
│   ├── check-landing-html.ts # Zero-JS HTML structure assertion suite
│   ├── gen-agents.ts       # Template sync ingesting packages/studiobridge templates
│   ├── gen-api-cards.ts    # Generates 119 Starlight API reference function cards
│   ├── gen-compat.ts       # Generates data/compat.json from diagnostics fixtures
│   ├── gen-llms.ts         # Consolidates all docs into public/llms-full.txt
│   └── gen-og.ts           # Renders og.svg and rasterizes og.png via Sharp
├── src/
│   ├── components/         # Static Astro components (Header, Hero, Footer, etc.)
│   │   ├── islands/        # Interactive React islands (SignalPath, InstallTabs, ConsoleDemo, Matrix)
│   │   └── starlight/      # Starlight ThemeProvider and ThemeSelect overrides
│   ├── content/docs/       # Starlight markdown articles (Getting Started, Architecture, Guides, API)
│   ├── data/               # Build-time generated JSON datasets (agents.json, compat.json, sessions/)
│   ├── pages/              # Astro pages (index.astro, compat.astro, changelog.astro, rss.xml.ts)
│   └── styles/             # Design tokens (tokens.css) and global base styles
└── tests/                  # Automated web quality audit suites
    ├── accessibility.spec.ts  # Axe-core / WCAG 2.2 AA audit suite
    ├── performance.spec.ts    # Bundle budgets, font weights & Lighthouse lab audits
    └── visual_regression.spec.ts # Responsive viewports, hairline continuity & themes
```

---

## 3. Local Development

### Prerequisites
- Node.js 20+ (recommended: Node.js 22 LTS)
- npm 10+

### Setup & Development Server
```bash
# Install dependencies
npm ci

# Start local development server with hot-reload
npm run dev
# -> Local server live at http://localhost:4321/
```

### Static Build & Preview
```bash
# Run prebuild generators and static compilation
npm run build

# Preview production build locally
npm run preview
```

### Type Checking
```bash
# Verify TypeScript and Astro types
npm run check
# or
npm run typecheck
```

---

## 4. Quality Gates & Automated Audit Suites

All merges and deployments are gated by strict automated test suites in `tests/`:

```bash
# Run complete web quality audit (a11y + visual + perf)
npm run test:audit

# Individual audit suites
npm run test:a11y        # WCAG 2.2 AA accessibility audit (zero violations)
npm run test:visual      # Responsive viewports (360px-1920px) & theme integrity
npm run test:perf        # Bundle size budgets & Lighthouse lab metric thresholds

# Component and integration suites
npm run test:hero        # Hero signal-path diagram & copy interactions
npm run test:install     # Dynamic agent installation tabs & template parity
npm run test:demo        # Console demo island & session playback
npm run test:compat      # Capability matrix & compatibility page
npm run test:docs        # Starlight documentation articles & API reference cards
npm run test:metadata    # SEO, GEO, JSON-LD, OpenGraph & llms.txt validation
npm run test:contrast    # WCAG 2.2 AA design token contrast ratios
npm run test:html        # Zero-JS static landing page HTML semantics
```

### Performance Budgets & Hard Thresholds

| Metric | Budget / Threshold | Measured Result | Status |
|---|---|---|---|
| **Initial JavaScript on `/`** | `≤ 90 KB` gzip | **69.6 KB** gzip | **PASS** (20.4 KB headroom) |
| **Self-Hosted Font Files** | `≤ 3` files | **3** files (WOFF2) | **PASS** |
| **Self-Hosted Font Weight** | `≤ 100 KB` total | **64.0 KB** total | **PASS** (36.0 KB headroom) |
| **Third-Party Blocking Requests** | `0` external calls | **0** external requests | **PASS** (100% self-hosted) |
| **Lighthouse Performance** | `≥ 95` / 100 | **100** / 100 | **PASS** |
| **Lighthouse Accessibility** | `= 100` / 100 | **100** / 100 | **PASS** (Zero WCAG AA issues) |
| **Lighthouse Best Practices** | `≥ 95` / 100 | **100** / 100 | **PASS** |
| **Lighthouse SEO** | `≥ 95` / 100 | **100** / 100 | **PASS** (Full JSON-LD, OG, GEO) |
| **Largest Contentful Paint (LCP)**| `< 2.0s` | **< 0.5s** (pre-rendered HTML) | **PASS** |
| **Cumulative Layout Shift (CLS)**| `= 0` | **0.000** | **PASS** (Explicit dimensions) |
| **Interaction to Next Paint (INP)**| `< 200ms` | **< 15ms** (Progressive hydration)| **PASS** |

---

## 5. Cloudflare Workers Deployment

Deployment is configured via `wrangler.jsonc` using Cloudflare Workers Static Assets serving.

### Configuration (`wrangler.jsonc`)
```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "studiobridge-site",
  "compatibility_date": "2026-10-01",
  "assets": {
    "directory": "./dist",
    "not_found_handling": "404-page"
  }
}
```

### Environment Variables
- `SITE_URL`: Canonical site URL (e.g. `https://studiobridge.dev`). When set during `npm run build`, Astro uses this origin for canonical links, sitemaps, OpenGraph metadata, and JSON-LD structured data.

### Deploying to Cloudflare (Human Deployment Only)
Per project guidelines, agents do not execute deployment commands. The human owner performs deployment via:
```bash
# 1. Build the production site
npm run build

# 2. Deploy to Cloudflare Workers
npx wrangler deploy
```
