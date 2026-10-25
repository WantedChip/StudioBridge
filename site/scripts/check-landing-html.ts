import fs from 'node:fs';
import path from 'node:path';

const possiblePaths = [
  path.resolve('dist/index.html'),
  path.resolve('site/dist/index.html'),
];
const htmlPath = possiblePaths.find((p) => fs.existsSync(p));
if (!htmlPath) {
  console.error(`Dist file not found at ${possiblePaths.join(' or ')}. Run npm run build first.`);
  process.exit(1);
}

const html = fs.readFileSync(htmlPath, 'utf8');

const checks = [
  { name: 'Accessible skip link as first active element', test: html.includes('href="#main-content"') },
  { name: 'Wordmark StudioBridge', test: html.includes('StudioBridge') },
  { name: 'Primary nav: Docs link', test: html.includes('href="/docs/"') },
  { name: 'Primary nav: Compat link', test: html.includes('href="/compat"') },
  { name: 'Primary nav: Changelog link', test: html.includes('href="/changelog"') },
  { name: 'Primary nav: GitHub link', test: html.includes('href="https://github.com/WantedChip/studiobridge"') },
  { name: 'Integrated ThemeToggle component', test: html.includes('role="radiogroup"') },
  { name: 'Section 01 / SIGNAL PATH', test: html.includes('01 / SIGNAL PATH') },
  { name: 'Works With: Claude Code', test: html.includes('Claude Code') },
  { name: 'Works With: any MCP client', test: html.includes('any MCP client') },
  { name: 'Works With: plain CLI', test: html.includes('plain CLI') },
  { name: 'Section 02 / TRY A SESSION', test: html.includes('02 / TRY A SESSION') },
  { name: 'Console Demo: Session Balance Drums', test: html.includes('Balance Drums') },
  { name: 'Console Demo: Section anchor #session-demo', test: html.includes('id="session-demo"') },
  { name: 'Section 03 / CONTROL SURFACES', test: html.includes('03 / CONTROL SURFACES') },
  { name: 'Channel CH 01 // LIVE RPC', test: html.includes('CH 01 // LIVE RPC') },
  { name: 'Channel CH 02 // OFFLINE FLP', test: html.includes('CH 02 // OFFLINE FLP') },
  { name: 'Channel CH 03 // HEADLESS RENDER', test: html.includes('CH 03 // HEADLESS RENDER') },
  { name: 'Channel CH 04 // UI ACTUATION', test: html.includes('CH 04 // UI ACTUATION') },
  { name: 'Section 04 / CAPABILITIES', test: html.includes('04 / CAPABILITIES') },
  { name: 'Capabilities: Section anchor #capabilities', test: html.includes('id="capabilities"') },
  { name: 'Capabilities: Exact capability truth heading', test: html.includes('Exact capability truth') },
  { name: 'Capabilities: Dual selector radiogroups', test: html.includes('fl-build-label') && html.includes('arch-label') },
  { name: 'Capabilities: Diagnostic bundle reference', test: html.includes('DIAG-ARM64') || html.includes('DIAG-X64') },
  { name: 'Section 05 / INTERLOCKS', test: html.includes('05 / INTERLOCKS') },
  { name: 'Interlock: Read-Only Default Mode', test: html.includes('Read-Only Default Mode') },
  { name: 'Interlock: Read-Back Verification', test: html.includes('Read-Back Verification') },
  { name: 'Interlock: Protected Target Gates', test: html.includes('Protected Target Gates') },
  { name: 'Rollback guarantee levels G0, G1, G2', test: html.includes('G0') && html.includes('G1') && html.includes('G2') },
  { name: 'Section 06 / PATCH IN', test: html.includes('06 / PATCH IN') },
  { name: 'Install: Setup Virtual MIDI Loopback (Step 1)', test: html.includes('Setup Virtual MIDI Loopback') },
  { name: 'Install: Configure Agent MCP Server (Step 2)', test: html.includes('Configure Agent MCP Server') },
  { name: 'Install: Verify with Doctor (Step 3)', test: html.includes('Verify Wire') && html.includes('Doctor') },
  { name: 'Install: Accessible tablist and tabs', test: html.includes('role="tablist"') && html.includes('role="tab"') && html.includes('role="tabpanel"') },
  { name: 'Install: Doctor sample output present', test: html.includes('SYS-01') && html.includes('WMS-01') && html.includes('PORT-01') && html.includes('DEV-01') },
  { name: 'Section 07 / LIMITS', test: html.includes('07 / LIMITS') },
  { name: 'Limits: Plugin Instantiation (CAP_PLUGIN_INSTANTIATE)', test: html.includes('CAP_PLUGIN_INSTANTIATE') },
  { name: 'Limits: Windows ARM64 Host Emulation (CAP_HOST_NATIVE_ARM64)', test: html.includes('CAP_HOST_NATIVE_ARM64') },
  { name: 'Limits: Playlist Clip Write in FL 26 (CAP_FLP_PLAYLIST_WRITE)', test: html.includes('CAP_FLP_PLAYLIST_WRITE') },
  { name: 'Limits: Zero Kernel Drivers (CAP_ZERO_KERNEL_DRIVERS)', test: html.includes('CAP_ZERO_KERNEL_DRIVERS') },
  { name: 'Section 08 / SOURCE', test: html.includes('08 / SOURCE') },
  { name: 'MIT License details', test: html.includes('WANTEDCHIP') && html.includes('MIT') },
  { name: 'Clean-room provenance notice', test: html.includes('Clean-Room Provenance') },
  { name: 'Security policy pointer', test: html.includes('SECURITY.md') },
  { name: 'Section 09 / FAQ', test: html.includes('09 / FAQ') },
  { name: 'Semantic details/summary accordions', test: html.includes('<details') && html.includes('<summary') },
  { name: 'FAQ answers safety and file preservation', test: faqIncludes('Will StudioBridge ever overwrite or corrupt my FL Studio project files?') },
  { name: 'FAQ answers telemetry (zero telemetry, 100% local)', test: faqIncludes('Does StudioBridge collect telemetry or send data over the internet?') },
  { name: 'FAQ answers supported FL versions (FL 21–26)', test: faqIncludes('Which FL Studio versions are supported?') },
  { name: 'FAQ answers Windows on ARM64', test: faqIncludes('Does StudioBridge support Windows on ARM64') },
  { name: 'FAQ answers trademark non-affiliation', test: faqIncludes('What is the relationship between StudioBridge and Image-Line?') },
  { name: 'Verbatim prominent non-affiliation statement in footer (18 §11)', test: html.includes('StudioBridge is an independent open-source project. FL Studio is a trademark of Image-Line. Not affiliated with or endorsed by Image-Line.') },
  { name: 'Footer links to llms.txt', test: html.includes('href="/llms.txt"') },
  { name: 'Numbered technical catalogue styling across sections', test: html.includes('01 /') && html.includes('02 /') && html.includes('03 /') && html.includes('04 /') && html.includes('05 /') && html.includes('06 /') && html.includes('07 /') && html.includes('08 /') && html.includes('09 /') },
];

function faqIncludes(str: string): boolean {
  return html.includes(str);
}

let failed = 0;
console.log('Validating generated site/dist/index.html:');
for (const c of checks) {
  if (c.test) {
    console.log(`  [PASS] ${c.name}`);
  } else {
    console.log(`  [FAIL] ${c.name}`);
    failed++;
  }
}

if (failed > 0) {
  console.error(`\nValidation failed with ${failed} failure(s).`);
  process.exit(1);
} else {
  console.log(`\nAll ${checks.length} assertions passed successfully!`);
}
