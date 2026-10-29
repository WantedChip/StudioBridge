import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { codeToHtml } from 'shiki';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Find templates directory relative to script or workspace root
const candidates = [
  path.resolve(__dirname, '../../packages/studiobridge/src/studiobridge/agents/templates'),
  path.resolve(process.cwd(), 'packages/studiobridge/src/studiobridge/agents/templates'),
  path.resolve(process.cwd(), '../packages/studiobridge/src/studiobridge/agents/templates'),
];

const foundDir = candidates.find((dir) => fs.existsSync(dir));
if (!foundDir) {
  console.error(`ERROR: Templates directory not found in candidates:\n${candidates.join('\n')}`);
  process.exit(1);
}
const templatesDir: string = foundDir;

export interface AgentDefinition {
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
}

export interface ProcessedAgent extends AgentDefinition {
  rawSnippet: string;
  highlightedHtml: string;
}

// 11 supported agents in canonical display order
const AGENT_SPECS: AgentDefinition[] = [
  {
    id: 'claude-code',
    name: 'Claude Code',
    templateFile: 'claude_code.json',
    configFormat: 'json',
    targetPath: '.mcp.json',
    scope: 'project',
    installCommand: 'uvx studiobridge agent install claude-code',
    cliCommand: 'sbridge agent install claude-code',
    nextSteps: "Run 'claude' in this folder and approve the MCP server if prompted.",
    windowsNote: 'Project-scope configuration stored in repository root .mcp.json.',
  },
  {
    id: 'claude-desktop',
    name: 'Claude Desktop',
    templateFile: 'claude_desktop.json',
    configFormat: 'json',
    targetPath: '%APPDATA%\\Claude\\claude_desktop_config.json',
    scope: 'user',
    installCommand: 'uvx studiobridge agent install claude-desktop',
    cliCommand: 'sbridge agent install claude-desktop',
    nextSteps: 'Restart Claude Desktop to connect to the studiobridge MCP server.',
    windowsNote: 'User-scope configuration for the Claude Desktop Windows client.',
  },
  {
    id: 'codex',
    name: 'Codex',
    templateFile: 'codex.toml',
    configFormat: 'toml',
    targetPath: '~/.codex/config.toml',
    scope: 'user',
    installCommand: 'uvx studiobridge agent install codex',
    cliCommand: 'sbridge agent install codex',
    nextSteps: "Run 'codex' or open your Codex IDE session.",
    windowsNote: 'TOML format with tool_timeout_sec = 120 for lengthy render tasks.',
  },
  {
    id: 'cursor',
    name: 'Cursor',
    templateFile: 'cursor.json',
    configFormat: 'json',
    targetPath: '.cursor/mcp.json',
    scope: 'project',
    installCommand: 'uvx studiobridge agent install cursor',
    cliCommand: 'sbridge agent install cursor',
    nextSteps: 'Reload Cursor window (Ctrl+Shift+P > Developer: Reload Window) or restart Cursor.',
    windowsNote: 'Project-scope configuration under .cursor/mcp.json.',
  },
  {
    id: 'opencode',
    name: 'opencode',
    templateFile: 'opencode.json',
    configFormat: 'json',
    targetPath: 'opencode.json',
    scope: 'project',
    installCommand: 'uvx studiobridge agent install opencode',
    cliCommand: 'sbridge agent install opencode',
    nextSteps: "Run 'opencode' in this folder.",
    windowsNote: 'opencode single array command format with enabled: true.',
  },
  {
    id: 'antigravity',
    name: 'Antigravity',
    templateFile: 'antigravity.json',
    configFormat: 'json',
    targetPath: '%APPDATA%\\Antigravity\\mcp_settings.json',
    scope: 'user',
    installCommand: 'uvx studiobridge agent install antigravity',
    cliCommand: 'sbridge agent install antigravity',
    nextSteps: "In Antigravity, click 'View raw config' / refresh MCP servers in the UI.",
    windowsNote: 'User-scope settings. Refreshes live in Antigravity IDE workspace.',
  },
  {
    id: 'gemini',
    name: 'Gemini CLI',
    templateFile: 'gemini.json',
    configFormat: 'json',
    targetPath: '~/.gemini/settings.json',
    scope: 'user',
    installCommand: 'uvx studiobridge agent install gemini',
    cliCommand: 'sbridge agent install gemini',
    nextSteps: "Run 'gemini' to start using studiobridge tools.",
    windowsNote: 'User-scope configuration in ~/.gemini/settings.json.',
  },
  {
    id: 'vscode',
    name: 'VS Code',
    templateFile: 'vscode.json',
    configFormat: 'json',
    targetPath: '.vscode/mcp.json',
    scope: 'project',
    installCommand: 'uvx studiobridge agent install vscode',
    cliCommand: 'sbridge agent install vscode',
    nextSteps: 'Restart VS Code or reload window to start GitHub Copilot MCP server.',
    windowsNote: 'VS Code format with type: "stdio". Works with Copilot Agent mode.',
  },
  {
    id: 'windsurf',
    name: 'Windsurf',
    templateFile: 'windsurf.json',
    configFormat: 'json',
    targetPath: '~/.codeium/windsurf/mcp_config.json',
    scope: 'user',
    installCommand: 'uvx studiobridge agent install windsurf',
    cliCommand: 'sbridge agent install windsurf',
    nextSteps: 'Restart Windsurf or refresh Cascade MCP tools.',
    windowsNote: 'User-scope Cascade MCP configuration for Codeium Windsurf.',
  },
  {
    id: 'zed',
    name: 'Zed',
    templateFile: 'zed.json',
    configFormat: 'json',
    targetPath: '%APPDATA%\\Zed\\settings.json',
    scope: 'user',
    installCommand: 'uvx studiobridge agent install zed',
    cliCommand: 'sbridge agent install zed',
    nextSteps: 'Restart Zed to activate the studiobridge context server.',
    windowsNote: 'Uses context_servers section in Zed settings.',
  },
  {
    id: 'generic',
    name: 'Generic',
    templateFile: 'generic.json',
    configFormat: 'json',
    targetPath: '~/.mcp.json',
    scope: 'user',
    installCommand: 'uvx studiobridge agent install generic',
    cliCommand: 'sbridge agent install generic',
    nextSteps: 'Configure your MCP client using the generated studiobridge server block.',
    windowsNote: 'Standard MCP server definition compatible with Cline, Roo, Continue, Goose, etc.',
  },
];

async function generateAgentsJson(): Promise<void> {
  console.log(`Ingesting agent templates from: ${templatesDir}`);
  const processed: ProcessedAgent[] = [];

  for (const spec of AGENT_SPECS) {
    const templatePath = path.join(templatesDir, spec.templateFile);
    if (!fs.existsSync(templatePath)) {
      throw new Error(`Template file not found: ${templatePath}`);
    }

    const rawTemplate = fs.readFileSync(templatePath, 'utf8').trim();

    // Resolve brand tokens without drift: {DIST} -> studiobridge, {CLI} -> sbridge
    const rawSnippet = rawTemplate
      .replaceAll('{DIST}', 'studiobridge')
      .replaceAll('{CLI}', 'sbridge');

    // Generate syntax-highlighted HTML using Shiki dual themes (github-light & github-dark)
    const highlightedHtml = await codeToHtml(rawSnippet, {
      lang: spec.configFormat,
      themes: {
        light: 'github-light',
        dark: 'github-dark',
      },
      defaultColor: false,
    });

    processed.push({
      ...spec,
      rawSnippet,
      highlightedHtml,
    });
    console.log(`  [OK] Processed ${spec.name} (${spec.templateFile})`);
  }

  // Determine output path: site/src/data/agents.json
  const outDirCandidates = [
    path.resolve(__dirname, '../src/data'),
    path.resolve(process.cwd(), 'src/data'),
    path.resolve(process.cwd(), 'site/src/data'),
  ];
  let targetDir = outDirCandidates.find((d) => fs.existsSync(path.dirname(d)));
  if (!targetDir) {
    targetDir = path.resolve(__dirname, '../src/data');
  }

  fs.mkdirSync(targetDir, { recursive: true });
  const outPath = path.join(targetDir, 'agents.json');

  fs.writeFileSync(outPath, JSON.stringify(processed, null, 2), 'utf8');
  console.log(`\nSuccessfully wrote ${processed.length} agent configs to: ${outPath}`);
}

generateAgentsJson().catch((err) => {
  console.error('Fatal error in gen-agents:', err);
  process.exit(1);
});
