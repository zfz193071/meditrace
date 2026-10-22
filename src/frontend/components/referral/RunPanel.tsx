"use client";
import { useEffect, useRef, useState } from "react";
import { workspaceApi as api, errorMessage, operationKey, type Run, type Revision, type Membership, type Capabilities } from "../../lib/referral-api/workspace";

const phaseText: Record<Run["phase"], string> = { pending: "Prepared - not started", reserved: "Capacity reserved", dispatched: "Request sent; waiting for result", complete: "Result saved", failed: "Check failed", unknown: "Outcome unknown", cancelled: "Check cancelled" };
export function RunPanel({ packetId, revision, initialRun, membership, caps, csrf, sourceDirty, onError, onRunChange }: {
  packetId: string; revision: Revision | null; initialRun: Run | null; membership: Membership | null;
  caps: Capabilities; csrf: string; sourceDirty: boolean; onError: (e: unknown) => void; onRunChange?: (run: Run | null) => void;
}) {
  const [run, setRun] = useState(initialRun);
  useEffect(() => { onRunChange?.(run); }, [run, onRunChange]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [polling, setPolling] = useState(true);
  const locked = useRef(false);
  const alive = useRef(true);
  const executing = useRef(false);
  const startedHere = useRef(new Set<string>());
  const newRunKey = useRef<string | null>(null);
  const stale = Boolean(run && (!revision || run.revision_id !== revision.id || run.stale));
  const memberActive = Boolean(membership?.valid_until && Date.parse(membership.valid_until) > Date.now() && membership.remaining > 0);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  // Only GET may be retried. Stop polling after 5 minutes or the first read failure.
  useEffect(() => {
    if (!run || !polling || !["pending", "running"].includes(run.state)) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const deadline = Date.now() + 300_000;
    async function tick() {
      try {
        const current = await api.run(run!.id);
        if (cancelled) return;
        setRun(current);
        if (Date.now() >= deadline) { setPolling(false); setError("Automatic status checks paused. Query status or recover the saved run; do not restart it."); }
        else if (["pending", "running"].includes(current.state)) timer = setTimeout(tick, 4000);
      } catch (e) { if (!cancelled) { setError(errorMessage(e)); setPolling(false); onError(e); } }
    }
    timer = setTimeout(tick, 4000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [run?.id, polling, onError]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!run) return;
    const update = () => setElapsed(Math.max(0, Math.floor(((run.finished_at ? Date.parse(run.finished_at) : Date.now()) - Date.parse(run.created_at)) / 1000)));
    update(); const timer = setInterval(update, 1000); return () => clearInterval(timer);
  }, [run?.created_at, run?.finished_at]); // eslint-disable-line react-hooks/exhaustive-deps
  async function act(action: "prepare" | "execute" | "query" | "reconcile" | "cancel") {
    if (locked.current) return;
    if (action === "execute" && (!run || startedHere.current.has(run.id))) return;
    locked.current = true; setBusy(true); setError("");
    try {
      let next: Run | null = run;
      if (action === "prepare" && revision) {
        newRunKey.current ??= operationKey();
        next = await api.createRun(packetId, { revision_id: revision.id, checklist_version: "outpatient-referral-demo@1" }, csrf, newRunKey.current);
        newRunKey.current = null;
      } else if (run) {
        if (action === "execute") {
          startedHere.current.add(run.id); executing.current = true;
          next = await api.execute(run.id, csrf, operationKey());
        } else if (action === "query") next = await api.run(run.id);
        else if (action === "reconcile") next = await api.reconcile(run.id, csrf);
        else if (action === "cancel") next = await api.cancel(run.id, csrf);
      }
      if (alive.current) { setRun(next); setPolling(true); }
    } catch (e) {
      if (alive.current) {
        setError(action === "execute" ? "The execution response was interrupted. Only status will be queried; the check will not be executed again automatically." : errorMessage(e));
        onError(e);
        if (action === "execute" && run) {
          try { const current = await api.run(run.id); if (alive.current) { setRun(current); setPolling(true); } }
          catch (readError) { if (alive.current) { setPolling(false); onError(readError); } }
        }
      }
    } finally { locked.current = false; executing.current = false; if (alive.current) setBusy(false); }
  }
  const available = (caps.sandbox_execution_available || caps.real_ai_execution_available) && caps.mode !== "bundled_demo";
  return <section className="rr-card" aria-labelledby="run-title"><h2 id="run-title">Optional automated check</h2>
    <p><strong>{!available ? "Unavailable" : caps.mode === "sandbox" ? "Fake / simulated mode" : "Invited mode - server verifies eligibility"}</strong></p>
    <p>Preparing a check does not call AI. Review the exact mode before starting. A successful check consumes one test credit; real mode may incur provider fees.</p>
    <p>{membership ? `Test credits: ${membership.remaining} remaining, ${membership.reserved} reserved.` : "Membership could not be loaded. Manual work remains available."}</p>
    {!memberActive && <p>No active test credits. You can still prepare sources and complete a manual handoff.</p>}
    <a href="#manual-review">Continue manually - no AI call</a>
    {sourceDirty && <p className="rr-alert">Save the selected sources as a new version before preparing a check.</p>}
    {error && <p role="alert" className="rr-alert">{error}</p>}
    {!run || !["pending", "running", "outcome_unknown"].includes(run.state) ? <button className="rr-primary" disabled={busy || !available || !memberActive || !revision || sourceDirty || revision.documents.length === 0} onClick={() => act("prepare")}>Prepare check</button> : null}
    {run && <div className="rr-run-status">
      <p role="status"><strong>{phaseText[run.phase]}</strong> · {elapsed}s since preparation</p>
      <p>Run mode: <strong>{run.mode === "real" ? "Real AI" : "Fake / simulated"}</strong>{stale ? " · Historical source version" : ""}</p>
      {run.mode === "real" && !membership?.real_ai_allowed && <p>Real AI is currently unavailable for this account or budget. Manual review remains available.</p>}
      {run.state === "outcome_unknown" && <p>The provider outcome is unknown. Costs may remain reserved. Recover this run without sending another model request.</p>}
      {run.state === "succeeded" && <p>{run.result?.findings.length ?? 0} items need human review. A saved result is not approval of a referral.</p>}
      {run.error_code && <p>Run stopped: {run.error_code.replace(/[^A-Z0-9_]/g, "")}. Query or recover the run before deciding what to do next.</p>}
      <div className="rr-actions">
        {run.state === "pending" && !startedHere.current.has(run.id) && <button className="rr-primary" disabled={busy || stale || sourceDirty || !memberActive || (run.mode === "real" && !membership?.real_ai_allowed)} onClick={() => act("execute")}>{run.mode === "real" ? "Start real AI check - 1 credit" : "Start simulated check - 1 credit"}</button>}
        <button disabled={busy} onClick={() => act("query")}>Query status</button>
        {["pending", "running", "outcome_unknown"].includes(run.state) && <button disabled={busy} onClick={() => act("reconcile")}>Recover without rerunning</button>}
        {run.state === "pending" && <button disabled={busy} onClick={() => act("cancel")}>Cancel prepared check</button>}
      </div>
      {busy && <p role="status">{executing.current ? "Check request in progress; status polling continues." : "Contacting the service…"}</p>}
    </div>}
  </section>;
}
