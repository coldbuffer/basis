import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const desktopRoot = path.resolve(__dirname, '..');
export const repoRoot = path.resolve(desktopRoot, '..');

/** Staged Basis API sidecar (Fellow `.gateway-stage` analogue). */
export const apiStageDir = path.join(desktopRoot, '.api-stage');

export const webDistDir = path.join(repoRoot, 'dist', 'web');

export const profilesDir = path.join(repoRoot, 'contracts', 'profiles');
