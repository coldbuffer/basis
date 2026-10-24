import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, it } from 'node:test';

import {
  materializeCopiedTree,
  normalizeWindowsPython3Launcher,
  relocatePackagedVenv,
} from './relocate-packaged-venv.mjs';

describe('materializeCopiedTree', () => {
  it('replaces file symlinks with real files', () => {
    if (process.platform === 'win32') return;
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'basis-mat-'));
    const target = path.join(root, 'python.exe');
    const link = path.join(root, 'python3.exe');
    fs.writeFileSync(target, 'stub');
    fs.symlinkSync(target, link);
    assert.ok(fs.lstatSync(link).isSymbolicLink());

    materializeCopiedTree(root);
    assert.ok(fs.statSync(link).isFile());
    assert.ok(!fs.lstatSync(link).isSymbolicLink());
    fs.rmSync(root, { recursive: true, force: true });
  });
});

describe('materializeCopiedTree dangling python links', () => {
  it('replaces broken python3 symlink with versioned binary', () => {
    if (process.platform === 'win32') return;
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'basis-py-dangle-'));
    const bin = path.join(root, 'bin');
    fs.mkdirSync(bin, { recursive: true });
    const py313 = path.join(bin, 'python3.13');
    fs.writeFileSync(py313, '#!/bin/sh\nexit 0\n');
    fs.chmodSync(py313, 0o755);
    fs.symlinkSync('/nonexistent/python3.13', path.join(bin, 'python3'));
    materializeCopiedTree(bin);
    assert.ok(fs.statSync(path.join(bin, 'python3')).isFile());
    fs.rmSync(root, { recursive: true, force: true });
  });
});

describe('relocatePackagedVenv', () => {
  it('rewrites console script shebangs to bundled python', () => {
    if (process.platform === 'win32') return;
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'basis-reloc-'));
    const sidecar = path.join(root, 'sidecar');
    const venv = path.join(sidecar, 'venv');
    const bin = path.join(venv, 'bin');
    const runtimeBin = path.join(sidecar, 'runtime', 'cpython', 'bin');
    fs.mkdirSync(bin, { recursive: true });
    fs.mkdirSync(runtimeBin, { recursive: true });
    const py = path.join(bin, 'python3.12');
    fs.writeFileSync(py, '');
    fs.chmodSync(py, 0o755);
    fs.writeFileSync(path.join(runtimeBin, 'python3'), '');
    fs.writeFileSync(path.join(venv, 'pyvenv.cfg'), 'home = /tmp\n');
    const basis = path.join(bin, 'basis');
    fs.writeFileSync(basis, '#!/bad/python3\nprint("ok")\n');
    fs.chmodSync(basis, 0o755);
    relocatePackagedVenv(venv);
    const first = fs.readFileSync(basis, 'utf8').split('\n')[0];
    assert.equal(first, '#!./python3.12');
    const cfg = fs.readFileSync(path.join(venv, 'pyvenv.cfg'), 'utf8');
    assert.match(cfg, /^home = \.\.\/runtime\/cpython\/bin/m);
    fs.rmSync(root, { recursive: true, force: true });
  });
});

describe('normalizeWindowsPython3Launcher', () => {
  it('no-op on unix', () => {
    if (process.platform === 'win32') return;
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'basis-py3-'));
    const py = path.join(root, 'python.exe');
    fs.writeFileSync(py, 'a');
    normalizeWindowsPython3Launcher(root);
    assert.ok(!fs.existsSync(path.join(root, 'python3.exe')));
    fs.rmSync(root, { recursive: true, force: true });
  });
});
