"use client";
import { useReviewTransport } from "./ReviewTransport";
import { useEffect, useRef, useState } from "react";
import { errorMessage, type ReviewEvent } from "../../lib/referral-api/workspace";

export function ReviewHistory({ packetId, refresh, navigationDisabled = false, onRun, onSnapshot, onError }: { packetId: string; refresh: number; navigationDisabled?: boolean; onRun: (id: string) => void; onSnapshot: (id: string) => void; onError: (e: unknown) => void }) {
  const api = useReviewTransport();
  const [items, setItems] = useState<ReviewEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState<"initial" | "more" | null>("initial");
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const generation = useRef(0);
  const paging = useRef(false);
  const busy = loading !== null;
  useEffect(() => {
    const current = ++generation.current;
    paging.current = false; setLoading("initial"); setError(""); setItems([]); setCursor(null);
    api.history(packetId).then(next => { if (current === generation.current) { setItems(next.items); setCursor(next.next_cursor ?? null); } }).catch(e => { if (current === generation.current) { setError(errorMessage(e)); onError(e); } }).finally(() => { if (current === generation.current) setLoading(null); });
    return () => { generation.current += 1; };
  }, [api, packetId, refresh, retry, onError]);
  function reload() {
    // Invalidate pagination immediately, before the reload effect runs.
    generation.current += 1;
    setRetry(n => n + 1);
  }
  async function more() {
    if (!cursor || busy || paging.current) return;
    const current = generation.current;
    paging.current = true; setLoading("more"); setError("");
    try {
      const next = await api.history(packetId, cursor);
      if (current !== generation.current) return;
      setItems(old => [...old, ...next.items.filter(item => !old.some(existing => existing.id === item.id))]); setCursor(next.next_cursor ?? null);
    }
    catch (e) { if (current === generation.current) { setError(errorMessage(e)); onError(e); } }
    finally { if (current === generation.current) { paging.current = false; setLoading(null); } }
  }
  return <details className="rr-card"><summary>Review history and confirmed handoffs</summary>
    <p>Previous decisions remain historical references. They are never automatically applied to a different run.</p>
    <button disabled={loading === "initial"} onClick={reload}>Reload history</button>
    {error && <p role="alert">{error}</p>}
    {busy && <p role="status">Loading review history…</p>}
    {!busy && !error && items.length === 0 && <p>No saved review events yet.</p>}
    <ol className="rr-history">{items.map(event => <li key={event.id}>
      <p><strong>{event.kind} · Review version {event.review_version}</strong> · {new Date(event.created_at).toLocaleString()}</p>
      <p className="rr-muted">Source revision {event.revision_id}</p>
      {event.kind === "resolution" && <>
        <p>{typeof event.content.action === "string" ? event.content.action : "Saved decision"}: {typeof event.content.reason === "string" ? event.content.reason : ""}</p>
        {typeof event.content.corrected_value === "string" && <p>Reviewer supplied: {event.content.corrected_value}</p>}
      </>}
      <div className="rr-actions">{event.run_id && <button disabled={navigationDisabled} onClick={() => onRun(event.run_id!)}>View this run</button>}
        {event.kind === "confirmation" && typeof event.content.snapshot_id === "string" && <button disabled={navigationDisabled} onClick={() => onSnapshot(String(event.content.snapshot_id))}>View confirmed handoff</button>}
      </div>
    </li>)}</ol>
    {cursor && <button disabled={busy} onClick={more}>Load older history</button>}
  </details>;
}
