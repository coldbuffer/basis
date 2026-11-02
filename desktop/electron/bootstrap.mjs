import { spawnBasisApi, waitForHttp } from './server-manager.mjs';
import { loadPackagedApiManifest } from './api-manifest.mjs';
import { isPackagedApp, packagedProfilePath, packagedWebDir, resolveRepoRoot } from './paths.mjs';
import { startStaticServer } from './static-server.mjs';

let apiChild = null;
let staticServer = null;

export async function bootstrapDesktopShell() {
  const packaged = isPackagedApp();
  const resourcesPath = packaged ? process.resourcesPath : undefined;
  const manifest = loadPackagedApiManifest(resourcesPath);
  const repoRoot = manifest?.kind === 'bundled-venv' ? resourcesPath : resolveRepoRoot();
  const profilePath = packagedProfilePath() ?? undefined;
  const { child, apiBase } = await spawnBasisApi({
    repoRoot,
    profilePath,
    resourcesPath,
    apiManifest: manifest,
  });
  apiChild = child;

  let webUrl = process.env.BASIS_DESKTOP_WEB_URL;
  if (!webUrl && isPackagedApp()) {
    const webDir = packagedWebDir();
    if (!webDir) throw new Error('Packaged web assets missing');
    const { server, url } = await startStaticServer(webDir, {
      host: '127.0.0.1',
      port: 0,
      apiProxyTarget: apiBase,
    });
    staticServer = server;
    webUrl = url;
  }
  if (!webUrl) {
    webUrl = 'http://127.0.0.1:3002';
    await waitForHttp(webUrl, 5_000).catch(() => {
      throw new Error('Dev renderer not running. Use `cd desktop && npm run dev` or set BASIS_DESKTOP_WEB_URL.');
    });
  }

  return { apiBase, webUrl, repoRoot };
}

export function shutdownDesktopShell() {
  if (apiChild) {
    try {
      apiChild.kill('SIGTERM');
    } catch {
      // ignore
    }
    apiChild = null;
  }
  if (staticServer) {
    try {
      staticServer.close();
    } catch {
      // ignore
    }
    staticServer = null;
  }
}
