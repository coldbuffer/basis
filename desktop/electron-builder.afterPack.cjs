const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

/** @param {import('electron-builder').AfterPackContext} context */
module.exports = async function afterPack(context) {
  const product = context.packager.appInfo.productFilename;
  let resourcesDir;
  if (context.electronPlatformName === 'darwin') {
    resourcesDir = path.join(context.appOutDir, `${product}.app`, 'Contents', 'Resources');
  } else if (context.electronPlatformName === 'win32') {
    resourcesDir = path.join(context.appOutDir, 'resources');
  } else {
    resourcesDir = path.join(context.appOutDir, 'resources');
  }

  const venvDir = path.join(resourcesDir, 'sidecar', 'venv');
  if (!fs.existsSync(venvDir)) return;

  const relocateUrl = pathToFileURL(
    path.join(__dirname, 'scripts', 'relocate-packaged-venv.mjs'),
  ).href;
  const { finalizePackagedSidecar } = await import(relocateUrl);
  finalizePackagedSidecar(venvDir);
  console.log('[afterPack] Finalized bundled Python sidecar:', venvDir);
};
