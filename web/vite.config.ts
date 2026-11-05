import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { fumadocsMdx } from 'fumadocs-mdx/vite';
import { defineConfig, type PluginOption } from 'vite';

const root = path.dirname(fileURLToPath(import.meta.url));

function readDesktopPackageVersion(): string {
  try {
    const raw = fs.readFileSync(path.resolve(root, '../desktop/package.json'), 'utf8');
    return (JSON.parse(raw) as { version?: string }).version ?? '0.0.0';
  } catch {
    return '0.0.0';
  }
}

/** Same as `web/server/config.ts` — API origin for dev-server `/api` proxy (not sent to the browser). */
function desktopApiProxyTarget(): string {
  return (process.env.BASIS_API_URL ?? 'http://127.0.0.1:8090').replace(/\/$/, '');
}

function hmrFromEnv(): { port: number; clientPort: number } | undefined {
  const raw = process.env.WEB_HMR_PORT?.trim();
  if (!raw) return undefined;
  const port = Number(raw);
  return { port, clientPort: port };
}

export default defineConfig(({ mode }) => ({
  // Packaged desktop serves SPA over http://127.0.0.1 — use root-relative assets so
  // deep routes (/workspaces/...) still load /assets/* (relative `./` breaks after navigation).
  base: '/',
  define:
    mode === 'desktop'
      ? { 'import.meta.env.VITE_BASIS_APP_VERSION': JSON.stringify(readDesktopPackageVersion()) }
      : undefined,
  server:
    mode === 'desktop'
      ? {
          proxy: {
            '/api': { target: desktopApiProxyTarget(), changeOrigin: true },
            '/openapi': { target: desktopApiProxyTarget(), changeOrigin: true },
          },
          ...(() => {
            const hmr = hmrFromEnv();
            return hmr ? { hmr } : {};
          })(),
        }
      : hmrFromEnv()
        ? { hmr: hmrFromEnv() }
        : undefined,
  // plugin-react 4.0.0's default export types collapse under NodeNext, so the call is cast.
  plugins: [fumadocsMdx(), (react as unknown as () => PluginOption[])(), tailwindcss()],
  resolve: {
    dedupe: ['react', 'react-dom'],
    alias: [
      { find: /^@\/\.source/, replacement: `${path.resolve(root, '.source')}/` },
      { find: /^@\//, replacement: `${path.resolve(root, 'src')}/` },
    ],
  },
  optimizeDeps: {
    include: [
      'graphology',
      'sigma',
      '@sigma/edge-curve',
      '@sigma/node-border',
      'graphology-layout-forceatlas2',
      '@tanstack/react-query',
      'vis-data',
      'vis-timeline',
    ],
  },
  build: {
    outDir: path.resolve(root, '../dist/web'),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (id.includes('@phosphor-icons')) return 'phosphor';
          if (id.includes('@radix-ui') || id.includes('/radix-ui/')) return 'radix';
          if (
            id.includes('react-dom') ||
            id.includes('react-router') ||
            id.includes('/react/')
          ) {
            return 'react-vendor';
          }
        },
      },
    },
  },
}));
