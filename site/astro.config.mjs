import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import react from '@astrojs/react';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  site: process.env.SITE_URL || 'https://studiobridge.dev',
  output: 'static',
  vite: {
    plugins: [tailwindcss()],
  },
  integrations: [
    starlight({
      title: 'StudioBridge Docs',
      customCss: ['./src/styles/tokens.css'],
      head: [
        {
          tag: 'meta',
          attrs: {
            name: 'theme-color',
            content: '#F3F0E8',
            media: '(prefers-color-scheme: light)',
          },
        },
        {
          tag: 'meta',
          attrs: {
            name: 'theme-color',
            content: '#0F0F0D',
            media: '(prefers-color-scheme: dark)',
          },
        },
      ],
      components: {
        ThemeProvider: './src/components/starlight/ThemeProvider.astro',
        ThemeSelect: './src/components/starlight/ThemeSelect.astro',
      },
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/WantedChip/studiobridge',
        },
      ],
      sidebar: [
        {
          label: 'Getting Started',
          items: [
            { label: 'Overview', slug: 'docs' },
            { label: 'Quickstart Guide', slug: 'docs/getting-started/quickstart' },
          ],
        },
        {
          label: 'Architecture',
          items: [
            { label: 'Control Planes', slug: 'docs/architecture/control-planes' },
            { label: 'Wire Protocol', slug: 'docs/architecture/wire-protocol' },
          ],
        },
        {
          label: 'Troubleshooting',
          items: [
            { label: 'Doctor Check Directory', slug: 'docs/troubleshooting/doctor-checks' },
          ],
        },
        {
          label: 'API Reference',
          items: [
            { label: 'Overview & Conventions', slug: 'docs/api' },
            { label: 'channels (Channel Rack)', slug: 'docs/api/channels' },
            { label: 'device (Hardware Surface)', slug: 'docs/api/device' },
            { label: 'general (DAW Engine)', slug: 'docs/api/general' },
            { label: 'mixer (Routing & Volume)', slug: 'docs/api/mixer' },
            { label: 'patterns (Clips & Piano Roll)', slug: 'docs/api/patterns' },
            { label: 'plugins (VST / AU Params)', slug: 'docs/api/plugins' },
            { label: 'transport (Playback & Tempo)', slug: 'docs/api/transport' },
            { label: 'ui (Windows & Focus)', slug: 'docs/api/ui' },
          ],
        },
      ],
    }),
    react(),
    sitemap(),
  ],
});
