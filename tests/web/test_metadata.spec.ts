/**
 * Automated Test Suite for SEO, GEO, LLM Files & OpenGraph Metadata
 *
 * Requirements:
 * 1. JSON-LD SoftwareApplication Schema Validation:
 *    - Google Rich Results compliant schema.org SoftwareApplication structured data.
 *    - Validates name, applicationCategory, operatingSystem, license, author, offers, softwareVersion, description, url, featureList, downloadUrl.
 *    - Present on /, /compat, and /changelog.
 * 2. OpenGraph & Twitter Card Metadata:
 *    - og:title, og:description, og:image, og:image:width (1200), og:image:height (630), og:type, og:url.
 *    - twitter:card (summary_large_image), twitter:title, twitter:description, twitter:image.
 *    - Validates generated og.png (valid PNG binary, >= 10KB) and og.svg (Paper palette, 1200x630).
 * 3. Machine-Readable LLM Context Files:
 *    - /llms.txt exists, clean markdown (0 HTML tags), covers architecture, DAWs, MCP tools, and install syntax.
 *    - /llms-full.txt exists, clean markdown (0 HTML tags), consolidated documentation suite > 100KB.
 * 4. Sitemap & RSS 2.0 Feed Validation:
 *    - sitemap-index.xml (or sitemap-0.xml) exists and validates as well-formed XML.
 *    - rss.xml exists and validates as well-formed RSS 2.0 with valid channel, items, and pubDates.
 *    - robots.txt specifies crawler policy and references sitemaps.
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
  throw new Error(`dist directory not found in candidates: ${candidates.join(', ')}. Run 'npm run build' first.`);
}

describe('SEO, GEO, OpenGraph & LLM Metadata Test Suite', () => {
  const distDir = resolveDistDir();

  describe('1. Schema.org SoftwareApplication JSON-LD', () => {
    const pagesToTest = [
      { name: 'Landing Page (/)', file: path.join(distDir, 'index.html'), expectedUrl: 'https://studiobridge.dev/' },
      { name: 'Compatibility Page (/compat)', file: path.join(distDir, 'compat/index.html'), expectedUrl: 'https://studiobridge.dev/compat' },
      { name: 'Changelog Page (/changelog)', file: path.join(distDir, 'changelog/index.html'), expectedUrl: 'https://studiobridge.dev/changelog' },
    ];

    for (const page of pagesToTest) {
      it(`emits valid Google Rich Results compliant SoftwareApplication schema on ${page.name}`, () => {
        assert.ok(fs.existsSync(page.file), `Page file must exist: ${page.file}`);
        const html = fs.readFileSync(page.file, 'utf8');

        // Extract <script type="application/ld+json">
        const jsonLdMatch = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
        assert.ok(jsonLdMatch, `Page ${page.name} must contain <script type="application/ld+json">`);

        let schema: any;
        try {
          schema = JSON.parse(jsonLdMatch[1]);
        } catch (err: any) {
          assert.fail(`Invalid JSON in application/ld+json on ${page.name}: ${err.message}`);
        }

        // Schema.org Core Requirements
        assert.strictEqual(schema['@context'], 'https://schema.org', 'Must have @context https://schema.org');
        assert.strictEqual(schema['@type'], 'SoftwareApplication', 'Must have @type SoftwareApplication');
        assert.strictEqual(schema.name, 'StudioBridge', 'Name must be StudioBridge');
        assert.strictEqual(schema.applicationCategory, 'AudioApplication', 'applicationCategory must be AudioApplication');
        assert.strictEqual(schema.operatingSystem, 'Windows 11', 'operatingSystem must be Windows 11');
        assert.strictEqual(schema.license, 'https://opensource.org/licenses/MIT', 'license must be MIT');

        // Author details
        assert.ok(schema.author, 'author field must be defined');
        assert.strictEqual(schema.author['@type'], 'Person', 'author @type must be Person');
        assert.strictEqual(schema.author.name, 'WantedChip', 'author name must be WantedChip');

        // Offers (Free software)
        assert.ok(schema.offers, 'offers field must be defined');
        assert.strictEqual(schema.offers['@type'], 'Offer', 'offers @type must be Offer');
        assert.strictEqual(schema.offers.price, '0', 'offers price must be 0');
        assert.strictEqual(schema.offers.priceCurrency, 'USD', 'offers priceCurrency must be USD');

        // Software Version & Download
        assert.ok(schema.softwareVersion, 'softwareVersion must be defined');
        assert.ok(schema.description && schema.description.length > 20, 'description must be comprehensive');
        assert.strictEqual(schema.url, page.expectedUrl, `url must match page URL ${page.expectedUrl}`);
        assert.ok(schema.downloadUrl && schema.downloadUrl.startsWith('https://'), 'downloadUrl must be valid HTTPS link');

        // Feature List
        assert.ok(Array.isArray(schema.featureList), 'featureList must be an array');
        assert.ok(schema.featureList.length >= 5, 'featureList must contain at least 5 key capabilities');
        assert.ok(
          schema.featureList.some((f: string) => f.includes('MCP') || f.includes('Model Context Protocol')),
          'featureList must highlight MCP support'
        );
      });
    }
  });

  describe('2. OpenGraph & Twitter Social Card Metadata', () => {
    const pagesToTest = [
      { name: 'Landing Page (/)', file: path.join(distDir, 'index.html'), expectedUrl: 'https://studiobridge.dev/' },
      { name: 'Compatibility Page (/compat)', file: path.join(distDir, 'compat/index.html'), expectedUrl: 'https://studiobridge.dev/compat' },
      { name: 'Changelog Page (/changelog)', file: path.join(distDir, 'changelog/index.html'), expectedUrl: 'https://studiobridge.dev/changelog' },
    ];

    for (const page of pagesToTest) {
      it(`contains complete OpenGraph and Twitter meta tags on ${page.name}`, () => {
        const html = fs.readFileSync(page.file, 'utf8');

        // OpenGraph Tags
        assert.ok(html.includes('property="og:title"'), `${page.name} must have og:title`);
        assert.ok(html.includes('property="og:description"'), `${page.name} must have og:description`);
        assert.ok(html.includes('property="og:image" content="https://studiobridge.dev/og.png"'), `${page.name} must have og:image pointing to https://studiobridge.dev/og.png`);
        assert.ok(html.includes('property="og:image:width" content="1200"'), `${page.name} must specify og:image:width 1200`);
        assert.ok(html.includes('property="og:image:height" content="630"'), `${page.name} must specify og:image:height 630`);
        assert.ok(html.includes('property="og:type" content="website"'), `${page.name} must have og:type website`);
        assert.ok(html.includes(`property="og:url" content="${page.expectedUrl}"`), `${page.name} must have og:url ${page.expectedUrl}`);

        // Twitter Card Tags
        assert.ok(html.includes('name="twitter:card" content="summary_large_image"'), `${page.name} must have twitter:card summary_large_image`);
        assert.ok(html.includes('name="twitter:title"'), `${page.name} must have twitter:title`);
        assert.ok(html.includes('name="twitter:description"'), `${page.name} must have twitter:description`);
        assert.ok(html.includes('name="twitter:image" content="https://studiobridge.dev/og.png"'), `${page.name} must have twitter:image`);

        // Canonical & RSS alternate links
        assert.ok(html.includes(`rel="canonical" href="${page.expectedUrl}"`), `${page.name} must have canonical link to ${page.expectedUrl}`);
        assert.ok(html.includes('rel="alternate" type="application/rss+xml"'), `${page.name} must have RSS feed alternate link`);
      });
    }

    it('generates valid OpenGraph raster PNG (dist/og.png) matching spec dimensions', () => {
      const pngPath = path.join(distDir, 'og.png');
      assert.ok(fs.existsSync(pngPath), `og.png must exist at ${pngPath}`);

      const buffer = fs.readFileSync(pngPath);
      assert.ok(buffer.length > 5000, `og.png must be non-empty (got ${buffer.length} bytes)`);

      // Verify standard PNG magic bytes: 0x89 0x50 0x4E 0x47 0x0D 0x0A 0x1A 0x0A
      const pngSignature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
      assert.ok(buffer.subarray(0, 8).equals(pngSignature), 'og.png must start with valid PNG 8-byte signature');

      // Verify IHDR chunk width (1200) and height (630)
      const ihdrChunk = buffer.subarray(12, 16).toString('ascii');
      assert.strictEqual(ihdrChunk, 'IHDR', 'Second chunk must be IHDR');
      const width = buffer.readUInt32BE(16);
      const height = buffer.readUInt32BE(20);
      assert.strictEqual(width, 1200, 'PNG width must be 1200px');
      assert.strictEqual(height, 630, 'PNG height must be 630px');
    });

    it('generates valid OpenGraph vector SVG (dist/og.svg) with Paper palette styling', () => {
      const svgPath = path.join(distDir, 'og.svg');
      assert.ok(fs.existsSync(svgPath), `og.svg must exist at ${svgPath}`);

      const svg = fs.readFileSync(svgPath, 'utf8');
      assert.ok(svg.includes('viewBox="0 0 1200 630"'), 'SVG must have 1200x630 viewBox');
      assert.ok(svg.includes('#F3F0E8'), 'SVG must use Paper Ground color (#F3F0E8)');
      assert.ok(svg.includes('#14130F'), 'SVG must use Ink color (#14130F)');
      assert.ok(svg.includes('#E8461A'), 'SVG must use Signal Accent color (#E8461A)');
      assert.ok(svg.includes('StudioBridge'), 'SVG must include StudioBridge wordmark');
      assert.ok(svg.includes('SIGNAL PATH'), 'SVG must include signal path motif');
      assert.ok(svg.includes('F0 7D 53 42'), 'SVG must render SysEx magic frame bytes');
    });
  });

  describe('3. Machine-Readable LLM Context Files (GEO / llms.txt & llms-full.txt)', () => {
    it('serves clean, valid Markdown without HTML artifacts in dist/llms.txt', () => {
      const llmsPath = path.join(distDir, 'llms.txt');
      assert.ok(fs.existsSync(llmsPath), `llms.txt must exist at ${llmsPath}`);

      const content = fs.readFileSync(llmsPath, 'utf8');
      assert.ok(content.length > 500, `llms.txt must have sufficient content (got ${content.length} chars)`);

      // Verify zero raw HTML tags
      const htmlMatches = content.match(/<[a-z][\s\S]*?>/gi);
      assert.strictEqual(
        htmlMatches,
        null,
        `llms.txt must contain ZERO HTML tags. Found: ${htmlMatches ? htmlMatches.join(', ') : ''}`
      );

      // Verify required architectural and capability facts
      assert.ok(content.includes('# StudioBridge'), 'Must start with # StudioBridge');
      assert.ok(content.includes('Architecture & Control Planes'), 'Must cover architecture control planes');
      assert.ok(content.includes('FL Studio 21'), 'Must mention supported FL Studio versions');
      assert.ok(content.includes('Windows 11 (ARM64'), 'Must mention Windows 11 ARM64 and x64');
      assert.ok(content.includes('Model Context Protocol (MCP) Tools'), 'Must define MCP tools');
      assert.ok(content.includes('mixer_list'), 'Must document mixer_list');
      assert.ok(content.includes('notes_apply'), 'Must document notes_apply');
      assert.ok(content.includes('checkpoint_rollback'), 'Must document checkpoint_rollback');
      assert.ok(content.includes('flp_inspect'), 'Must document offline flp tools');
      assert.ok(content.includes('render_start'), 'Must document render tools');
      assert.ok(content.includes('uvx studiobridge agent install'), 'Must document agent installer syntax');
      assert.ok(content.includes('sbridge doctor'), 'Must document doctor diagnostic command');
      assert.ok(content.includes('llms-full.txt'), 'Must reference llms-full.txt');
    });

    it('serves consolidated Markdown dump without HTML artifacts in dist/llms-full.txt', () => {
      const fullPath = path.join(distDir, 'llms-full.txt');
      assert.ok(fs.existsSync(fullPath), `llms-full.txt must exist at ${fullPath}`);

      const content = fs.readFileSync(fullPath, 'utf8');
      assert.ok(content.length > 100000, `llms-full.txt must contain comprehensive docs (>100KB, got ${content.length} chars)`);

      // Verify zero raw HTML tags
      const htmlMatches = content.match(/<[a-z][\s\S]*?>/gi);
      assert.strictEqual(
        htmlMatches,
        null,
        `llms-full.txt must contain ZERO HTML tags. Found: ${htmlMatches ? htmlMatches.slice(0, 5).join(', ') : ''}`
      );

      // Verify consolidated documentation modules are included
      assert.ok(content.includes('Overview & Architecture'), 'Must include Overview section');
      assert.ok(content.includes('Getting Started & Quickstart'), 'Must include Quickstart section');
      assert.ok(content.includes('Control Planes Deep Dive'), 'Must include Control Planes section');
      assert.ok(content.includes('SysEx Wire Protocol Specification'), 'Must include Wire Protocol section');
      assert.ok(content.includes('Doctor Checks Directory'), 'Must include Doctor Checks section');
      assert.ok(content.includes('API Reference Overview'), 'Must include API Overview section');
      assert.ok(content.includes('Module: mixer'), 'Must include Mixer module');
      assert.ok(content.includes('Module: channels'), 'Must include Channels module');
      assert.ok(content.includes('Module: transport'), 'Must include Transport module');
      assert.ok(content.includes('mixer.getTrackVolume'), 'Must include individual API function cards');
    });
  });

  describe('4. Sitemap & RSS 2.0 Feed Validation', () => {
    it('produces valid XML sitemap (sitemap-index.xml or sitemap-0.xml)', () => {
      const sitemapIndex = path.join(distDir, 'sitemap-index.xml');
      const sitemap0 = path.join(distDir, 'sitemap-0.xml');
      const sitemapFile = fs.existsSync(sitemapIndex) ? sitemapIndex : sitemap0;

      assert.ok(fs.existsSync(sitemapFile), 'Sitemap XML must exist in dist');
      const xml = fs.readFileSync(sitemapFile, 'utf8');

      assert.ok(xml.startsWith('<?xml'), 'Sitemap must start with XML declaration');
      assert.ok(xml.includes('<sitemapindex') || xml.includes('<urlset'), 'Sitemap must have valid root element');
      assert.ok(xml.endsWith('</sitemapindex>') || xml.endsWith('</urlset>'), 'Sitemap must close root element');
    });

    it('generates well-formed RSS 2.0 changelog feed at dist/rss.xml', () => {
      const rssPath = path.join(distDir, 'rss.xml');
      assert.ok(fs.existsSync(rssPath), `rss.xml must exist at ${rssPath}`);

      const xml = fs.readFileSync(rssPath, 'utf8');
      assert.ok(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>'), 'RSS must have UTF-8 XML declaration');
      assert.ok(xml.includes('<rss version="2.0"'), 'Must have root <rss version="2.0"> element');
      assert.ok(xml.includes('<channel>'), 'Must have <channel> element');
      assert.ok(xml.includes('<title>StudioBridge Releases &amp; Changelog</title>'), 'Must have channel title');
      assert.ok(xml.includes('<link>https://studiobridge.dev/changelog</link>'), 'Must link to changelog');
      assert.ok(xml.includes('<atom:link href="https://studiobridge.dev/rss.xml"'), 'Must have Atom self-referencing link');
      assert.ok(xml.includes('<lastBuildDate>'), 'Must have lastBuildDate');

      // Verify items
      const itemMatches = xml.match(/<item>[\s\S]*?<\/item>/g);
      assert.ok(itemMatches && itemMatches.length >= 6, `Must contain at least 6 release items (found ${itemMatches?.length})`);

      for (const item of itemMatches) {
        assert.ok(item.includes('<title>'), 'Item must contain <title>');
        assert.ok(item.includes('<link>'), 'Item must contain <link>');
        assert.ok(item.includes('<guid isPermaLink="true">'), 'Item must contain <guid>');
        assert.ok(item.includes('<pubDate>'), 'Item must contain <pubDate>');
        assert.ok(item.includes('<description>'), 'Item must contain <description>');
      }

      assert.ok(xml.endsWith('</rss>'), 'RSS feed must close root </rss> tag');
    });

    it('configures robots.txt crawling policies and sitemap pointers', () => {
      const robotsPath = path.join(distDir, 'robots.txt');
      assert.ok(fs.existsSync(robotsPath), `robots.txt must exist at ${robotsPath}`);

      const robots = fs.readFileSync(robotsPath, 'utf8');
      assert.ok(robots.includes('User-agent: *'), 'Must specify User-agent: *');
      assert.ok(robots.includes('Allow: /'), 'Must specify Allow: /');
      assert.ok(robots.includes('Sitemap: https://studiobridge.dev/sitemap-index.xml'), 'Must point to sitemap-index.xml');
      assert.ok(robots.includes('Sitemap: https://studiobridge.dev/rss.xml'), 'Must point to rss.xml');
    });
  });
});
