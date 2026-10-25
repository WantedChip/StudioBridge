/**
 * API Card & Reference Documentation Generator (T-WEB-08 / T-MAN-03)
 *
 * Ingests the normalized FL Studio API manifest fixture (api_v44.json)
 * and generates structured Starlight documentation articles:
 * 1. Overview index: site/src/content/docs/docs/api/index.md
 * 2. Module articles: site/src/content/docs/docs/api/{module}.md
 * 3. Individual function cards: site/src/content/docs/docs/api/{module}/{function}.md
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface ApiArg {
  name: string;
  type: string;
  optional?: boolean;
  default?: unknown;
  range?: [number, number];
  enum_name?: string;
  since?: number;
  doc?: string;
}

interface ApiVerify {
  getter: string;
  compare: string;
  settle: number;
  tol?: number;
  args?: unknown[];
}

interface ApiFunction {
  args: ApiArg[];
  ret: string;
  summary: string;
  since: number;
  mutating: boolean;
  protected: boolean;
  verify?: ApiVerify | null;
  undo?: string;
  plane?: string;
  undocumented?: boolean;
  present_in_build?: boolean;
}

interface ApiModule {
  summary: string;
  functions: Record<string, ApiFunction>;
}

interface ApiManifest {
  api_version: number;
  fl_version: string;
  build_id: string;
  modules: Record<string, ApiModule>;
}

const PYTHON_TYPE_MAP: Record<string, string> = {
  int: 'int',
  float: 'float',
  bool: 'bool',
  str: 'str',
  none: 'None',
  bytes: 'bytes',
  enum: 'int',
  flags: 'int',
  list: 'list',
  dict: 'dict',
};

const MODULE_TITLES: Record<string, string> = {
  channels: 'Channel Rack & Generators',
  device: 'Hardware Controller & Device Surface',
  general: 'General FL Studio DAW Engine',
  mixer: 'Mixer Tracks, Routing & Volume',
  patterns: 'Patterns, Clips & Sequencer',
  plugins: 'Plugin Parameters & VST/AU',
  transport: 'Transport, Playback & Recording',
  ui: 'User Interface Windows & Focus',
};

function resolveFixturePath(): string {
  const candidates = [
    path.resolve(process.cwd(), 'packages/studiobridge/src/studiobridge/manifest/fixtures/api_v44.json'),
    path.resolve(process.cwd(), '../packages/studiobridge/src/studiobridge/manifest/fixtures/api_v44.json'),
    path.resolve(__dirname, '../../packages/studiobridge/src/studiobridge/manifest/fixtures/api_v44.json'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error(`api_v44.json fixture not found in candidates: ${candidates.join(', ')}`);
}

function formatSignature(_modName: string, fnName: string, fn: ApiFunction): string {
  const retType = PYTHON_TYPE_MAP[fn.ret] || fn.ret;
  const paramStrs: string[] = [];

  for (const arg of fn.args) {
    const pType = arg.enum_name || PYTHON_TYPE_MAP[arg.type] || arg.type;
    if (arg.optional) {
      if (arg.default !== undefined && arg.default !== null) {
        paramStrs.push(`${arg.name}: ${pType} = ${JSON.stringify(arg.default)}`);
      } else {
        paramStrs.push(`${arg.name}: ${pType} = None`);
      }
    } else {
      paramStrs.push(`${arg.name}: ${pType}`);
    }
  }

  const oneLine = `def ${fnName}(${paramStrs.join(', ')}) -> ${retType}: ...`;
  if (oneLine.length <= 75 && paramStrs.length <= 2) {
    return `\`\`\`python\n${oneLine}\n\`\`\``;
  }

  const indented = paramStrs.map((p) => `    ${p},`).join('\n');
  if (indented) {
    return `\`\`\`python\ndef ${fnName}(\n${indented}\n) -> ${retType}: ...\n\`\`\``;
  }
  return `\`\`\`python\ndef ${fnName}() -> ${retType}: ...\n\`\`\``;
}

function formatParametersTable(fn: ApiFunction): string {
  if (!fn.args || fn.args.length === 0) {
    return 'This function takes no parameters.';
  }

  const rows: string[] = [
    '| Parameter | Type | Optional | Range | Since | Description |',
    '| :--- | :--- | :--- | :--- | :--- | :--- |',
  ];

  for (const arg of fn.args) {
    const pName = `\`${arg.name}\``;
    const typeStr = arg.enum_name ? `\`${arg.type}\` (${arg.enum_name})` : `\`${arg.type}\``;
    const optStr = arg.optional ? 'Yes' : 'No';
    const rangeStr = arg.range ? `\`[${arg.range[0]}, ${arg.range[1]}]\`` : '—';
    const sinceStr = arg.since ? `API v${arg.since}` : `API v${fn.since}`;
    const descStr = arg.doc ? arg.doc.trim().replace(/\n+/g, ' ') : '—';
    rows.push(`| ${pName} | ${typeStr} | ${optStr} | ${rangeStr} | ${sinceStr} | ${descStr} |`);
  }

  return rows.join('\n');
}

function formatMetadataTable(fn: ApiFunction): string {
  let verifyStr = 'None';
  if (fn.verify) {
    const parts: string[] = [
      `getter: \`${fn.verify.getter}\``,
      `compare: \`${fn.verify.compare}\``,
      `settle: \`${fn.verify.settle}ms\``,
    ];
    if (fn.verify.tol !== undefined) parts.push(`tol: \`${fn.verify.tol}\``);
    if (fn.verify.args) parts.push(`args: \`${JSON.stringify(fn.verify.args)}\``);
    verifyStr = parts.join(', ');
  }

  const rows: string[] = [
    '| Property | Value |',
    '| :--- | :--- |',
    `| Since API Version | API v${fn.since} |`,
    `| Mutating | ${fn.mutating ? 'Yes' : 'No'} |`,
    `| Protected Target | ${fn.protected ? 'Yes' : 'No'} |`,
    `| Verification | ${verifyStr} |`,
    `| Undo Mode | \`${fn.undo || 'none'}\` |`,
    `| Execution Plane | \`${fn.plane || 'midi'}\` |`,
  ];

  if (fn.undocumented) {
    rows.push('| Undocumented | Yes (discovered via runtime introspection) |');
  }
  if (fn.present_in_build === false) {
    rows.push('| Present in Build | No (deprecated or missing in current runtime) |');
  }

  return rows.join('\n');
}

function generateFunctionCardMarkdown(
  modName: string,
  fnName: string,
  fn: ApiFunction,
  isStandalone = false
): string {
  const resourceUri = `studio://api/${modName}/${fnName}`;
  const sig = formatSignature(modName, fnName, fn);
  const params = formatParametersTable(fn);
  const meta = formatMetadataTable(fn);
  const retType = PYTHON_TYPE_MAP[fn.ret] || fn.ret;

  const header = isStandalone
    ? `---
title: "${modName}.${fnName}"
description: "Reference card for ${modName}.${fnName} in StudioBridge FL Studio API v44."
sidebar:
  hidden: true
---

[← Back to ${modName} Module](/docs/api/${modName}/)

# \`${modName}.${fnName}\`
`
    : `### \`${fnName}\`

<div class="api-card-header">
  <span class="api-badge ${fn.mutating ? 'badge-mutating' : 'badge-readonly'}">${fn.mutating ? 'MUTATING' : 'READ-ONLY'}</span>
  <span class="api-badge badge-plane">${fn.plane || 'midi'}</span>
  <a href="/docs/api/${modName}/${fnName.toLowerCase()}/" class="api-permalink">Permalink</a>
</div>
`;

  return `${header}
**Resource URI:** \`${resourceUri}\`

${fn.summary.trim()}

#### Signature

${sig}

#### Parameters

${params}

#### Return Value

- **Type:** \`${retType}\`

#### Metadata

${meta}
`;
}

export function generateApiDocs(): void {
  const fixturePath = resolveFixturePath();
  const raw = fs.readFileSync(fixturePath, 'utf8');
  const manifest: ApiManifest = JSON.parse(raw);

  const outBaseDir = path.resolve(
    process.cwd().endsWith('site') ? process.cwd() : path.join(process.cwd(), 'site'),
    'src/content/docs/docs/api'
  );

  fs.mkdirSync(outBaseDir, { recursive: true });

  const modNames = Object.keys(manifest.modules).sort();
  let totalFunctions = 0;
  let totalMutating = 0;

  for (const m of modNames) {
    const fns = manifest.modules[m].functions;
    totalFunctions += Object.keys(fns).length;
    totalMutating += Object.values(fns).filter((f) => f.mutating).length;
  }

  // 1. Generate Index Page: site/src/content/docs/docs/api/index.md
  const indexRows: string[] = [
    '| Module | Title | Functions | Mutating | Execution Plane | Reference Link |',
    '| :--- | :--- | :--- | :--- | :--- | :--- |',
  ];

  for (const m of modNames) {
    const mod = manifest.modules[m];
    const fnCount = Object.keys(mod.functions).length;
    const mutCount = Object.values(mod.functions).filter((f) => f.mutating).length;
    const title = MODULE_TITLES[m] || m;
    indexRows.push(
      `| \`${m}\` | ${title} | ${fnCount} | ${mutCount} | \`midi\` | [${m} API](/docs/api/${m}/) |`
    );
  }

  const indexMd = `---
title: "FL Studio API Reference Overview"
description: "Authoritative reference for StudioBridge FL Studio API v44, detailing 119 RPC functions across 8 modules."
---

The **StudioBridge API Reference** documents the normalized Python API surface exposed by FL Studio's controller script runtime (API v44 / FL Studio 24.1+).

Coding agents access these functions via the Live MIDI RPC Plane using standard tool calls and MCP resource URIs (\`studio://api/{module}/{function}\`).

## Module Index

${indexRows.join('\n')}

**Total Surface:** ${totalFunctions} functions (${totalMutating} mutating, ${totalFunctions - totalMutating} read-only) across ${modNames.length} modules.

---

## Architectural Principles

### 1. Unified Resource URIs
Every function in the FL Studio Python API maps to a canonical resource URI:
\`\`\`
studio://api/{module}/{function}
\`\`\`
Examples:
- \`studio://api/transport/isPlaying\`
- \`studio://api/mixer/getTrackVolume\`
- \`studio://api/channels/setChannelVolume\`

### 2. Execution Planes & Sandboxing
- **Live MIDI RPC Plane (\`midi\`):** All functions listed in this reference execute inside the FL Studio controller script sandbox on the host audio thread.
- **Python 3.9 Runtime:** Functions execute inside the embedded Python environment with builtin types (\`int\`, \`float\`, \`str\`, \`bool\`, \`None\`). No sockets or external C-extensions are loaded.

### 3. Read-Only Default & Safety Guarantees
- By default, sessions operate in **read-only mode**. Mutating calls require explicit safety elevation or safe session unlocking.
- Mutating operations implement automatic **read-back verification** and record entries in the mutation journal with rollback capability (\`G0-G2\` guarantee levels).

### 4. Parameter Validation & Range Bounds
- Integer and float parameters are strictly validated against hardware ranges before dispatch across the MIDI wire.
- Out-of-bounds parameters are rejected client-side with descriptive error messages, preventing DAW instability.
`;

  fs.writeFileSync(path.join(outBaseDir, 'index.md'), indexMd, 'utf8');
  console.log(`[gen-api-cards] Generated API Index: ${path.join(outBaseDir, 'index.md')}`);

  // 2. Generate Each Module Article and Individual Function Cards
  for (const modName of modNames) {
    const mod = manifest.modules[modName];
    const modTitle = MODULE_TITLES[modName] || modName;
    const fnNames = Object.keys(mod.functions).sort();

    const modDir = path.join(outBaseDir, modName);
    fs.mkdirSync(modDir, { recursive: true });

    // Table of functions for the module overview
    const fnSummaryRows: string[] = [
      '| Function | Type | Return | Since | Summary |',
      '| :--- | :--- | :--- | :--- | :--- |',
    ];

    const cardsSections: string[] = [];

    for (const fnName of fnNames) {
      const fn = mod.functions[fnName];
      const mutBadge = fn.mutating ? '**Mutating**' : 'Read-only';
      const retType = PYTHON_TYPE_MAP[fn.ret] || fn.ret;
      const cleanSummary = fn.summary.trim().replace(/\n+/g, ' ');

      fnSummaryRows.push(
        `| [\`${fnName}\`](#${fnName.toLowerCase()}) | ${mutBadge} | \`${retType}\` | v${fn.since} | ${cleanSummary} |`
      );

      // Section for module page
      cardsSections.push(generateFunctionCardMarkdown(modName, fnName, fn, false));

      // Standalone card file
      const standaloneCard = generateFunctionCardMarkdown(modName, fnName, fn, true);
      const standaloneFile = path.join(modDir, `${fnName}.md`);
      fs.writeFileSync(standaloneFile, standaloneCard, 'utf8');
    }

    const moduleMd = `---
title: "${modName} — ${modTitle}"
description: "Complete API reference for the ${modName} module (${fnNames.length} functions) in StudioBridge FL Studio API v44."
---

[← Back to API Overview](/docs/api/)

The \`${modName}\` module provides direct control over FL Studio's ${modTitle.toLowerCase()}.

- **Functions:** ${fnNames.length}
- **Execution Plane:** \`midi\` (Live MIDI SysEx RPC)
- **API Version:** v44

## Function Summary

${fnSummaryRows.join('\n')}

---

## Detailed Function Reference

${cardsSections.join('\n---\n\n')}
`;

    const moduleFile = path.join(outBaseDir, `${modName}.md`);
    fs.writeFileSync(moduleFile, moduleMd, 'utf8');
    console.log(`[gen-api-cards] Generated Module: ${moduleFile} (${fnNames.length} functions)`);
  }

  console.log(`[gen-api-cards] Successfully generated ${totalFunctions} API cards across ${modNames.length} modules.`);
}

// Execute directly if run as a script
if (process.argv[1]?.endsWith('gen-api-cards.ts')) {
  generateApiDocs();
}
