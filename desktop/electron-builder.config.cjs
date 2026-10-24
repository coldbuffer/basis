const fs = require('node:fs');
const path = require('node:path');

const desktopDir = __dirname;
const apiStage = path.join(desktopDir, '.api-stage');

const extraResources = [
  { from: '../dist/web', to: 'web', filter: ['**/*'] },
  { from: '../profiles', to: 'profiles', filter: ['**/*'] },
  { from: '.api-stage/api-manifest.json', to: 'api-manifest.json' },
];
if (fs.existsSync(path.join(apiStage, 'monorepo-root.json'))) {
  extraResources.push({ from: '.api-stage/monorepo-root.json', to: 'monorepo-root.json' });
}
if (fs.existsSync(path.join(apiStage, 'sidecar'))) {
  extraResources.push({ from: '.api-stage/sidecar', to: 'sidecar', filter: ['**/*'] });
}

/** @type {import('electron-builder').Configuration} */
module.exports = {
  appId: 'dev.basis.desktop',
  productName: 'Basis',
  directories: {
    output: 'release',
    buildResources: 'build',
  },
  files: ['electron/**/*', 'package.json'],
  extraResources,
  mac: {
    icon: 'build/icon.icns',
    category: 'public.app-category.productivity',
    target: [
      { target: 'dmg', arch: ['arm64', 'x64'] },
      { target: 'zip', arch: ['arm64', 'x64'] },
    ],
    hardenedRuntime: false,
    gatekeeperAssess: false,
    artifactName: '${productName}-${version}-darwin-${arch}.${ext}',
  },
  win: {
    icon: 'build/icon.ico',
    target: ['nsis', 'portable'],
    artifactName: '${productName}-${version}-win32-${arch}.${ext}',
  },
  nsis: {
    oneClick: false,
    allowToChangeInstallationDirectory: true,
  },
  linux: {
    target: ['dir'],
  },
  asar: true,
  afterPack: './electron-builder.afterPack.cjs',
};
