/**
 * OpenGraph Social Sharing Card Generator (v0.6.9 / T-WEB-09)
 *
 * Generates site/public/og.svg and site/public/og.png (1200x630) per 18_landing_page_spec.md §7, §8, §12.
 * Design characteristics:
 * - Technical signal-path motif with patch cable curves and SysEx hex frames.
 * - Patchbay registration marks and hairline rack grid.
 * - Paper palette: #F3F0E8 (Ground), #14130F (Ink), #E8461A (Signal), #55524A (Muted), #CFC9BA (Line).
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import zlib from 'node:zlib';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const candidates = [
  path.resolve(__dirname, '../public'),
  path.resolve(process.cwd(), 'site/public'),
  path.resolve(process.cwd(), 'public'),
];
const publicDir = candidates.find((d) => fs.existsSync(d)) || candidates[0];
if (!fs.existsSync(publicDir)) {
  fs.mkdirSync(publicDir, { recursive: true });
}

const WIDTH = 1200;
const HEIGHT = 630;

function generateSvg(): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" width="${WIDTH}" height="${HEIGHT}">
  <defs>
    <style>
      .font-sans { font-family: 'Inter Tight', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
      .font-display { font-family: 'Bricolage Grotesque', -apple-system, BlinkMacSystemFont, sans-serif; font-weight: 800; }
      .font-mono { font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; }
    </style>
    <linearGradient id="cableGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#E8461A" />
      <stop offset="50%" stop-color="#FF6A2B" />
      <stop offset="100%" stop-color="#E8461A" />
    </linearGradient>
  </defs>

  <!-- Ground: Paper Palette #F3F0E8 -->
  <rect width="${WIDTH}" height="${HEIGHT}" fill="#F3F0E8" />

  <!-- Outer Rack Boundary & Border -->
  <rect x="36" y="36" width="1128" height="558" fill="none" stroke="#CFC9BA" stroke-width="1.5" />

  <!-- Registration Marks (+) at 4 rack corners -->
  <g stroke="#837E70" stroke-width="1.5">
    <!-- Top-Left -->
    <line x1="28" y1="36" x2="44" y2="36" />
    <line x1="36" y1="28" x2="36" y2="44" />
    <!-- Top-Right -->
    <line x1="1156" y1="36" x2="1172" y2="36" />
    <line x1="1164" y1="28" x2="1164" y2="44" />
    <!-- Bottom-Left -->
    <line x1="28" y1="594" x2="44" y2="594" />
    <line x1="36" y1="586" x2="36" y2="602" />
    <!-- Bottom-Right -->
    <line x1="1156" y1="594" x2="1172" y2="594" />
    <line x1="1164" y1="586" x2="1164" y2="602" />
  </g>

  <!-- Top Rack Rail Header (y=36 to y=96) -->
  <line x1="36" y1="96" x2="1164" y2="96" stroke="#CFC9BA" stroke-width="1.5" />

  <!-- LED Indicator -->
  <circle cx="68" cy="66" r="6" fill="#E8461A" />
  <circle cx="68" cy="66" r="10" fill="none" stroke="#E8461A" stroke-opacity="0.3" stroke-width="2" />

  <!-- Spec Identification Header -->
  <text x="92" y="71" class="font-mono" font-size="12" font-weight="600" fill="#55524A" letter-spacing="1.5">
    STUDIOBRIDGE // SPEC 18 §8 // RACK REF: SB-2026-OG // 01 / SIGNAL PATH
  </text>

  <!-- Architecture Badges on Top Right -->
  <g class="font-mono" font-size="10" font-weight="600">
    <!-- Badge 1: Windows 11 -->
    <rect x="880" y="54" width="130" height="24" rx="2" fill="#FBF9F4" stroke="#837E70" stroke-width="1" />
    <text x="892" y="70" fill="#14130F" letter-spacing="0.5">WIN 11 (ARM64/x64)</text>

    <!-- Badge 2: MIT -->
    <rect x="1022" y="54" width="110" height="24" rx="2" fill="#FBF9F4" stroke="#837E70" stroke-width="1" />
    <text x="1038" y="70" fill="#14130F" letter-spacing="0.5">MIT LICENSE</text>
  </g>

  <!-- LEFT COLUMN: Headline & Value Proposition -->
  <!-- Wordmark -->
  <g transform="translate(68, 170)">
    <!-- Signal Accent Square -->
    <rect x="0" y="-36" width="14" height="14" rx="1.5" fill="#E8461A" />
    <text x="26" y="-22" class="font-display" font-size="34" font-weight="800" fill="#14130F" letter-spacing="-0.5">
      StudioBridge
    </text>

    <!-- Main Headline -->
    <text x="0" y="52" class="font-display" font-size="44" font-weight="800" fill="#14130F" letter-spacing="-1">
      Patch your agent
    </text>
    <text x="0" y="104" class="font-display" font-size="44" font-weight="800" fill="#14130F" letter-spacing="-1">
      into your DAW.
    </text>

    <!-- Subtitle Copy -->
    <text x="0" y="162" class="font-sans" font-size="18" fill="#55524A" font-weight="400">
      Read, edit and render FL Studio projects from any coding agent.
    </text>
    <text x="0" y="192" class="font-sans" font-size="18" fill="#55524A" font-weight="400">
      Verified writes, reversibility, and 100% local execution.
    </text>

    <!-- Specification Bullets -->
    <g transform="translate(0, 240)" class="font-mono" font-size="12" fill="#14130F">
      <!-- Bullet 1 -->
      <circle cx="4" cy="-4" r="3" fill="#E8461A" />
      <text x="16" y="0">FL STUDIO 21–26</text>

      <!-- Bullet 2 -->
      <circle cx="160" cy="-4" r="3" fill="#E8461A" />
      <text x="172" y="0">REVERSIBLE JOURNAL</text>

      <!-- Bullet 3 -->
      <circle cx="340" cy="-4" r="3" fill="#E8461A" />
      <text x="352" y="0">ZERO NATIVE DRIVERS</text>
    </g>
  </g>

  <!-- RIGHT COLUMN: Signal-Path Hardware Schematic -->
  <g transform="translate(640, 130)">
    <!-- Technical Panel Enclosure -->
    <rect x="0" y="0" width="490" height="380" rx="2" fill="#FBF9F4" stroke="#CFC9BA" stroke-width="1.5" />

    <!-- Enclosure Header -->
    <rect x="0" y="0" width="490" height="36" fill="#EDE9DF" stroke="#CFC9BA" stroke-width="1.5" />
    <text x="16" y="23" class="font-mono" font-size="11" font-weight="700" fill="#55524A" letter-spacing="1">
      CH 01 // 2-WAY SIGNAL PATH ROUTING
    </text>
    <text x="380" y="23" class="font-mono" font-size="11" font-weight="600" fill="#1D7A4A">
      ● VERIFIED
    </text>

    <!-- Node 1: AGENT -->
    <g transform="translate(24, 60)">
      <rect x="0" y="0" width="120" height="64" rx="2" fill="#F3F0E8" stroke="#837E70" stroke-width="1.5" />
      <text x="60" y="28" class="font-mono" font-size="10" font-weight="600" fill="#55524A" text-anchor="middle">CLIENT</text>
      <text x="60" y="48" class="font-mono" font-size="12" font-weight="700" fill="#14130F" text-anchor="middle">AGENT</text>
      <!-- Jack Port Out -->
      <circle cx="120" cy="32" r="5" fill="#14130F" />
      <circle cx="120" cy="32" r="2.5" fill="#E8461A" />
    </g>

    <!-- Node 2: MCP SERVER -->
    <g transform="translate(184, 60)">
      <rect x="0" y="0" width="120" height="64" rx="2" fill="#F3F0E8" stroke="#837E70" stroke-width="1.5" />
      <text x="60" y="28" class="font-mono" font-size="10" font-weight="600" fill="#55524A" text-anchor="middle">PROTOCOL</text>
      <text x="60" y="48" class="font-mono" font-size="12" font-weight="700" fill="#14130F" text-anchor="middle">MCP HOST</text>
      <!-- Jack Ports In/Out -->
      <circle cx="0" cy="32" r="5" fill="#14130F" />
      <circle cx="0" cy="32" r="2.5" fill="#E8461A" />
      <circle cx="120" cy="32" r="5" fill="#14130F" />
      <circle cx="120" cy="32" r="2.5" fill="#E8461A" />
    </g>

    <!-- Node 3: BROKER &amp; SYSEX -->
    <g transform="translate(344, 60)">
      <rect x="0" y="0" width="120" height="64" rx="2" fill="#F3F0E8" stroke="#837E70" stroke-width="1.5" />
      <text x="60" y="28" class="font-mono" font-size="10" font-weight="600" fill="#55524A" text-anchor="middle">MIDI / RPC</text>
      <text x="60" y="48" class="font-mono" font-size="12" font-weight="700" fill="#14130F" text-anchor="middle">BROKER</text>
      <!-- Jack Ports In/Out -->
      <circle cx="0" cy="32" r="5" fill="#14130F" />
      <circle cx="0" cy="32" r="2.5" fill="#E8461A" />
      <circle cx="60" cy="64" r="5" fill="#14130F" />
      <circle cx="60" cy="64" r="2.5" fill="#E8461A" />
    </g>

    <!-- Cable 1: Agent -> MCP -->
    <path d="M 144 92 C 158 92, 170 92, 184 92" fill="none" stroke="url(#cableGrad)" stroke-width="3" />
    <!-- Cable 2: MCP -> Broker -->
    <path d="M 304 92 C 318 92, 330 92, 344 92" fill="none" stroke="url(#cableGrad)" stroke-width="3" />

    <!-- Node 4: FL STUDIO (Below) -->
    <g transform="translate(184, 180)">
      <rect x="0" y="0" width="280" height="64" rx="2" fill="#14130F" stroke="#14130F" stroke-width="1.5" />
      <text x="140" y="26" class="font-mono" font-size="10" font-weight="600" fill="#A9A497" text-anchor="middle">CONTROLLER SCRIPT / WINMM</text>
      <text x="140" y="48" class="font-mono" font-size="13" font-weight="700" fill="#F1EEE6" text-anchor="middle">FL STUDIO (HOST DAW)</text>
      <!-- Jack Port In -->
      <circle cx="220" cy="0" r="5" fill="#F3F0E8" />
      <circle cx="220" cy="0" r="2.5" fill="#E8461A" />
    </g>

    <!-- Cable 3: Broker -> FL Studio -->
    <path d="M 404 124 C 404 150, 404 160, 404 180" fill="none" stroke="url(#cableGrad)" stroke-width="3" />

    <!-- SysEx Telegram Terminal Box -->
    <g transform="translate(24, 270)">
      <rect x="0" y="0" width="440" height="86" rx="2" fill="#14130F" />
      <text x="16" y="24" class="font-mono" font-size="10" font-weight="700" fill="#E8461A" letter-spacing="1">
        LIVE WIRE TELEGRAM // SYSEX FRAME
      </text>
      <!-- Hex Bytes -->
      <text x="16" y="50" class="font-mono" font-size="14" font-weight="700" fill="#F3F0E8" letter-spacing="2">
        F0 7D 53 42 01 01 12 00 24 10 F7
      </text>
      <!-- Frame Breakdown -->
      <text x="16" y="72" class="font-mono" font-size="10" fill="#A9A497">
        SOF · VENDOR(7D) · MAGIC(SB) · OP_MIXER_SET · CRC-16(0x1021) · EOF
      </text>
    </g>
  </g>

  <!-- Bottom Rack Rail Footer (y=534 to y=594) -->
  <line x1="36" y1="534" x2="1164" y2="534" stroke="#CFC9BA" stroke-width="1.5" />

  <text x="68" y="568" class="font-sans" font-size="13" font-weight="500" fill="#55524A">
    https://studiobridge.dev · Independent Open-Source DAW Automation Bridge
  </text>
  <text x="1132" y="568" class="font-mono" font-size="11" font-weight="600" fill="#55524A" text-anchor="end">
    PROTOCOL: MIDI-SYSEX 53 42 // ZERO TELEMETRY
  </text>
</svg>
`;
}

// Fallback pure-Node PNG generator
const CRC_TABLE = new Uint32Array(256);
for (let n = 0; n < 256; n++) {
  let c = n;
  for (let k = 0; k < 8; k++) {
    if (c & 1) c = 0xedb88320 ^ (c >>> 1);
    else c = c >>> 1;
  }
  CRC_TABLE[n] = c >>> 0;
}

function crc32(buf: Buffer): number {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  }
  return (c ^ 0xffffffff) >>> 0;
}

function createPngChunk(type: string, data: Buffer): Buffer {
  const len = data.length;
  const chunk = Buffer.alloc(4 + 4 + len + 4);
  chunk.writeUInt32BE(len, 0);
  chunk.write(type, 4, 4, 'ascii');
  data.copy(chunk, 8);
  const typeAndData = chunk.subarray(4, 8 + len);
  chunk.writeUInt32BE(crc32(typeAndData), 8 + len);
  return chunk;
}

function createFallbackPng(width: number, height: number): Buffer {
  // 8-byte PNG signature
  const signature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

  // IHDR chunk: 13 bytes (width, height, bitDepth=8, colorType=2 (RGB), comp=0, filter=0, interlace=0)
  const ihdrData = Buffer.alloc(13);
  ihdrData.writeUInt32BE(width, 0);
  ihdrData.writeUInt32BE(height, 4);
  ihdrData[8] = 8; // 8 bits per sample
  ihdrData[9] = 2; // RGB
  ihdrData[10] = 0; // Deflate
  ihdrData[11] = 0; // Filter 0
  ihdrData[12] = 0; // No interlace
  const ihdrChunk = createPngChunk('IHDR', ihdrData);

  // Generate image data in RGB (Paper palette background #F3F0E8: 243, 240, 232)
  const rawScanlines = Buffer.alloc(height * (1 + width * 3));
  for (let y = 0; y < height; y++) {
    const rowOffset = y * (1 + width * 3);
    rawScanlines[rowOffset] = 0; // filter byte: None
    for (let x = 0; x < width; x++) {
      const pixelOffset = rowOffset + 1 + x * 3;
      // Border checking
      const isBorder = (x >= 36 && x <= 1164 && (y === 36 || y === 594 || y === 96 || y === 534)) ||
                       ((x === 36 || x === 1164) && y >= 36 && y <= 594);
      // Status LED indicator at (68, 66)
      const dxLed = x - 68;
      const dyLed = y - 66;
      const isLed = dxLed * dxLed + dyLed * dyLed <= 36;

      if (isLed) {
        // Signal Orange #E8461A (232, 70, 26)
        rawScanlines[pixelOffset] = 232;
        rawScanlines[pixelOffset + 1] = 70;
        rawScanlines[pixelOffset + 2] = 26;
      } else if (isBorder) {
        // Line #CFC9BA (207, 201, 186)
        rawScanlines[pixelOffset] = 207;
        rawScanlines[pixelOffset + 1] = 201;
        rawScanlines[pixelOffset + 2] = 186;
      } else {
        // Ground Paper #F3F0E8 (243, 240, 232)
        rawScanlines[pixelOffset] = 243;
        rawScanlines[pixelOffset + 1] = 240;
        rawScanlines[pixelOffset + 2] = 232;
      }
    }
  }

  const idatData = zlib.deflateSync(rawScanlines);
  const idatChunk = createPngChunk('IDAT', idatData);
  const iendChunk = createPngChunk('IEND', Buffer.alloc(0));

  return Buffer.concat([signature, ihdrChunk, idatChunk, iendChunk]);
}

export async function generateOpenGraphCards(): Promise<{ svgPath: string; pngPath: string }> {
  const svgContent = generateSvg();
  const svgPath = path.join(publicDir, 'og.svg');
  fs.writeFileSync(svgPath, svgContent, 'utf8');
  console.log(`[gen-og] Generated ${svgPath} (${WIDTH}x${HEIGHT})`);

  const pngPath = path.join(publicDir, 'og.png');
  let pngSuccess = false;

  // Try rendering with sharp if available
  try {
    let sharpMod: any;
    try {
      sharpMod = (await import('sharp')).default;
    } catch {
      const localSharp = path.resolve(__dirname, '../node_modules/sharp');
      if (fs.existsSync(localSharp)) {
        sharpMod = (await import(localSharp)).default;
      }
    }
    if (sharpMod) {
      await sharpMod(Buffer.from(svgContent)).png().toFile(pngPath);
      pngSuccess = true;
      console.log(`[gen-og] Rendered high-fidelity raster PNG via sharp at ${pngPath}`);
    }
  } catch (err) {
    console.warn('[gen-og] sharp render failed or unavailable:', err);
  }

  if (!pngSuccess) {
    const pngBuffer = createFallbackPng(WIDTH, HEIGHT);
    fs.writeFileSync(pngPath, pngBuffer);
    console.log(`[gen-og] Rendered pure-Node raster fallback PNG at ${pngPath} (${pngBuffer.length} bytes)`);
  }

  return { svgPath, pngPath };
}

// Direct execution when run via CLI
if (process.argv[1] && (process.argv[1].endsWith('gen-og.ts') || process.argv[1].endsWith('gen-og.js'))) {
  generateOpenGraphCards()
    .then(({ svgPath, pngPath }) => {
      console.log(`[gen-og] Complete. Output:\n  ${svgPath}\n  ${pngPath}`);
    })
    .catch((err) => {
      console.error('[gen-og] Fatal error:', err);
      process.exit(1);
    });
}
