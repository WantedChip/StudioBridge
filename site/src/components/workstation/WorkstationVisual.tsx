import React from 'react';
import type { SessionStepVisual, MixerTrackVisual, PianoRollNoteVisual, RenderVisual } from '../../data/sessions/index.ts';

export interface WorkstationVisualProps {
  visual: SessionStepVisual;
  stepNumber: number;
  totalSteps: number;
  className?: string;
}

// Fallback states if a session step does not define a particular view's payload
const DEFAULT_MIXER_TRACKS: MixerTrackVisual[] = [
  { id: 0, name: 'Master', volume: 1.0, pan: 0.0, peakDb: -0.8, mute: false, solo: false },
  { id: 1, name: 'Kick', volume: 0.85, pan: 0.0, peakDb: -0.4, mute: false, solo: false },
  { id: 2, name: 'Snare', volume: 0.72, pan: -0.1, peakDb: -1.8, mute: false, solo: false },
  { id: 3, name: 'Closed Hat', volume: 0.70, pan: 0.25, peakDb: -4.2, mute: false, solo: false },
  { id: 4, name: 'Open Hat', volume: 0.68, pan: 0.35, peakDb: -3.2, mute: false, solo: false },
];

const DEFAULT_PIANO_NOTES: PianoRollNoteVisual[] = [
  { id: 'n0', pitch: 38, pitchName: 'D1', startStep: 0, durationSteps: 1, velocity: 100, verified: true },
  { id: 'n2', pitch: 41, pitchName: 'F1', startStep: 2, durationSteps: 1, velocity: 92, verified: true },
  { id: 'n5', pitch: 43, pitchName: 'G1', startStep: 5, durationSteps: 1, velocity: 88, verified: true },
  { id: 'n7', pitch: 45, pitchName: 'A1', startStep: 7, durationSteps: 1, velocity: 105, verified: true },
];

const DEFAULT_WAVEFORM_POINTS = [
  0.18, 0.32, 0.45, 0.68, 0.52, 0.82, 0.70, 0.94,
  0.75, 0.88, 0.82, 0.65, 0.78, 0.85, 0.90, 0.72,
  0.58, 0.70, 0.84, 0.62, 0.48, 0.38, 0.24, 0.10,
];

export default function WorkstationVisual({
  visual,
  stepNumber,
  totalSteps,
  className = '',
}: WorkstationVisualProps): React.JSX.Element {
  const [activeTabOverride, setActiveTabOverride] = React.useState<'auto' | 'mixer' | 'pianoroll' | 'render'>('auto');

  // When activeTabOverride is 'auto', follow the step's native view
  const currentView = activeTabOverride === 'auto' ? visual.view : activeTabOverride;

  return (
    <div
      className={`border border-line bg-surface rounded-[2px] p-4 flex flex-col justify-between select-none shadow-xs text-ink font-mono text-xs ${className}`}
      data-testid="workstation-visual"
      aria-label="Abstract Audio Workstation Visualization"
    >
      {/* Workstation Top Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-3 border-b border-line">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-[1px] bg-signal animate-pulse" aria-hidden="true"></span>
          <span className="font-bold tracking-wider uppercase text-[11px] text-ink">
            ENGINE STATUS: {visual.view.toUpperCase()}
          </span>
          <span className="text-line-strong select-none">|</span>
          <span className="text-[10px] text-ink-muted tabular-nums">
            STEP {stepNumber + 1}/{totalSteps}
          </span>
        </div>

        {/* View Switcher Pills */}
        <div className="flex items-center gap-1 bg-bg p-0.5 border border-line rounded-[2px]">
          <button
            type="button"
            onClick={() => setActiveTabOverride('auto')}
            className={`px-2 py-0.5 text-[10px] font-semibold rounded-[1px] transition-colors focus-ring ${
              activeTabOverride === 'auto'
                ? 'bg-ink text-bg'
                : 'text-ink-muted hover:text-ink'
            }`}
            title="Auto-follow current step view"
          >
            AUTO
          </button>
          <button
            type="button"
            onClick={() => setActiveTabOverride('mixer')}
            className={`px-2 py-0.5 text-[10px] font-semibold rounded-[1px] transition-colors focus-ring ${
              currentView === 'mixer' && activeTabOverride !== 'auto'
                ? 'bg-ink text-bg'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            MIXER
          </button>
          <button
            type="button"
            onClick={() => setActiveTabOverride('pianoroll')}
            className={`px-2 py-0.5 text-[10px] font-semibold rounded-[1px] transition-colors focus-ring ${
              currentView === 'pianoroll' && activeTabOverride !== 'auto'
                ? 'bg-ink text-bg'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            ROLL
          </button>
          <button
            type="button"
            onClick={() => setActiveTabOverride('render')}
            className={`px-2 py-0.5 text-[10px] font-semibold rounded-[1px] transition-colors focus-ring ${
              currentView === 'render' && activeTabOverride !== 'auto'
                ? 'bg-ink text-bg'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            AUDIO
          </button>
        </div>
      </div>

      {/* Main Rack View */}
      <div className="flex-1 min-h-[340px] flex flex-col justify-center">
        {currentView === 'mixer' && (
          <MixerRack
            tracks={visual.mixer?.tracks || DEFAULT_MIXER_TRACKS}
            stepDescription={visual.description}
          />
        )}
        {currentView === 'pianoroll' && (
          <PianoRollRack
            notes={visual.pianoroll?.notes || DEFAULT_PIANO_NOTES}
            channelName={visual.pianoroll?.channelName || '3xOsc Bass'}
            patternNumber={visual.pianoroll?.patternNumber || 2}
            activeSteps={visual.pianoroll?.stepGridActiveSteps || [0, 2, 5, 7]}
            stepDescription={visual.description}
          />
        )}
        {currentView === 'render' && (
          <RenderRack
            renderData={
              visual.render || {
                jobId: 'rnd_88f2a1',
                status: 'idle',
                progressPct: 0,
                waveformPoints: DEFAULT_WAVEFORM_POINTS,
              }
            }
            stepDescription={visual.description}
          />
        )}
      </div>

      {/* Workstation Footer Note / Status Pill */}
      <div className="pt-3 mt-3 border-t border-line flex flex-wrap items-center justify-between gap-2 text-[10px] text-ink-muted">
        <div className="flex items-center gap-1.5 truncate max-w-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-ok" aria-hidden="true"></span>
          <span className="truncate">{visual.description}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 border border-line bg-bg rounded-[1px]">
            ORIGINAL ABSTRACT DAW
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. Abstract Mixer Rack Component
// ---------------------------------------------------------------------------
interface MixerRackProps {
  tracks: MixerTrackVisual[];
  stepDescription: string;
}

function MixerRack({ tracks }: MixerRackProps): React.JSX.Element {
  return (
    <div className="w-full h-full flex flex-col justify-between gap-3">
      <div className="flex items-center justify-between border-b border-line/60 pb-1.5 text-[10px] text-ink-muted">
        <span className="tracking-widest uppercase">MIXER STRIP ARRAY · 5 CHANNELS</span>
        <span className="tabular-nums">BUS PEAK TOLERANCE: ±0.0100</span>
      </div>

      {/* Grid of Mixer Channel Strips */}
      <div className="grid grid-cols-5 gap-2 sm:gap-3 py-1 flex-1">
        {tracks.map((track) => {
          const isMaster = track.id === 0;
          const isHot = track.clipping || track.peakDb > 0.0;
          // Volume fader position calculation (0.0 to 1.0)
          const faderTopPct = Math.max(0, Math.min(100, (1 - track.volume) * 100));

          // Peak meter segment counts (12 segments total)
          // dB mapping: -48 to +3 dB
          const normPeak = Math.max(0, Math.min(1, (track.peakDb + 48) / 51));
          const litSegments = Math.round(normPeak * 12);

          return (
            <div
              key={track.id}
              className={`flex flex-col items-center justify-between p-1.5 sm:p-2 border rounded-[2px] transition-all ${
                track.highlighted
                  ? 'border-signal bg-signal/5'
                  : 'border-line bg-bg/50'
              }`}
            >
              {/* Channel Header */}
              <div className="w-full text-center border-b border-line/40 pb-1">
                <div className="text-[9px] text-ink-muted uppercase truncate">
                  CH {track.id.toString().padStart(2, '0')}
                </div>
                <div
                  className={`text-[11px] font-bold truncate ${
                    isMaster ? 'text-signal' : 'text-ink'
                  }`}
                  title={track.name}
                >
                  {track.name}
                </div>
              </div>

              {/* Fader & Peak Meter Container */}
              <div className="flex items-center justify-center gap-1 sm:gap-2 my-2 h-44 sm:h-48 w-full">
                {/* Vertical Segmented Peak Meter */}
                <div
                  className="flex flex-col-reverse justify-between w-2 sm:w-2.5 h-full p-0.5 bg-bg border border-line rounded-[1px]"
                  title={`Peak: ${track.peakDb > 0 ? '+' : ''}${track.peakDb.toFixed(1)} dB`}
                >
                  {Array.from({ length: 12 }).map((_, idx) => {
                    const isLit = idx < litSegments;
                    const isClipSeg = idx >= 10;
                    const isWarnSeg = idx >= 8 && idx < 10;

                    let segColor = 'bg-line/20';
                    if (isLit) {
                      if (isClipSeg) segColor = 'bg-err';
                      else if (isWarnSeg) segColor = 'bg-warn';
                      else segColor = 'bg-ok';
                    }

                    return (
                      <div
                        key={idx}
                        className={`w-full h-1.5 sm:h-2 rounded-[0.5px] transition-colors duration-150 ${segColor}`}
                      />
                    );
                  })}
                </div>

                {/* Vertical Fader Track & Thumb */}
                <div className="relative w-4 sm:w-5 h-full flex items-center justify-center">
                  {/* Fader Slot Line */}
                  <div className="absolute top-1 bottom-1 w-1 bg-line-strong rounded-full"></div>

                  {/* Fader Thumb */}
                  <div
                    className={`absolute w-4 sm:w-5 h-6 sm:h-7 rounded-[1px] border shadow-xs flex items-center justify-center transition-all duration-200 ${
                      track.highlighted
                        ? 'bg-signal border-ink text-white'
                        : 'bg-surface border-line-strong text-ink'
                    }`}
                    style={{ top: `calc(${faderTopPct}% - 12px)` }}
                    aria-label={`${track.name} fader at ${(track.volume * 100).toFixed(0)}%`}
                  >
                    <div className="w-2.5 h-0.5 bg-line-strong"></div>
                  </div>
                </div>
              </div>

              {/* Pan & Flags */}
              <div className="w-full flex items-center justify-between text-[9px] gap-1 pt-1 border-t border-line/40">
                <span
                  className={`px-1 py-0.5 rounded-[1px] border font-bold ${
                    track.mute
                      ? 'bg-err text-white border-err'
                      : 'border-line text-ink-muted'
                  }`}
                >
                  M
                </span>
                <span
                  className={`tabular-nums text-[9px] ${
                    isHot ? 'text-err font-bold' : 'text-ink-muted'
                  }`}
                >
                  {track.peakDb > 0 ? `+${track.peakDb.toFixed(1)}` : track.peakDb.toFixed(1)}
                </span>
                <span
                  className={`px-1 py-0.5 rounded-[1px] border font-bold ${
                    track.solo
                      ? 'bg-signal text-white border-signal'
                      : 'border-line text-ink-muted'
                  }`}
                >
                  S
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. Abstract Piano Roll & Step Grid Component
// ---------------------------------------------------------------------------
interface PianoRollRackProps {
  notes: PianoRollNoteVisual[];
  channelName: string;
  patternNumber: number;
  activeSteps: number[];
  stepDescription: string;
}

const PITCH_LANES = [
  { pitch: 48, label: 'C2' },
  { pitch: 47, label: 'B1' },
  { pitch: 45, label: 'A1' },
  { pitch: 43, label: 'G1' },
  { pitch: 41, label: 'F1' },
  { pitch: 38, label: 'D1' },
  { pitch: 36, label: 'C1' },
];

function PianoRollRack({
  notes,
  channelName,
  patternNumber,
  activeSteps,
}: PianoRollRackProps): React.JSX.Element {
  return (
    <div className="w-full h-full flex flex-col justify-between gap-3">
      {/* Pattern Header */}
      <div className="flex items-center justify-between border-b border-line/60 pb-1.5 text-[10px] text-ink-muted">
        <div className="flex items-center gap-2">
          <span className="font-bold text-ink uppercase tracking-wider">{channelName}</span>
          <span className="text-line-strong select-none">&bull;</span>
          <span>PATTERN {patternNumber.toString().padStart(2, '0')}</span>
          <span className="text-line-strong select-none">&bull;</span>
          <span className="text-ok font-semibold">TIER 1 ACTUATION</span>
        </div>
        <div className="tabular-nums">16 STEPS · 96 PPQ · 4 BARS</div>
      </div>

      {/* Step Sequencer Trigger Row */}
      <div className="border border-line bg-bg p-1.5 rounded-[2px]">
        <div className="text-[9px] text-ink-muted mb-1 flex items-center justify-between">
          <span className="uppercase tracking-widest">STEP SEQUENCER TRIGGER BUS</span>
          <span className="text-ok font-semibold">ORACLE: VERIFIED</span>
        </div>
        <div
          className="grid gap-1"
          style={{ gridTemplateColumns: 'repeat(16, minmax(0, 1fr))' }}
        >
          {Array.from({ length: 16 }).map((_, stepIdx) => {
            const isActive = activeSteps.includes(stepIdx);
            const isQuarterBeat = stepIdx % 4 === 0;

            return (
              <div
                key={stepIdx}
                className={`h-4 sm:h-5 rounded-[1px] border flex items-center justify-center transition-all ${
                  isActive
                    ? 'bg-signal border-signal text-white font-bold'
                    : isQuarterBeat
                    ? 'bg-surface border-line-strong text-ink-muted'
                    : 'bg-surface/50 border-line text-ink-muted/50'
                }`}
                title={`Step ${stepIdx + 1} ${isActive ? '(Triggered)' : ''}`}
              >
                <span className="text-[8px] sm:text-[9px] tabular-nums">{stepIdx + 1}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Piano Roll Note Grid */}
      <div className="border border-line bg-bg rounded-[2px] overflow-hidden flex flex-col flex-1">
        <div className="text-[9px] px-2 py-1 bg-surface border-b border-line flex items-center justify-between text-ink-muted">
          <span>PITCH LANE MATRIX</span>
          <span>VELOCITY RANGE [78..110]</span>
        </div>

        <div className="flex-1 flex flex-col divide-y divide-line/40">
          {PITCH_LANES.map((lane) => {
            const laneNotes = notes.filter((n) => n.pitch === lane.pitch);

            return (
              <div key={lane.pitch} className="flex items-center h-5 sm:h-6 relative">
                {/* Pitch Label */}
                <div className="w-8 sm:w-10 h-full border-r border-line bg-surface flex items-center justify-center text-[9px] sm:text-[10px] font-bold text-ink shrink-0">
                  {lane.label}
                </div>

                {/* 16 Step Columns */}
                <div
                  className="flex-1 grid h-full relative divide-x divide-line/20"
                  style={{ gridTemplateColumns: 'repeat(16, minmax(0, 1fr))' }}
                >
                  {Array.from({ length: 16 }).map((_, sIdx) => {
                    const isBeat = sIdx % 4 === 0;
                    return (
                      <div
                        key={sIdx}
                        className={`h-full ${isBeat ? 'bg-surface/30' : ''}`}
                      />
                    );
                  })}

                  {/* Rendered Notes in this Lane */}
                  {laneNotes.map((note) => {
                    const leftPct = (note.startStep / 16) * 100;
                    const widthPct = (note.durationSteps / 16) * 100;

                    return (
                      <div
                        key={note.id}
                        className="absolute top-0.5 bottom-0.5 rounded-[1px] bg-signal border border-line-strong shadow-xs flex items-center justify-between px-1 text-[8px] text-white font-bold overflow-hidden transition-all duration-150 animate-fadeIn"
                        style={{
                          left: `calc(${leftPct}% + 1px)`,
                          width: `calc(${widthPct}% - 2px)`,
                        }}
                        title={`Note ${note.pitchName} @ Step ${note.startStep} (Vel: ${note.velocity})`}
                      >
                        <span className="truncate">{note.pitchName}</span>
                        <span className="opacity-80 text-[7px]">{note.velocity}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Abstract Render Supervisor & Acoustic Waveform Component
// ---------------------------------------------------------------------------
interface RenderRackProps {
  renderData: RenderVisual;
  stepDescription: string;
}

function RenderRack({ renderData }: RenderRackProps): React.JSX.Element {
  const isFinished = renderData.status === 'completed' || renderData.status === 'analyzed';
  const waveform = renderData.waveformPoints && renderData.waveformPoints.length > 0
    ? renderData.waveformPoints
    : DEFAULT_WAVEFORM_POINTS;

  return (
    <div className="w-full h-full flex flex-col justify-between gap-3">
      {/* Supervisor Telemetry Bar */}
      <div className="flex items-center justify-between border-b border-line/60 pb-1.5 text-[10px] text-ink-muted">
        <div className="flex items-center gap-2">
          <span className="font-bold text-ink uppercase tracking-wider">HEADLESS SUPERVISOR</span>
          <span className="text-line-strong select-none">&bull;</span>
          <span>FL64.exe (PID 18402)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-[1px] ${
              renderData.status === 'analyzed'
                ? 'bg-ok'
                : renderData.status === 'rendering'
                ? 'bg-signal animate-pulse'
                : 'bg-warn'
            }`}
          />
          <span className="font-bold uppercase tracking-wider text-ink">
            {renderData.status}
          </span>
        </div>
      </div>

      {/* Render Progress Bar */}
      <div className="border border-line bg-bg p-2 rounded-[2px]">
        <div className="flex items-center justify-between text-[10px] mb-1.5">
          <span className="text-ink-muted uppercase">JOB: {renderData.jobId} &rarr; output/preview.wav</span>
          <span className="font-bold tabular-nums text-ink">{renderData.progressPct}%</span>
        </div>
        <div className="w-full h-3 bg-surface border border-line rounded-[1px] overflow-hidden relative">
          <div
            className={`h-full transition-all duration-300 ${
              isFinished ? 'bg-ok' : 'bg-signal'
            }`}
            style={{ width: `${renderData.progressPct}%` }}
          />
        </div>
      </div>

      {/* Acoustic Waveform Envelope Display */}
      <div className="border border-line bg-bg rounded-[2px] p-2 flex flex-col flex-1">
        <div className="flex items-center justify-between text-[9px] text-ink-muted mb-1 border-b border-line/40 pb-1">
          <span className="uppercase tracking-widest">ACOUSTIC WAVEFORM ENVELOPE (L/R)</span>
          <span className="text-ok font-semibold">
            {renderData.status === 'analyzed' ? 'SPECTRUM GATE: PASSED' : 'ANALYZING...'}
          </span>
        </div>

        {/* Waveform Symmetrical Drawing */}
        <div className="flex-1 min-h-[100px] flex items-center justify-between gap-1 py-1">
          {waveform.map((height, idx) => {
            const hPct = Math.max(10, Math.min(100, height * 100));
            return (
              <div
                key={idx}
                className="flex-1 flex flex-col items-center justify-center h-full gap-0.5"
              >
                {/* Upper Channel Peak */}
                <div
                  className={`w-full rounded-[0.5px] transition-all duration-200 ${
                    isFinished ? 'bg-signal/80' : 'bg-line-strong'
                  }`}
                  style={{ height: `${hPct / 2}%` }}
                />
                {/* Center Baseline Dot */}
                <div className="w-0.5 h-0.5 bg-line-strong rounded-full" />
                {/* Lower Channel Peak (symmetric) */}
                <div
                  className={`w-full rounded-[0.5px] transition-all duration-200 ${
                    isFinished ? 'bg-signal/80' : 'bg-line-strong'
                  }`}
                  style={{ height: `${hPct / 2}%` }}
                />
              </div>
            );
          })}
        </div>

        {/* Audio Quality Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 pt-1.5 border-t border-line/40 text-[9px]">
          <div className="bg-surface p-1 border border-line/50 rounded-[1px]">
            <div className="text-ink-muted">DURATION</div>
            <div className="font-bold text-ink tabular-nums">
              {renderData.durationS ? `${renderData.durationS.toFixed(1)}s` : '16.0s'}
            </div>
          </div>
          <div className="bg-surface p-1 border border-line/50 rounded-[1px]">
            <div className="text-ink-muted">TRUE PEAK</div>
            <div className="font-bold text-ink tabular-nums">
              {renderData.peakDbfs ? `${renderData.peakDbfs.toFixed(1)} dBFS` : '-0.4 dBFS'}
            </div>
          </div>
          <div className="bg-surface p-1 border border-line/50 rounded-[1px]">
            <div className="text-ink-muted">INTEGRATED RMS</div>
            <div className="font-bold text-ink tabular-nums">
              {renderData.rmsDbfs ? `${renderData.rmsDbfs.toFixed(1)} dBFS` : '-12.8 dBFS'}
            </div>
          </div>
          <div className="bg-surface p-1 border border-line/50 rounded-[1px]">
            <div className="text-ink-muted">CLIPPED SAMPLES</div>
            <div className="font-bold text-ok tabular-nums">0 (0.00%)</div>
          </div>
        </div>
      </div>
    </div>
  );
}
