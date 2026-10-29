#!/usr/bin/env node
/**
 * StudioBridge npm launcher shim.
 *
 * Dispatches command invocation to the underlying StudioBridge Python distribution
 * via uvx, pipx, or a local Python runtime.
 *
 * Requirements: [NPM-01], [NPM-02], [REG-01].
 *
 * CRITICAL STDIO DISCIPLINE:
 * Under NO circumstances may this launcher print anything to stdout.
 * Stdout is reserved strictly for MCP JSON-RPC protocol frames.
 * All logs, banners, diagnostic messages, or errors MUST go strictly to stderr.
 */

'use strict';

const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const process = require('node:process');

const DIST = 'studiobridge';
const PINNED_VERSION = '0.1.0';
const SPEC = `${DIST}==${PINNED_VERSION}`;

/**
 * Locate executable on PATH with platform-specific extension resolution.
 *
 * @param {string} cmd Base command name without extension (e.g. 'uvx', 'python')
 * @returns {string | null} Absolute path to executable if found, null otherwise.
 */
function findOnPath(cmd) {
  if (path.isAbsolute(cmd)) {
    try {
      if (fs.existsSync(cmd)) return cmd;
    } catch {
      return null;
    }
  }

  const pathEnv = process.env.PATH || '';
  const entries = pathEnv.split(path.delimiter);
  const isWindows = process.platform === 'win32';

  let extensions = [''];
  if (isWindows) {
    const pathext = process.env.PATHEXT || '.COM;.EXE;.BAT;.CMD';
    extensions = pathext.split(';').map((ext) => ext.toLowerCase());
    if (!extensions.includes('')) {
      extensions.push('');
    }
  }

  for (const entry of entries) {
    if (!entry) continue;
    for (const ext of extensions) {
      const candidate = path.join(
        entry,
        isWindows && !cmd.toLowerCase().endsWith(ext) ? `${cmd}${ext}` : cmd
      );
      try {
        const stat = fs.statSync(candidate);
        if (stat.isFile()) {
          if (!isWindows) {
            try {
              fs.accessSync(candidate, fs.constants.X_OK);
              return candidate;
            } catch {
              continue;
            }
          }
          return candidate;
        }
      } catch {
        // File does not exist or inaccessible, continue searching
      }
    }
  }

  return null;
}

/**
 * Tokenize a command line string into an array of arguments, respecting quotes.
 *
 * @param {string} cmdLine
 * @returns {string[]}
 */
function tokenizeArgs(cmdLine) {
  const result = [];
  let current = '';
  let inDouble = false;
  let inSingle = false;

  for (let i = 0; i < cmdLine.length; i++) {
    const ch = cmdLine[i];
    if (ch === '"' && !inSingle) {
      inDouble = !inDouble;
    } else if (ch === "'" && !inDouble) {
      inSingle = !inSingle;
    } else if (/\s/.test(ch) && !inDouble && !inSingle) {
      if (current.length > 0) {
        result.push(current);
        current = '';
      }
    } else {
      current += ch;
    }
  }
  if (current.length > 0) {
    result.push(current);
  }
  return result;
}

/**
 * Execute child process forwarding stdio unchanged and exiting with matching code.
 *
 * @param {string} executable
 * @param {string[]} args
 */
function runChild(executable, args) {
  const child = spawn(executable, args, {
    stdio: 'inherit',
    windowsHide: true,
    shell: false,
  });

  child.on('error', (err) => {
    process.stderr.write(
      `[studiobridge-launcher] Failed to start process '${executable}': ${err.message}\n`
    );
    process.exit(1);
  });

  child.on('close', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
    } else {
      process.exit(code ?? 0);
    }
  });
}

/**
 * Main launcher entry point.
 */
function main() {
  const invokedBase = path.basename(
    process.argv[1] || '',
    path.extname(process.argv[1] || '')
  );
  const rawArgs = process.argv.slice(2);

  // If invoked as studiobridge-mcp and 'mcp' is not the first argument, prepend it.
  const isMcpAlias = invokedBase === 'studiobridge-mcp';
  const effectiveArgs =
    isMcpAlias && rawArgs[0] !== 'mcp' ? ['mcp', ...rawArgs] : rawArgs;

  // 1. Check custom override env SBRIDGE_PY_CMD
  if (process.env.SBRIDGE_PY_CMD) {
    const rawCmd = process.env.SBRIDGE_PY_CMD.trim();
    const parts = tokenizeArgs(rawCmd);
    const baseExec = parts[0] || 'python';
    const extraArgs = parts.slice(1);
    const resolved = findOnPath(baseExec) || baseExec;
    runChild(resolved, [...extraArgs, ...effectiveArgs]);
    return;
  }

  // 2. Prefer uvx (Astral uv runner)
  const uvxPath = findOnPath('uvx');
  if (uvxPath) {
    runChild(uvxPath, ['--from', SPEC, 'sbridge', ...effectiveArgs]);
    return;
  }

  // 3. Fallback to pipx
  const pipxPath = findOnPath('pipx');
  if (pipxPath) {
    runChild(pipxPath, ['run', '--spec', SPEC, 'sbridge', ...effectiveArgs]);
    return;
  }

  // 4. Fallback to system Python runtime
  const isWindows = process.platform === 'win32';
  const pythonCandidates = isWindows
    ? ['py', 'python', 'python3']
    : ['python3', 'python'];

  for (const name of pythonCandidates) {
    const resolved = findOnPath(name);
    if (!resolved) continue;

    const isPyLauncher =
      isWindows && path.basename(resolved).toLowerCase().startsWith('py');
    const testExec = resolved;
    const testArgsPrefix = isPyLauncher ? ['-3'] : [];

    try {
      const verCheck = spawnSync(
        testExec,
        [
          ...testArgsPrefix,
          '-c',
          'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")',
        ],
        {
          encoding: 'utf8',
          stdio: ['ignore', 'pipe', 'ignore'],
          windowsHide: true,
        }
      );
      if (verCheck.status === 0 && verCheck.stdout) {
        const parts = verCheck.stdout.trim().split('.');
        const major = parseInt(parts[0], 10);
        const minor = parseInt(parts[1], 10);
        if (major === 3 && minor >= 10 && minor < 15) {
          // Check if studiobridge is installed in this Python environment
          const checkInstalled = spawnSync(
            testExec,
            [...testArgsPrefix, '-c', 'import studiobridge'],
            {
              stdio: ['ignore', 'ignore', 'ignore'],
              windowsHide: true,
            }
          );
          if (checkInstalled.status === 0) {
            runChild(testExec, [
              ...testArgsPrefix,
              '-m',
              'studiobridge',
              ...effectiveArgs,
            ]);
            return;
          }

          // Not installed: setup isolated virtual environment
          const baseCacheDir = isWindows
            ? process.env.LOCALAPPDATA ||
              path.join(os.homedir(), 'AppData', 'Local')
            : process.env.XDG_CACHE_HOME ||
              path.join(os.homedir(), '.cache');
          const venvDir = path.join(
            baseCacheDir,
            DIST,
            `venv-${PINNED_VERSION}`
          );
          const venvPython = isWindows
            ? path.join(venvDir, 'Scripts', 'python.exe')
            : path.join(venvDir, 'bin', 'python');

          if (!fs.existsSync(venvPython)) {
            process.stderr.write(
              `[studiobridge-launcher] Setting up isolated venv in ${venvDir}...\n`
            );
            const venvRes = spawnSync(
              testExec,
              [...testArgsPrefix, '-m', 'venv', venvDir],
              {
                stdio: ['ignore', 'ignore', 'inherit'],
                windowsHide: true,
              }
            );
            if (venvRes.status !== 0) {
              process.stderr.write(
                '[studiobridge-launcher] Failed to create virtual environment.\n'
              );
              continue;
            }

            process.stderr.write(
              `[studiobridge-launcher] Installing ${SPEC}...\n`
            );
            const pipRes = spawnSync(
              venvPython,
              ['-m', 'pip', 'install', '--quiet', SPEC],
              {
                stdio: ['ignore', 'ignore', 'inherit'],
                windowsHide: true,
              }
            );
            if (pipRes.status !== 0) {
              process.stderr.write(
                `[studiobridge-launcher] Failed to install ${SPEC}.\n`
              );
              continue;
            }
          }

          runChild(venvPython, ['-m', 'studiobridge', ...effectiveArgs]);
          return;
        }
      }
    } catch {
      // Continue to next candidate
    }
  }

  // 5. No suitable runtime found: print precise installation instructions to stderr
  process.stderr.write(
    '[studiobridge-launcher] Error: No compatible Python environment found.\n\n'
  );
  process.stderr.write(
    'StudioBridge requires Python >= 3.10 (or Astral uv).\n'
  );
  process.stderr.write('To install Astral uv (recommended):\n');
  if (isWindows) {
    process.stderr.write(
      '  PowerShell: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"\n'
    );
  } else {
    process.stderr.write(
      '  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh\n'
    );
  }
  process.stderr.write(
    '\nAlternatively, install Python 3.10+ from: https://www.python.org/downloads/\n'
  );
  process.exit(1);
}

main();
