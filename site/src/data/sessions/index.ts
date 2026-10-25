import balanceDrums from './balance-drums.json';
import addBassline from './add-bassline.json';
import renderPreview from './render-preview.json';

export interface MixerTrackVisual {
  id: number;
  name: string;
  volume: number; // 0.0 - 1.0
  pan: number; // -1.0 to 1.0
  peakDb: number;
  mute: boolean;
  solo: boolean;
  clipping?: boolean;
  highlighted?: boolean;
}

export interface PianoRollNoteVisual {
  id: string;
  pitch: number;
  pitchName: string;
  startStep: number;
  durationSteps: number;
  velocity: number;
  verified?: boolean;
}

export interface RenderVisual {
  jobId: string;
  status: 'idle' | 'starting' | 'rendering' | 'completed' | 'analyzed';
  progressPct: number;
  durationS?: number;
  peakDbfs?: number;
  rmsDbfs?: number;
  silenceRatio?: number;
  waveformPoints?: number[];
}

export interface SessionStepVisual {
  view: 'mixer' | 'pianoroll' | 'render';
  description: string;
  mixer?: {
    tracks: MixerTrackVisual[];
  };
  pianoroll?: {
    channelName: string;
    patternNumber: number;
    notes: PianoRollNoteVisual[];
    stepGridActiveSteps?: number[];
  };
  render?: RenderVisual;
}

export interface SessionStep {
  stepNumber: number;
  role: 'user' | 'agent' | 'tool';
  text?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result?: Record<string, unknown> | string;
  verified?: boolean;
  journalId?: number;
  visual: SessionStepVisual;
}

export interface ScriptedSession {
  id: string;
  title: string;
  tabLabel: string;
  summary: string;
  source: 'emulator' | 'live';
  environmentLabel: string;
  recordedAt: string;
  fl: {
    build: string;
    arch: string;
  };
  steps: SessionStep[];
}

export const SESSIONS: ScriptedSession[] = [
  balanceDrums as unknown as ScriptedSession,
  addBassline as unknown as ScriptedSession,
  renderPreview as unknown as ScriptedSession,
];

export function getSession(id: string): ScriptedSession {
  const found = SESSIONS.find((s) => s.id === id);
  return found || SESSIONS[0];
}
