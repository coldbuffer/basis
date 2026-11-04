import type { ComponentType, SVGProps } from 'react';
import Clickhouse from '@thesvg/react/clickhouse';
import Databricks from '@thesvg/react/databricks';
import Duckdb from '@thesvg/react/duckdb';
import Mysql from '@thesvg/react/mysql';
import Postgresql from '@thesvg/react/postgresql';
import Snowflake from '@thesvg/react/snowflake';
import Sqlite from '@thesvg/react/sqlite';
import Trino from '@thesvg/react/trino';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';

type EngineIconProps = SVGProps<SVGSVGElement> & { variant?: 'default' };

const ICONS: Record<string, ComponentType<EngineIconProps>> = {
  postgres: Postgresql,
  postgresql: Postgresql,
  mysql: Mysql,
  sqlite: Sqlite,
  duckdb: Duckdb,
  clickhouse: Clickhouse,
  snowflake: Snowflake,
  databricks: Databricks,
  trino: Trino,
};

export function SqlCatalogEngineIcon({
  scheme,
  size = 16,
}: {
  scheme: string;
  size?: number;
}) {
  const Icon = ICONS[scheme.trim().toLowerCase()];
  if (!Icon) {
    return <PublicIcon name="database" size={size} className="text-muted-foreground" />;
  }
  return (
    <Icon
      width={size}
      height={size}
      variant="default"
      aria-hidden
      className="size-4 shrink-0 text-inherit"
    />
  );
}
