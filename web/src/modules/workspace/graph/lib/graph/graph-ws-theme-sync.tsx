import { type ReactNode, useLayoutEffect } from 'react';

import { useTheme } from '@/lib/shell/theme.js';
import { syncBasisGraphTheme } from '@/modules/workspace/graph/lib/graph/basis-graph-theme-sync.js';

/** Apply Basis CSS tokens to graph theme before children mount (canvas/HUD). */
export function GraphWsThemeSync({ children }: { children: ReactNode }) {
  const { theme } = useTheme();

  useLayoutEffect(() => {
    syncBasisGraphTheme(theme);
  }, [theme]);

  return children;
}
