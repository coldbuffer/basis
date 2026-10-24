import type { ModelKind } from '@/components/admin/models/model-endpoint-panel.js';

export type ConfiguredModelRow = {
  id: string;
  kind: ModelKind;
  provider: string;
  api_base: string;
  model: string;
  display_name: string;
  enabled: boolean;
  configured: boolean;
};

export type ConfiguredModelGroup = {
  key: string;
  provider: string;
  api_base: string;
  models: ConfiguredModelRow[];
};

export function groupConfiguredModels(models: ConfiguredModelRow[]): ConfiguredModelGroup[] {
  const map = new Map<string, ConfiguredModelGroup>();
  for (const model of models) {
    const provider = model.provider || 'custom';
    const apiBase = model.api_base || '';
    const key = `${provider}\u0000${apiBase}`;
    const existing = map.get(key);
    if (existing) {
      existing.models.push(model);
    } else {
      map.set(key, { key, provider, api_base: apiBase, models: [model] });
    }
  }
  return [...map.values()].sort((a, b) => {
    const byProvider = a.provider.localeCompare(b.provider);
    if (byProvider !== 0) return byProvider;
    return a.api_base.localeCompare(b.api_base);
  });
}
