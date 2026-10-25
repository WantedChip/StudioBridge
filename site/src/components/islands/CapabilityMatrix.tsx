import React, { useState, useMemo } from 'react';
import rawCompatData from '../../data/compat.json';

export type CapabilityState = 'available' | 'degraded' | 'unavailable';
export type TargetArch = 'ARM64' | 'x64';
export type FLBuildId = '26.1.3' | '25.2.3' | '21.2';

export interface CapabilityItem {
  id: string;
  name: string;
  category: 'Live Protocol' | 'Offline FLP Engine' | 'Actuation & Render' | 'Host Architecture' | 'System & Architecture';
  state: CapabilityState;
  statusLabel: string;
  reason: string;
  alternatives: string;
  diagRef: string;
}

export interface EnvironmentMetadata {
  machineId: 'Machine A' | 'Machine B';
  hardware: string;
  cpu: string;
  ram: string;
  os: string;
  arch: TargetArch;
  midiBackend: string;
  pythonRuntime: string;
  doctorStatus: string;
  verifiedAt: string;
}

export interface MatrixEntry {
  flBuild: FLBuildId;
  flName: string;
  arch: TargetArch;
  environment: EnvironmentMetadata;
  diagId: string;
  capabilities: Record<string, CapabilityItem>;
}

export interface CompatDataset {
  meta: {
    schemaVersion: string;
    generatedAt: string;
    specVersion: string;
    description: string;
    testedEnvironments: Record<'machineA' | 'machineB', EnvironmentMetadata>;
    flBuilds: Array<{ id: FLBuildId; label: string; releaseYear: string }>;
    architectures: Array<{ id: TargetArch; label: string; description: string }>;
  };
  matrix: Record<string, MatrixEntry>;
  capabilitiesList: Array<{
    id: string;
    name: string;
    category: CapabilityItem['category'];
    description: string;
  }>;
}

const compatData = rawCompatData as unknown as CompatDataset;

export default function CapabilityMatrix(): React.JSX.Element {
  const [selectedBuild, setSelectedBuild] = useState<FLBuildId>('26.1.3');
  const [selectedArch, setSelectedArch] = useState<TargetArch>('ARM64');
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({
    CAP_PLUGIN_INSTANTIATE: true,
    CAP_HOST_NATIVE_ARM64: true,
  });

  const matrixKey = `${selectedBuild}-${selectedArch}`;
  const currentEntry = compatData.matrix[matrixKey] || compatData.matrix['26.1.3-ARM64'];

  const toggleRow = (capId: string) => {
    setExpandedRows((prev) => ({
      ...prev,
      [capId]: !prev[capId],
    }));
  };

  const expandAll = () => {
    const allExpanded: Record<string, boolean> = {};
    compatData.capabilitiesList.forEach((cap) => {
      allExpanded[cap.id] = true;
    });
    setExpandedRows(allExpanded);
  };

  const collapseAll = () => {
    setExpandedRows({});
  };

  // Summary counts
  const counts = useMemo(() => {
    let available = 0;
    let degraded = 0;
    let unavailable = 0;

    compatData.capabilitiesList.forEach((cap) => {
      const item = currentEntry.capabilities[cap.id];
      if (!item) return;
      if (item.state === 'available') available++;
      else if (item.state === 'degraded') degraded++;
      else if (item.state === 'unavailable') unavailable++;
    });

    return { available, degraded, unavailable, total: compatData.capabilitiesList.length };
  }, [currentEntry]);

  return (
    <section
      id="capabilities"
      data-section="04-capabilities"
      className="relative border-b border-line bg-bg py-20 px-4 sm:px-6 lg:px-8"
      aria-labelledby="capabilities-heading"
    >
      <div className="mx-auto max-w-7xl">
        {/* Section Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12 pb-6 border-b border-line">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="font-mono text-xs uppercase tracking-wider text-signal font-bold">
                04 / CAPABILITIES
              </span>
              <span className="h-px w-8 bg-line" aria-hidden="true"></span>
              <span className="font-mono text-xs uppercase tracking-wider text-ink-muted">
                TRUTH TABLE &amp; TESTED MATRIX
              </span>
            </div>

            <h2
              id="capabilities-heading"
              className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-ink"
            >
              Exact capability truth.
            </h2>
            <p className="mt-2 max-w-2xl text-base sm:text-lg text-ink-muted leading-relaxed">
              Every host capability claim is verified on authentic test hardware and backed by real diagnostic bundles.
              Select your FL Studio version and processor architecture to inspect exact states, failure boundaries, and workarounds.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <a
              href="/compat"
              className="inline-flex items-center gap-2 border border-line-strong bg-surface px-4 py-2 text-xs font-mono font-semibold uppercase tracking-wider text-ink hover:bg-ink hover:text-bg transition-colors focus-ring rounded-[1px]"
            >
              <span>View Full /compat Page</span>
              <span aria-hidden="true">&rarr;</span>
            </a>
          </div>
        </div>

        {/* Dual Selectors Panel */}
        <div className="mb-8 border border-line bg-surface p-6 shadow-xs rounded-[2px]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Selector 1: FL Studio Build */}
            <div>
              <label
                id="fl-build-label"
                className="font-mono text-xs uppercase tracking-wider text-ink-muted block mb-3 font-semibold"
              >
                1. SELECT FL STUDIO VERSION
              </label>
              <div
                role="radiogroup"
                aria-labelledby="fl-build-label"
                className="grid grid-cols-3 gap-2"
              >
                {compatData.meta.flBuilds.map((build) => {
                  const isSelected = selectedBuild === build.id;
                  return (
                    <button
                      key={build.id}
                      type="button"
                      role="radio"
                      aria-checked={isSelected}
                      onClick={() => setSelectedBuild(build.id)}
                      className={`flex flex-col items-start p-3 border text-left transition-all focus-ring rounded-[1px] ${
                        isSelected
                          ? 'border-signal bg-signal/5 text-ink shadow-xs ring-1 ring-signal'
                          : 'border-line bg-bg text-ink-muted hover:border-line-strong hover:text-ink'
                      }`}
                    >
                      <span className="font-mono text-xs font-bold text-ink">
                        {build.label}
                      </span>
                      <span className="font-sans text-[11px] text-ink-muted mt-0.5">
                        {build.releaseYear}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Selector 2: CPU Architecture */}
            <div>
              <label
                id="arch-label"
                className="font-mono text-xs uppercase tracking-wider text-ink-muted block mb-3 font-semibold"
              >
                2. SELECT HOST ARCHITECTURE
              </label>
              <div
                role="radiogroup"
                aria-labelledby="arch-label"
                className="grid grid-cols-2 gap-2"
              >
                {compatData.meta.architectures.map((arch) => {
                  const isSelected = selectedArch === arch.id;
                  return (
                    <button
                      key={arch.id}
                      type="button"
                      role="radio"
                      aria-checked={isSelected}
                      onClick={() => setSelectedArch(arch.id)}
                      className={`flex flex-col items-start p-3 border text-left transition-all focus-ring rounded-[1px] ${
                        isSelected
                          ? 'border-signal bg-signal/5 text-ink shadow-xs ring-1 ring-signal'
                          : 'border-line bg-bg text-ink-muted hover:border-line-strong hover:text-ink'
                      }`}
                    >
                      <span className="font-mono text-xs font-bold text-ink flex items-center gap-2">
                        <span>{arch.label}</span>
                        {arch.id === 'ARM64' && (
                          <span className="text-[10px] font-mono px-1.5 py-0.2 bg-signal/15 text-signal font-semibold rounded-[1px]">
                            SNAPDRAGON
                          </span>
                        )}
                      </span>
                      <span className="font-sans text-[11px] text-ink-muted mt-0.5">
                        {arch.description}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Test Provenance & Diagnostic Bar */}
          <div className="mt-6 pt-5 border-t border-line flex flex-wrap items-center justify-between gap-4 font-mono text-xs">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-ink-muted">
              <div>
                TEST RIG: <span className="text-ink font-semibold">{currentEntry.environment.machineId} ({currentEntry.environment.hardware})</span>
              </div>
              <div>
                OS: <span className="text-ink">{currentEntry.environment.os}</span>
              </div>
              <div>
                DIAG BUNDLE: <span className="text-signal font-semibold">{currentEntry.diagId}</span>
              </div>
              <div>
                STATUS: <span className="text-ok font-semibold">{currentEntry.environment.doctorStatus}</span>
              </div>
            </div>

            {/* Matrix Status Badges & Quick Expand */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 text-[11px] font-semibold text-ok">
                  <span className="w-2 h-2 rounded-[1px] bg-ok" aria-hidden="true"></span>
                  <span>{counts.available} AVAILABLE</span>
                </span>
                <span className="text-line">|</span>
                <span className="flex items-center gap-1 text-[11px] font-semibold text-warn">
                  <span className="w-2 h-2 rounded-[1px] bg-warn" aria-hidden="true"></span>
                  <span>{counts.degraded} DEGRADED</span>
                </span>
                <span className="text-line">|</span>
                <span className="flex items-center gap-1 text-[11px] font-semibold text-err">
                  <span className="w-2 h-2 rounded-[1px] bg-err" aria-hidden="true"></span>
                  <span>{counts.unavailable} UNAVAILABLE</span>
                </span>
              </div>

              <div className="flex items-center gap-1 ml-2">
                <button
                  type="button"
                  onClick={expandAll}
                  className="px-2 py-1 text-[11px] border border-line text-ink-muted hover:text-ink hover:bg-bg transition-colors rounded-[1px]"
                >
                  Expand all
                </button>
                <button
                  type="button"
                  onClick={collapseAll}
                  className="px-2 py-1 text-[11px] border border-line text-ink-muted hover:text-ink hover:bg-bg transition-colors rounded-[1px]"
                >
                  Collapse all
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Dynamic Capability Table */}
        <div className="border border-line bg-surface rounded-[2px] overflow-x-auto shadow-xs">
          <table className="w-full text-left border-collapse" aria-label="FL Studio Capability Matrix">
            <thead>
              <tr className="border-b border-line bg-bg font-mono text-[11px] uppercase tracking-wider text-ink-muted">
                <th scope="col" className="py-3 px-4 sm:px-6 font-semibold w-1/3">
                  Capability / Subsystem
                </th>
                <th scope="col" className="py-3 px-4 font-semibold w-1/4">
                  Category
                </th>
                <th scope="col" className="py-3 px-4 font-semibold w-1/4">
                  Verification Status
                </th>
                <th scope="col" className="py-3 px-4 sm:px-6 font-semibold text-right w-1/6">
                  Details
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line font-sans text-xs">
              {compatData.capabilitiesList.map((cap) => {
                const item = currentEntry.capabilities[cap.id];
                if (!item) return null;

                const isExpanded = !!expandedRows[cap.id];
                const rowId = `cap-row-${cap.id}`;
                const detailsId = `cap-details-${cap.id}`;

                return (
                  <React.Fragment key={cap.id}>
                    <tr
                      id={rowId}
                      className={`hover:bg-bg/60 transition-colors cursor-pointer ${
                        item.state === 'unavailable'
                          ? 'bg-err/5'
                          : item.state === 'degraded'
                            ? 'bg-warn/5'
                            : ''
                      }`}
                      onClick={() => toggleRow(cap.id)}
                    >
                      {/* Capability Name & ID */}
                      <td className="py-3.5 px-4 sm:px-6">
                        <div className="font-display text-sm font-bold text-ink">
                          {item.name}
                        </div>
                        <div className="font-mono text-[11px] text-signal font-medium mt-0.5">
                          {item.id}
                        </div>
                      </td>

                      {/* Category */}
                      <td className="py-3.5 px-4 font-mono text-[11px] text-ink-muted">
                        {item.category}
                      </td>

                      {/* Status Indicator (WCAG AA: LED + Explicit Text + Icon) */}
                      <td className="py-3.5 px-4">
                        <div className="inline-flex items-center gap-2">
                          {/* LED indicator */}
                          <span
                            className={`w-2.5 h-2.5 rounded-[1px] shrink-0 ${
                              item.state === 'available'
                                ? 'bg-ok shadow-[0_0_6px_rgba(29,122,74,0.4)]'
                                : item.state === 'degraded'
                                  ? 'bg-warn shadow-[0_0_6px_rgba(138,90,0,0.4)]'
                                  : 'bg-err shadow-[0_0_6px_rgba(179,38,30,0.4)]'
                            }`}
                            aria-hidden="true"
                          ></span>

                          {/* Icon representation (never color alone) */}
                          <span
                            className={`font-mono text-xs font-bold shrink-0 ${
                              item.state === 'available'
                                ? 'text-ok'
                                : item.state === 'degraded'
                                  ? 'text-warn'
                                  : 'text-err'
                            }`}
                            aria-hidden="true"
                          >
                            {item.state === 'available' && '✓'}
                            {item.state === 'degraded' && '▲'}
                            {item.state === 'unavailable' && '✕'}
                          </span>

                          {/* Explicit text label */}
                          <span
                            className={`font-mono text-[11px] font-bold tracking-wider uppercase ${
                              item.state === 'available'
                                ? 'text-ok'
                                : item.state === 'degraded'
                                  ? 'text-warn'
                                  : 'text-err'
                            }`}
                          >
                            {item.statusLabel}
                          </span>
                        </div>
                      </td>

                      {/* Expand / Collapse Button */}
                      <td className="py-3.5 px-4 sm:px-6 text-right">
                        <button
                          type="button"
                          aria-expanded={isExpanded}
                          aria-controls={detailsId}
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleRow(cap.id);
                          }}
                          className="font-mono text-[11px] text-ink-muted hover:text-ink px-2 py-1 border border-line rounded-[1px] inline-flex items-center gap-1 focus-ring"
                        >
                          <span>{isExpanded ? 'Hide' : 'Explain'}</span>
                          <span aria-hidden="true">{isExpanded ? '↑' : '↓'}</span>
                        </button>
                      </td>
                    </tr>

                    {/* Expandable Details Drawer */}
                    {isExpanded && (
                      <tr id={detailsId} className="bg-bg/40 border-b border-line">
                        <td colSpan={4} className="py-4 px-4 sm:px-6">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                            {/* Technical Rationale */}
                            <div className="border border-line bg-surface p-4 rounded-[1px]">
                              <div className="font-mono text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-1 flex items-center justify-between">
                                <span>TECHNICAL RATIONALE &amp; HOST BEHAVIOR</span>
                                <span className="text-signal">{item.diagRef}</span>
                              </div>
                              <p className="text-ink leading-relaxed">
                                {item.reason}
                              </p>
                            </div>

                            {/* Alternative Path / Workaround */}
                            <div className="border border-line bg-surface p-4 rounded-[1px]">
                              <div className="font-mono text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-1">
                                <span>ALTERNATIVE PATH / ENGINEERING WORKAROUND</span>
                              </div>
                              <p className="text-ink leading-relaxed">
                                {item.alternatives}
                              </p>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer Callout & Link to Documentation */}
        <div className="mt-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 text-xs font-sans text-ink-muted">
          <div>
            Data sourced from authentic hardware test receipts: <code className="font-mono text-ink font-semibold">sbridge diag</code> bundles on Snapdragon ARM64 and AMD/Intel x64.
          </div>
          <a
            href="/compat"
            className="font-mono text-xs font-semibold text-signal hover:underline inline-flex items-center gap-1"
          >
            <span>Read complete compatibility analysis &amp; hardware provenance</span>
            <span aria-hidden="true">&rarr;</span>
          </a>
        </div>
      </div>
    </section>
  );
}
