"use client";
import { useReviewTransport } from "./ReviewTransport";
import { useEffect, useState } from "react";
import { errorMessage, type Evidence, type Page, type Revision } from "../../lib/referral-api/workspace";
import { evidenceSlice, verifyPageHash } from "../../lib/referral-api/evidence";

export function EvidencePanel({ packetId, evidence, revision, onError }: { packetId: string; evidence: Evidence; revision: Revision; onError: (e: unknown) => void }) {
  const api = useReviewTransport();
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const doc = revision.documents.find(doc => doc.id === evidence.document_id);
  useEffect(() => {
    let alive = true;
    async function read() {
      setPage(null); setError("");
      try {
        if (!doc || revision.packet_id !== packetId) throw new Error("Invalid source");
        const next = await api.page(packetId, evidence.document_id, evidence.page_number);
        if (!evidenceSlice(evidence, next, revision) || !await verifyPageHash(next)) {
          if (alive) setError("Source verification failed. This citation cannot be highlighted; reload the saved review.");
          return;
        }
        if (alive) setPage(next);
      } catch (e) { if (alive) { setError(errorMessage(e)); onError(e); } }
    }
    void read(); return () => { alive = false; };
  }, [api, packetId, evidence, revision, doc, onError, attempt]);
  const slice = page && evidenceSlice(evidence, page, revision);
  return <article className="rr-evidence" aria-label={`${doc?.filename ?? "Unavailable source"}, page ${evidence.page_number}`}>
    <h4>{doc?.filename ?? "Source unavailable"}</h4>
    <p className="rr-muted">Source version {revision.revision_number} · Page {evidence.page_number} · Characters {evidence.start_cp}–{evidence.end_cp}</p>
    {error ? <><p role="alert" className="rr-alert">{error}</p><button onClick={() => setAttempt(n => n + 1)}>Retry source</button></> : !slice ? <p role="status">Verifying source text…</p> : <>
      <p className="rr-source-excerpt">{slice.before}<mark>{slice.quote}</mark>{slice.after}</p>
      <details><summary>Read full normalized page</summary><p tabIndex={0} aria-label="Normalized source page" className="rr-full-page">{Array.from(page!.normalized_text).slice(0, evidence.start_cp).join("")}<mark>{slice.quote}</mark>{Array.from(page!.normalized_text).slice(evidence.end_cp).join("")}</p></details>
    </>}
    {doc && <a href={api.originalUrl(packetId, doc.id)} download>Download original {doc.kind === "pdf" ? "PDF" : "text"} — page {evidence.page_number}</a>}
    <p className="rr-muted">The normalized text is the citation reference. Original files are downloaded, not embedded or executed.</p>
  </article>;
}
