"use client";
import { useEffect, useState } from "react";
import { workspaceApi as api, errorMessage, type ReviewEvent } from "../../lib/referral-api/workspace";

export function ReviewHistory({ packetId, refresh, onRun, onSnapshot, onError }: { packetId: string; refresh: number; onRun: (id: string) => void; onSnapshot: (id: string) => void; onError: (e: unknown) => void }) {
  const [items, setItems] = useState<ReviewEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let alive = true; setBusy(true); setError("");
    api.history(packetId).then(next => { if (alive) { setItems(next.items); setCursor(next.next_cursor ?? null); } }).catch(e => { if (alive) { setError(errorMessage(e)); onError(e); } }).finally(() => { if (alive) setBusy(false); });
    return () => { alive = false; };
  }, [packetId, refresh, retry, onError]);
  async function more() {
    if (!cursor || busy) return;
    setBusy(true); setError("");
    try { const next = await api.history(packetId, cursor); setItems(old => [...old, ...next.items.filter(item => !old.some(existing => existing.id === item.id))]); setCursor(next.next_cursor ?? null); }
    catch (e) { setError(errorMessage(e)); onError(e); } finally { setBusy(false); }
  }
  return <details className="rr-card"><summary>Review history and confirmed handoffs</summary>
    <p>Previous decisions remain historical references. They are never automatically applied to a different run.</p>
    {error && <p role="alert">{error} <button onClick={() => setRetry(n => n + 1)}>Reload history</button></p>}
    {busy && <p role="status">Loading review history…</p>}
    {!busy && !error && items.length === 0 && <p>No saved review events yet.</p>}
    <ol className="rr-history">{items.map(event => <li key={event.id}>
      <p><strong>{event.kind} · Review version {event.review_version}</strong> · {new Date(event.created_at).toLocaleString()}</p>
      <p className="rr-muted">Source revision {event.revision_id}</p>
      {event.kind === "resolution" && <>
        <p>{typeof event.content.action === "string" ? event.content.action : "Saved decision"}: {typeof event.content.reason === "string" ? event.content.reason : ""}</p>
        {typeof event.content.corrected_value === "string" && <p>Reviewer supplied: {event.content.corrected_value}</p>}
      </>}
      <div className="rr-actions">{event.run_id && <button onClick={() => onRun(event.run_id!)}>View this run</button>}
        {event.kind === "confirmation" && typeof event.content.snapshot_id === "string" && <button onClick={() => onSnapshot(String(event.content.snapshot_id))}>View confirmed handoff</button>}
      </div>
    </li>)}</ol>
    {cursor && <button disabled={busy} onClick={more}>Load older history</button>}
  </details>;
}
