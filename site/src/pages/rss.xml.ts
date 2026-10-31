import type { APIRoute } from 'astro';

export const GET: APIRoute = async (context) => {
  const siteUrl = (context.site ? context.site.toString() : 'https://studiobridge.dev').replace(/\/$/, '');

  const releases = [
    {
      version: 'v1.0.0',
      title: 'StudioBridge v1.0.0 — General Availability: HTTP Daemon, MCPB Bundle & Native ARM64',
      link: `${siteUrl}/changelog#v1.0.0`,
      pubDate: 'Sat, 31 Oct 2026 12:00:00 GMT',
      description:
        'General Availability release introducing the local loopback HTTP REST server and Streamable HTTP transport, Claude Desktop MCPB bundle distribution, Cloudflare edge deployment with strict security headers, native ARM64 toolchain and differential parity testing, and zero-trust security audit enforcement.',
    },
    {
      version: 'v0.6.0',
      title: 'StudioBridge v0.6.0 — Landing Page, Starlight Docs & Design System',
      link: `${siteUrl}/changelog#v0.6.0`,
      pubDate: 'Sun, 26 Oct 2026 00:00:00 GMT',
      description:
        'Launch of the official StudioBridge static site and documentation portal. Features the interactive Signal-Path hero diagram, truth-table capability matrix explorer for Windows ARM64 and x64, interactive console demo with authentic transcripts, complete Starlight documentation suite with 119 API function cards, automated llms.txt context compilation, OpenGraph social card generation, and comprehensive SEO/GEO schema.org metadata.',
    },
    {
      version: 'v0.5.0',
      title: 'StudioBridge v0.5.0 — Offline FLP Engine & Binary Codec',
      link: `${siteUrl}/changelog#v0.5.0`,
      pubDate: 'Sat, 25 Oct 2026 12:00:00 GMT',
      description:
        'Complete offline FLP binary codec featuring lossless round-trip parsing, AST-level mutation, structural invariant validation, seed template instantiation, and offline FLP MCP tools. Enables agent inspection and generation of FL Studio project files without running the host DAW application.',
    },
    {
      version: 'v0.4.0',
      title: 'StudioBridge v0.4.0 — Piano Roll Actuation & Render Orchestration',
      link: `${siteUrl}/changelog#v0.4.0`,
      pubDate: 'Fri, 24 Oct 2026 12:00:00 GMT',
      description:
        'Implementation of focus-guarded Win32 window actuation and keyboard macro automation for native piano-roll note application. Added headless FL Studio command-line render supervision with process lifecycle management and acoustic quality analysis (dBFS peaks, loudness, clipping detection).',
    },
    {
      version: 'v0.3.0',
      title: 'StudioBridge v0.3.0 — Model Context Protocol (MCP) Server',
      link: `${siteUrl}/changelog#v0.3.0`,
      pubDate: 'Thu, 23 Oct 2026 12:00:00 GMT',
      description:
        'Production Model Context Protocol (MCP) server exposing tools for DAW inspection, live transport/mixer/channel control, safety modes, and mutation journaling. Includes one-line automated agent installer templates supporting 10 coding agents and IDEs.',
    },
    {
      version: 'v0.2.0',
      title: 'StudioBridge v0.2.0 — Manifest & Core Python SDK',
      link: `${siteUrl}/changelog#v0.2.0`,
      pubDate: 'Wed, 22 Oct 2026 12:00:00 GMT',
      description:
        'Typed Python SDK wrapping the FL Studio controller API. Introduced read-back verification against configurable numerical tolerances, three safety interlock modes (read-only, write-permitted, protected targets), and an append-only mutation journal with rollback guarantees (G0-G2).',
    },
    {
      version: 'v0.1.0',
      title: 'StudioBridge v0.1.0 — Foundation, Wire Protocol & ctypes WinMM',
      link: `${siteUrl}/changelog#v0.1.0`,
      pubDate: 'Tue, 21 Oct 2026 12:00:00 GMT',
      description:
        'Initial release establishing the monorepo foundation, pure-Python ctypes WinMM virtual MIDI backend for Windows ARM64 and x64, 2-way SysEx RPC framing with CRC-16 CCITT verification, packet chunking/reassembly, and the 26-point sbridge doctor diagnostics suite.',
    },
  ];

  const itemsXml = releases
    .map(
      (r) => `    <item>
      <title>${escapeXml(r.title)}</title>
      <link>${escapeXml(r.link)}</link>
      <guid isPermaLink="true">${escapeXml(r.link)}</guid>
      <pubDate>${r.pubDate}</pubDate>
      <description><![CDATA[${r.description}]]></description>
    </item>`
    )
    .join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>StudioBridge Releases &amp; Changelog</title>
    <description>Release announcements, architecture updates, and changelog for StudioBridge — the agent bridge for FL Studio.</description>
    <link>${escapeXml(siteUrl)}/changelog</link>
    <atom:link href="${escapeXml(siteUrl)}/rss.xml" rel="self" type="application/rss+xml" />
    <language>en-us</language>
    <lastBuildDate>${releases[0].pubDate}</lastBuildDate>
${itemsXml}
  </channel>
</rss>`;

  return new Response(xml, {
    status: 200,
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
    },
  });
};

function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
