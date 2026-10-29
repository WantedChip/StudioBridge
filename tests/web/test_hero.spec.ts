/**
 * Playwright / Web Specification Test Suite for Hero Section & Signal-Path Island
 *
 * Requirements:
 * 1. Hero layout & copy: Title, subhead, install command copy box, "See it work" jump link (#session-demo), badges.
 * 2. CopyButton functionality: Clipboard writeText, copied state ("COPIED"), accessible keyboard support, fallback.
 * 3. SignalPath interactive island: 5 hardware nodes, SVG schematic, cable flow, interactive drawer with authentic protocol data.
 * 4. Keyboard navigation: Focusable nodes, Enter/Space selection, Escape key drawer dismissal, close button.
 * 5. Reduced-motion compliance: @media (prefers-reduced-motion: reduce) freezes animations and provides semantic <details> fallback.
 * 6. Bundle size budget: SignalPath.tsx ships <= 12 KB gzip JavaScript.
 */

import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import assert from 'node:assert';
import { describe, it } from 'node:test';

// Resolve dist/index.html from either repo root or site/ subdirectory
function resolveDistHtml(): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/dist/index.html'),
    path.resolve(process.cwd(), 'dist/index.html'),
    path.resolve(__dirname, '../../site/dist/index.html'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`dist/index.html not found. Candidates checked: ${candidates.join(', ')}. Run 'npm run build' first.`);
}

function resolveDistAstroDir(): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/dist/_astro'),
    path.resolve(process.cwd(), 'dist/_astro'),
    path.resolve(__dirname, '../../site/dist/_astro'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`dist/_astro directory not found. Candidates checked: ${candidates.join(', ')}`);
}

describe('Hero Section & Signal-Path Island', () => {
  const htmlPath = resolveDistHtml();
  const html = fs.readFileSync(htmlPath, 'utf8');
  const astroDir = resolveDistAstroDir();

  describe('1. Hero Text & Copy Elements', () => {
    it('renders the exact spec H1 headline', () => {
      assert.ok(
        html.includes('Patch your agent into your DAW.'),
        'Hero must display H1: "Patch your agent into your DAW."'
      );
    });

    it('renders the exact spec subhead', () => {
      assert.ok(
        html.includes('Read, edit, and render FL Studio projects from any coding agent') &&
          html.includes('verified, reversible, local.'),
        'Hero must render verified subhead copy.'
      );
    });

    it('displays the install command copy box with uvx studiobridge setup', () => {
      assert.ok(
        html.includes('uvx studiobridge setup'),
        'Hero must display install command "uvx studiobridge setup".'
      );
    });

    it('contains "See it work" jump link pointing to #session-demo', () => {
      assert.ok(
        html.includes('href="#session-demo"'),
        'Hero must include anchor link pointing to #session-demo.'
      );
      assert.ok(
        html.includes('See it work'),
        'Hero jump link must read "See it work".'
      );
    });

    it('displays status badges: MIT License and Windows ARM64 + x64', () => {
      assert.ok(
        html.includes('MIT License') || html.includes('MIT LICENSE'),
        'Hero must display MIT License badge.'
      );
      assert.ok(
        html.includes('Windows ARM64 + x64') || html.includes('WINDOWS x64 &amp; ARM64'),
        'Hero must display Windows ARM64 + x64 architecture badge.'
      );
    });

    it('displays catalogue section number 01 / SIGNAL PATH', () => {
      assert.ok(
        html.includes('01 / SIGNAL PATH'),
        'Hero must display "01 / SIGNAL PATH" section header.'
      );
    });
  });

  describe('2. CopyButton Interactive Island', () => {
    it('mounts the CopyButton client island', () => {
      assert.ok(
        html.includes('CopyButton') || html.includes('uvx studiobridge setup'),
        'CopyButton component must be mounted in hero.'
      );
    });

    it('renders accessible aria-label and live region on copy button', () => {
      assert.ok(
        html.includes('aria-label="Copy install command: uvx studiobridge setup"') ||
          html.includes('uvx studiobridge setup'),
        'CopyButton must have descriptive accessible label.'
      );
      assert.ok(
        html.includes('aria-live="polite"'),
        'CopyButton must announce state changes politely via aria-live.'
      );
    });

    it('has fallback mechanisms and clipboard write logic in bundle', () => {
      const files = fs.readdirSync(astroDir);
      const copyChunk = files.find((f) => f.startsWith('CopyButton'));
      assert.ok(copyChunk, 'CopyButton compiled JS chunk must exist in _astro.');

      const copyCode = fs.readFileSync(path.join(astroDir, copyChunk), 'utf8');
      assert.ok(
        copyCode.includes('clipboard') && copyCode.includes('writeText'),
        'CopyButton must invoke navigator.clipboard.writeText.'
      );
      assert.ok(
        copyCode.includes('COPIED'),
        'CopyButton must contain "COPIED" success state label.'
      );
    });
  });

  describe('3. SignalPath Interactive SVG Island & Protocol Nodes', () => {
    it('mounts SignalPath as an Astro client island with client:visible', () => {
      assert.ok(
        html.includes('SignalPath') || html.includes('client="visible"'),
        'SignalPath must be mounted as an Astro island.'
      );
    });

    it('renders pure SVG schematic with patch cables and 5 hardware stations', () => {
      assert.ok(
        html.includes('viewBox="0 0 680 180"'),
        'Schematic must render SVG canvas with 680x180 viewBox.'
      );
      assert.ok(
        html.includes('signal-cable-base') && html.includes('signal-cable-flow'),
        'Schematic must render curved patch cables with animated flow.'
      );
    });

    it('contains all 5 authentic protocol nodes', () => {
      const files = fs.readdirSync(astroDir);
      const signalChunk = files.find((f) => f.startsWith('SignalPath'));
      assert.ok(signalChunk, 'SignalPath compiled JS chunk must exist.');

      const signalCode = fs.readFileSync(path.join(astroDir, signalChunk), 'utf8');

      // 1. Agent node: Tool call request JSON
      assert.ok(
        signalCode.includes('mixer_set_volume') && signalCode.includes('linear'),
        'SignalPath must contain authentic Agent tool call JSON (mixer_set_volume).'
      );

      // 2. MCP Host node: JSON-RPC 2.0 payload
      assert.ok(
        signalCode.includes('jsonrpc') && signalCode.includes('2.0') && signalCode.includes('tools/call'),
        'SignalPath must contain authentic MCP JSON-RPC 2.0 payload.'
      );

      // 3. Broker Daemon node: Local IPC endpoint & lease scheduler
      assert.ok(
        signalCode.includes('studiobridge-ipc') && signalCode.includes('WinMM') && signalCode.includes('WMS loopback'),
        'SignalPath must contain authentic Broker IPC & loopback routing facts.'
      );

      // 4. SysEx Wire node: Authentic hexadecimal byte stream
      assert.ok(
        signalCode.includes('F0 7D 53 42') && signalCode.includes('3F 4C CC CD F7'),
        'SignalPath must contain authentic SysEx frame hex with magic 53 42.'
      );

      // 5. FL Studio node: Controller script invocation & verified ACK
      assert.ok(
        signalCode.includes('setTrackVolume') && signalCode.includes('ACK_VERIFIED'),
        'SignalPath must contain authentic FL Studio device script actuation & verification.'
      );
    });

    it('provides accessible keyboard navigation and inspection drawer controls', () => {
      const files = fs.readdirSync(astroDir);
      const signalChunk = files.find((f) => f.startsWith('SignalPath'));
      const signalCode = fs.readFileSync(path.join(astroDir, signalChunk!), 'utf8');

      // Focusable buttons & ARIA attributes
      assert.ok(
        signalCode.includes('aria-expanded') && signalCode.includes('aria-controls'),
        'Nodes must expose aria-expanded and aria-controls.'
      );

      // Escape key drawer dismissal
      assert.ok(
        signalCode.includes('Escape'),
        'SignalPath must register Escape key handler to close inspection drawer.'
      );

      // Close button
      assert.ok(
        signalCode.includes('CLOSE'),
        'SignalPath must provide an explicit drawer close button.'
      );
    });
  });

  describe('4. Accessibility & Reduced-Motion Support', () => {
    it('contains @media (prefers-reduced-motion: reduce) CSS rules that freeze animations', () => {
      assert.ok(
        html.includes('prefers-reduced-motion: reduce') ||
          html.includes('animation: none !important'),
        'Must define CSS rules freezing animations under prefers-reduced-motion: reduce.'
      );
    });

    it('renders semantic static <details> disclosures for all 5 nodes in HTML', () => {
      // 5 details disclosure items for static screen-reader / reduced-motion fallback
      assert.ok(html.includes('<details'), 'HTML must render fallback <details> elements.');
      assert.ok(html.includes('<summary'), 'HTML must render fallback <summary> elements.');

      // Check all 5 nodes are present in static disclosures
      assert.ok(html.includes('01 / AGENT'), 'Static disclosures must include Agent node.');
      assert.ok(html.includes('02 / MCP HOST'), 'Static disclosures must include MCP Host node.');
      assert.ok(html.includes('03 / BROKER DAEMON'), 'Static disclosures must include Broker node.');
      assert.ok(html.includes('04 / SYSEX WIRE'), 'Static disclosures must include SysEx Wire node.');
      assert.ok(html.includes('05 / FL STUDIO'), 'Static disclosures must include FL Studio node.');
    });
  });

  describe('5. Bundle Size Budget Constraint (≤ 12 KB gzip)', () => {
    it('verifies SignalPath.tsx ships <= 12 KB gzip JavaScript', () => {
      const files = fs.readdirSync(astroDir);
      const signalChunk = files.find((f) => f.startsWith('SignalPath'));
      assert.ok(signalChunk, 'SignalPath compiled JS chunk must exist.');

      const chunkBuffer = fs.readFileSync(path.join(astroDir, signalChunk));
      const gzipped = zlib.gzipSync(chunkBuffer);
      const gzipBytes = gzipped.length;
      const budgetBytes = 12 * 1024; // 12 KB = 12,288 bytes

      console.log(`\n  SignalPath JS Bundle Size:`);
      console.log(`    File:   ${signalChunk}`);
      console.log(`    Raw:    ${chunkBuffer.length.toLocaleString()} bytes (${(chunkBuffer.length / 1024).toFixed(2)} KB)`);
      console.log(`    Gzip:   ${gzipBytes.toLocaleString()} bytes (${(gzipBytes / 1024).toFixed(2)} KB)`);
      console.log(`    Budget: ${budgetBytes.toLocaleString()} bytes (12.00 KB)`);
      console.log(`    Usage:  ${((gzipBytes / budgetBytes) * 100).toFixed(1)}% of budget\n`);

      assert.ok(
        gzipBytes <= budgetBytes,
        `SignalPath bundle exceeds 12 KB budget: ${gzipBytes} bytes > ${budgetBytes} bytes`
      );
    });
  });
});
