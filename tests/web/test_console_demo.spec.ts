/**
 * Test Suite for Interactive Console Demo Island & Session Playback
 *
 * Requirements:
 * 1. Three authentic recorded session transcripts:
 *    - balance-drums.json: mixer_set, tolerance checks, read-back verification.
 *    - add-bassline.json: notes_apply, notes_read, piano roll oracle verification.
 *    - render-preview.json: render_start, render_status, render_analyze acoustic validation.
 * 2. Honest environment provenance: Clearly labeled with source ("Recorded with the emulator"
 *    or "Recorded on FL 26.1.3 / ARM64") and dates.
 * 3. Clean-room provenance: Zero proprietary FL Studio logos, screenshots, or copyrighted UI.
 * 4. Abstract Workstation Visual: SVG/CSS drawing with mixer faders, dB peak bars,
 *    piano roll note lanes, step grid triggers, and render progress/waveform preview.
 * 5. Player controls & Accessibility: Keyboard operability (Space, Arrow keys, Tabs),
 *    role="tablist"/tab/tabpanel, aria-live region, prefers-reduced-motion compliance.
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

function resolveSessionsDir(): string {
  const candidates = [
    path.resolve(process.cwd(), 'site/src/data/sessions'),
    path.resolve(process.cwd(), 'src/data/sessions'),
    path.resolve(__dirname, '../../site/src/data/sessions'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error(`sessions directory not found. Candidates checked: ${candidates.join(', ')}`);
}

describe('Interactive Console Demo Island & Session Playback', () => {
  const htmlPath = resolveDistHtml();
  const html = fs.readFileSync(htmlPath, 'utf8');
  const sessionsDir = resolveSessionsDir();

  describe('1. Scripted Session Transcripts & Schemas', () => {
    const requiredSessions = [
      {
        file: 'balance-drums.json',
        id: 'balance-drums',
        expectedEnv: 'Recorded with the emulator',
        expectedTools: ['mixer_list', 'mixer_set', 'mixer_get'],
        expectedView: 'mixer',
      },
      {
        file: 'add-bassline.json',
        id: 'add-bassline',
        expectedEnv: 'Recorded on FL 26.1.3 / ARM64',
        expectedTools: ['channel_get', 'notes_apply', 'notes_read'],
        expectedView: 'pianoroll',
      },
      {
        file: 'render-preview.json',
        id: 'render-preview',
        expectedEnv: 'Recorded on FL 26.1.3 / ARM64',
        expectedTools: ['render_start', 'render_status', 'render_analyze'],
        expectedView: 'render',
      },
    ];

    it('contains all three required session files', () => {
      for (const req of requiredSessions) {
        const filePath = path.join(sessionsDir, req.file);
        assert.ok(fs.existsSync(filePath), `Missing session file: ${req.file}`);
      }
    });

    it('validates authentic session structure, tools, and honest environment provenance', () => {
      for (const req of requiredSessions) {
        const filePath = path.join(sessionsDir, req.file);
        const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));

        assert.strictEqual(data.id, req.id, `Session ID mismatch in ${req.file}`);
        assert.ok(data.title && data.title.length > 0, `Missing title in ${req.file}`);
        assert.strictEqual(data.environmentLabel, req.expectedEnv, `Environment label mismatch in ${req.file}`);
        assert.ok(data.recordedAt && data.recordedAt.startsWith('2026-'), `Invalid recordedAt in ${req.file}`);
        assert.ok(data.fl && data.fl.build && data.fl.arch, `Missing fl build/arch in ${req.file}`);
        assert.ok(Array.isArray(data.steps) && data.steps.length >= 4, `Session steps too short in ${req.file}`);

        // Verify tool calls
        const toolCalls = data.steps
          .filter((s: { role: string; tool?: string }) => s.role === 'tool' && s.tool)
          .map((s: { tool: string }) => s.tool);

        for (const tool of req.expectedTools) {
          assert.ok(
            toolCalls.includes(tool),
            `Session ${req.file} missing expected tool invocation: ${tool}`
          );
        }

        // Verify visual views
        const views = data.steps.map((s: { visual?: { view?: string } }) => s.visual?.view);
        assert.ok(
          views.includes(req.expectedView),
          `Session ${req.file} missing expected visual view: ${req.expectedView}`
        );
      }
    });

    it('verifies tolerance checks and mutation receipts in balance-drums.json', () => {
      const data = JSON.parse(fs.readFileSync(path.join(sessionsDir, 'balance-drums.json'), 'utf8'));
      const setStep = data.steps.find((s: { tool?: string }) => s.tool === 'mixer_set');
      assert.ok(setStep, 'Must include mixer_set step');
      assert.strictEqual(setStep.args.tolerance, 0.01, 'Tolerance argument must be 0.01');
      assert.strictEqual(setStep.args.verify, true, 'Verify argument must be true');
      assert.ok(setStep.result.journal_id, 'Must record journal_id in receipt');
      assert.ok(Array.isArray(setStep.result.mutations), 'Must record mutations array');
    });

    it('verifies piano-roll oracle validation in add-bassline.json', () => {
      const data = JSON.parse(fs.readFileSync(path.join(sessionsDir, 'add-bassline.json'), 'utf8'));
      const applyStep = data.steps.find((s: { tool?: string }) => s.tool === 'notes_apply');
      assert.ok(applyStep, 'Must include notes_apply step');
      assert.strictEqual(applyStep.args.verify, 'oracle', 'notes_apply verify must be oracle');
      assert.strictEqual(applyStep.args.pattern, 2, 'Pattern must be 2');
      assert.strictEqual(applyStep.args.channel, 3, 'Channel must be 3');

      const readStep = data.steps.find((s: { tool?: string }) => s.tool === 'notes_read');
      assert.ok(readStep, 'Must include notes_read verification step');
      assert.strictEqual(readStep.result.status, 'match_100%', 'Must verify 100% match');
    });

    it('verifies headless render supervisor and acoustic analysis in render-preview.json', () => {
      const data = JSON.parse(fs.readFileSync(path.join(sessionsDir, 'render-preview.json'), 'utf8'));
      const startStep = data.steps.find((s: { tool?: string }) => s.tool === 'render_start');
      assert.ok(startStep, 'Must include render_start step');

      const analyzeStep = data.steps.find((s: { tool?: string }) => s.tool === 'render_analyze');
      assert.ok(analyzeStep, 'Must include render_analyze step');
      assert.strictEqual(analyzeStep.result.is_valid, true, 'Acoustic validation must pass');
      assert.strictEqual(analyzeStep.result.clipping_samples, 0, 'Zero clipping samples required');
    });
  });

  describe('2. Landing Page Integration & DOM Rendering', () => {
    it('renders section 02 / TRY A SESSION with anchor id="session-demo"', () => {
      assert.ok(
        html.includes('id="session-demo"'),
        'Section must have id="session-demo" matching Hero jump link'
      );
      assert.ok(
        html.includes('02 / TRY A SESSION'),
        'Section must display catalogue section kicker "02 / TRY A SESSION"'
      );
      assert.ok(
        html.includes('See the bridge in action.'),
        'Section must render main headline'
      );
    });

    it('renders session switcher tabs with ARIA tablist semantics', () => {
      assert.ok(
        html.includes('role="tablist"') && html.includes('aria-label="Recorded agent sessions"'),
        'Must contain tablist with descriptive label'
      );
      assert.ok(
        html.includes('role="tab"') && html.includes('id="tab-balance-drums"'),
        'Must contain tab for balance-drums'
      );
      assert.ok(
        html.includes('id="tab-add-bassline"'),
        'Must contain tab for add-bassline'
      );
      assert.ok(
        html.includes('id="tab-render-preview"'),
        'Must contain tab for render-preview'
      );
    });

    it('renders honest environment and provenance banner', () => {
      assert.ok(
        html.includes('Recorded with the emulator') || html.includes('Recorded on FL 26.1.3 / ARM64'),
        'Must display honest environment label'
      );
      assert.ok(
        html.includes('Zero proprietary FL Studio UI or logos'),
        'Must display clean-room IP notice'
      );
    });

    it('renders accessible player controls: Play, Step, Reset, Speed, Transcript Only', () => {
      assert.ok(
        html.includes('PLAY') || html.includes('PAUSE'),
        'Must display Play / Pause control'
      );
      assert.ok(
        html.includes('STEP'),
        'Must display Step Forward control'
      );
      assert.ok(
        html.includes('RESET'),
        'Must display Reset control'
      );
      assert.ok(
        html.includes('SPEED:'),
        'Must display Speed selector'
      );
      assert.ok(
        html.includes('TRANSCRIPT ONLY'),
        'Must display Transcript Only mode toggle'
      );
    });

    it('renders screen reader live region for step progression', () => {
      assert.ok(
        html.includes('aria-live="polite"'),
        'Must provide aria-live="polite" announcement region'
      );
    });
  });

  describe('3. Clean-Room Abstract Workstation Visual', () => {
    it('renders original abstract DAW visual container', () => {
      assert.ok(
        html.includes('data-testid="workstation-visual"') ||
          html.includes('aria-label="Abstract Audio Workstation Visualization"'),
        'Must render WorkstationVisual container'
      );
      assert.ok(
        html.includes('ORIGINAL ABSTRACT DAW'),
        'Must declare original abstract DAW notice'
      );
    });

    it('renders abstract mixer components (faders, channels, dB peak meters)', () => {
      assert.ok(
        html.includes('MIXER STRIP ARRAY') || html.includes('Master') || html.includes('Kick'),
        'Must render mixer strip array'
      );
      assert.ok(
        html.includes('BUS PEAK TOLERANCE: ±0.0100') || html.includes('TOLERANCE'),
        'Must display write tolerance indicator'
      );
    });

    it('ensures ZERO proprietary FL Studio graphics, logos, or assets are referenced', () => {
      const lowerHtml = html.toLowerCase();
      assert.ok(
        !lowerHtml.includes('fl_logo') &&
          !lowerHtml.includes('flstudio.png') &&
          !lowerHtml.includes('fruityloops') &&
          !lowerHtml.includes('image-line/logo'),
        'Must NOT reference any proprietary FL Studio logos or graphic assets'
      );
    });
  });
});
