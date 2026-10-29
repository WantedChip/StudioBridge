/**
 * Test Suite for Capability Matrix Explorer Island & Compatibility Page
 *
 * Requirements:
 * 1. Build-time compatibility compiler & authentic fixtures:
 *    - Ingests authentic test data from Machine A (Snapdragon X Elite ARM64) and Machine B (x64).
 *    - Validates compat.json mapping FL Studio builds (26.1.3, 25.2.3, 21.2) and architectures (ARM64, x64).
 *    - Maps 12 core capabilities:
 *      CAP_LIVE_TRANSPORT, CAP_LIVE_MIXER, CAP_LIVE_NOTES, CAP_OFFLINE_FLP_PARSE,
 *      CAP_OFFLINE_FLP_MUTATE, CAP_OFFLINE_FLP_INVARIANTS, CAP_HEADLESS_RENDER,
 *      CAP_PIANO_ROLL_ACTUATION, CAP_PLUGIN_INSTANTIATE, CAP_HOST_NATIVE_ARM64,
 *      CAP_FLP_PLAYLIST_WRITE, CAP_ZERO_KERNEL_DRIVERS.
 * 2. Status indicators:
 *    - Uses both color (LEDs) and explicit text and icon labels (never color alone - WCAG AA).
 * 3. Expandable details:
 *    - Expanding degraded or unavailable items shows technical rationale, alternative paths,
 *      and diagnostic evidence IDs.
 * 4. Dedicated /compat page:
 *    - Displays complete side-by-side comparison matrix, hardware specifications,
 *      technical deep dives, breadcrumb, and non-affiliation statement.
 * 5. Landing page integration:
 *    - Section 04 / CAPABILITIES integrated between Section 03 and Section 05.
 */

import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert';
import { describe, it } from 'node:test';

function resolveDistFile(relativePath: string): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/dist', relativePath),
    path.resolve(process.cwd(), 'dist', relativePath),
    path.resolve(__dirname, '../../site/dist', relativePath),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`dist file '${relativePath}' not found. Checked: ${candidates.join(', ')}. Run 'npm run build' first.`);
}

function resolveCompatJsonPath(): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/src/data/compat.json'),
    path.resolve(process.cwd(), 'src/data/compat.json'),
    path.resolve(__dirname, '../../site/src/data/compat.json'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`compat.json not found. Checked: ${candidates.join(', ')}`);
}

describe('Capability Matrix Explorer Island & Compatibility Page', () => {
  const compatJsonPath = resolveCompatJsonPath();
  const compatRaw = JSON.parse(fs.readFileSync(compatJsonPath, 'utf8'));

  describe('1. Authentic Diagnostics Data & Compat Schema', () => {
    it('should have valid metadata with spec version and tested environments', () => {
      assert.ok(compatRaw.meta, 'meta section must exist');
      assert.strictEqual(compatRaw.meta.schemaVersion, '1.0.0');
      assert.strictEqual(compatRaw.meta.specVersion, '1.0.0');
      assert.ok(compatRaw.meta.testedEnvironments.machineA, 'Machine A metadata must exist');
      assert.ok(compatRaw.meta.testedEnvironments.machineB, 'Machine B metadata must exist');

      const a = compatRaw.meta.testedEnvironments.machineA;
      assert.strictEqual(a.arch, 'ARM64');
      assert.ok(a.hardware.includes('Surface') || a.cpu.includes('Snapdragon'));
      assert.ok(a.midiBackend.includes('Windows MIDI Services') || a.midiBackend.includes('WinMM'));

      const b = compatRaw.meta.testedEnvironments.machineB;
      assert.strictEqual(b.arch, 'x64');
      assert.ok(b.cpu.includes('Ryzen') || b.cpu.includes('Intel'));
    });

    it('should compile exactly 6 matrix configurations (3 FL builds x 2 architectures)', () => {
      const keys = Object.keys(compatRaw.matrix);
      assert.strictEqual(keys.length, 6);
      assert.ok(keys.includes('26.1.3-ARM64'));
      assert.ok(keys.includes('26.1.3-x64'));
      assert.ok(keys.includes('25.2.3-ARM64'));
      assert.ok(keys.includes('25.2.3-x64'));
      assert.ok(keys.includes('21.2-ARM64'));
      assert.ok(keys.includes('21.2-x64'));
    });

    it('should cover all 12 core capabilities in each matrix combination', () => {
      const requiredCaps = [
        'CAP_LIVE_TRANSPORT',
        'CAP_LIVE_MIXER',
        'CAP_LIVE_NOTES',
        'CAP_OFFLINE_FLP_PARSE',
        'CAP_OFFLINE_FLP_MUTATE',
        'CAP_OFFLINE_FLP_INVARIANTS',
        'CAP_HEADLESS_RENDER',
        'CAP_PIANO_ROLL_ACTUATION',
        'CAP_PLUGIN_INSTANTIATE',
        'CAP_HOST_NATIVE_ARM64',
        'CAP_FLP_PLAYLIST_WRITE',
        'CAP_ZERO_KERNEL_DRIVERS',
      ];

      for (const [key, entry] of Object.entries<any>(compatRaw.matrix)) {
        for (const capId of requiredCaps) {
          const cap = entry.capabilities[capId];
          assert.ok(cap, `Capability ${capId} must exist in entry ${key}`);
          assert.strictEqual(cap.id, capId);
          assert.ok(['available', 'degraded', 'unavailable'].includes(cap.state));
          assert.ok(cap.reason && cap.reason.length > 10, `Valid reason required for ${capId} in ${key}`);
          assert.ok(cap.alternatives && cap.alternatives.length > 5, `Valid alternatives required for ${capId} in ${key}`);
          assert.ok(cap.diagRef && cap.diagRef.includes('DIAG-'), `Valid diagRef required for ${capId} in ${key}`);
        }
      }
    });

    it('should verify exact state transitions across architectures and versions', () => {
      // 1. CAP_PLUGIN_INSTANTIATE is always unavailable across all configurations
      for (const entry of Object.values<any>(compatRaw.matrix)) {
        assert.strictEqual(entry.capabilities['CAP_PLUGIN_INSTANTIATE'].state, 'unavailable');
        assert.strictEqual(entry.capabilities['CAP_PLUGIN_INSTANTIATE'].statusLabel, 'UNAVAILABLE');
      }

      // 2. CAP_HOST_NATIVE_ARM64 is degraded on ARM64, available on x64
      assert.strictEqual(compatRaw.matrix['26.1.3-ARM64'].capabilities['CAP_HOST_NATIVE_ARM64'].state, 'degraded');
      assert.strictEqual(compatRaw.matrix['25.2.3-ARM64'].capabilities['CAP_HOST_NATIVE_ARM64'].state, 'degraded');
      assert.strictEqual(compatRaw.matrix['21.2-ARM64'].capabilities['CAP_HOST_NATIVE_ARM64'].state, 'degraded');
      assert.strictEqual(compatRaw.matrix['26.1.3-x64'].capabilities['CAP_HOST_NATIVE_ARM64'].state, 'available');
      assert.strictEqual(compatRaw.matrix['25.2.3-x64'].capabilities['CAP_HOST_NATIVE_ARM64'].state, 'available');
      assert.strictEqual(compatRaw.matrix['21.2-x64'].capabilities['CAP_HOST_NATIVE_ARM64'].state, 'available');

      // 3. CAP_FLP_PLAYLIST_WRITE is degraded on FL 26.1.3, available on FL 25.2.3 and 21.2
      assert.strictEqual(compatRaw.matrix['26.1.3-ARM64'].capabilities['CAP_FLP_PLAYLIST_WRITE'].state, 'degraded');
      assert.strictEqual(compatRaw.matrix['26.1.3-x64'].capabilities['CAP_FLP_PLAYLIST_WRITE'].state, 'degraded');
      assert.strictEqual(compatRaw.matrix['25.2.3-ARM64'].capabilities['CAP_FLP_PLAYLIST_WRITE'].state, 'available');
      assert.strictEqual(compatRaw.matrix['25.2.3-x64'].capabilities['CAP_FLP_PLAYLIST_WRITE'].state, 'available');
      assert.strictEqual(compatRaw.matrix['21.2-ARM64'].capabilities['CAP_FLP_PLAYLIST_WRITE'].state, 'available');
      assert.strictEqual(compatRaw.matrix['21.2-x64'].capabilities['CAP_FLP_PLAYLIST_WRITE'].state, 'available');

      // 4. CAP_ZERO_KERNEL_DRIVERS is available across all
      for (const entry of Object.values<any>(compatRaw.matrix)) {
        assert.strictEqual(entry.capabilities['CAP_ZERO_KERNEL_DRIVERS'].state, 'available');
        assert.strictEqual(entry.capabilities['CAP_ZERO_KERNEL_DRIVERS'].statusLabel, 'AVAILABLE');
      }
    });
  });

  describe('2. Landing Page Integration (Section 04 / CAPABILITIES)', () => {
    const indexPath = resolveDistFile('index.html');
    const indexHtml = fs.readFileSync(indexPath, 'utf8');

    it('should contain section 04 / CAPABILITIES with id="capabilities"', () => {
      assert.ok(indexHtml.includes('04 / CAPABILITIES'), 'Must contain section tag 04 / CAPABILITIES');
      assert.ok(indexHtml.includes('id="capabilities"'), 'Must contain anchor id="capabilities"');
      assert.ok(indexHtml.includes('Exact capability truth'), 'Must contain section heading');
    });

    it('should contain dual selector controls with accessible radiogroups', () => {
      assert.ok(indexHtml.includes('role="radiogroup"'), 'Must contain radiogroup controls');
      assert.ok(indexHtml.includes('fl-build-label'), 'Must have accessible label for FL Studio versions');
      assert.ok(indexHtml.includes('arch-label'), 'Must have accessible label for architectures');
      assert.ok(indexHtml.includes('FL Studio 26.1.3'), 'Must contain FL 26 option');
      assert.ok(indexHtml.includes('Windows ARM64'), 'Must contain ARM64 option');
      assert.ok(indexHtml.includes('Windows x64'), 'Must contain x64 option');
    });

    it('should enforce WCAG AA indicator compliance (LED + Text + Icon)', () => {
      // Must contain all three indicators: LED class, explicit text, icon symbol
      assert.ok(indexHtml.includes('bg-ok') || indexHtml.includes('bg-warn') || indexHtml.includes('bg-err'), 'Must contain LED classes');
      assert.ok(indexHtml.includes('AVAILABLE'), 'Must contain explicit text label AVAILABLE');
      assert.ok(indexHtml.includes('DEGRADED'), 'Must contain explicit text label DEGRADED');
      assert.ok(indexHtml.includes('UNAVAILABLE'), 'Must contain explicit text label UNAVAILABLE');
      assert.ok(indexHtml.includes('✓') && indexHtml.includes('▲') && indexHtml.includes('✕'), 'Must contain icon glyphs');
    });

    it('should link directly to full /compat page', () => {
      assert.ok(indexHtml.includes('href="/compat"'), 'Must link to /compat page');
    });

    it('should place Section 04 between Section 03 and Section 05', () => {
      const idx03 = indexHtml.indexOf('03 / CONTROL SURFACES');
      const idx04 = indexHtml.indexOf('04 / CAPABILITIES');
      const idx05 = indexHtml.indexOf('05 / INTERLOCKS');

      assert.ok(idx03 > -1, 'Section 03 must exist');
      assert.ok(idx04 > -1, 'Section 04 must exist');
      assert.ok(idx05 > -1, 'Section 05 must exist');
      assert.ok(idx03 < idx04, 'Section 03 must come before Section 04');
      assert.ok(idx04 < idx05, 'Section 04 must come before Section 05');
    });
  });

  describe('3. Dedicated Compatibility Report Page (/compat)', () => {
    let compatHtml: string;

    it('should generate dist/compat/index.html or dist/compat.html', () => {
      let resolvedPath: string | null = null;
      try {
        resolvedPath = resolveDistFile('compat/index.html');
      } catch {
        resolvedPath = resolveDistFile('compat.html');
      }
      assert.ok(resolvedPath && fs.existsSync(resolvedPath), 'compat page file must exist in dist');
      compatHtml = fs.readFileSync(resolvedPath, 'utf8');
    });

    it('should contain page header, skip link, and breadcrumb to home', () => {
      assert.ok(compatHtml.includes('href="#main-content"'), 'Must contain accessible skip-link');
      assert.ok(compatHtml.includes('aria-label="Breadcrumb"'), 'Must contain breadcrumb navigation');
      assert.ok(compatHtml.includes('href="/"'), 'Must have breadcrumb link back to Home');
      assert.ok(compatHtml.includes('Tested Compatibility Matrix'), 'Must contain h1 title');
    });

    it('should contain full side-by-side comparison matrix for all 6 configurations', () => {
      assert.ok(compatHtml.includes('SIDE-BY-SIDE MATRIX'), 'Must contain side-by-side matrix heading');
      assert.ok(compatHtml.includes('DIAG-ARM64-26-01'), 'Must include ARM64 FL 26 diagnostic bundle ID');
      assert.ok(compatHtml.includes('DIAG-X64-26-01'), 'Must include x64 FL 26 diagnostic bundle ID');
      assert.ok(compatHtml.includes('CAP_LIVE_TRANSPORT'), 'Must include CAP_LIVE_TRANSPORT');
      assert.ok(compatHtml.includes('CAP_PLUGIN_INSTANTIATE'), 'Must include CAP_PLUGIN_INSTANTIATE');
      assert.ok(compatHtml.includes('CAP_HOST_NATIVE_ARM64'), 'Must include CAP_HOST_NATIVE_ARM64');
      assert.ok(compatHtml.includes('CAP_FLP_PLAYLIST_WRITE'), 'Must include CAP_FLP_PLAYLIST_WRITE');
      assert.ok(compatHtml.includes('CAP_ZERO_KERNEL_DRIVERS'), 'Must include CAP_ZERO_KERNEL_DRIVERS');
    });

    it('should contain technical deep-dives on degraded and unavailable boundaries', () => {
      assert.ok(compatHtml.includes('Honest Rationale &amp; Technical Limits') || compatHtml.includes('Honest Rationale & Technical Limits'));
      assert.ok(compatHtml.includes('Third-Party Plugin Instantiation'));
      assert.ok(compatHtml.includes('FL Studio Host Under Prism Emulation'));
      assert.ok(compatHtml.includes('Playlist Clip Creation in FL Studio 26'));
      assert.ok(compatHtml.includes('Zero Proprietary Kernel Drivers'));
      assert.ok(compatHtml.includes('sbridge flp template add'), 'Must describe seed template workaround');
    });

    it('should detail authentic hardware test specifications for Machine A and Machine B', () => {
      assert.ok(compatHtml.includes('Machine A'), 'Must document Machine A');
      assert.ok(compatHtml.includes('Snapdragon X Elite'), 'Must document Snapdragon processor');
      assert.ok(compatHtml.includes('Machine B'), 'Must document Machine B');
      assert.ok(compatHtml.includes('Ryzen') || compatHtml.includes('Intel'), 'Must document x64 processor');
      assert.ok(compatHtml.includes('sbridge diag'), 'Must reference sbridge diag command');
    });

    it('should include verbatim prominent non-affiliation disclaimer', () => {
      const verbatimDisclaimer = 'StudioBridge is an independent open-source project. FL Studio is a trademark of Image-Line. Not affiliated with or endorsed by Image-Line.';
      assert.ok(compatHtml.includes(verbatimDisclaimer), 'Must include verbatim non-affiliation statement in footer');
    });
  });
});
