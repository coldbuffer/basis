/** Model provider brand icons via `@lobehub/icons` (LobeHub logo set). */
import type { ComponentType } from 'react';
import {
  DeepSeek,
  Minimax,
  Moonshot,
  Ollama,
  OpenAI,
  OpenRouter,
  Zhipu,
} from '@lobehub/icons';
import { cn } from '@/lib/utils.js';

type ProviderIconComponent = ComponentType<{ size?: number; className?: string }> & {
  Color?: ComponentType<{ size?: number; className?: string }>;
};

const ICON_BY_PROVIDER_ID: Record<string, ProviderIconComponent> = {
  deepseek: DeepSeek,
  openai: OpenAI,
  openrouter: OpenRouter,
  zhipu: Zhipu,
  minimax: Minimax,
  moonshot: Moonshot,
  ollama: Ollama,
};

type Props = {
  providerId: string;
  size?: number;
  className?: string;
};

export function ModelProviderIcon({ providerId, size = 18, className }: Props) {
  const Icon = ICON_BY_PROVIDER_ID[providerId.trim().toLowerCase()];
  if (!Icon) {
    return (
      <span
        className={cn(
          'inline-flex shrink-0 items-center justify-center rounded-md bg-foreground/[0.06] text-[10px] font-semibold uppercase text-muted-foreground',
          className,
        )}
        style={{ width: size, height: size }}
        aria-hidden
      >
        ···
      </span>
    );
  }
  const Component = Icon.Color ?? Icon;
  return (
    <span
      className={cn('inline-flex shrink-0 items-center justify-center leading-none', className)}
      aria-hidden
    >
      <Component size={size} className="block" />
    </span>
  );
}
