import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useRef, useState } from "react";
import { wsApiErrorMessage } from '@/lib/workspace/ws-api-error';
import { workspaceOpenApiPOST } from '@/lib/openapi/client.js';
import {
  ontologyApiSuffix,
  useOntologyWorkspaceId,
} from '@/components/app/shared/workspace/ontology-workspace-context.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.js";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs.js";
import { Button } from "@/components/ui/button.js";
import { Input } from "@/components/ui/input.js";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select.js";
import { Textarea } from "@/components/ui/textarea.js";
import { useI18n } from "@/i18n/context.js";
import { fmt, formatLocaleNumber } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import { cn } from "@/lib/utils.js";
import {
  ontBadgeBase,
  ontFormatBadgeClass,
  ontFormatBadgeFallback,
  ontInput,
  ontLabel,
  ontLoaderAdvancedToggle,
  ontLoaderDropzone,
  ontLoaderDropzoneActive,
  ontLoaderErrorBox,
  ontLoaderFieldGroup,
  ontLoaderModeTab,
  ontLoaderModeTabActive,
  ontLoaderModeTabIdle,
  ontLoaderPanelBody,
  ontLoaderPreviewCard,
  ontLoaderPreviewGrid,
  ontLoaderPreviewMetaLabel,
  ontLoaderPreviewMetaValue,
  ontLoaderPreviewMetaValueMono,
  ontLoaderPreviewTitle,
  ontLoaderSelect,
  ontLoaderSuccessBox,
  ontLoaderTextarea,
} from "@/lib/ui-classes/ontology-ui.js";

type LoaderMode = "url" | "file" | "create";
type CreateMode = "scratch" | "data" | "text";

interface OntologyPreview {
  uri: string;
  name: string;
  description?: string;
  namespace?: string;
  version?: string;
  license?: string;
  format: string;
  estimated_triples: number;
  source_url?: string;
}

interface LoaderProps {
  onLoaded: () => void;
  onClose: () => void;
}

function FormatBadge({ format }: { format: string }) {
  const { t } = useI18n();
  const key = format.toLowerCase();
  const labels = t.ontology.hub.manager.format_labels;
  const label = labels[key as keyof typeof labels] ?? format;
  return (
    <span
      className={cn(
        ontBadgeBase,
        ontFormatBadgeClass[key] ?? ontFormatBadgeFallback,
      )}
    >
      {label}
    </span>
  );
}

function FieldGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className={ontLoaderFieldGroup}>
      <label className={ontLabel}>{label}</label>
      {children}
    </div>
  );
}

function PreviewCard({ preview }: { preview: OntologyPreview }) {
  const { t, locale } = useI18n();
  const l = t.ontology.hub.loader;
  const m = t.ontology.hub.manager;
  return (
    <div className={ontLoaderPreviewCard}>
      <div className="mb-3 flex items-center gap-2">
        <PublicIcon name="check-circle" size={16} className="text-ok" />
        <span className="text-xs font-bold text-ok">{l.preview_ready}</span>
        <FormatBadge format={preview.format} />
      </div>

      <div className={ontLoaderPreviewTitle}>{preview.name}</div>
      {preview.description && (
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
          {preview.description}
        </p>
      )}

      <div className={ontLoaderPreviewGrid}>
        <PreviewRow label={l.namespace} value={preview.namespace || preview.uri} mono />
        {preview.version && <PreviewRow label={m.detail_version} value={preview.version} />}
        {preview.license && <PreviewRow label={l.license} value={preview.license} />}
        <PreviewRow
          label={l.estimated_triples}
          value={formatLocaleNumber(locale, preview.estimated_triples)}
        />
      </div>
    </div>
  );
}

function PreviewRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className={ontLoaderPreviewMetaLabel}>{label}</span>
      <span className={mono ? ontLoaderPreviewMetaValueMono : ontLoaderPreviewMetaValue}>
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// URL Import panel
// ---------------------------------------------------------------------------

function URLImportPanel({ onLoaded }: { onLoaded: () => void }) {
  const { t, locale } = useI18n();
  const l = t.ontology.hub.loader;
  const m = t.ontology.hub.manager;
  const workspaceId = useOntologyWorkspaceId();
  const [url, setUrl] = useState("");
  const [format, setFormat] = useState("");
  const [customName, setCustomName] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [preview, setPreview] = useState<OntologyPreview | null>(null);
  const [previewState, setPreviewState] = useState<"idle" | "loading" | "error">("idle");
  const [loadState, setLoadState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handlePreview = async () => {
    if (!url.trim()) return;
    setPreviewState("loading");
    setPreview(null);
    setErrorMsg("");
    try {
      const preview = await workspaceOpenApiPOST<OntologyPreview>(
        workspaceId,
        ontologyApiSuffix('preview'),
        { body: { url: url.trim(), format: format || undefined } },
      );
      setPreview(preview);
      setPreviewState("idle");
    } catch (e) {
      setPreviewState("error");
      setErrorMsg(wsApiErrorMessage(e, locale as Locale));
    }
  };

  const handleLoad = async () => {
    if (!url.trim()) return;
    setLoadState("loading");
    try {
      await workspaceOpenApiPOST(workspaceId, ontologyApiSuffix('load'), {
        body: {
          url: url.trim(),
          format: format || undefined,
          name: customName || undefined,
          description: description || undefined,
          tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
        },
      });
      setLoadState("success");
      setTimeout(() => {
        setLoadState("idle");
        onLoaded();
      }, 1200);
    } catch (e) {
      setLoadState("error");
      setErrorMsg(wsApiErrorMessage(e, locale as Locale));
    }
  };

  return (
    <div className={ontLoaderPanelBody}>
      <FieldGroup label={l.ontology_url}>
        <div className="flex gap-2">
          <Input
            type="url"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setPreview(null);
              setPreviewState("idle");
            }}
            placeholder={l.url_placeholder}
            className={cn(ontInput, "min-w-0 flex-1")}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handlePreview}
            disabled={!url.trim() || previewState === "loading"}
            className="shrink-0"
          >
            {previewState === "loading" ? (
              <PublicIcon name="loader-01" size={13} className="animate-spin" />
            ) : (
              l.fetch_preview
            )}
          </Button>
        </div>
      </FieldGroup>

      {previewState === "error" && (
        <div className={ontLoaderErrorBox}>
          <PublicIcon name="alert-circle" size={13} />
          <span>{errorMsg}</span>
        </div>
      )}

      {preview && <PreviewCard preview={preview} />}

      <Button
        type="button"
        variant="ghost"
        onClick={() => setShowAdvanced((v) => !v)}
        className={cn(ontLoaderAdvancedToggle, "h-auto justify-start font-normal")}
      >
        <PublicIcon name="chevron-down"
          size={13}
          className={cn("transition-transform duration-200", showAdvanced && "rotate-180")}
        />
        {l.advanced_options}
      </Button>

      {showAdvanced && (
        <div className="flex flex-col gap-3">
          <FieldGroup label={l.format_override}>
            <div className="native-select--full">
              <NativeSelect
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className={ontLoaderSelect}
              >
                <NativeSelectOption value="">{l.format_auto}</NativeSelectOption>
                <NativeSelectOption value="turtle">{l.format_select_extended.turtle}</NativeSelectOption>
                <NativeSelectOption value="xml">{l.format_select_extended.xml}</NativeSelectOption>
                <NativeSelectOption value="nt">{l.format_select_extended.nt}</NativeSelectOption>
                <NativeSelectOption value="json-ld">{l.format_select_extended.json_ld}</NativeSelectOption>
              </NativeSelect>
            </div>
          </FieldGroup>
          <FieldGroup label={l.custom_display_name}>
            <Input
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder={l.custom_name_placeholder}
              className={ontInput}
            />
          </FieldGroup>
          <FieldGroup label={m.detail_description}>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={l.description_optional}
              className={ontInput}
            />
          </FieldGroup>
          <FieldGroup label={l.tags_comma}>
            <Input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder={l.tags_placeholder_url}
              className={ontInput}
            />
          </FieldGroup>
        </div>
      )}

      {loadState === "success" && (
        <div className={ontLoaderSuccessBox}>
          <PublicIcon name="check-circle" size={13} />
          <span>{l.load_success}</span>
        </div>
      )}

      {loadState === "error" && (
        <div className={ontLoaderErrorBox}>
          <PublicIcon name="alert-circle" size={13} />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="mt-1 flex justify-end gap-2">
        <Button
          type="button"
          size="sm"
          onClick={handleLoad}
          disabled={!url.trim() || loadState === "loading"}
        >
          {loadState === "loading" ? (
            <>
              <PublicIcon name="loader-01" size={13} className="animate-spin" />
              {t.core.common.loading}
            </>
          ) : (
            <>
              <PublicIcon name="globe-02" size={13} />
              {m.load_ontology}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// File Upload panel
// ---------------------------------------------------------------------------

function FileUploadPanel({ onLoaded }: { onLoaded: () => void }) {
  const { t, locale } = useI18n();
  const l = t.ontology.hub.loader;
  const mgr = t.ontology.hub.manager;
  const workspaceId = useOntologyWorkspaceId();
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState("");
  const [content, setContent] = useState("");
  const [format, setFormat] = useState("");
  const [loadState, setLoadState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [dragging, setDragging] = useState(false);

  const handleFile = (file: File) => {
    setFileName(file.name);
    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    const fmtMap: Record<string, string> = {
      ttl: "turtle", rdf: "xml", owl: "xml", xml: "xml",
      nt: "nt", jsonld: "json-ld", json: "json-ld",
    };
    // Leave format empty for unknown extensions so the backend auto-detects
    setFormat(fmtMap[ext] ?? "");
    const reader = new FileReader();
    reader.onload = (e) => setContent(e.target?.result as string || "");
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleLoad = async () => {
    if (!content) return;
    setLoadState("loading");
    try {
      await workspaceOpenApiPOST(workspaceId, ontologyApiSuffix('load'), {
        body: { content, ...(format ? { format } : {}) },
      });
      setLoadState("success");
      setTimeout(() => {
        setLoadState("idle");
        onLoaded();
      }, 1200);
    } catch (e) {
      setLoadState("error");
      setErrorMsg(wsApiErrorMessage(e, locale as Locale));
    }
  };

  return (
    <div className={ontLoaderPanelBody}>
      <div
        className={cn(ontLoaderDropzone, dragging && ontLoaderDropzoneActive)}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
      >
        <PublicIcon name="upload-01" size={24} className="text-primary" />
        {fileName ? (
          <div className="text-sm font-semibold text-foreground">{fileName}</div>
        ) : (
          <>
            <div className="text-sm text-muted-foreground">
              {l.drop_file_prefix}
              <span className="text-primary">{l.browse}</span>
            </div>
            <div className="text-[11px] text-muted-foreground">{l.drop_extensions}</div>
          </>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".ttl,.rdf,.owl,.nt,.jsonld,.json,.xml,.n3"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />
      </div>

      {content && (
        <FieldGroup label={l.format}>
          <div className="native-select--full">
            <NativeSelect
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              className={ontLoaderSelect}
            >
              <NativeSelectOption value="turtle">{mgr.format_labels.turtle}</NativeSelectOption>
              <NativeSelectOption value="xml">{mgr.format_labels.xml}</NativeSelectOption>
              <NativeSelectOption value="nt">{mgr.format_labels.nt}</NativeSelectOption>
              <NativeSelectOption value="json-ld">{mgr.format_labels.json_ld}</NativeSelectOption>
            </NativeSelect>
          </div>
        </FieldGroup>
      )}

      {loadState === "success" && (
        <div className={ontLoaderSuccessBox}>
          <PublicIcon name="check-circle" size={13} />
          <span>{fmt(l.load_success_file, { file: fileName })}</span>
        </div>
      )}

      {loadState === "error" && (
        <div className={ontLoaderErrorBox}>
          <PublicIcon name="alert-circle" size={13} />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          type="button"
          size="sm"
          onClick={handleLoad}
          disabled={!content || loadState === "loading"}
        >
          {loadState === "loading" ? (
            <>
              <PublicIcon name="loader-01" size={13} className="animate-spin" />
              {t.core.common.loading}
            </>
          ) : (
            <>
              <PublicIcon name="upload-01" size={13} />
              {l.load_file}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create New panel
// ---------------------------------------------------------------------------

function CreateNewPanel({ onLoaded }: { onLoaded: () => void }) {
  const { t, locale } = useI18n();
  const l = t.ontology.hub.loader;
  const m = t.ontology.hub.manager;
  const workspaceId = useOntologyWorkspaceId();
  const [createMode, setCreateMode] = useState<CreateMode>("scratch");
  const [namespace, setNamespace] = useState("https://example.org/ontology/");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [sampleData, setSampleData] = useState("");
  const [schemaText, setSchemaText] = useState("");
  const [createState, setCreateState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleCreate = async () => {
    if (!name.trim() || !namespace.trim()) return;
    setCreateState("loading");
    try {
      await workspaceOpenApiPOST(workspaceId, ontologyApiSuffix('create'), {
        body: {
          mode: createMode,
          namespace: namespace.trim(),
          name: name.trim(),
          description: description || undefined,
          tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
          sample_data: createMode === "data" ? sampleData : undefined,
          schema_text: createMode === "text" ? schemaText : undefined,
        },
      });
      setCreateState("success");
      setTimeout(() => {
        setCreateState("idle");
        onLoaded();
      }, 1200);
    } catch (e) {
      setCreateState("error");
      setErrorMsg(wsApiErrorMessage(e, locale as Locale));
    }
  };

  return (
    <div className={ontLoaderPanelBody}>
      <div className="flex gap-1.5">
        {(["scratch", "data", "text"] as CreateMode[]).map((mode) => (
          <Button
            key={mode}
            type="button"
            variant="ghost"
            onClick={() => setCreateMode(mode)}
            className={cn(
              ontLoaderModeTab,
              "h-auto font-normal",
              createMode === mode ? ontLoaderModeTabActive : ontLoaderModeTabIdle,
            )}
          >
            {mode === "scratch"
              ? l.create_from_scratch
              : mode === "data"
                ? l.create_from_data
                : l.create_from_text}
          </Button>
        ))}
      </div>

      <FieldGroup label={l.display_name_required}>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={l.name_placeholder}
          className={ontInput}
        />
      </FieldGroup>

      <FieldGroup label={l.namespace_required}>
        <Input
          value={namespace}
          onChange={(e) => setNamespace(e.target.value)}
          placeholder={l.namespace_placeholder}
          className={ontInput}
        />
      </FieldGroup>

      <FieldGroup label={m.detail_description}>
        <Input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={l.description_optional}
          className={ontInput}
        />
      </FieldGroup>

      <FieldGroup label={l.tags_comma}>
        <Input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder={l.tags_placeholder_create}
          className={ontInput}
        />
      </FieldGroup>

      {createMode === "data" && (
        <FieldGroup label={l.sample_data}>
          <Textarea
            value={sampleData}
            onChange={(e) => setSampleData(e.target.value)}
            placeholder={l.sample_data_placeholder}
            rows={6}
            className={ontLoaderTextarea}
          />
        </FieldGroup>
      )}

      {createMode === "text" && (
        <FieldGroup label={l.schema_requirements}>
          <Textarea
            value={schemaText}
            onChange={(e) => setSchemaText(e.target.value)}
            placeholder={l.schema_placeholder}
            rows={6}
            className={ontLoaderTextarea}
          />
        </FieldGroup>
      )}

      {createState === "success" && (
        <div className={ontLoaderSuccessBox}>
          <PublicIcon name="check-circle" size={13} />
          <span>{l.create_success}</span>
        </div>
      )}

      {createState === "error" && (
        <div className={ontLoaderErrorBox}>
          <PublicIcon name="alert-circle" size={13} />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          type="button"
          size="sm"
          onClick={handleCreate}
          disabled={!name.trim() || !namespace.trim() || createState === "loading"}
        >
          {createState === "loading" ? (
            <>
              <PublicIcon name="loader-01" size={13} className="animate-spin" />
              {l.creating}
            </>
          ) : (
            <>
              <PublicIcon name="plus-01" size={13} />
              {l.create_ontology}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main OntologyLoader modal
// ---------------------------------------------------------------------------

export function OntologyLoader({ onLoaded, onClose }: LoaderProps) {
  const { t } = useI18n();
  const l = t.ontology.hub.loader;
  const [mode, setMode] = useState<LoaderMode>("url");

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="flex max-h-[min(92vh,44rem)] max-w-2xl flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
        <DialogHeader className="border-b border-border px-6 py-4 text-left">
          <DialogTitle>{l.dialog_title}</DialogTitle>
          <DialogDescription>{l.dialog_desc}</DialogDescription>
        </DialogHeader>

        <Tabs
          value={mode}
          onValueChange={(value) => setMode(value as LoaderMode)}
          className="flex min-h-0 flex-1 flex-col"
        >
          <TabsList className="mx-6 mt-4 w-auto justify-start">
            <TabsTrigger value="url" className="gap-1.5">
              <PublicIcon name="globe-02" size={12} />
              {l.tab_url}
            </TabsTrigger>
            <TabsTrigger value="file" className="gap-1.5">
              <PublicIcon name="upload-01" size={12} />
              {l.tab_file}
            </TabsTrigger>
            <TabsTrigger value="create" className="gap-1.5">
              <PublicIcon name="plus-01" size={12} />
              {l.tab_create}
            </TabsTrigger>
          </TabsList>

          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
            <TabsContent value="url" className="mt-0">
              <URLImportPanel onLoaded={onLoaded} />
            </TabsContent>
            <TabsContent value="file" className="mt-0">
              <FileUploadPanel onLoaded={onLoaded} />
            </TabsContent>
            <TabsContent value="create" className="mt-0">
              <CreateNewPanel onLoaded={onLoaded} />
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
