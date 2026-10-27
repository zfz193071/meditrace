"use client";
import { useReviewTransport } from "./ReviewTransport";
import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage, operationKey, type Run, type ReviewState, type DecisionInput, type Finding, type Packet } from "../../lib/referral-api/workspace";
import { type HandoffView } from "../../lib/referral-api/handoff";
import { EvidencePanel } from "./EvidencePanel";
import { HandoffSummary } from "./HandoffSummary";
import { ReviewHistory } from "./ReviewHistory";
import { useUnsavedChanges } from "./WorkspaceGate";

const kinds: Record<Finding["kind"], string> = { missing: "Missing information", unknown: "Needs clarification", identity_mismatch: "Identity mismatch", statement_difference: "Statement difference", attachment_unmatched: "Attachment not found", parse_quality: "Parsing quality" };
const rules: Record<string, string> = { C01: "Patient name recorded", C02: "Date of birth recorded consistently", C03: "Referrer and contact information recorded", C04: "Receiving specialty or service recorded", C05: "Referral reason recorded", C06: "Current medication status recorded", C07: "Allergy status recorded", C08: "Reports said to be attached can be found" };
const actions: Record<DecisionInput["action"], string> = { resolve: "Resolve", dismiss: "Dismiss with reason", defer: "Keep unresolved", reopen: "Reopen" };
type Props = { packet: Packet; run: Run | null; csrf: string; sourceDirty: boolean; onError: (e: unknown) => void; onDirty: (dirty: boolean) => void };

export function ReviewWorkspace({ packet, run, csrf, sourceDirty, onError, onDirty }: Props) {
  const api = useReviewTransport();
  const [chosen, setChosen] = useState<Run | null>(null);
  const [dirty, setDirty] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [view, setView] = useState<HandoffView | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewPending, setReviewPending] = useState(false);
  const pendingReview = useRef(false);
  const active = chosen ?? run;
  const viewing = useRef(0);
  const dirtyChanged = useCallback((next: boolean) => { setDirty(next); onDirty(next); }, [onDirty]);
  const pendingChanged = useCallback((next: boolean) => { pendingReview.current = next; setReviewPending(next); }, []);
  useEffect(() => () => { ++viewing.current; }, []);
  const changed = useCallback(() => { setRefresh(n => n + 1); setView(null); }, []);
  async function navigate(kind: "run" | "snapshot", id: string) {
    if (busy || pendingReview.current || (dirty && !window.confirm("Discard unsaved review edits to view saved history?"))) return;
    const request = ++viewing.current; setBusy(true); setError("");
    try {
      if (kind === "run") {
        const next = await api.run(id);
        if (request === viewing.current) { setChosen(next); setView(null); }
      } else {
        const next = await api.handoff(packet.id, id);
        if (request === viewing.current) setView(next);
      }
    } catch (e) { if (request === viewing.current) { setError(errorMessage(e)); onError(e); } }
    finally { if (request === viewing.current) setBusy(false); }
  }
  return <>
    <section id="evidence-review" className="rr-card" aria-label="Evidence review">
      <div className="rr-heading"><h2>3. Review evidence and prepare handoff</h2>{chosen && <button disabled={busy || reviewPending} onClick={() => { if (pendingReview.current) return; if (!dirty || window.confirm("Discard unsaved review edits?")) { setChosen(null); setView(null); } }}>Return to latest run</button>}</div>
      {error && <p role="alert" className="rr-alert">{error}</p>}{busy && <p role="status">Loading saved review…</p>}
      {reviewPending && <p role="status">Saving review. Wait before switching runs or handoffs.</p>}
      {active?.state === "succeeded" && active.result ? <ReviewSurface key={`${active.id}:${packet.current_revision}`} packet={packet} run={active} csrf={csrf} sourceDirty={sourceDirty || busy} onError={onError} onDirty={dirtyChanged} onPending={pendingChanged} onChanged={changed} onConfirmed={id => navigate("snapshot", id)} />
        : <p>No completed check is available to review. You can use the manual handoff below. No AI request is started here.</p>}
    </section>
    {view && <section className="rr-card"><p className="rr-notice">Confirmed snapshot · Review version {view.review_version}{view.historical ? " · Historical — not the current review" : ""}</p><HandoffSummary view={view} />{api.snapshotUrl && <div className="rr-actions"><a href={api.snapshotUrl(packet.id, view.snapshot_id, "txt")}>Download confirmed text</a><a href={api.snapshotUrl(packet.id, view.snapshot_id, "pdf")}>Download confirmed PDF</a></div>}</section>}
    <ReviewHistory packetId={packet.id} refresh={refresh} navigationDisabled={busy || reviewPending} onRun={id => navigate("run", id)} onSnapshot={id => navigate("snapshot", id)} onError={onError} />
  </>;
}

function ReviewSurface({ packet, run, csrf, sourceDirty, onError, onDirty, onPending, onChanged, onConfirmed }: Omit<Props, "run"> & { run: Run; onPending: (pending: boolean) => void; onChanged: () => void; onConfirmed: (id: string) => void }) {
  const api = useReviewTransport();
  const [state, setState] = useState<ReviewState | null>(null);
  const [selected, setSelected] = useState(run.result?.findings[0]?.id ?? "");
  const [kind, setKind] = useState("all");
  const [status, setStatus] = useState("all");
  const [showFacts, setShowFacts] = useState(false);
  const [pane, setPane] = useState<"items" | "evidence">("items");
  const [focusRequest, setFocusRequest] = useState(0);
  const [action, setAction] = useState<DecisionInput["action"]>("resolve");
  const [reason, setReason] = useState("");
  const [correction, setCorrection] = useState("");
  const [linked, setLinked] = useState<string[]>([]);
  const [edited, setEdited] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [message, setMessage] = useState("");
  const [confirming, setConfirming] = useState(false);
  const detail = useRef<HTMLElement>(null);
  useEffect(() => {
    // The evidence panel must be visible before focusing it, including when
    // animation frames are paused in a background tab or the item is unchanged.
    if (focusRequest > 0) detail.current?.focus();
  }, [focusRequest]);
  const lock = useRef(false);
  const alive = useRef(true);
  const operation = useRef<{ input: string; key: string } | null>(null);
  const result = run.result!;
  useUnsavedChanges(edited);
  useEffect(() => { onDirty(edited); return () => onDirty(false); }, [edited, onDirty]);
  useEffect(() => () => onPending(false), [onPending]);
  const reload = useCallback(async () => {
    if (lock.current) return;
    setBusy(true); setError(""); setConfirming(false);
    try {
      const next = await api.reviewState(run.id);
      if (!alive.current) return;
      if (next.run_id !== run.id || next.revision.id !== run.revision_id || result.run_id !== run.id || result.revision_id !== run.revision_id || next.revision.packet_id !== packet.id) throw new Error("Review context mismatch");
      setState(next); setBlocked(false); setMessage("Saved decisions loaded. Any unsaved edit remains below for comparison.");
    } catch (e) { if (alive.current) { setBlocked(true); setError(errorMessage(e)); onError(e); } }
    finally { if (alive.current) setBusy(false); }
  }, [api, run.id, run.revision_id, result.run_id, result.revision_id, packet.id, onError]);
  useEffect(() => { alive.current = true; void reload(); return () => { alive.current = false; }; }, [reload]);
  const stale = !state || state.stale || run.stale || !state.revision.is_current || state.revision.revision_number !== packet.current_revision;
  const decisions = new Map(state?.decisions.map(d => [d.finding_id, d]) ?? []);
  const currentStatus = (id: string) => decisions.get(id)?.status ?? "open";
  const finding = result.findings.find(f => f.id === selected);
  const saved = finding ? decisions.get(finding.id) : undefined;
  const visible = result.findings.filter(f => (kind === "all" || f.kind === kind) && (status === "all" || currentStatus(f.id) === status));
  const facts = finding ? result.facts.filter(f => (finding.fact_ids ?? []).includes(f.id)) : [];
  const evidenceIds = new Set([...(finding?.evidence_ids ?? []), ...facts.flatMap(f => f.evidence_ids)]);
  const evidence = finding?.kind === "missing" ? [] : result.evidence.filter(e => evidenceIds.has(e.id));
  const open = result.findings.filter(f => currentStatus(f.id) === "open").length;
  const identity = result.findings.some(f => f.kind === "identity_mismatch" && currentStatus(f.id) !== "resolved");
  const disabled = busy || blocked || stale || sourceDirty;
  function resetEdit() { setAction("resolve"); setReason(""); setCorrection(""); setLinked([]); setEdited(false); operation.current = null; setConfirming(false); }
  function select(id: string) {
    if (busy || lock.current) return;
    if (edited && !window.confirm("Discard unsaved edits to select another item?")) return;
    setSelected(id); resetEdit(); setPane("evidence");
    setFocusRequest(value => value + 1);
  }
  function edit() { setEdited(true); setConfirming(false); }
  async function save() {
    if (!finding || !state || disabled || lock.current) return;
    lock.current = true; onPending(true); setBusy(true); setError("");
    const body: DecisionInput = { expected_review_version: state.review_version, action, reason, corrected_value: correction.trim() ? correction : null, linked_evidence_ids: linked };
    const signature = JSON.stringify({ finding: finding.id, body });
    if (operation.current?.input !== signature) operation.current = { input: signature, key: operationKey() };
    try {
      const event = await api.resolve(run.id, finding.id, body, csrf, operation.current.key);
      if (!alive.current) return;
      setState(old => old && { ...old, review_version: event.review_version, decisions: [...old.decisions.filter(d => d.finding_id !== finding.id), { finding_id: finding.id, status: { resolve: "resolved" as const, dismiss: "dismissed" as const, defer: "unresolved" as const, reopen: "open" as const }[action], action, reason, corrected_value: body.corrected_value ?? null, linked_evidence_ids: linked, review_version: event.review_version }] });
      resetEdit(); setMessage("Reviewer decision saved. Original facts and citations are unchanged."); onChanged();
    } catch (e) { if (alive.current) { setError(errorMessage(e)); setBlocked(true); onError(e); } }
    finally { lock.current = false; if (alive.current) { setBusy(false); onPending(false); } }
  }
  async function confirm() {
    if (!state || disabled || edited || open || lock.current) return;
    lock.current = true; onPending(true); setBusy(true); setError("");
    try {
      const snapshot = await api.confirm(packet.id, { mode: "assisted", run_id: run.id, revision_id: state.revision.id, expected_review_version: state.review_version }, csrf);
      if (!alive.current) return;
      setState(old => old && { ...old, review_version: snapshot.review_version }); setConfirming(false);
      // The write has completed. Allow its confirmed snapshot to open normally.
      onPending(false); onChanged(); onConfirmed(snapshot.id);
    } catch (e) { if (alive.current) { setError(errorMessage(e)); setBlocked(true); onError(e); } }
    finally { lock.current = false; if (alive.current) { setBusy(false); onPending(false); } }
  }
  return <>
    <p>Run mode: {run.mode} · Source version {state?.revision.revision_number ?? "…"} · Review version {state?.review_version ?? "…"}</p>
    {identity && <p role="status" className="rr-alert">Identity unresolved — verify the differing identity details. This warning remains in the handoff unless resolved.</p>}
    {stale && state && <p className="rr-alert">Historical source version. Review decisions are read-only; use the latest saved sources to review and confirm.</p>}
    {sourceDirty && <p className="rr-alert">Save or restore source changes before saving a review decision.</p>}
    {error && <p role="alert" className="rr-alert">{error} Your unsaved correction is retained. Reload saved decisions, compare them, then explicitly save again.</p>}
    {message && <p role="status">{message}</p>}
    <button disabled={busy} onClick={reload}>Reload saved decisions</button>
    {busy && <p role="status">Reading or saving review…</p>}
    {state && <>
      <div className="rr-mobile-switch" aria-label="Review panels"><button aria-pressed={pane === "items"} onClick={() => setPane("items")}>Items</button><button aria-pressed={pane === "evidence"} onClick={() => setPane("evidence")}>Evidence and decision</button></div>
      <div className={`rr-review-grid rr-show-${pane}`}>
        <section className="rr-review-items" aria-label="Review items"><h3>Items ({result.findings.length})</h3>
          <label htmlFor="finding-kind">Filter by type</label><select id="finding-kind" value={kind} onChange={e => setKind(e.target.value)}><option value="all">All types</option>{Object.entries(kinds).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <label htmlFor="finding-status">Filter by status</label><select id="finding-status" value={status} onChange={e => setStatus(e.target.value)}>{["all", "open", "resolved", "dismissed", "unresolved"].map(value => <option key={value} value={value}>{value === "all" ? "All statuses" : value}</option>)}</select>
          {visible.length === 0 && <p>No items match these filters.</p>}
          <ul className="rr-findings">{visible.map(f => <li key={f.id}><button disabled={busy} aria-pressed={selected === f.id} onClick={() => select(f.id)}><span>{kinds[f.kind]} · {f.field_keys.join(", ")}<small>{currentStatus(f.id)} · {f.rule_id}</small></span></button></li>)}</ul>
        </section>
        <section ref={detail} tabIndex={-1} className="rr-review-detail" aria-label="Evidence and decision">{finding ? <>
          <h3>{kinds[finding.kind]}</h3><p>{finding.message}</p><p><strong>Checklist requirement:</strong> {rules[finding.rule_id] ?? finding.rule_id} · {finding.checklist_version}</p>
          <p>Checked successfully parsed sources in version {state.revision.revision_number}: {finding.checked_document_ids.map(id => state.revision.documents.find(d => d.id === id)?.filename ?? "Unavailable source").join("; ")}</p>
          {finding.kind === "missing" && <p className="rr-notice">Not found in the supplied, successfully parsed material. Absence has no source quote; it does not mean the patient has no such history.</p>}
          {facts.map(f => <div key={f.id} className="rr-fact"><strong>{f.field_key}: {f.value_raw}</strong><p>{f.assertion_status}{f.temporal_context ? ` · ${f.temporal_context}` : ""}</p></div>)}
          <div className="rr-evidence-grid">{evidence.map(e => <EvidencePanel key={`${run.id}:${e.id}`} packetId={packet.id} evidence={e} revision={state.revision} onError={onError} />)}</div>
          {saved && <div className="rr-notice"><strong>Saved decision: {saved.status}</strong><p>{saved.reason}</p>{saved.corrected_value && <p>Reviewer supplied: {saved.corrected_value}</p>}</div>}
          <fieldset disabled={disabled}><legend>Human decision</legend><p>Corrections are reviewer supplied. They do not rewrite the original fact or create a source citation.</p>
            <label htmlFor="review-action">Action</label><select id="review-action" value={action} onChange={e => { setAction(e.target.value as DecisionInput["action"]); edit(); }}>{Object.entries(actions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
            <label htmlFor="review-reason">Reason {action === "dismiss" || action === "defer" ? "(required)" : "(optional)"}</label><textarea id="review-reason" maxLength={4000} rows={3} value={reason} onChange={e => { setReason(e.target.value); edit(); }} />
            <label htmlFor="review-correction">Reviewer supplied correction (optional)</label><textarea id="review-correction" rows={2} maxLength={4000} value={correction} onChange={e => { setCorrection(e.target.value); edit(); }} />
            {evidence.map(e => <label className="rr-check" key={e.id}><input type="checkbox" checked={linked.includes(e.id)} onChange={event => { setLinked(ids => event.target.checked ? [...ids, e.id] : ids.filter(id => id !== e.id)); edit(); }} /><span>Link citation: {state.revision.documents.find(d => d.id === e.document_id)?.filename} · page {e.page_number}</span></label>)}
            <button disabled={disabled || ((action === "dismiss" || action === "defer") && !reason.trim())} onClick={save}>Save decision</button>
          </fieldset>
          {edited && <p className="rr-alert">Unsaved review edits. <button disabled={busy} onClick={() => { if (!lock.current) resetEdit(); }}>Discard review edits</button></p>}
        </> : <p>No findings in this saved result. Review the recorded facts below before confirming.</p>}</section>
      </div>
      <details onToggle={e => setShowFacts(e.currentTarget.open)}><summary>All extracted facts ({result.facts.length})</summary>{showFacts && result.facts.map(f => <div className="rr-fact" key={f.id}><p><strong>{f.field_key}: {f.value_raw}</strong> · {f.assertion_status} {f.temporal_context}</p>{f.evidence_ids.map(id => { const e = result.evidence.find(e => e.id === id); return e ? <EvidencePanel key={id} packetId={packet.id} evidence={e} revision={state.revision} onError={onError} /> : <p key={id}>Citation unavailable.</p>; })}</div>)}</details>
      <div className="rr-confirm"><p>{open} open items. Every item must be resolved, dismissed or explicitly kept unresolved before confirmation. Reviewed does not mean complete.</p>
        {(stale || blocked || sourceDirty || edited) && <p>Confirmation unavailable: {stale ? "historical source version" : blocked ? "reload saved decisions after the error" : sourceDirty ? "unsaved source changes" : "save or discard review edits"}.</p>}
        <button disabled={disabled || edited || open > 0} onClick={() => setConfirming(true)}>Confirm reviewed handoff</button>
        {confirming && <div className="rr-notice"><p>Create an immutable handoff for this source and review version? Unresolved items and identity warnings will remain visible.</p><button disabled={disabled || edited || open > 0} onClick={confirm}>Create confirmed snapshot</button><button disabled={busy} onClick={() => setConfirming(false)}>Keep reviewing</button></div>}
      </div>
    </>}
  </>;
}
