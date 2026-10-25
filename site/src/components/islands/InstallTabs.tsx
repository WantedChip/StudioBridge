import React, { useState, useRef, useCallback } from 'react';
import CopyButton from '../CopyButton.tsx';
import rawAgentsData from '../../data/agents.json';

export interface AgentConfig {
  id: string;
  name: string;
  templateFile: string;
  configFormat: 'json' | 'toml';
  targetPath: string;
  scope: 'project' | 'user';
  installCommand: string;
  cliCommand: string;
  nextSteps: string;
  windowsNote?: string;
  rawSnippet: string;
  highlightedHtml: string;
}

const AGENTS: AgentConfig[] = rawAgentsData as AgentConfig[];

export type TargetArch = 'arm64' | 'x64';

export const SAMPLE_DOCTOR_OUTPUT = `StudioBridge Doctor Report (2026-10-25 18:30:00 UTC)
FL Studio Running: Yes (FL64.exe, PID 14280)
==============================================================================
Status   ID          Severity  Check Name
------------------------------------------------------------------------------
[PASS]   SYS-01      error     Windows 11 (build 26100, ARM64 / x64 compatible)
[PASS]   PY-01       error     Python 3.12 (64-bit runtime, ctypes WinMM backend)
[PASS]   FL-01       error     FL Studio installation detected (FL 2024 / 21–26)
[PASS]   WMS-01      error     Windows MIDI Services virtual loopback pair active
[PASS]   PORT-01     error     MIDI endpoints 'StudioBridge In' & 'Out' unlocked
[PASS]   DEV-01      error     Device script integrity verified (SHA-256 valid)
[PASS]   IPC-01      error     Broker daemon endpoint healthy (0.42 ms latency)
[PASS]   WIRE-01     error     SysEx 2-way RPC round-trip verified (ping/pong ACK)
------------------------------------------------------------------------------
Summary: 8 passed, 0 warned, 0 failed, 0 skipped.
Result: HEALTHY (ready for StudioBridge operations).`;

export default function InstallTabs(): React.JSX.Element {
  const [activeArch, setActiveArch] = useState<TargetArch>('arm64');
  const [activeAgentId, setActiveAgentId] = useState<string>('claude-code');
  const tabRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  const activeAgent = AGENTS.find((a) => a.id === activeAgentId) || AGENTS[0];

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
      let nextIndex = currentIndex;
      const count = AGENTS.length;

      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        nextIndex = (currentIndex + 1) % count;
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        nextIndex = (currentIndex - 1 + count) % count;
      } else if (e.key === 'Home') {
        e.preventDefault();
        nextIndex = 0;
      } else if (e.key === 'End') {
        e.preventDefault();
        nextIndex = count - 1;
      } else {
        return;
      }

      const nextAgent = AGENTS[nextIndex];
      if (nextAgent) {
        setActiveAgentId(nextAgent.id);
        const nextButton = tabRefs.current.get(nextAgent.id);
        if (nextButton) {
          nextButton.focus();
        }
      }
    },
    [],
  );

  return (
    <section
      id="install"
      data-section="06-patch-in"
      className="relative border-b border-line bg-bg py-20 px-4 sm:px-6 lg:px-8"
      aria-labelledby="install-heading"
    >
      <div className="mx-auto max-w-7xl">
        {/* Section Header */}
        <div className="flex flex-col gap-2 mb-12">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs uppercase tracking-wider text-signal font-bold">
              06 / PATCH IN
            </span>
            <span className="h-px w-8 bg-line" aria-hidden="true"></span>
            <span className="font-mono text-xs uppercase tracking-wider text-ink-muted">
              INSTALLATION & INTEGRATION
            </span>
          </div>

          <h2
            id="install-heading"
            className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-ink"
          >
            Patch your agent into your DAW.
          </h2>

          <p className="max-w-3xl text-base sm:text-lg text-ink-muted leading-relaxed">
            Zero proprietary kernel drivers. Zero configuration drift. Three verified steps from
            fresh clone or clean terminal to bidirectional SysEx RPC actuation.
          </p>
        </div>

        {/* Architecture Selector Bar */}
        <div className="mb-12 border border-line bg-surface p-4 sm:p-6 registration-mark registration-mark-tl registration-mark-br">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <span className="font-mono text-xs uppercase tracking-wider text-ink-muted block mb-1">
                TARGET ARCHITECTURE
              </span>
              <p className="text-sm text-ink font-medium">
                Select your host Windows architecture to tailor prerequisite commands:
              </p>
            </div>

            {/* Architecture Toggle Buttons */}
            <div
              role="radiogroup"
              aria-label="Windows Target Architecture"
              className="inline-flex border border-line p-1 bg-bg"
            >
              <button
                type="button"
                role="radio"
                aria-checked={activeArch === 'arm64'}
                onClick={() => setActiveArch('arm64')}
                className={`px-4 py-2 text-xs font-mono font-semibold uppercase tracking-wider transition-colors focus-ring ${
                  activeArch === 'arm64'
                    ? 'bg-signal text-white'
                    : 'bg-transparent text-ink-muted hover:text-ink hover:bg-surface'
                }`}
              >
                Windows ARM64
                <span className="ml-1.5 opacity-80 font-normal lowercase">(prism + wms)</span>
              </button>

              <button
                type="button"
                role="radio"
                aria-checked={activeArch === 'x64'}
                onClick={() => setActiveArch('x64')}
                className={`px-4 py-2 text-xs font-mono font-semibold uppercase tracking-wider transition-colors focus-ring ${
                  activeArch === 'x64'
                    ? 'bg-signal text-white'
                    : 'bg-transparent text-ink-muted hover:text-ink hover:bg-surface'
                }`}
              >
                Windows x64
                <span className="ml-1.5 opacity-80 font-normal lowercase">(intel / amd)</span>
              </button>
            </div>
          </div>

          {/* Architecture Prerequisites Note */}
          <div className="mt-4 pt-4 border-t border-line text-xs font-mono text-ink-muted flex items-start gap-2">
            <span className="text-signal font-bold select-none">[NOTE]</span>
            <div className="flex-1">
              <div
                id="arch-details-arm64"
                className={activeArch === 'arm64' ? 'block' : 'hidden'}
              >
                <strong>ARM64 Target (Snapdragon X Elite / Plus):</strong> FL Studio executes under
                Windows 11 Prism x64 emulation. StudioBridge MIDI routing uses native Windows MIDI
                Services (WMS) loopback in user space. Zero kernel-mode drivers (<code className="text-ink">.sys</code>) required.
              </div>
              <div
                id="arch-details-x64"
                className={activeArch === 'x64' ? 'block' : 'hidden'}
              >
                <strong>x64 Target (Intel / AMD):</strong> Native 64-bit execution. StudioBridge uses
                Windows MIDI Services loopback endpoints by default; an existing loopMIDI port pair is
                automatically accepted as a seamless fallback if WMS is not present.
              </div>
            </div>
          </div>
        </div>

        {/* 3 Setup Steps Grid / Timeline */}
        <div className="space-y-12">
          {/* STEP 1: MIDI Loopback */}
          <div className="border border-line bg-surface p-6 sm:p-8 registration-mark registration-mark-tr">
            <div className="flex items-center gap-3 mb-4">
              <span className="inline-flex items-center justify-center h-6 px-2 bg-signal text-white font-mono text-xs font-bold uppercase tracking-wider">
                STEP 01
              </span>
              <span className="font-mono text-sm uppercase tracking-wider text-ink font-bold">
                Setup Virtual MIDI Loopback
              </span>
            </div>

            <div className="mb-6 leading-relaxed max-w-3xl text-sm text-ink-muted">
              <p
                id="step1-desc-arm64"
                className={activeArch === 'arm64' ? 'block' : 'hidden'}
              >
                Create the Windows MIDI Services (WMS) virtual loopback pair (<code className="text-ink">StudioBridge In</code> and{' '}
                <code className="text-ink">StudioBridge Out</code>). This provides isolated, user-mode MIDI channels between FL Studio's
                controller script and the StudioBridge daemon without third-party kernel drivers.
              </p>
              <p
                id="step1-desc-x64"
                className={activeArch === 'x64' ? 'block' : 'hidden'}
              >
                Create the loopback MIDI endpoints (<code className="text-ink">StudioBridge In</code> and{' '}
                <code className="text-ink">StudioBridge Out</code>) via Windows MIDI Services. If running on Windows 10/11 prior to WMS,
                pre-configured loopMIDI ports are recognized immediately as a seamless fallback.
              </p>
            </div>

            {/* Step 1 Command Box */}
            <div className="border border-line bg-bg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono text-xs mb-4">
              <div className="flex items-center gap-2 overflow-x-auto text-ink">
                <span className="text-signal select-none font-bold">&gt;</span>
                <code>uvx studiobridge loopback create</code>
              </div>
              <CopyButton
                text="uvx studiobridge loopback create"
                ariaLabel="Copy virtual MIDI loopback setup command"
              />
            </div>

            {/* Ports Verify Helper */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-mono text-ink-muted pt-2">
              <span>Verify loopback endpoints anytime:</span>
              <div className="flex items-center gap-2">
                <code className="bg-bg border border-line px-2 py-1 text-ink">uvx studiobridge ports</code>
                <CopyButton
                  text="uvx studiobridge ports"
                  label="COPY"
                  ariaLabel="Copy verify ports command"
                />
              </div>
            </div>
          </div>

          {/* STEP 2: Configure Agent MCP */}
          <div className="border border-line bg-surface p-6 sm:p-8 registration-mark registration-mark-tl registration-mark-br">
            <div className="flex items-center gap-3 mb-4">
              <span className="inline-flex items-center justify-center h-6 px-2 bg-signal text-white font-mono text-xs font-bold uppercase tracking-wider">
                STEP 02
              </span>
              <span className="font-mono text-sm uppercase tracking-wider text-ink font-bold">
                Configure Agent MCP Server
              </span>
            </div>

            <p className="text-sm text-ink-muted mb-6 leading-relaxed max-w-3xl">
              Install the StudioBridge MCP server automatically into your agent of choice, or copy the exact configuration block below.
              Every snippet is generated directly from the repository's installer templates at build time for guaranteed zero configuration drift.
            </p>

            {/* Automated 1-Liner Install */}
            <div className="border border-line bg-bg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono text-xs mb-8">
              <div className="flex items-center gap-2 overflow-x-auto text-ink">
                <span className="text-signal select-none font-bold">&gt;</span>
                <code>uvx studiobridge agent install {activeAgent.id}</code>
              </div>
              <CopyButton
                text={`uvx studiobridge agent install ${activeAgent.id}`}
                ariaLabel={`Copy automated install command for ${activeAgent.name}`}
              />
            </div>

            {/* Agent Tab Selector Header */}
            <div className="flex items-center justify-between gap-4 mb-3">
              <span className="font-mono text-xs uppercase tracking-wider text-ink-muted">
                SELECT AGENT OR IDE TEMPLATE:
              </span>
              <span className="font-mono text-xs text-signal font-semibold">
                {activeAgent.name} ({activeAgent.configFormat.toUpperCase()})
              </span>
            </div>

            {/* Agent Tab Buttons List (role="tablist") */}
            <div
              role="tablist"
              aria-label="Agent configuration templates"
              className="flex items-center gap-1 border-b border-line pb-px overflow-x-auto mb-6 scrollbar-thin"
            >
              {AGENTS.map((agent, idx) => {
                const isSelected = activeAgentId === agent.id;
                return (
                  <button
                    key={agent.id}
                    ref={(el) => {
                      if (el) {
                        tabRefs.current.set(agent.id, el);
                      } else {
                        tabRefs.current.delete(agent.id);
                      }
                    }}
                    id={`tab-${agent.id}`}
                    role="tab"
                    type="button"
                    aria-selected={isSelected}
                    aria-controls={`panel-${agent.id}`}
                    tabIndex={isSelected ? 0 : -1}
                    onClick={() => setActiveAgentId(agent.id)}
                    onKeyDown={(e) => handleKeyDown(e, idx)}
                    className={`px-3 py-2 text-xs font-mono whitespace-nowrap transition-colors focus-ring border-t border-l border-r ${
                      isSelected
                        ? 'border-line bg-bg text-ink font-bold border-b-2 border-b-signal -mb-px'
                        : 'border-transparent text-ink-muted hover:text-ink hover:bg-bg/50'
                    }`}
                  >
                    {agent.name}
                  </button>
                );
              })}
            </div>

            {/* Active Tab Panel (role="tabpanel") */}
            <div
              id={`panel-${activeAgent.id}`}
              role="tabpanel"
              aria-labelledby={`tab-${activeAgent.id}`}
              className="border border-line bg-bg p-4 sm:p-6"
            >
              {/* File & Scope Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 mb-4 border-b border-line text-xs font-mono">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2 py-0.5 bg-surface border border-line text-ink font-semibold">
                    {activeAgent.targetPath}
                  </span>
                  <span className="px-2 py-0.5 bg-surface border border-line text-ink-muted uppercase">
                    scope: {activeAgent.scope}
                  </span>
                  <span className="px-2 py-0.5 bg-surface border border-line text-signal uppercase font-bold">
                    {activeAgent.configFormat}
                  </span>
                </div>

                <CopyButton
                  text={activeAgent.rawSnippet}
                  label="COPY CONFIG"
                  copiedLabel="CONFIG COPIED"
                  ariaLabel={`Copy ${activeAgent.name} configuration snippet`}
                />
              </div>

              {/* Syntax Highlighted Code Block */}
              <div
                className="overflow-x-auto text-xs font-mono rounded-none border border-line bg-surface p-4 text-ink leading-relaxed"
                dangerouslySetInnerHTML={{ __html: activeAgent.highlightedHtml }}
              />

              {/* Tab Panel Footer Notes */}
              <div className="mt-4 pt-4 border-t border-line space-y-2 text-xs font-mono text-ink-muted">
                <p>
                  <strong className="text-ink">Next step:</strong> {activeAgent.nextSteps}
                </p>
                {activeAgent.windowsNote && (
                  <p className="text-ink-muted">
                    <span className="text-signal">[INFO]</span> {activeAgent.windowsNote} Standard execution uses{' '}
                    <code className="text-ink">uvx studiobridge mcp</code>. For Node/npm environments:{' '}
                    <code className="text-ink">cmd /c npx -y studiobridge mcp</code>.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* STEP 3: Verify with Doctor */}
          <div className="border border-line bg-surface p-6 sm:p-8 registration-mark registration-mark-bl">
            <div className="flex items-center gap-3 mb-4">
              <span className="inline-flex items-center justify-center h-6 px-2 bg-signal text-white font-mono text-xs font-bold uppercase tracking-wider">
                STEP 03
              </span>
              <span className="font-mono text-sm uppercase tracking-wider text-ink font-bold">
                Verify Wire &amp; Runtime with Doctor
              </span>
            </div>

            <p className="text-sm text-ink-muted mb-6 leading-relaxed max-w-3xl">
              Execute <code className="text-ink">sbridge doctor</code> to run comprehensive preflight diagnostics across host environment,
              FL Studio installation, loopback port topology, script file integrity, broker IPC daemon health, and SysEx wire ping/pong.
            </p>

            {/* Step 3 Command Box */}
            <div className="border border-line bg-bg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono text-xs mb-6">
              <div className="flex items-center gap-2 overflow-x-auto text-ink">
                <span className="text-signal select-none font-bold">&gt;</span>
                <code>uvx studiobridge doctor</code>
              </div>
              <CopyButton
                text="uvx studiobridge doctor"
                ariaLabel="Copy doctor verification command"
              />
            </div>

            {/* Sample Doctor Output Console Box */}
            <div className="border border-line bg-bg">
              {/* Terminal Title Bar */}
              <div className="flex items-center justify-between px-4 py-2 border-b border-line bg-surface text-xs font-mono">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-ok" aria-hidden="true"></span>
                  <span className="font-semibold text-ink">TERMINAL // sbridge doctor</span>
                </div>
                <CopyButton
                  text={SAMPLE_DOCTOR_OUTPUT}
                  label="COPY OUTPUT"
                  copiedLabel="OUTPUT COPIED"
                  ariaLabel="Copy sample doctor report"
                />
              </div>

              {/* Terminal Content */}
              <pre
                tabIndex={0}
                aria-label="Sample sbridge doctor output"
                className="p-4 overflow-x-auto font-mono text-xs text-ink leading-relaxed whitespace-pre focus-ring"
              >
                {SAMPLE_DOCTOR_OUTPUT}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
