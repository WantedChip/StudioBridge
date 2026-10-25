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
      customCss: ['./src/styles/tokens.css', './src/styles/global.css'],
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/WantedChip/studiobridge',
        },
      ],
      sidebar: [
        {
          label: 'Documentation',
          items: [
            { label: 'Overview', slug: 'docs' },
          ],
        },
      ],
    }),
    react(),
    sitemap(),
  ],
});
