import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useImportVocabulary } from '../lib/queries.js';
import type { ImportResponse } from '../lib/types.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';
import { cn } from '@/lib/utils.js';
import {
  exWsVocabImportDropzone,
  exWsVocabImportDropzoneActive,
  exWsVocabImportError,
  exWsVocabImportStateCol,
  exWsVocabImportStateIcon,
  exWsVocabImportSuccessCol,
} from '@/lib/ui-classes/ws-ui.js';
import { govOhMuted } from '@/lib/ui-classes/governance-ui.js';
export const ImportDropzone: React.FC = () => {
  const { t, locale } = useI18n();
  const copy = t.vocabulary.page;
  const apiError = useApiErrorMessage();
  const [file, setFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const importMutation = useImportVocabulary();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const selectedFile = acceptedFiles[0];
    if (selectedFile) {
      setFile(selectedFile);
      setImportResult(null);

      importMutation.mutate(selectedFile, {
        onSuccess: (data) => {
          setImportResult(data);
          setTimeout(() => {
            setFile(null);
            setImportResult(null);
          }, 4000);
        },
        onError: () => {
          setFile(null);
        },
      });
    }
  }, [importMutation]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/turtle': ['.ttl'],
      'application/rdf+xml': ['.rdf', '.owl'],
    },
    maxFiles: 1,
  });

  return (
    <div>
      <div
        {...getRootProps()}
        className={cn(
          exWsVocabImportDropzone,
          isDragActive && exWsVocabImportDropzoneActive,
        )}
      >
        <input {...getInputProps()} />

        {importMutation.isPending ? (
          <div className={cn(govOhMuted, exWsVocabImportStateCol)}>
            <PublicIcon name='loader-01' className={cn('animate-spin', exWsVocabImportStateIcon)} size={20} />
            <span className="text-xs">{copy.uploading} {file?.name}…</span>
          </div>
        ) : importResult ? (
          <div className={exWsVocabImportSuccessCol}>
            <PublicIcon name='check-circle' className={exWsVocabImportStateIcon} size={20} />
            <span className="text-xs font-medium">{copy.import_ok}</span>
            <span className={cn(govOhMuted, 'mt-0.5 text-[11px]')}>
              {fmt(copy.added_summary, {
                nodes: formatLocaleNumber(locale, importResult.nodes_added),
                edges: formatLocaleNumber(locale, importResult.edges_added),
              })}
            </span>
          </div>
        ) : (
          <div className={exWsVocabImportStateCol}>
            <PublicIcon name='upload-01'
              className={cn(
                exWsVocabImportStateIcon,
                isDragActive ? 'text-primary' : 'text-muted-foreground',
              )}
              size={20}
            />
            <span className="text-xs font-medium text-foreground">
              {isDragActive ? copy.drop_active : copy.drop}
            </span>
            <span className={cn(govOhMuted, 'mt-0.5 text-[11px]')}>.ttl · .rdf · .owl</span>
          </div>
        )}
      </div>
      {importMutation.isError && (
        <p className={exWsVocabImportError}>{apiError(importMutation.error)}</p>
      )}
    </div>
  );
};
