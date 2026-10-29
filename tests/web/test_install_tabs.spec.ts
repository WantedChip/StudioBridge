/**
 * Test Suite for Dynamic Agent Installation Tabs Island
 *
 * Requirements:
 * 1. Zero-drift template verification: Snippets match packages/studiobridge/src/studiobridge/agents/templates/.
 * 2. Architecture toggle: Windows ARM64 (Prism + WMS loopback) vs Windows x64 (WMS + loopMIDI fallback).
 * 3. 3-step setup structure: Step 1 (Loopback), Step 2 (Agent MCP), Step 3 (Doctor diagnostics).
 * 4. Keyboard & ARIA accessibility: role="tablist", role="tab", role="tabpanel", arrow key navigation, focus rings.
 * 5. Clipboard copy buttons: Accessible copy triggers for terminal commands and config blocks.
 * 6. Authentic sample doctor output: Verified passing checks (SYS-01, PY-01, FL-01, WMS-01, PORT-01, DEV-01, IPC-01, WIRE-01).
 * 7. Dual-theme syntax highlighting: Shiki adaptations for Light "Paper" and Dark "Rack" palettes.
 */

import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert';
import { describe, it } from 'node:test';

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

function resolveTemplatesDir(): string {
  const candidates = [
    path.resolve(process.cwd(), 'packages/studiobridge/src/studiobridge/agents/templates'),
    path.resolve(process.cwd(), '../packages/studiobridge/src/studiobridge/agents/templates'),
    path.resolve(__dirname, '../../packages/studiobridge/src/studiobridge/agents/templates'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`Templates dir not found. Candidates checked: ${candidates.join(', ')}`);
}

function resolveAgentsJson(): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/src/data/agents.json'),
    path.resolve(process.cwd(), 'src/data/agents.json'),
    path.resolve(__dirname, '../../site/src/data/agents.json'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`agents.json not found. Run 'npm run prebuild' or 'npm run gen:agents' first.`);
}

function resolveTokensCss(): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/src/styles/tokens.css'),
    path.resolve(process.cwd(), 'src/styles/tokens.css'),
    path.resolve(__dirname, '../../site/src/styles/tokens.css'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`tokens.css not found.`);
}

describe('Dynamic Agent Installation Tabs Island', () => {
  const htmlPath = resolveDistHtml();
  const html = fs.readFileSync(htmlPath, 'utf8');
  const templatesDir = resolveTemplatesDir();
  const agentsJsonPath = resolveAgentsJson();
  const agentsData = JSON.parse(fs.readFileSync(agentsJsonPath, 'utf8'));
  const tokensCss = fs.readFileSync(resolveTokensCss(), 'utf8');

  describe('1. Zero-Drift Template Generation', () => {
    const expectedAgents = [
      { id: 'claude-code', name: 'Claude Code', template: 'claude_code.json', format: 'json' },
      { id: 'claude-desktop', name: 'Claude Desktop', template: 'claude_desktop.json', format: 'json' },
      { id: 'codex', name: 'Codex', template: 'codex.toml', format: 'toml' },
      { id: 'cursor', name: 'Cursor', template: 'cursor.json', format: 'json' },
      { id: 'opencode', name: 'opencode', template: 'opencode.json', format: 'json' },
      { id: 'antigravity', name: 'Antigravity', template: 'antigravity.json', format: 'json' },
      { id: 'gemini', name: 'Gemini CLI', template: 'gemini.json', format: 'json' },
      { id: 'vscode', name: 'VS Code', template: 'vscode.json', format: 'json' },
      { id: 'windsurf', name: 'Windsurf', template: 'windsurf.json', format: 'json' },
      { id: 'zed', name: 'Zed', template: 'zed.json', format: 'json' },
      { id: 'generic', name: 'Generic', template: 'generic.json', format: 'json' },
    ];

    it('contains exactly the 11 specified agent configurations', () => {
      assert.strictEqual(agentsData.length, 11, 'Must contain exactly 11 agent tabs');
      const ids = agentsData.map((a: { id: string }) => a.id);
      for (const expected of expectedAgents) {
        assert.ok(ids.includes(expected.id), `Missing agent id ${expected.id}`);
      }
    });

    it('matches repository installer templates with zero drift and resolved tokens', () => {
      for (const expected of expectedAgents) {
        const agent = agentsData.find((a: { id: string }) => a.id === expected.id);
        assert.ok(agent, `Agent ${expected.id} not found in agents.json`);

        const templatePath = path.join(templatesDir, expected.template);
        assert.ok(fs.existsSync(templatePath), `Template file missing: ${expected.template}`);

        const rawTemplate = fs.readFileSync(templatePath, 'utf8').trim();
        const expectedSnippet = rawTemplate
          .replaceAll('{DIST}', 'studiobridge')
          .replaceAll('{CLI}', 'sbridge');

        assert.strictEqual(
          agent.rawSnippet,
          expectedSnippet,
          `Drift detected in snippet for ${expected.name}`
        );

        assert.ok(
          !agent.rawSnippet.includes('{DIST}') && !agent.rawSnippet.includes('{CLI}'),
          `Unresolved tokens found in ${expected.name}`
        );

        assert.ok(
          agent.highlightedHtml.includes('<pre class="shiki'),
          `Highlighted HTML missing Shiki pre block for ${expected.name}`
        );
      }
    });
  });

  describe('2. Architecture Toggle (ARM64 vs x64)', () => {
    it('renders the architecture selector radiogroup and options', () => {
      assert.ok(
        html.includes('role="radiogroup"') && html.includes('Windows Target Architecture'),
        'Must render architecture radiogroup'
      );
      assert.ok(
        html.includes('Windows ARM64') && html.includes('Windows x64'),
        'Must render both Windows ARM64 and Windows x64 toggle buttons'
      );
    });

    it('renders ARM64 prerequisites mentioning Snapdragon, Prism, and native WMS', () => {
      assert.ok(
        html.includes('Snapdragon X Elite') || html.includes('ARM64 Target'),
        'Must mention ARM64 / Snapdragon target'
      );
      assert.ok(
        html.includes('Prism') && html.includes('Windows MIDI Services'),
        'Must explain Prism emulation and native Windows MIDI Services for ARM64'
      );
      assert.ok(
        html.includes('Zero kernel-mode drivers') || html.includes('zero kernel drivers'),
        'Must highlight zero kernel drivers policy'
      );
    });

    it('renders x64 prerequisites with WMS loopback and loopMIDI fallback', () => {
      assert.ok(
        html.includes('Intel / AMD') || html.includes('x64 Target'),
        'Must mention Intel / AMD x64 target'
      );
      assert.ok(
        html.includes('loopMIDI') || html.includes('fallback'),
        'Must mention loopMIDI fallback for legacy Windows systems'
      );
    });
  });

  describe('3. Three-Step Setup Structure', () => {
    it('renders Step 1 with virtual loopback creation and port verification commands', () => {
      assert.ok(
        html.includes('STEP 01') && html.includes('Setup Virtual MIDI Loopback'),
        'Step 1 heading must be present'
      );
      assert.ok(
        html.includes('uvx studiobridge loopback create'),
        'Must display loopback create command'
      );
      assert.ok(
        html.includes('uvx studiobridge ports'),
        'Must display port verification helper command'
      );
    });

    it('renders Step 2 with automated install command and agent tabs', () => {
      assert.ok(
        html.includes('STEP 02') && html.includes('Configure Agent MCP Server'),
        'Step 2 heading must be present'
      );
      assert.ok(
        html.includes('uvx studiobridge agent install'),
        'Must display automated agent install command'
      );
    });

    it('renders Step 3 with doctor command and sample report', () => {
      assert.ok(
        html.includes('STEP 03') && html.includes('Verify Wire'),
        'Step 3 heading must be present'
      );
      assert.ok(
        html.includes('uvx studiobridge doctor'),
        'Must display doctor verification command'
      );
    });
  });

  describe('4. Tab Navigation & Accessibility', () => {
    it('renders accessible tablist container with proper aria-label', () => {
      assert.ok(
        html.includes('role="tablist"') && html.includes('aria-label="Agent configuration templates"'),
        'Must have role="tablist" with descriptive aria-label'
      );
    });

    it('renders role="tab" elements with proper ARIA attributes', () => {
      assert.ok(
        html.includes('role="tab"') && html.includes('aria-controls="panel-claude-code"'),
        'Tab must have role="tab" and aria-controls'
      );
      assert.ok(
        html.includes('id="tab-claude-code"'),
        'Tab must have corresponding id'
      );
    });

    it('renders active role="tabpanel" linked to active tab', () => {
      assert.ok(
        html.includes('role="tabpanel"') && html.includes('aria-labelledby="tab-claude-code"'),
        'Panel must have role="tabpanel" and aria-labelledby'
      );
    });
  });

  describe('5. Sample Doctor Diagnostics Report', () => {
    it('displays authentic doctor passing checks matching the specifications', () => {
      const requiredChecks = [
        'SYS-01',
        'PY-01',
        'FL-01',
        'WMS-01',
        'PORT-01',
        'DEV-01',
        'IPC-01',
        'WIRE-01',
      ];
      for (const check of requiredChecks) {
        assert.ok(
          html.includes(check),
          `Doctor sample report must include passing check ID ${check}`
        );
      }
      assert.ok(
        html.includes('Result: HEALTHY (ready for StudioBridge operations).'),
        'Doctor sample output must conclude with HEALTHY result'
      );
    });
  });

  describe('6. Dual-Theme Syntax Highlighting Adaptations', () => {
    it('tokens.css contains rules mapping Shiki dual-theme tokens to Paper and Rack palettes', () => {
      assert.ok(
        tokensCss.includes('.shiki'),
        'tokens.css must declare .shiki styling rules'
      );
      assert.ok(
        tokensCss.includes('var(--surface)'),
        'tokens.css must map .shiki background to var(--surface)'
      );
      assert.ok(
        tokensCss.includes('var(--shiki-light)') && tokensCss.includes('var(--shiki-dark)'),
        'tokens.css must map .shiki token colors to dual-theme variables'
      );
      assert.ok(
        tokensCss.includes(':root[data-theme="dark"]') || tokensCss.includes('[data-theme="dark"] .shiki'),
        'tokens.css must include dark theme overrides for Shiki'
      );
    });
  });
});
