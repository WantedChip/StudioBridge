import React, { useState, useEffect, useRef, useCallback } from 'react';
import { SESSIONS, type ScriptedSession, type SessionStep } from '../../data/sessions/index.ts';
import WorkstationVisual from '../workstation/WorkstationVisual.tsx';

export default function ConsoleDemo(): React.JSX.Element {
  const [activeSessionId, setActiveSessionId] = useState<string>('balance-drums');
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [speed, setSpeed] = useState<1 | 2>(1);
  const [transcriptOnly, setTranscriptOnly] = useState<boolean>(false);
  const [userPaused, setUserPaused] = useState<boolean>(false);

  const activeSession: ScriptedSession =
    SESSIONS.find((s) => s.id === activeSessionId) || SESSIONS[0];
  const totalSteps = activeSession.steps.length;
  const currentStep: SessionStep = activeSession.steps[currentStepIndex] || activeSession.steps[0];

  const containerRef = useRef<HTMLDivElement>(null);
  const transcriptScrollRef = useRef<HTMLDivElement>(null);
  const activeStepElementRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  // Check prefers-reduced-motion
  const prefersReducedMotion = useCallback(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }, []);

  // IntersectionObserver for playing only when visible on screen
  useEffect(() => {
    if (prefersReducedMotion() || userPaused) return;

    const el = containerRef.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting) {
          if (!userPaused) setIsPlaying(true);
        } else {
          setIsPlaying(false);
        }
      },
      { threshold: 0.3 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [prefersReducedMotion, userPaused]);

  // Interval timer for playback progression
  useEffect(() => {
    if (!isPlaying) return;

    const intervalMs = speed === 2 ? 1400 : 2800;
    const timer = setInterval(() => {
      setCurrentStepIndex((prev) => {
        if (prev + 1 >= totalSteps) {
          // Loop seamlessly after showing last step
          return 0;
        }
        return prev + 1;
      });
    }, intervalMs);

    return () => clearInterval(timer);
  }, [isPlaying, speed, totalSteps]);

  // Auto-scroll transcript container to the current active step
  useEffect(() => {
    if (activeStepElementRef.current) {
      activeStepElementRef.current.scrollIntoView({
        behavior: prefersReducedMotion() ? 'auto' : 'smooth',
        block: 'nearest',
      });
    }
  }, [currentStepIndex, prefersReducedMotion]);

  // Switch session handler
  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId);
    setCurrentStepIndex(0);
  };

  // Keyboard navigation across tabs
  const handleTabKeyDown = (
    e: React.KeyboardEvent<HTMLButtonElement>,
    currentIndex: number
  ) => {
    let nextIndex = currentIndex;
    const count = SESSIONS.length;

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

    const targetSession = SESSIONS[nextIndex];
    if (targetSession) {
      handleSelectSession(targetSession.id);
      const btn = tabRefs.current.get(targetSession.id);
      if (btn) btn.focus();
    }
  };

  // Global Island Keyboard shortcuts (Space = Play/Pause, ArrowRight = Step, ArrowLeft = Back)
  const handleContainerKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    // Ignore keystrokes inside input / textarea
    const targetTag = (e.target as HTMLElement)?.tagName?.toLowerCase();
    if (targetTag === 'input' || targetTag === 'textarea') return;

    if (e.code === 'Space') {
      // Prevent page scrolling on space
      e.preventDefault();
      setIsPlaying((prev) => {
        const next = !prev;
        if (!next) setUserPaused(true);
        return next;
      });
    } else if (e.key === 'ArrowRight') {
      // Step forward
      e.preventDefault();
      setIsPlaying(false);
      setUserPaused(true);
      setCurrentStepIndex((prev) => (prev + 1) % totalSteps);
    } else if (e.key === 'ArrowLeft') {
      // Step backward
      e.preventDefault();
      setIsPlaying(false);
      setUserPaused(true);
      setCurrentStepIndex((prev) => (prev - 1 + totalSteps) % totalSteps);
    }
  };

  const handlePlayToggle = () => {
    setIsPlaying((prev) => {
      const next = !prev;
      if (!next) setUserPaused(true);
      return next;
    });
  };

  const handleStepForward = () => {
    setIsPlaying(false);
    setUserPaused(true);
    setCurrentStepIndex((prev) => (prev + 1) % totalSteps);
  };

  const handleReset = () => {
    setIsPlaying(false);
    setUserPaused(true);
    setCurrentStepIndex(0);
  };

  return (
    <section
      id="session-demo"
      ref={containerRef}
      onKeyDown={handleContainerKeyDown}
      tabIndex={0}
      aria-label="02 / TRY A SESSION Interactive Console Demo"
      className="border-b border-line py-16 px-4 sm:px-6 lg:px-8 bg-bg relative focus:outline-hidden"
    >
      {/* Live Region for Screen Reader Announcements */}
      <div className="sr-only" aria-live="polite">
        {`Displaying step ${currentStepIndex + 1} of ${totalSteps} in session ${
          activeSession.title
        }. ${
          currentStep.role === 'user'
            ? `User prompt: ${currentStep.text}`
            : currentStep.role === 'tool'
            ? `Tool call: ${currentStep.tool}`
            : `Agent reply: ${currentStep.text}`
        }`}
      </div>

      <div className="max-w-7xl mx-auto">
        {/* Section Header */}
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 border border-line rounded-[1px] bg-surface mb-3 font-mono text-[11px] text-ink-muted">
              <span className="w-2 h-2 rounded-[1px] bg-signal inline-block" aria-hidden="true"></span>
              <span className="font-semibold text-ink uppercase tracking-wider">
                02 / TRY A SESSION
              </span>
              <span className="text-line-strong select-none">|</span>
              <span>SYNCHRONIZED AUDIT PLAYBACK</span>
            </div>
            <h2 className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight text-ink">
              See the bridge in action.
            </h2>
          </div>
          <p className="font-sans text-sm text-ink-muted max-w-md">
            Side-by-side agent session replay: terminal MCP tool calls paired with an original, abstract audio workstation reacting step-by-step.
          </p>
        </div>

        {/* Session Switcher Tabs */}
        <div className="border border-line bg-surface rounded-[2px] p-2 mb-6">
          <div
            role="tablist"
            aria-label="Recorded agent sessions"
            className="flex flex-wrap items-center gap-2"
          >
            {SESSIONS.map((session, idx) => {
              const isSelected = session.id === activeSessionId;
              return (
                <button
                  key={session.id}
                  id={`tab-${session.id}`}
                  role="tab"
                  aria-selected={isSelected}
                  aria-controls={`panel-${session.id}`}
                  tabIndex={isSelected ? 0 : -1}
                  ref={(el) => {
                    if (el) tabRefs.current.set(session.id, el);
                    else tabRefs.current.delete(session.id);
                  }}
                  onClick={() => handleSelectSession(session.id)}
                  onKeyDown={(e) => handleTabKeyDown(e, idx)}
                  className={`px-3 py-2 rounded-[1px] font-mono text-xs font-semibold transition-all flex items-center gap-2 focus-ring ${
                    isSelected
                      ? 'bg-ink text-bg shadow-xs'
                      : 'bg-bg text-ink-muted hover:text-ink hover:bg-surface border border-line'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isSelected ? 'bg-signal' : 'bg-line-strong'
                    }`}
                    aria-hidden="true"
                  />
                  <span>{session.tabLabel}</span>
                  <span className="opacity-70 text-[10px] hidden sm:inline-block">
                    ({session.steps.length} steps)
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Session Metadata & Provenance Banner */}
        <div className="border border-line bg-surface/50 rounded-[2px] px-4 py-2.5 mb-6 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-1.5 font-bold text-ink">
              <span className="w-2 h-2 rounded-[1px] bg-ok" aria-hidden="true"></span>
              {activeSession.environmentLabel}
            </span>
            <span className="text-line-strong select-none">&bull;</span>
            <span className="text-ink-muted tabular-nums">Date: {activeSession.recordedAt}</span>
            <span className="text-line-strong select-none">&bull;</span>
            <span className="text-ink-muted">FL {activeSession.fl.build} / {activeSession.fl.arch}</span>
          </div>

          <div className="flex items-center gap-2 text-ink-muted text-[11px]">
            <span className="w-1.5 h-1.5 rounded-full bg-signal" aria-hidden="true"></span>
            <span>Zero proprietary FL Studio UI or logos</span>
          </div>
        </div>

        {/* Player Controls Bar */}
        <div className="border border-line bg-surface rounded-[2px] p-3 mb-6 flex flex-wrap items-center justify-between gap-4 shadow-xs">
          {/* Left: Playback Controls */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Play / Pause Button */}
            <button
              type="button"
              onClick={handlePlayToggle}
              aria-label={isPlaying ? 'Pause session playback' : 'Play session playback'}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-ink text-bg rounded-[1px] font-mono text-xs font-bold hover:opacity-90 transition-opacity focus-ring"
            >
              {isPlaying ? (
                <>
                  <span aria-hidden="true">&bdquo;&bdquo;</span>
                  <span>PAUSE</span>
                </>
              ) : (
                <>
                  <span aria-hidden="true">&#9654;</span>
                  <span>PLAY</span>
                </>
              )}
            </button>

            {/* Step Forward Button */}
            <button
              type="button"
              onClick={handleStepForward}
              aria-label="Step forward to next transcript step"
              className="inline-flex items-center gap-1 px-3 py-1.5 border border-line-strong text-ink rounded-[1px] font-mono text-xs font-medium hover:bg-bg transition-colors focus-ring"
            >
              <span>STEP</span>
              <span aria-hidden="true">&rarr;</span>
            </button>

            {/* Reset Button */}
            <button
              type="button"
              onClick={handleReset}
              aria-label="Reset session to step 1"
              className="inline-flex items-center gap-1 px-3 py-1.5 border border-line text-ink-muted hover:text-ink rounded-[1px] font-mono text-xs transition-colors focus-ring"
            >
              <span>RESET</span>
              <span aria-hidden="true">&#8635;</span>
            </button>

            {/* Step Counter Indicator */}
            <div className="font-mono text-xs text-ink-muted px-2 py-1 bg-bg border border-line rounded-[1px] tabular-nums">
              STEP <strong className="text-ink">{currentStepIndex + 1}</strong> / {totalSteps}
            </div>
          </div>

          {/* Right: Playback Options (Speed, Transcript Only) */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Speed Toggle */}
            <div className="flex items-center gap-1 bg-bg p-1 border border-line rounded-[1px]">
              <span className="font-mono text-[10px] text-ink-muted px-1 uppercase">SPEED:</span>
              <button
                type="button"
                onClick={() => setSpeed(1)}
                className={`px-2 py-0.5 font-mono text-xs rounded-[1px] font-semibold transition-colors focus-ring ${
                  speed === 1 ? 'bg-ink text-bg' : 'text-ink-muted hover:text-ink'
                }`}
              >
                1x
              </button>
              <button
                type="button"
                onClick={() => setSpeed(2)}
                className={`px-2 py-0.5 font-mono text-xs rounded-[1px] font-semibold transition-colors focus-ring ${
                  speed === 2 ? 'bg-ink text-bg' : 'text-ink-muted hover:text-ink'
                }`}
              >
                2x
              </button>
            </div>

            {/* Transcript Only Mode Toggle */}
            <button
              type="button"
              onClick={() => setTranscriptOnly((prev) => !prev)}
              aria-pressed={transcriptOnly}
              className={`px-3 py-1.5 border rounded-[1px] font-mono text-xs font-medium transition-colors focus-ring ${
                transcriptOnly
                  ? 'bg-signal text-white border-signal'
                  : 'bg-surface border-line text-ink-muted hover:text-ink hover:bg-bg'
              }`}
            >
              {transcriptOnly ? 'TRANSCRIPT ONLY (ON)' : 'TRANSCRIPT ONLY'}
            </button>
          </div>
        </div>

        {/* Main Side-by-Side Console & Workstation Workspace */}
        <div
          id={`panel-${activeSession.id}`}
          role="tabpanel"
          aria-labelledby={`tab-${activeSession.id}`}
          className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch"
        >
          {/* Left Pane: Terminal Transcript */}
          <div
            className={`flex flex-col transition-all ${
              transcriptOnly ? 'lg:col-span-12' : 'lg:col-span-7'
            }`}
          >
            <div className="border border-line bg-surface rounded-[2px] flex flex-col h-full shadow-xs overflow-hidden">
              {/* Terminal Window Header Bar */}
              <div className="border-b border-line bg-bg px-4 py-2.5 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5" aria-hidden="true">
                    <span className="w-2.5 h-2.5 rounded-full bg-line-strong inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-line-strong inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-line-strong inline-block" />
                  </div>
                  <span className="font-mono text-xs font-semibold text-ink ml-2">
                    session://{activeSession.id}.transcript
                  </span>
                </div>
                <div className="flex items-center gap-2 font-mono text-[10px] text-ink-muted">
                  <span className="w-1.5 h-1.5 rounded-full bg-ok" aria-hidden="true"></span>
                  <span>MCP RUNTIME READY</span>
                </div>
              </div>

              {/* Terminal Scrollable Message Stream */}
              <div
                ref={transcriptScrollRef}
                tabIndex={0}
                aria-label="Agent session transcript log"
                className="p-4 overflow-y-auto max-h-[520px] min-h-[460px] flex flex-col gap-4 focus:outline-hidden"
              >
                {activeSession.steps.map((step, idx) => {
                  const isActive = idx === currentStepIndex;
                  const isPast = idx < currentStepIndex;

                  return (
                    <div
                      key={step.stepNumber}
                      ref={isActive ? activeStepElementRef : null}
                      onClick={() => {
                        setIsPlaying(false);
                        setUserPaused(true);
                        setCurrentStepIndex(idx);
                      }}
                      className={`cursor-pointer rounded-[2px] p-3 border font-mono text-xs transition-all ${
                        isActive
                          ? 'border-signal bg-bg shadow-xs ring-1 ring-signal'
                          : isPast
                          ? 'border-line/70 bg-surface/50 opacity-90 hover:opacity-100 hover:border-line-strong'
                          : 'border-line/40 bg-surface/20 opacity-50 hover:opacity-80'
                      }`}
                    >
                      {/* Step Header */}
                      <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-line/40">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isActive ? 'bg-signal animate-ping' : 'bg-line-strong'
                            }`}
                            aria-hidden="true"
                          />
                          <span className="font-bold uppercase tracking-wider text-[10px] text-ink">
                            STEP {idx + 1} // {step.role.toUpperCase()}
                          </span>
                        </div>
                        {isActive && (
                          <span className="text-[10px] font-bold text-signal uppercase tracking-wider">
                            ACTIVE
                          </span>
                        )}
                      </div>

                      {/* Content by Step Role */}
                      {step.role === 'user' && (
                        <div className="text-ink leading-relaxed">
                          <span className="text-signal font-bold select-none mr-2">&gt;</span>
                          <span>{step.text}</span>
                        </div>
                      )}

                      {step.role === 'tool' && (
                        <div className="flex flex-col gap-2">
                          {/* Tool Name Callout */}
                          <div className="flex items-center justify-between bg-bg p-2 border border-line rounded-[1px]">
                            <span className="text-ink font-bold">
                              mcp_call: <span className="text-signal">{step.tool}</span>
                            </span>
                            {step.verified && (
                              <span className="text-[10px] text-ok font-semibold border border-ok/40 px-1 rounded-[1px]">
                                VERIFIED
                              </span>
                            )}
                          </div>

                          {/* Tool Arguments */}
                          {step.args && (
                            <div className="text-[11px] bg-bg/80 p-2 border border-line/60 rounded-[1px] overflow-x-auto text-ink-muted">
                              <div className="text-[9px] uppercase tracking-wider text-ink font-semibold mb-1">
                                ARGS:
                              </div>
                              <pre className="font-mono text-[11px] whitespace-pre-wrap">
                                {JSON.stringify(step.args, null, 2)}
                              </pre>
                            </div>
                          )}

                          {/* Tool Result Receipt */}
                          {step.result && (
                            <div className="text-[11px] bg-surface p-2 border border-line rounded-[1px] overflow-x-auto">
                              <div className="text-[9px] uppercase tracking-wider text-ok font-semibold mb-1 flex items-center justify-between">
                                <span>RECEIPT / MUTATION JOURNAL:</span>
                                {step.journalId && (
                                  <span className="text-ink font-bold">#{step.journalId}</span>
                                )}
                              </div>
                              <pre className="font-mono text-[11px] text-ink whitespace-pre-wrap">
                                {typeof step.result === 'string'
                                  ? step.result
                                  : JSON.stringify(step.result, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}

                      {step.role === 'agent' && (
                        <div className="flex flex-col gap-2">
                          <div className="text-ink leading-relaxed font-sans text-sm">
                            {step.text}
                          </div>
                          <div className="flex items-center gap-2 pt-1 border-t border-line/40 text-[10px] text-ok font-semibold">
                            <span className="w-1.5 h-1.5 rounded-full bg-ok" aria-hidden="true"></span>
                            <span>OPERATION COMPLETED &amp; REVERSIBLE CHECKPOINT CREATED</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Terminal Footer Navigation Help */}
              <div className="border-t border-line bg-bg px-4 py-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-ink-muted font-mono">
                <span>Keyboard: [Space] Play/Pause &bull; [&rarr;] Step &bull; [&larr;] Back</span>
                <span className="text-ink font-semibold">
                  MUTATION GUARANTEE: G1 VERIFIED
                </span>
              </div>
            </div>
          </div>

          {/* Right Pane: Workstation Visual (Original Abstract DAW) */}
          {!transcriptOnly && (
            <div className="lg:col-span-5 flex flex-col">
              <WorkstationVisual
                visual={currentStep.visual}
                stepNumber={currentStepIndex}
                totalSteps={totalSteps}
                className="h-full min-h-[460px]"
              />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
