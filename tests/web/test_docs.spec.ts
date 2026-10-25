/**
 * Automated Test Suite for Starlight Documentation & API Reference Integration (v0.6.8 / T-WEB-08)
 *
 * Requirements per 18_landing_page_spec.md §5, §7.1a and sub-phase v0.6.8:
 * 1. Internal Link Validity ([LNK-01]):
 *    - All internal links across all docs pages resolve to existing files and valid target anchors.
 *    - Zero broken internal links across the documentation collection.
 * 2. Starlight Sidebar Hierarchy ([SBR-01]):
 *    - Verifies top-level groups: Getting Started, Architecture, Troubleshooting, API Reference.
 *    - Verifies all articles and module reference guides are correctly indexed.
 * 3. Doctor Check Directory Completeness ([DOC-01]):
 *    - Validates that every doctor check code (D-*) defined in doctor.py has an authoritative
 *      explanation, failure mode, root cause, and recovery command steps.
 * 4. Theme Synchronization ([THM-06]):
 *    - Verifies Starlight shares the 'sb-theme' localStorage key.
 *    - Verifies custom CSS tokens (--bg, --surface, --ink, --line, --signal) map to --sl-color-*.
 *    - Verifies ThemeProvider and ThemeSelect components ensure instant two-way synchronization.
 * 5. API Reference Manifest Fidelity ([API-01]):
 *    - Verifies all 8 modules (channels, device, general, mixer, patterns, plugins, transport, ui)
 *      and 119 functions from api_v44.json are compiled into structured cards.
 */

import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert';
import { describe, it } from 'node:test';

function resolveDistDir(): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/dist'),
    path.resolve(process.cwd(), 'dist'),
    path.resolve(__dirname, '../../site/dist'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error(`dist directory not found. Candidates: ${candidates.join(', ')}. Run 'npm run build' first.`);
}

function resolveSiteSrcDir(): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/src'),
    path.resolve(process.cwd(), 'src'),
    path.resolve(__dirname, '../../site/src'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error(`site/src directory not found. Candidates: ${candidates.join(', ')}`);
}

function resolveRepoPath(relPath: string): string {
  const candidates = [
    path.resolve(process.cwd(), relPath),
    path.resolve(process.cwd(), '..', relPath),
    path.resolve(__dirname, '../..', relPath),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error(`Path '${relPath}' not found in repo candidates: ${candidates.join(', ')}`);
}

function getAllHtmlFiles(dir: string, fileList: string[] = []): string[] {
  if (!fs.existsSync(dir)) return fileList;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      getAllHtmlFiles(fullPath, fileList);
    } else if (entry.isFile() && entry.name.endsWith('.html')) {
      fileList.push(fullPath);
    }
  }
  return fileList;
}

describe('Starlight Documentation & API Reference Integration (v0.6.8 / T-WEB-08)', () => {
  const distDir = resolveDistDir();
  const docsDistDir = path.join(distDir, 'docs');
  const siteSrcDir = resolveSiteSrcDir();

  it('[THM-06] Tokens map Starlight properties directly to Patchbay CSS variables', () => {
    const tokensPath = path.join(siteSrcDir, 'styles/tokens.css');
    assert.ok(fs.existsSync(tokensPath), 'tokens.css must exist');
    const tokensContent = fs.readFileSync(tokensPath, 'utf8');

    assert.ok(tokensContent.includes('--sl-color-bg: var(--bg)'), 'Maps --sl-color-bg to --bg');
    assert.ok(tokensContent.includes('--sl-color-bg-nav: var(--surface)'), 'Maps --sl-color-bg-nav to --surface');
    assert.ok(tokensContent.includes('--sl-color-bg-sidebar: var(--surface)'), 'Maps --sl-color-bg-sidebar to --surface');
    assert.ok(tokensContent.includes('--sl-color-text: var(--ink)'), 'Maps --sl-color-text to --ink');
    assert.ok(tokensContent.includes('--sl-color-accent: var(--signal)'), 'Maps --sl-color-accent to --signal');
  });

  it('[THM-06] Starlight ThemeProvider & ThemeSelect share sb-theme key and event dispatcher', () => {
    const providerPath = path.join(siteSrcDir, 'components/starlight/ThemeProvider.astro');
    assert.ok(fs.existsSync(providerPath), 'Custom ThemeProvider.astro must exist');
    const providerContent = fs.readFileSync(providerPath, 'utf8');

    assert.ok(providerContent.includes("localStorage.getItem('sb-theme')"), 'ThemeProvider reads sb-theme');
    assert.ok(providerContent.includes("setAttribute('data-theme', 'dark')"), 'Sets data-theme="dark"');
    assert.ok(providerContent.includes("setAttribute('data-theme', 'light')"), 'Sets data-theme="light"');
    assert.ok(providerContent.includes("removeAttribute('data-theme')"), 'Removes data-theme attribute on system');

    const selectPath = path.join(siteSrcDir, 'components/starlight/ThemeSelect.astro');
    assert.ok(fs.existsSync(selectPath), 'Custom ThemeSelect.astro must exist');
    const selectContent = fs.readFileSync(selectPath, 'utf8');

    assert.ok(selectContent.includes("const storageKey = 'sb-theme'"), 'ThemeSelect uses sb-theme storageKey');
    assert.ok(selectContent.includes("localStorage.setItem(storageKey"), 'ThemeSelect writes to sb-theme');
    assert.ok(selectContent.includes("new CustomEvent('sb-theme-change'"), 'Dispatches sb-theme-change custom event');
    assert.ok(selectContent.includes("addEventListener('storage'"), 'Listens to cross-tab storage changes');
  });

  it('[SBR-01] Starlight sidebar hierarchy configures Getting Started, Architecture, Troubleshooting, and API Reference', () => {
    const configPath = resolveRepoPath('site/astro.config.mjs');
    const configContent = fs.readFileSync(configPath, 'utf8');

    // Check top-level group labels
    assert.ok(configContent.includes("label: 'Getting Started'"), "Sidebar includes 'Getting Started'");
    assert.ok(configContent.includes("label: 'Architecture'"), "Sidebar includes 'Architecture'");
    assert.ok(configContent.includes("label: 'Troubleshooting'"), "Sidebar includes 'Troubleshooting'");
    assert.ok(configContent.includes("label: 'API Reference'"), "Sidebar includes 'API Reference'");

    // Check core article slugs
    assert.ok(configContent.includes("slug: 'docs'"), "Sidebar indexes 'docs' overview");
    assert.ok(configContent.includes("slug: 'docs/getting-started/quickstart'"), "Sidebar indexes quickstart");
    assert.ok(configContent.includes("slug: 'docs/architecture/control-planes'"), "Sidebar indexes control planes");
    assert.ok(configContent.includes("slug: 'docs/architecture/wire-protocol'"), "Sidebar indexes wire protocol");
    assert.ok(configContent.includes("slug: 'docs/troubleshooting/doctor-checks'"), "Sidebar indexes doctor checks");
    assert.ok(configContent.includes("slug: 'docs/api'"), "Sidebar indexes API overview");

    // Check module slugs
    const expectedModules = ['channels', 'device', 'general', 'mixer', 'patterns', 'plugins', 'transport', 'ui'];
    for (const mod of expectedModules) {
      assert.ok(configContent.includes(`slug: 'docs/api/${mod}'`), `Sidebar indexes API module '${mod}'`);
    }
  });

  it('[DOC-01] Every doctor check code (D-*) from doctor.py is documented with cause and remedy', () => {
    const doctorPyPath = resolveRepoPath('packages/studiobridge/src/studiobridge/setup/doctor.py');
    const doctorPyContent = fs.readFileSync(doctorPyPath, 'utf8');

    // Extract all unique check IDs
    const checkIdMatches = doctorPyContent.matchAll(/id=["'](D-[A-Z0-9-]+)["']/g);
    const uniqueCheckIds = Array.from(new Set(Array.from(checkIdMatches).map((m) => m[1]))).sort();

    assert.ok(uniqueCheckIds.length >= 25, `Expected at least 25 unique doctor check IDs, found ${uniqueCheckIds.length}`);

    const doctorDocPath = path.join(siteSrcDir, 'content/docs/docs/troubleshooting/doctor-checks.md');
    assert.ok(fs.existsSync(doctorDocPath), 'doctor-checks.md must exist');
    const doctorDocContent = fs.readFileSync(doctorDocPath, 'utf8');

    for (const checkId of uniqueCheckIds) {
      assert.ok(
        doctorDocContent.includes(checkId),
        `Doctor check ID '${checkId}' must be present in doctor-checks.md`
      );

      // Verify that failure mode, root causes, and recovery steps exist around this check
      const checkSectionRegex = new RegExp(`### \`${checkId}\`([\\s\\S]*?)(?=### \`D-|$)`);
      const match = doctorDocContent.match(checkSectionRegex);
      assert.ok(match, `Section for '${checkId}' must exist with heading '### \`${checkId}\`'`);

      const sectionText = match[1];
      assert.ok(sectionText.includes('Failure Mode:'), `'${checkId}' must document Failure Mode`);
      assert.ok(sectionText.includes('Root Causes:'), `'${checkId}' must document Root Causes`);
      assert.ok(sectionText.includes('Recovery Steps:'), `'${checkId}' must document Recovery Steps`);
    }
  });

  it('[API-01] Generates all 8 API modules and 119 function reference cards from manifest fixture', () => {
    const manifestPath = resolveRepoPath('packages/studiobridge/src/studiobridge/manifest/fixtures/api_v44.json');
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

    const modules = Object.keys(manifest.modules);
    assert.strictEqual(modules.length, 8, 'API v44 manifest has 8 modules');

    const apiDistDir = path.join(docsDistDir, 'api');
    assert.ok(fs.existsSync(apiDistDir), 'dist/docs/api must exist');

    let totalFunctionCards = 0;

    for (const modName of modules) {
      const modDocPath = path.join(apiDistDir, `${modName}/index.html`);
      assert.ok(fs.existsSync(modDocPath), `Module page 'dist/docs/api/${modName}/index.html' must exist`);

      const modHtml = fs.readFileSync(modDocPath, 'utf8');
      const fnNames = Object.keys(manifest.modules[modName].functions);

      for (const fnName of fnNames) {
        totalFunctionCards++;
        // Check that function is included in the module documentation
        assert.ok(
          modHtml.includes(fnName),
          `Function '${fnName}' must be present in module page '${modName}'`
        );

        // Check standalone card HTML file exists
        const cardPath = path.join(apiDistDir, modName, fnName.toLowerCase(), 'index.html');
        assert.ok(
          fs.existsSync(cardPath),
          `Standalone card '${cardPath}' must exist for '${modName}.${fnName}'`
        );
      }
    }

    assert.strictEqual(totalFunctionCards, 119, 'Must generate exactly 119 function cards');
  });

  it('[LNK-01] Zero broken internal links exist across the entire documentation collection', () => {
    const allHtmlFiles = getAllHtmlFiles(docsDistDir);
    assert.ok(allHtmlFiles.length > 0, 'Documentation HTML files must exist in dist/docs/');

    // Map of all generated files and their extracted heading / element IDs
    const documentIdMap = new Map<string, Set<string>>();

    for (const filePath of allHtmlFiles) {
      const relativeToDist = path.relative(distDir, filePath).replace(/\\/g, '/');
      const html = fs.readFileSync(filePath, 'utf8');

      // Extract all id attributes
      const idMatches = html.matchAll(/\sid=["']([^"']+)["']/g);
      const ids = new Set<string>();
      for (const m of idMatches) {
        ids.add(m[1]);
      }
      documentIdMap.set(relativeToDist, ids);
    }

    const brokenLinks: string[] = [];

    // Check each file's hrefs
    for (const filePath of allHtmlFiles) {
      const sourceRel = path.relative(distDir, filePath).replace(/\\/g, '/');
      const html = fs.readFileSync(filePath, 'utf8');

      // Match all href="..."
      const hrefMatches = html.matchAll(/href=["']([^"']+)["']/g);

      for (const match of hrefMatches) {
        const href = match[1];

        // Skip external, mailto, tel, javascript links
        if (
          href.startsWith('http://') ||
          href.startsWith('https://') ||
          href.startsWith('mailto:') ||
          href.startsWith('tel:') ||
          href.startsWith('javascript:')
        ) {
          continue;
        }

        // Parse path and hash
        const [urlPath, hash] = href.split('#');

        if (!urlPath) {
          // In-page anchor: #foo
          if (hash) {
            const currentIds = documentIdMap.get(sourceRel);
            if (!currentIds || !currentIds.has(hash)) {
              brokenLinks.push(`[In-page Anchor] In '${sourceRel}', '#${hash}' does not match any element id`);
            }
          }
          continue;
        }

        // Internal path link: e.g. /docs/api/channels/ or /compat
        let targetFile = '';
        const normalized = urlPath.startsWith('/') ? urlPath.slice(1) : urlPath;
        const ext = path.extname(normalized);

        if (ext && ext !== '.html') {
          // Static assets (.css, .xml, .svg, .js, .woff2, etc.)
          targetFile = normalized;
        } else if (normalized.endsWith('.html')) {
          targetFile = normalized;
        } else if (normalized.endsWith('/')) {
          targetFile = `${normalized}index.html`;
        } else {
          // Could be directory without trailing slash or file
          const candidateDir = `${normalized}/index.html`;
          const candidateFile = `${normalized}.html`;
          if (documentIdMap.has(candidateDir) || fs.existsSync(path.join(distDir, candidateDir))) {
            targetFile = candidateDir;
          } else if (documentIdMap.has(candidateFile) || fs.existsSync(path.join(distDir, candidateFile))) {
            targetFile = candidateFile;
          } else {
            targetFile = candidateDir;
          }
        }

        const targetFullPath = path.join(distDir, targetFile);
        if (!fs.existsSync(targetFullPath)) {
          brokenLinks.push(`[Broken Path] In '${sourceRel}', link '${href}' target '${targetFile}' does not exist on disk`);
          continue;
        }

        // If link specifies a hash anchor on the target page
        if (hash) {
          const targetIds = documentIdMap.get(targetFile);
          if (targetIds && !targetIds.has(hash)) {
            brokenLinks.push(
              `[Broken Target Anchor] In '${sourceRel}', link '${href}' target '${targetFile}' has no element id '#${hash}'`
            );
          }
        }
      }
    }

    if (brokenLinks.length > 0) {
      console.error('Broken links found:');
      for (const b of brokenLinks) {
        console.error(`  - ${b}`);
      }
    }

    assert.strictEqual(
      brokenLinks.length,
      0,
      `Expected 0 broken internal links, found ${brokenLinks.length}:\n${brokenLinks.slice(0, 10).join('\n')}`
    );
  });
});
