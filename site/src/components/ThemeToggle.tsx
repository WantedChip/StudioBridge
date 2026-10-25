import React, { useEffect, useState, useRef, useCallback } from 'react';

export type ThemeChoice = 'light' | 'system' | 'dark';

interface ThemeOption {
  value: ThemeChoice;
  label: string;
  icon: (props: { className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }) => React.JSX.Element;
}

function SunIcon({ className, 'aria-hidden': ariaHidden = true }: { className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={ariaHidden}
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </svg>
  );
}

function MonitorIcon({ className, 'aria-hidden': ariaHidden = true }: { className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={ariaHidden}
    >
      <rect width="20" height="14" x="2" y="3" rx="2" />
      <line x1="8" x2="16" y1="21" y2="21" />
      <line x1="12" x2="12" y1="17" y2="21" />
    </svg>
  );
}

function MoonIcon({ className, 'aria-hidden': ariaHidden = true }: { className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={ariaHidden}
    >
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  );
}

const THEME_OPTIONS: readonly ThemeOption[] = [
  { value: 'light', label: 'Light', icon: SunIcon },
  { value: 'system', label: 'System', icon: MonitorIcon },
  { value: 'dark', label: 'Dark', icon: MoonIcon },
] as const;

function getStoredTheme(): ThemeChoice {
  if (typeof window === 'undefined') return 'system';
  try {
    const val = localStorage.getItem('sb-theme');
    if (val === 'light' || val === 'dark' || val === 'system') {
      return val;
    }
  } catch {
    // localStorage may be disabled or inaccessible in private browsing
  }
  return 'system';
}

function applyThemeToDocument(theme: ThemeChoice) {
  if (typeof document === 'undefined') return;
  if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
}

export function ThemeToggle(): React.JSX.Element {
  const [theme, setTheme] = useState<ThemeChoice>('system');
  const [mounted, setMounted] = useState(false);
  const buttonRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const selectTheme = useCallback((newTheme: ThemeChoice) => {
    setTheme(newTheme);
    applyThemeToDocument(newTheme);
    try {
      localStorage.setItem('sb-theme', newTheme);
    } catch {
      // Ignore localStorage write failures
    }
    window.dispatchEvent(
      new CustomEvent('sb-theme-change', { detail: { theme: newTheme } })
    );
  }, []);

  // Initialize theme from localStorage on mount and listen to system/storage events
  useEffect(() => {
    setMounted(true);
    const initial = getStoredTheme();
    setTheme(initial);
    applyThemeToDocument(initial);

    // [THM-04] Live listener for system dark/light preference changes
    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const handleSystemChange = () => {
      const current = getStoredTheme();
      if (current === 'system') {
        // Under system theme, data-theme attribute remains absent,
        // but dispatch event to re-notify any dependent listeners.
        window.dispatchEvent(
          new CustomEvent('sb-theme-change', { detail: { theme: 'system' } })
        );
      }
    };

    // Cross-tab synchronization
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'sb-theme') {
        const val = getStoredTheme();
        setTheme(val);
        applyThemeToDocument(val);
      }
    };

    mql.addEventListener('change', handleSystemChange);
    window.addEventListener('storage', handleStorageChange);

    return () => {
      mql.removeEventListener('change', handleSystemChange);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
    let targetIndex = -1;

    switch (e.key) {
      case 'ArrowLeft':
      case 'ArrowUp':
        e.preventDefault();
        targetIndex = (currentIndex - 1 + THEME_OPTIONS.length) % THEME_OPTIONS.length;
        break;
      case 'ArrowRight':
      case 'ArrowDown':
        e.preventDefault();
        targetIndex = (currentIndex + 1) % THEME_OPTIONS.length;
        break;
      case 'Home':
        e.preventDefault();
        targetIndex = 0;
        break;
      case 'End':
        e.preventDefault();
        targetIndex = THEME_OPTIONS.length - 1;
        break;
      case ' ':
      case 'Enter':
        e.preventDefault();
        selectTheme(THEME_OPTIONS[currentIndex].value);
        return;
      default:
        return;
    }

    if (targetIndex >= 0) {
      const targetOption = THEME_OPTIONS[targetIndex];
      selectTheme(targetOption.value);
      buttonRefs.current[targetIndex]?.focus();
    }
  };

  const activeTheme = mounted ? theme : 'system';

  return (
    <div
      role="radiogroup"
      aria-label="Color theme"
      className="inline-flex items-center p-0.5 rounded-[2px] bg-surface border border-line"
    >
      {THEME_OPTIONS.map((option, idx) => {
        const isChecked = activeTheme === option.value;
        const Icon = option.icon;

        return (
          <button
            key={option.value}
            ref={(el) => {
              buttonRefs.current[idx] = el;
            }}
            type="button"
            role="radio"
            aria-checked={isChecked}
            aria-label={`${option.label} theme`}
            tabIndex={isChecked ? 0 : -1}
            onClick={() => selectTheme(option.value)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            className={`group inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono tracking-tight transition-colors rounded-[1px] select-none cursor-pointer ${
              isChecked
                ? 'bg-bg text-ink border border-line-strong font-medium shadow-xs'
                : 'text-ink-muted hover:text-ink hover:bg-bg/40 border border-transparent'
            } focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2`}
          >
            <Icon className="w-3.5 h-3.5 shrink-0 opacity-80 group-hover:opacity-100" />
            <span>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export default ThemeToggle;
