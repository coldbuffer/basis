import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  wsApiErrorMessage,
  wsGetJson,
  wsMutationResult,
  wsPartialSuccessWarning,
  parseWsJson,
} from '@/lib/workspace/ws-api-error';
import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import { ontologyApiSuffix, useOntologyWorkspaceId } from "./ontology-workspace-context";
import { workspaceOntologyProposalPath } from "@/lib/nav/nav-config.js";
import { readOntologyUrlState, writeProposalSelection } from '../lib/ontology-url-state.js';
import { cn } from "@/lib/utils.js";
import { Button } from "@/components/ui/button.js";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.js";
import { Input } from "@/components/ui/input.js";
import { Label } from "@/components/ui/label.js";
import { useI18n } from "@/i18n/context.js";
import { fmt, formatLocaleDateTime, formatLocaleNumber } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import type { AnyLocaleMessages } from "@/i18n/pick-locale.js";

type VersionsLocale = AnyLocaleMessages['ontology']['hub']['versions'];

interface VersionEntry {
  version_id: string;
  ontology_uri: string;
  state: "draft" | "published";
  author: string;
  date: string;
  diff_summary: Record<string, any>;
}

function shaclSummaryLine(
  locale: Locale,
  shacl: Record<string, unknown>,
  sh: VersionsLocale["shacl"],
): string {
  if (!shacl || Object.keys(shacl).length === 0) return sh.none;
  const conforms = shacl.conforms ?? shacl.valid;
  const rawViolations = shacl.violations ?? shacl.results ?? shacl.report;
  const violationCount = Array.isArray(rawViolations) ? rawViolations.length : 0;
  if (typeof conforms === "boolean") {
    if (conforms) return sh.conforms;
    if (violationCount === 1) return sh.not_conforms_one;
    return fmt(sh.not_conforms, { count: formatLocaleNumber(locale, violationCount) });
  }
  if (violationCount > 0) {
    return fmt(sh.violations_listed, { count: formatLocaleNumber(locale, violationCount) });
  }
  return sh.see_report;
}

const IMPACT_KEY_MAP: Record<string, keyof VersionsLocale['impact']> = {
  classes_added: 'classes_added',
  classes_removed: 'classes_removed',
  properties_added: 'properties_added',
  properties_removed: 'properties_removed',
  individuals_added: 'individuals_added',
  individuals_removed: 'individuals_removed',
};

function impactSummaryLine(
  locale: Locale,
  impact: Record<string, unknown>,
  imp: VersionsLocale["impact"],
): string {
  if (!impact || Object.keys(impact).length === 0) return imp.none;
  const parts: string[] = [];
  for (const [key, templateKey] of Object.entries(IMPACT_KEY_MAP)) {
    const val = impact[key];
    if (typeof val === 'number' && val > 0 && templateKey !== 'none' && templateKey !== 'see_json') {
      parts.push(fmt(imp[templateKey] as string, { count: formatLocaleNumber(locale, val) }));
    }
  }
  if (parts.length) return parts.join(" · ");
  const summary = impact.summary ?? impact.message;
  if (typeof summary === "string" && summary.trim()) return summary.trim();
  return imp.see_json;
}

interface Proposal {
  proposal_id: string;
  draft_id: string;
  ontology_uri: string;
  summary: string;
  author: string;
  reviewer: string | null;
  state: "draft" | "proposed" | "approved" | "published" | "rejected";
  impact_analysis: Record<string, any>;
  shacl_validation: Record<string, any>;
  created_at: string;
  updated_at: string;
  comments: Record<string, any>[];
}

export function VersionsPanel() {
  const { t, locale } = useI18n();
  const v = t.ontology.hub.versions;
  const workspaceId = useOntologyWorkspaceId();
  const [ontologyUri, setOntologyUri] = useState<string>("");
  const [versions, setVersions] = useState<VersionEntry[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [showProposalModal, setShowProposalModal] = useState(false);
  const [showCompareModal, setShowCompareModal] = useState(false);
  const [comparePair, setComparePair] = useState<{ v1: string; v2: string } | null>(null);
  const [compareResult, setCompareResult] = useState<Record<string, any> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [modalNotice, setModalNotice] = useState("");
  const [proposalLinkCopied, setProposalLinkCopied] = useState(false);
  const urlProposalId = readOntologyUrlState().proposalId;
  const [uriDialogOpen, setUriDialogOpen] = useState(false);
  const [uriDraft, setUriDraft] = useState("");
  const openedProposalFromUrl = useRef<string | null>(null);

  useEffect(() => {
    const { proposalId } = readOntologyUrlState();
    if (!proposalId || proposals.length === 0) return;
    if (openedProposalFromUrl.current === proposalId) return;
    const match = proposals.find((p) => p.proposal_id === proposalId);
    if (!match) return;
    openedProposalFromUrl.current = proposalId;
    if (match.ontology_uri) setOntologyUri(match.ontology_uri);
    setSelectedProposal(match);
    setShowProposalModal(true);
  }, [proposals]);

  useEffect(() => {
    if (!selectedProposal) return;
    const fresh = proposals.find((p) => p.proposal_id === selectedProposal.proposal_id);
    if (fresh && fresh.state !== selectedProposal.state) {
      setSelectedProposal(fresh);
    }
  }, [proposals, selectedProposal?.proposal_id, selectedProposal?.state]);

  const loadVersions = useCallback(async () => {
    if (!ontologyUri) return;
    setError("");
    try {
      const { data, partialWarning } = await wsGetJson<VersionEntry[]>(
        workspaceId,
        ontologyApiSuffix(`versions/${encodeURIComponent(ontologyUri)}`),
        {
          fallbackMessage: v.api.load_versions_failed,
          partialWarning: v.api.partial_versions,
          locale: locale as Locale,
        },
      );
      setVersions(data);
      if (partialWarning) setError(partialWarning);
    } catch (err) {
      setError(wsApiErrorMessage(err, locale as Locale));
    }
  }, [workspaceId, ontologyUri, v.api, locale]);

  const loadProposals = useCallback(async () => {
    setError("");
    try {
      const { data, partialWarning } = await wsGetJson<Proposal[]>(
        workspaceId,
        ontologyApiSuffix("proposals"),
        {
          fallbackMessage: v.api.load_proposals_failed,
          partialWarning: v.api.partial_proposals,
          locale: locale as Locale,
        },
      );
      setProposals(data);
      if (partialWarning) setError(partialWarning);
    } catch (err) {
      setError(wsApiErrorMessage(err, locale as Locale));
    }
  }, [workspaceId, v.api, locale]);

  useEffect(() => {
    let ignore = false;
    async function fetchInitial() {
      if (!ignore) setError("");
      try {
        const { data: propData, partialWarning: propWarn } = await wsGetJson<Proposal[]>(
          workspaceId,
          ontologyApiSuffix("proposals"),
          {
            fallbackMessage: v.api.load_proposals_failed,
            partialWarning: v.api.partial_proposals,
            locale: locale as Locale,
          },
        );
        if (!ignore) {
          setProposals(propData);
          if (propWarn) setError(propWarn);
        }
      } catch (err) {
        if (!ignore) setError(wsApiErrorMessage(err, locale as Locale));
      }

      if (!ontologyUri) return;
      try {
        const { data: verData, partialWarning: verWarn } = await wsGetJson<VersionEntry[]>(
          workspaceId,
          ontologyApiSuffix(`versions/${encodeURIComponent(ontologyUri)}`),
          {
            fallbackMessage: v.api.load_versions_failed,
            partialWarning: v.api.partial_versions,
            locale: locale as Locale,
          },
        );
        if (!ignore) {
          setVersions(verData);
          if (verWarn) setError((prev) => prev || verWarn);
        }
      } catch (err) {
        if (!ignore) setError((prev) => prev || wsApiErrorMessage(err, locale as Locale));
      }
    }
    void fetchInitial();
    return () => { ignore = true; };
  }, [workspaceId, ontologyUri, v.api, locale]);

  const approveProposal = useCallback(async (proposalId: string) => {
    setError("");
    try {
      const response = await workspaceOpenApiResponse(
        'POST',
        workspaceId,
        ontologyApiSuffix(`proposals/${proposalId}/approve`),
      );
      const partial = await wsMutationResult(
        response,
        v.api.approve_failed,
        v.api.partial_approve,
        locale as Locale,
      );
      if (partial) setError(partial);
      else setModalNotice(v.approved_notice);
      loadProposals();
    } catch (err) {
      setError(wsApiErrorMessage(err, locale as Locale));
    }
  }, [workspaceId, loadProposals, v.api, v.approved_notice, locale]);

  const rejectProposal = useCallback(async (proposalId: string) => {
    setError("");
    try {
      const response = await workspaceOpenApiResponse(
        'POST',
        workspaceId,
        ontologyApiSuffix(`proposals/${proposalId}/reject`),
      );
      const partial = await wsMutationResult(
        response,
        v.api.reject_failed,
        v.api.partial_reject,
        locale as Locale,
      );
      if (partial) setError(partial);
      else setModalNotice(v.rejected_notice);
      loadProposals();
    } catch (err) {
      setError(wsApiErrorMessage(err, locale as Locale));
    }
  }, [workspaceId, loadProposals, v.api, v.rejected_notice, locale]);

  const publishProposal = useCallback(async (proposalId: string) => {
    setError("");
    try {
      const response = await workspaceOpenApiResponse(
        'POST',
        workspaceId,
        ontologyApiSuffix(`proposals/${proposalId}/publish`),
      );
      const partial = await wsMutationResult(
        response,
        v.api.publish_failed,
        v.api.partial_publish,
        locale as Locale,
      );
      if (partial) setError(partial);
      else setModalNotice(v.published_notice);
      loadProposals();
      loadVersions();
    } catch (err) {
      setError(wsApiErrorMessage(err, locale as Locale));
    }
  }, [workspaceId, loadProposals, loadVersions, v.api, v.published_notice, locale]);

  const runVersionComparison = useCallback(async () => {
    if (!comparePair || !ontologyUri) return;
    setIsLoading(true);
    setError("");
    try {
      const response = await workspaceOpenApiResponse(
        'POST',
        workspaceId,
        ontologyApiSuffix(`versions/${encodeURIComponent(ontologyUri)}/compare`),
        {
          body: {
            version1: comparePair.v1,
            version2: comparePair.v2,
          },
        },
      );
      const data = await parseWsJson<Record<string, unknown>>(
        response,
        v.api.compare_failed,
      );
      const partial = wsPartialSuccessWarning(
        response,
        data,
        v.api.partial_compare,
      );
      if (partial) setError(partial);
      setCompareResult(data);
    } catch (err) {
      setError(wsApiErrorMessage(err, locale as Locale));
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId, comparePair, ontologyUri, v.api, locale]);

  const ontologyUriButtonLabel = ontologyUri
    ? fmt(v.uri_prefix, {
        uri:
          ontologyUri.length > 40 ? `${ontologyUri.slice(0, 40)}…` : ontologyUri,
      })
    : v.set_uri;

  const getStateIcon = (state: string) => {
    switch (state) {
      case "published":
        return <PublicIcon name="check-circle" size={16} className="text-ok" />;
      case "approved":
        return <PublicIcon name="check-circle" size={16} className="text-primary" />;
      case "rejected":
        return <PublicIcon name="x-circle" size={16} className="text-destructive" />;
      case "proposed":
        return <PublicIcon name="alert-circle" size={16} className="text-warn" />;
      default:
        return <PublicIcon name="clock-01" size={16} className="text-muted-foreground" />;
    }
  };

  return (
    <div className="flex h-full flex-col overflow-auto p-5">
      <div className="mb-5 flex items-center justify-between gap-3">
        <h1 className="m-0 text-xl font-bold text-foreground">{v.title}</h1>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            setUriDraft(ontologyUri);
            setUriDialogOpen(true);
          }}
        >
          {ontologyUriButtonLabel}
        </Button>
      </div>

      {error ? (
        <div className="mb-4 rounded-xl border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <div className="mb-6">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
          <PublicIcon name="stack" size={16} />
          {v.version_history}
        </h2>
        <div className="flex flex-col gap-2">
          {versions.length === 0 ? (
            <div className="text-sm text-muted-foreground">{v.no_versions}</div>
          ) : (
            versions.map((version) => (
              <div
                key={version.version_id}
                className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 transition-colors"
              >
                {getStateIcon(version.state)}
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-foreground">{version.version_id}</div>
                  <div className="text-xs text-muted-foreground">
                    {version.author} • {formatLocaleDateTime(locale, version.date, { dateStyle: "medium" })}
                  </div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setComparePair({ v1: version.version_id, v2: versions[0]?.version_id || "" });
                    setShowCompareModal(true);
                  }}
                >
                  <PublicIcon name="arrow-right" size={12} />
                  {v.compare}
                </Button>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="mb-6">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
          <PublicIcon name="git-merge" size={16} />
          {v.change_proposals}
        </h2>
        <div className="flex flex-col gap-2">
          {proposals.length === 0 ? (
            <div className="text-sm text-muted-foreground">{v.no_proposals}</div>
          ) : (
            proposals.map((proposal) => (
              <div
                key={proposal.proposal_id}
                data-testid={`ontology-proposal-list-item-${proposal.proposal_id}`}
                className={cn(
                  "flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 transition-colors",
                  urlProposalId === proposal.proposal_id &&
                    "ring-2 ring-primary ring-offset-2 ring-offset-background",
                )}
              >
                {getStateIcon(proposal.state)}
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-foreground">{proposal.summary}</div>
                  <div className="text-xs text-muted-foreground">
                    {proposal.author} • {formatLocaleDateTime(locale, proposal.created_at, { dateStyle: "medium" })}
                  </div>
                </div>
                {proposal.state === "proposed" && (
                  <div className="flex gap-1.5">
                    <Button type="button" size="sm" onClick={() => approveProposal(proposal.proposal_id)}>
                      <PublicIcon name="check-circle" size={12} />
                      {v.approve}
                    </Button>
                    <Button type="button" size="sm" variant="outline" onClick={() => rejectProposal(proposal.proposal_id)}>
                      <PublicIcon name="x-circle" size={12} />
                      {v.reject}
                    </Button>
                  </div>
                )}
                {proposal.state === "approved" && (
                  <Button type="button" size="sm" onClick={() => publishProposal(proposal.proposal_id)}>
                    <PublicIcon name="paper-plane" size={12} />
                    {v.publish}
                  </Button>
                )}
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    writeProposalSelection(proposal.proposal_id);
                    setSelectedProposal(proposal);
                    setModalNotice("");
                    setShowProposalModal(true);
                  }}
                >
                  <PublicIcon name="file-01" size={12} />
                  {v.details}
                </Button>
              </div>
            ))
          )}
        </div>
      </div>

      <Dialog open={showProposalModal && Boolean(selectedProposal)} onOpenChange={setShowProposalModal}>
        <DialogContent className="max-h-[min(92vh,40rem)] max-w-2xl overflow-y-auto">
          {selectedProposal ? (
            <>
            <DialogHeader>
              <DialogTitle>{v.proposal_modal_title}</DialogTitle>
              <DialogDescription>{selectedProposal.summary}</DialogDescription>
            </DialogHeader>
            <div className="mb-3">
              <Label className="text-muted-foreground">{v.summary}</Label>
              <div className="mt-1 text-sm text-foreground">{selectedProposal.summary}</div>
            </div>
            <div className="mb-3">
              <Label className="text-muted-foreground">{v.state}</Label>
              <div className="mt-1 flex items-center gap-1.5 text-sm text-foreground">
                {getStateIcon(selectedProposal.state)}
                {v.proposal_states[selectedProposal.state] ?? selectedProposal.state}
              </div>
            </div>
            <div className="mb-3">
              <Label className="text-muted-foreground">{v.proposal_id}</Label>
              <div className="mt-1 flex items-center gap-2">
                <code className="min-w-0 flex-1 break-all font-mono text-xs text-muted-foreground">
                  {selectedProposal.proposal_id}
                </code>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    void navigator.clipboard.writeText(selectedProposal.proposal_id);
                    setModalNotice(v.id_copied);
                  }}
                >
                  {t.core.common.copy}
                </Button>
                {workspaceId ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    data-testid="ontology-proposal-copy-link"
                    onClick={() => {
                      const path = workspaceOntologyProposalPath(workspaceId, selectedProposal.proposal_id);
                      const href = `${window.location.origin}${path}`;
                      void navigator.clipboard.writeText(href).then(() => {
                        setProposalLinkCopied(true);
                        window.setTimeout(() => setProposalLinkCopied(false), 2000);
                      });
                    }}
                  >
                    {proposalLinkCopied ? v.copy_proposal_link_done : v.copy_proposal_link}
                  </Button>
                ) : null}
              </div>
            </div>
            {selectedProposal.shacl_validation?.conforms === false ? (
              <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {fmt(v.shacl_publish_blocked, {
                  summary: shaclSummaryLine(locale, selectedProposal.shacl_validation, v.shacl),
                })}
              </div>
            ) : null}
            {modalNotice ? (
              <div className="mb-3 text-xs text-ok">{modalNotice}</div>
            ) : null}
            <div className="mb-3">
              <Label className="text-muted-foreground">{v.impact_analysis}</Label>
              <div className="mb-1.5 text-xs text-muted-foreground">
                {impactSummaryLine(locale, selectedProposal.impact_analysis, v.impact)}
              </div>
              <pre className="max-h-40 overflow-auto rounded-md border bg-muted/50 p-3 font-mono text-xs text-foreground">
                {JSON.stringify(selectedProposal.impact_analysis, null, 2)}
              </pre>
            </div>
            <div className="mb-3">
              <Label className="text-muted-foreground">{v.shacl_validation}</Label>
              <div className="mb-1.5 text-xs text-muted-foreground">
                {shaclSummaryLine(locale, selectedProposal.shacl_validation, v.shacl)}
              </div>
              <pre className="max-h-40 overflow-auto rounded-md border bg-muted/50 p-3 font-mono text-xs text-foreground">
                {JSON.stringify(selectedProposal.shacl_validation, null, 2)}
              </pre>
            </div>
            <div>
              <Label className="text-muted-foreground">
                {fmt(v.comments, { count: formatLocaleNumber(locale, selectedProposal.comments.length) })}
              </Label>
              <div className="mt-1 max-h-[120px] space-y-1.5 overflow-auto">
                {selectedProposal.comments.map((comment, idx) => (
                  <div key={String(comment.id ?? idx)} className="rounded-md border bg-muted/40 p-2">
                    <div className="text-xs font-semibold text-foreground">{comment.author}</div>
                    <div className="text-xs text-muted-foreground">{comment.text}</div>
                  </div>
                ))}
              </div>
            </div>
            <DialogFooter className="mt-4 flex-wrap gap-2">
              {selectedProposal.state === "proposed" && (
                <>
                  <Button type="button" size="sm" onClick={() => approveProposal(selectedProposal.proposal_id)}>
                    <PublicIcon name="check-circle" size={12} />
                    {v.approve}
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => rejectProposal(selectedProposal.proposal_id)}>
                    <PublicIcon name="x-circle" size={12} />
                    {v.reject}
                  </Button>
                </>
              )}
              {selectedProposal.state === "approved" && (
                <Button type="button" size="sm" onClick={() => publishProposal(selectedProposal.proposal_id)}>
                  <PublicIcon name="paper-plane" size={12} />
                  {v.publish}
                </Button>
              )}
              <Button type="button" size="sm" variant="ghost" className="ml-auto" onClick={() => setShowProposalModal(false)}>
                {v.close}
              </Button>
            </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog open={showCompareModal && Boolean(comparePair)} onOpenChange={setShowCompareModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{v.compare_title}</DialogTitle>
            <DialogDescription>{v.compare_desc}</DialogDescription>
          </DialogHeader>
          {comparePair ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="compare-v1">{v.version1}</Label>
                  <Input
                    id="compare-v1"
                    value={comparePair.v1}
                    onChange={(e) => setComparePair({ ...comparePair, v1: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="compare-v2">{v.version2}</Label>
                  <Input
                    id="compare-v2"
                    value={comparePair.v2}
                    onChange={(e) => setComparePair({ ...comparePair, v2: e.target.value })}
                  />
                </div>
              </div>
              <DialogFooter className="gap-2">
                <Button type="button" variant="outline" onClick={() => setShowCompareModal(false)}>
                  {t.core.common.cancel}
                </Button>
                <Button type="button" disabled={isLoading} onClick={runVersionComparison}>
                  <PublicIcon name="scales" size={12} />
                  {isLoading ? v.comparing : v.compare}
                </Button>
              </DialogFooter>
              {compareResult ? (
                <pre className="mt-2 max-h-64 overflow-auto rounded-md border bg-muted/40 p-3 font-mono text-xs">
                  {JSON.stringify(compareResult, null, 2)}
                </pre>
              ) : null}
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog open={uriDialogOpen} onOpenChange={setUriDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{v.scope_title}</DialogTitle>
            <DialogDescription>{v.scope_desc}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="ontology-uri-scope">{v.ontology_uri}</Label>
            <Input
              id="ontology-uri-scope"
              value={uriDraft}
              onChange={(e) => setUriDraft(e.target.value)}
              placeholder={v.uri_placeholder}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setUriDialogOpen(false)}>
              {t.core.common.cancel}
            </Button>
            <Button
              type="button"
              onClick={() => {
                setOntologyUri(uriDraft.trim());
                setUriDialogOpen(false);
              }}
            >
              {v.apply}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
