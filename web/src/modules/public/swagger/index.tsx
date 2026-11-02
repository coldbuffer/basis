import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import SwaggerUI from 'swagger-ui-react';
import 'swagger-ui-react/swagger-ui.css';
import { ProductSiteHeader } from '@/components/app/marketing/product-site-header.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { useI18n } from '@/i18n/context.js';
import { productDocsPageMeta } from '@/modules/public/docs/lib/product-docs-page-meta.js';
import { getToken } from '@/lib/session/auth-token.js';
import { openapiSpecUrl, type OpenApiSpecVariant } from '@/lib/openapi/spec-url.js';

export function SwaggerPage() {
  const { t, locale } = useI18n();
  const apiReferenceTitle =
    productDocsPageMeta(locale, 'api-reference')?.title ?? 'API reference';
  const p = t.swagger.page;
  const [variant, setVariant] = useState<OpenApiSpecVariant>('full');
  const specUrl = useMemo(() => openapiSpecUrl(variant), [variant]);

  useEffect(() => {
    const previous = document.title;
    document.title = `${apiReferenceTitle} — Basis`;
    return () => {
      document.title = previous;
    };
  }, [apiReferenceTitle]);

  const requestInterceptor = useMemo(
    () => (req: { headers?: Record<string, string> }) => {
      const token = getToken();
      if (token) {
        req.headers = { ...req.headers, Authorization: `Bearer ${token}` };
      }
      return req;
    },
    [],
  );

  return (
    <div className="flex h-dvh max-h-dvh flex-col overflow-hidden bg-background text-foreground">
      <ProductSiteHeader activeKey="developers" />
      <div className="flex min-h-0 flex-1 flex-col border-t border-border">
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 px-5 py-3 sm:px-8">
          <p className="text-sm text-muted-foreground">
            {p.subtitle}{' '}
            <Link to="/docs/api-reference" className="text-foreground underline-offset-4 hover:underline">
              {apiReferenceTitle}
            </Link>
          </p>
          <Select value={variant} onValueChange={(v) => setVariant(v as OpenApiSpecVariant)}>
            <SelectTrigger className="w-[220px]" size="sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="full">{p.spec_full}</SelectItem>
              <SelectItem value="platform">{p.spec_platform}</SelectItem>
              <SelectItem value="workspaces">{p.spec_workspace}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="basis-swagger-panel min-h-0 flex-1 overflow-auto">
          <SwaggerUI
            key={specUrl}
            url={specUrl}
            docExpansion="list"
            defaultModelsExpandDepth={-1}
            tryItOutEnabled
            requestInterceptor={requestInterceptor}
          />
        </div>
      </div>
    </div>
  );
}
