/** Parse platform connector allowlist imports (JSON envelope or CSV). */

import { parseCsvLine } from '@/lib/admin/csv.js';

export type ParsedPlatformAllowlist = string[] | '*';

function parseEnabledFlag(raw: string | undefined): boolean {
  const v = (raw ?? '').trim().toLowerCase();
  return v === '1' || v === 'true' || v === 'yes' || v === 'y';
}

/**
 * CSV formats:
 * - `service` column only → every row is allowed
 * - `service` + `platform_enabled` / `platform_enabled_draft` / `enabled` → only true rows
 * - one service id per line (no header)
 * - single cell `*`
 */
export function parsePlatformAllowlistCsv(text: string): ParsedPlatformAllowlist | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (trimmed === '*') return '*';

  const lines = trimmed.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length === 0) return null;

  const headerCells = parseCsvLine(lines[0]).map((c) => c.trim().toLowerCase());
  const hasHeader = headerCells.includes('service');

  if (hasHeader) {
    const serviceIdx = headerCells.indexOf('service');
    const enabledIdx = headerCells.findIndex((h) =>
      ['platform_enabled', 'platform_enabled_draft', 'enabled', 'allow'].includes(h),
    );
    const services: string[] = [];
    for (let i = 1; i < lines.length; i++) {
      const cells = parseCsvLine(lines[i]);
      const service = cells[serviceIdx]?.trim();
      if (!service) continue;
      if (enabledIdx >= 0) {
        if (parseEnabledFlag(cells[enabledIdx])) services.push(service);
      } else {
        services.push(service);
      }
    }
    return services.length > 0 ? services : null;
  }

  const services: string[] = [];
  for (const line of lines) {
    const first = parseCsvLine(line)[0]?.trim();
    if (!first || first === '*') continue;
    services.push(first);
  }
  return services.length > 0 ? services : null;
}

export function parsePlatformAllowlistJson(text: string): ParsedPlatformAllowlist | null {
  const parsed = JSON.parse(text) as { allowed_providers?: string[] | string };
  const ap = parsed.allowed_providers;
  if (ap === '*') return '*';
  if (Array.isArray(ap)) {
    const services = ap.filter((s): s is string => typeof s === 'string' && s.trim().length > 0);
    return services.length > 0 ? services : null;
  }
  return null;
}

export function parsePlatformAllowlistFile(
  text: string,
  filename: string,
): ParsedPlatformAllowlist | null {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.csv')) {
    return parsePlatformAllowlistCsv(text);
  }
  try {
    return parsePlatformAllowlistJson(text);
  } catch {
    return parsePlatformAllowlistCsv(text);
  }
}
