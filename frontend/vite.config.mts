import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';

// Builds the landing page into static/landing/ with stable file names. Django serves the output
// (WhiteNoise adds content hashes in production), so Node is only needed to rebuild it.
export default defineConfig({
  plugins: [react()],
  root: import.meta.dirname,
  publicDir: false,
  build: {
    outDir: resolve(import.meta.dirname, '../static/landing'),
    emptyOutDir: true,
    cssCodeSplit: false,
    target: 'es2020',
    rollupOptions: {
      input: resolve(import.meta.dirname, 'landing/main.tsx'),
      output: { entryFileNames: 'landing.js', chunkFileNames: 'landing-[name].js', assetFileNames: 'landing[extname]' },
    },
  },
});
