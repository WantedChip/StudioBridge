/**
 * LLM Context Documentation Compiler
 *
 * Compiles site/public/llms-full.txt from site/src/content/docs/docs/.
 * Produces clean, consolidated Markdown for AI/LLM consumption with:
 * - Starlight frontmatter parsed and converted to clean markdown headers/blockquotes.
 * - All HTML tags (<details>, <summary>, <div>, <span>) stripped or converted.
 * - Complete coverage of Overview, Quickstart, Control Planes, Wire Protocol, Doctor Checks, and API Cards.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const candidatesDocs = [
  path.resolve(__dirname, '../src/content/docs/docs'),
  path.resolve(process.cwd(), 'site/src/content/docs/docs'),
  path.resolve(process.cwd(), 'src/content/docs/docs'),
];
const foundDocsDir = candidatesDocs.find((d) => fs.existsSync(d));
if (!foundDocsDir) {
  console.error(`ERROR: docs directory not found in candidates:\n${candidatesDocs.join('\n')}`);
  process.exit(1);
}
const docsDir: string = foundDocsDir;

const candidatesPublic = [
  path.resolve(__dirname, '../public'),
  path.resolve(process.cwd(), 'site/public'),
  path.resolve(process.cwd(), 'public'),
];
const publicDir = candidatesPublic.find((d) => fs.existsSync(d)) || candidatesPublic[0];
if (!fs.existsSync(publicDir)) {
  fs.mkdirSync(publicDir, { recursive: true });
}

function stripHtml(markdown: string): string {
  // Convert <summary>(.*?)</summary> to bold text
  let text = markdown.replace(/<summary>([\s\S]*?)<\/summary>/gi, '\n**$1**\n');
  // Convert line breaks and hr
  text = text.replace(/<br\s*\/?>/gi, '\n');
  text = text.replace(/<hr\s*\/?>/gi, '\n---\n');
  // Remove all other HTML tags
  text = text.replace(/<\/?[a-zA-Z][^>]*>/g, '');
  // Unescape standard html entities
  text = text
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&rarr;/g, '->')
    .replace(/&larr;/g, '<-')
    .replace(/&sect;/g, '§')
    .replace(/&copy;/g, '(C)');
  return text;
}

function cleanMarkdown(raw: string, fallbackTitle?: string): string {
  let title = fallbackTitle || '';
  let description = '';
  let body = raw;

  if (raw.startsWith('---')) {
    const end = raw.indexOf('---', 3);
    if (end !== -1) {
      const frontmatter = raw.slice(3, end);
      body = raw.slice(end + 3).trim();
      const titleMatch = frontmatter.match(/title:\s*["']?([^"'\n\r]+)["']?/);
      if (titleMatch) title = titleMatch[1].trim();
      const descMatch = frontmatter.match(/description:\s*["']?([^"'\n\r]+)["']?/);
      if (descMatch) description = descMatch[1].trim();
    }
  }

  let cleaned = stripHtml(body).trim();
  const parts: string[] = [];

  if (title && !cleaned.startsWith('# ') && !cleaned.startsWith('## ')) {
    parts.push(`## ${title}\n`);
  }
  if (description) {
    parts.push(`> ${description}\n`);
  }
  parts.push(cleaned);
  return parts.join('\n');
}

export function compileLlmsFull(): { outputPath: string; charCount: number; sectionCount: number } {
  const sections: string[] = [];

  // 1. Master Header
  sections.push(`# StudioBridge — Consolidated Documentation Suite (llms-full.txt)

> Comprehensive reference documentation for StudioBridge — the agent bridge for FL Studio.
> Read, edit, and render FL Studio projects from any coding agent — verified, reversible, local.
> Generated at build-time from site/src/content/docs/docs/ for AI/LLM context injection.
> License: MIT (Copyright (C) 2026 WantedChip). Zero telemetry, 100% local.

---
`);

  // 2. Table of Contents
  sections.push(`## Documentation Index
1. [Overview & Architecture](#1-overview--architecture)
2. [Getting Started & Quickstart](#2-getting-started--quickstart)
3. [Control Planes Deep Dive](#3-control-planes-deep-dive)
4. [SysEx Wire Protocol Specification](#4-sysex-wire-protocol-specification)
5. [Troubleshooting & Doctor Checks Directory](#5-troubleshooting--doctor-checks-directory)
6. [API Reference Overview](#6-api-reference-overview)
7. [API Module Reference](#7-api-module-reference)
8. [API Function Cards](#8-api-function-cards)

---
`);

  let sectionCount = 0;

  // Section 1: Overview
  const indexPath = path.join(docsDir, 'index.md');
  if (fs.existsSync(indexPath)) {
    sections.push(`## 1. Overview & Architecture\n`);
    sections.push(cleanMarkdown(fs.readFileSync(indexPath, 'utf8'), 'Overview'));
    sections.push('\n---\n');
    sectionCount++;
  }

  // Section 2: Quickstart
  const quickstartPath = path.join(docsDir, 'getting-started/quickstart.md');
  if (fs.existsSync(quickstartPath)) {
    sections.push(`## 2. Getting Started & Quickstart\n`);
    sections.push(cleanMarkdown(fs.readFileSync(quickstartPath, 'utf8'), 'Quickstart Guide'));
    sections.push('\n---\n');
    sectionCount++;
  }

  // Section 3: Control Planes
  const planesPath = path.join(docsDir, 'architecture/control-planes.md');
  if (fs.existsSync(planesPath)) {
    sections.push(`## 3. Control Planes Deep Dive\n`);
    sections.push(cleanMarkdown(fs.readFileSync(planesPath, 'utf8'), 'Control Planes'));
    sections.push('\n---\n');
    sectionCount++;
  }

  // Section 4: Wire Protocol
  const wirePath = path.join(docsDir, 'architecture/wire-protocol.md');
  if (fs.existsSync(wirePath)) {
    sections.push(`## 4. SysEx Wire Protocol Specification\n`);
    sections.push(cleanMarkdown(fs.readFileSync(wirePath, 'utf8'), 'Wire Protocol'));
    sections.push('\n---\n');
    sectionCount++;
  }

  // Section 5: Doctor Checks Directory
  const doctorPath = path.join(docsDir, 'troubleshooting/doctor-checks.md');
  if (fs.existsSync(doctorPath)) {
    sections.push(`## 5. Troubleshooting & Doctor Checks Directory\n`);
    sections.push(cleanMarkdown(fs.readFileSync(doctorPath, 'utf8'), 'Doctor Checks Directory'));
    sections.push('\n---\n');
    sectionCount++;
  }

  // Section 6: API Overview
  const apiIndexPath = path.join(docsDir, 'api/index.md');
  if (fs.existsSync(apiIndexPath)) {
    sections.push(`## 6. API Reference Overview\n`);
    sections.push(cleanMarkdown(fs.readFileSync(apiIndexPath, 'utf8'), 'API Overview'));
    sections.push('\n---\n');
    sectionCount++;
  }

  // Section 7: API Modules (8 modules)
  const apiModules = ['channels', 'device', 'general', 'mixer', 'patterns', 'plugins', 'transport', 'ui'];
  sections.push(`## 7. API Module Reference\n`);
  for (const mod of apiModules) {
    const modFile = path.join(docsDir, `api/${mod}.md`);
    if (fs.existsSync(modFile)) {
      sections.push(`### Module: ${mod}\n`);
      sections.push(cleanMarkdown(fs.readFileSync(modFile, 'utf8'), `Module: ${mod}`));
      sections.push('\n');
      sectionCount++;
    }
  }
  sections.push('---\n');

  // Section 8: API Function Cards
  sections.push(`## 8. API Function Cards\n`);
  for (const mod of apiModules) {
    const modDir = path.join(docsDir, `api/${mod}`);
    if (fs.existsSync(modDir)) {
      const cardFiles = fs.readdirSync(modDir).filter((f) => f.endsWith('.md')).sort();
      for (const cardFile of cardFiles) {
        const fullCardPath = path.join(modDir, cardFile);
        const funcName = path.basename(cardFile, '.md');
        sections.push(`#### ${mod}.${funcName}\n`);
        sections.push(cleanMarkdown(fs.readFileSync(fullCardPath, 'utf8'), `${mod}.${funcName}`));
        sections.push('\n');
        sectionCount++;
      }
    }
  }

  const fullText = sections.join('\n');
  const outputPath = path.join(publicDir, 'llms-full.txt');
  fs.writeFileSync(outputPath, fullText, 'utf8');

  console.log(`[gen-llms] Generated ${outputPath} (${fullText.length} characters, ${sectionCount} documentation items)`);
  return { outputPath, charCount: fullText.length, sectionCount };
}

// Direct execution CLI
if (process.argv[1] && (process.argv[1].endsWith('gen-llms.ts') || process.argv[1].endsWith('gen-llms.js'))) {
  try {
    compileLlmsFull();
  } catch (err) {
    console.error('[gen-llms] Fatal error:', err);
    process.exit(1);
  }
}
