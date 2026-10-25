import React, { useState, useEffect, useRef, useCallback } from 'react';

export interface CopyButtonProps {
  /** The text string to copy to the clipboard */
  text: string;
  /** Label displayed in default idle state (default: "COPY") */
  label?: string;
  /** Label displayed in success state (default: "COPIED") */
  copiedLabel?: string;
  /** Accessible aria-label for screen readers */
  ariaLabel?: string;
  /** Additional CSS class names */
  className?: string;
  /** Whether to show the icon alongside the label */
  showIcon?: boolean;
}

/**
 * Interactive React component with clipboard write, visual feedback,
 * accessible keyboard support, and fallback copy mechanism.
 */
export default function CopyButton({
  text,
  label = 'COPY',
  copiedLabel = 'COPIED',
  ariaLabel,
  className = '',
  showIcon = true,
}: CopyButtonProps): React.JSX.Element {
  const [copied, setCopied] = useState<boolean>(false);
  const [hasError, setHasError] = useState<boolean>(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const handleCopy = useCallback(async () => {
    let success = false;

    // Primary: Modern Async Clipboard API
    if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        success = true;
      } catch {
        // Fall back to execCommand if permission denied or blocked
        success = false;
      }
    }

    // Fallback: document.execCommand('copy') via temporary textarea
    if (!success && typeof document !== 'undefined') {
      try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        textarea.style.top = '-9999px';
        textarea.setAttribute('readonly', '');
        textarea.setAttribute('aria-hidden', 'true');
        document.body.appendChild(textarea);
        textarea.select();
        const doc = document as unknown as { execCommand?: (cmd: string) => boolean };
        success = typeof doc.execCommand === 'function' ? doc.execCommand('copy') : false;
        document.body.removeChild(textarea);
      } catch {
        success = false;
      }
    }

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    if (success) {
      setCopied(true);
      setHasError(false);
      timeoutRef.current = setTimeout(() => {
        setCopied(false);
      }, 2000);
    } else {
      setHasError(true);
      timeoutRef.current = setTimeout(() => {
        setHasError(false);
      }, 2500);
    }
  }, [text]);

  const buttonAriaLabel = ariaLabel
    ? ariaLabel
    : copied
      ? 'Copied to clipboard'
      : hasError
        ? 'Failed to copy to clipboard'
        : `Copy command: ${text}`;

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={buttonAriaLabel}
      title={copied ? 'Copied!' : hasError ? 'Copy failed' : 'Copy to clipboard'}
      className={`relative inline-flex items-center gap-1.5 px-2.5 py-1 font-mono text-xs font-semibold uppercase tracking-wider rounded-[2px] border transition-colors cursor-pointer select-none focus-ring ${
        copied
          ? 'border-ok/50 bg-ok/10 text-ok'
          : hasError
            ? 'border-err/50 bg-err/10 text-err'
            : 'border-line hover:border-line-strong bg-bg hover:bg-surface text-ink-muted hover:text-ink'
      } ${className}`}
    >
      {showIcon && (
        <span className="shrink-0" aria-hidden="true">
          {copied ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-3.5 h-3.5 text-ok"
            >
              <polyline points="3 8.5 6.5 12 13 4" />
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-3.5 h-3.5"
            >
              <rect width="9" height="11" x="5" y="3" rx="1" />
              <path d="M3 11V3a1 1 0 0 1 1-1h7" />
            </svg>
          )}
        </span>
      )}
      <span aria-live="polite">{copied ? copiedLabel : hasError ? 'FAILED' : label}</span>
    </button>
  );
}
