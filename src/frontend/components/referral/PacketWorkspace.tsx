"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { workspaceApi as api, errorMessage, operationKey, type Packet, type Revision, type Run, type Membership, type Document } from "../../lib/referral-api/workspace";
import { type Access, expiryLabel, useUnsavedChanges } from "./WorkspaceGate";
import { RunPanel } from "./RunPanel";
import { ReviewWorkspace } from "./ReviewWorkspace";
import { ManualDraft } from "./ManualDraft";

const same = (a: string[], b: string[]) => a.length === b.length && a.every((value, i) => value === b[i]);
const parseMessage: Record<string, string> = { PDF_ENCRYPTED: "Password-protected PDFs are not supported.", PDF_NO_TEXT: "No readable text. Paste the text or use a text PDF.", PDF_TOO_MANY_PAGES: "Page limit exceeded.", TEXT_TOO_LONG: "Text limit exceeded." };
export function PacketWorkspace({ packetId, ...access }: Access & { packetId: string }) {
  const { csrf, onError } = access;
  const [packet, setPacket] = useState<Packet | null>(null);
  const [revision, setRevision] = useState<Revision | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [member, setMember] = useState<Membership | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [savedSelection, setSavedSelection] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [removed, setRemoved] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [reviewDirty, setReviewDirty] = useState(false);
  const [manualDirty, setManualDirty] = useState(false);
  const [restore, setRestore] = useState(0);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const alive = useRef(true);
  const lock = useRef(false);
  const textKey = useRef<string | null>(null);
  const loadVersion = useRef(0);
  const dirty = Boolean(reviewDirty || manualDirty || text || (packet && title !== packet.title) || !same(selected, savedSelection));
  useUnsavedChanges(dirty);
  const fail = useCallback((e: unknown) => { setError(errorMessage(e)); onError(e); }, [onError]);
  const load = useCallback(async (keepInput = false) => {
    const version = ++loadVersion.current;
    try {
      const next = await api.packet(packetId);
      const [rev, latest, membership] = await Promise.all([
        next.current_revision ? api.revision(packetId, next.current_revision) : Promise.resolve(null),
        api.latestRun(packetId), api.membership().catch(e => { onError(e); return null; }),
      ]);
      if (!alive.current || version !== loadVersion.current) return;
      setPacket(next); setRevision(rev); setRun(latest); setMember(membership);
      if (!keepInput) {
        const ids = next.draft.draft_version > 0 && next.draft.base_revision === next.current_revision ? next.draft.selected_document_ids : next.current_document_ids;
        setSelected(ids); setSavedSelection(ids); setTitle(next.title); setText(""); setRestore(n => n + 1);
        if (next.draft.draft_version > 0 && next.draft.base_revision !== next.current_revision) setNotice("The selection draft was for an older source version. The current saved version is shown; reselect before saving.");
        else if (next.draft.draft_version > 0) setNotice(`Restored your saved selection. Last saved step: ${next.draft.last_location}.`);
      }
    } catch (e) { if (alive.current && version === loadVersion.current) fail(e); }
  }, [packetId, fail, onError]);
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false; }; }, [load]);
  // Parsing state is read-only. After eight queries the user can explicitly reload.
  useEffect(() => {
    if (!packet?.documents.some(d => ["uploading", "parsing"].includes(d.parse_status)) || attempt >= 8) return;
    const timer = setTimeout(() => { setAttempt(n => n + 1); void load(true); }, 4000);
    return () => clearTimeout(timer);
  }, [packet, attempt, load]);
  async function action(job: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try { await job(); } catch (e) { if (alive.current) fail(e); }
    finally { lock.current = false; if (alive.current) { setBusy(false); setUploading(""); } }
  }
  async function reload() {
    if (dirty && !window.confirm("Discard unsaved source, manual note and review edits, and reload saved material?")) return;
    setError(""); setAttempt(0); await action(() => load());
  }
  function showResult(doc: Document) {
    if (doc.parse_status === "rejected" || doc.parse_status === "failed") setUploadErrors(errors => [...errors, `${doc.filename}: ${parseMessage[doc.parse_error_code ?? ""] ?? "Parsing failed. Use readable text or a different text PDF."}${doc.parse_error_page ? ` Page ${doc.parse_error_page}.` : ""}`]);
    else setNotice(`${doc.filename} imported. Select it below and save a source version; importing does not change the saved version.`);
  }
  async function uploadFiles(files: File[]) {
    await action(async () => {
      setUploadErrors([]);
      for (const file of files) {
        if (!alive.current) break;
        if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 2 * 1024 * 1024) {
          setUploadErrors(errors => [...errors, `${file.name}: choose a PDF no larger than 2 MiB.`]); continue;
        }
        setUploading(file.name);
        try { const doc = await api.uploadPdf(packetId, file, csrf, operationKey()); if (alive.current) showResult(doc); }
        catch (e) { if (alive.current) { setUploadErrors(errors => [...errors, `${file.name}: ${errorMessage(e)}`]); onError(e); } break; }
      }
      await load(true);
    });
  }
  if (removed) return <section className="rr-card"><h1>Packet deleted</h1><p>Access has ended. Stored files are queued for cleanup.</p><a href="/workspace">Back to packets</a></section>;
  if (!packet) return <section className="rr-card"><h1>Referral packet</h1>{error ? <><p role="alert">{error}</p><button onClick={reload}>Retry loading</button></> : <p role="status">Loading saved material…</p>}</section>;
  const sourceDirty = !same(selected, packet.current_document_ids);
  const ready = selected.every(id => packet.documents.find(d => d.id === id)?.parse_status === "ready");
  const pages = packet.documents.filter(d => selected.includes(d.id)).reduce((sum, d) => sum + (d.page_count ?? 0), 0);
  return <>
    <div className="rr-heading"><div><a href="/workspace">All packets</a><h1>{packet.title}</h1><p>{expiryLabel(packet.expires_at)} · Expires {new Date(packet.expires_at).toLocaleString()}</p></div><button disabled={busy} onClick={reload}>Reload saved material</button></div>
    {error && <p role="alert" className="rr-alert">{error}</p>}{notice && <p role="status" className="rr-notice">{notice}</p>}
    {dirty && <p className="rr-alert">Unsaved changes. Save or discard your source, note or review edits before leaving.</p>}
    <details className="rr-card"><summary>Packet settings</summary><label htmlFor="rename-title">Packet title</label><input id="rename-title" maxLength={200} value={title} disabled={busy} onChange={e => setTitle(e.target.value)} />
      <div className="rr-actions"><button disabled={busy || !title.trim() || title === packet.title} onClick={() => action(async () => { const next = await api.rename(packetId, { title: title.trim() }, csrf); setPacket(p => p && { ...p, title: next.title }); setTitle(next.title); })}>Save title</button>
      <button disabled={busy} onClick={() => setDeleting(true)}>Delete packet</button></div>
      {deleting && <div role="group" aria-label="Confirm packet deletion"><p>Delete all access to this packet immediately? Physical cleanup will follow.</p><button className="rr-danger" disabled={busy} onClick={() => action(async () => { await api.remove(packetId, csrf); setText(""); setSelected([]); setSavedSelection([]); setRemoved(true); })}>Confirm delete</button><button disabled={busy} onClick={() => setDeleting(false)}>Keep packet</button></div>}
    </details>
    <div className="rr-editor-grid"><section className="rr-card"><h2>1. Import sources</h2><p>Text PDFs only, up to 2 MiB each. Files upload one at a time. Importing never starts an AI check.</p>
      <label htmlFor="pdf-upload">Choose PDF files</label><input id="pdf-upload" type="file" accept="application/pdf,.pdf" multiple disabled={busy} onChange={e => { const files = Array.from(e.target.files ?? []); e.target.value = ""; void uploadFiles(files); }} />
      {uploading && <p role="status">Uploading and parsing: {uploading}</p>}
      <label htmlFor="source-text">Or paste synthetic referral text</label><textarea id="source-text" rows={7} value={text} disabled={busy} onChange={e => { setText(e.target.value); textKey.current = null; }} />
      <p className="rr-muted">{Array.from(text).length} / 10,000 characters. Pasted text is kept only in memory until imported.</p>
      <button disabled={busy || !text.trim() || Array.from(text).length > 10_000} onClick={() => action(async () => {
        textKey.current ??= operationKey(); const doc = await api.uploadText(packetId, { text, filename: "pasted-text.txt" }, csrf, textKey.current);
        setText(""); textKey.current = null; showResult(doc); await load(true);
      })}>Import pasted text</button>
      {uploadErrors.length > 0 && <ul role="alert" className="rr-alert">{uploadErrors.map((value, i) => <li key={i}>{value}</li>)}</ul>}
    </section>
    <section className="rr-card"><h2>2. Select and save a source version</h2><p>Up to 5 documents, 25 pages and 30,000 combined characters. Imported candidates are separate from the saved version.</p>
      <p>Saved source version: <strong>{packet.current_revision || "None"}</strong> · Selected: {selected.length}/5 · Pages: {pages}/25</p>
      {packet.documents.length === 0 ? <p>No imported documents yet.</p> : <ul className="rr-documents">{packet.documents.map(doc => <li key={doc.id}>
        <label className="rr-check"><input type="checkbox" checked={selected.includes(doc.id)} disabled={busy || doc.parse_status !== "ready" || (!selected.includes(doc.id) && selected.length >= 5)} onChange={e => setSelected(ids => e.target.checked ? [...ids, doc.id] : ids.filter(id => id !== doc.id))} /><span>{doc.filename}</span></label>
        <p>{packet.current_document_ids.includes(doc.id) ? "In saved version" : "Candidate - not in saved version"} · {doc.parse_status} {doc.page_count ? `· ${doc.page_count} pages` : ""}</p>
        {doc.parse_error_code && <p className="rr-alert">{parseMessage[doc.parse_error_code] ?? "This document could not be parsed safely. Import readable text or a replacement PDF."}{doc.parse_error_page ? ` Page ${doc.parse_error_page}.` : ""}</p>}
      </li>)}</ul>}
      {attempt >= 8 && <p role="status">Automatic parsing checks paused. Reload saved material to check again; files will not upload again automatically.</p>}
      <div className="rr-actions"><button disabled={busy || same(selected, savedSelection)} onClick={() => action(async () => {
        const saved = await api.saveDraft(packetId, { expected_draft_version: packet.draft.draft_version, base_revision: packet.current_revision, selected_document_ids: selected, last_location: "documents" }, csrf);
        setPacket(p => p && { ...p, draft: saved }); setSavedSelection([...selected]); setNotice("Selection draft saved. It will restore after sign-in or a payment return. The source version has not changed.");
      })}>Save selection draft</button>
      <button className="rr-primary" disabled={busy || manualDirty || reviewDirty || !sourceDirty || !ready || pages > 25 || (!packet.current_revision && selected.length === 0)} onClick={() => action(async () => {
        const next = await api.saveRevision(packetId, { expected_revision: packet.current_revision, document_ids: selected }, csrf);
        setRevision(next); setSavedSelection([...selected]); setNotice(`Source version ${next.revision_number} saved. Previous checks remain historical.`); await load(true);
      })}>Save source version</button></div>
    </section></div>
    <RunPanel key={`${packetId}:${packet.current_revision}:${restore}`} packetId={packetId} revision={revision} initialRun={run} membership={member} caps={access.capabilities} csrf={csrf} sourceDirty={sourceDirty || busy || reviewDirty} onError={onError} onRunChange={setRun} />
    <ReviewWorkspace key={`review:${packetId}:${packet.current_revision}:${restore}`} packet={packet} run={run} csrf={csrf} sourceDirty={sourceDirty || busy || manualDirty} onError={onError} onDirty={setReviewDirty} />
    {reviewDirty && <p className="rr-notice">Save or discard review edits before changing the source version or starting another check.</p>}
    {manualDirty && <p className="rr-notice">Save your manual note before changing the source version.</p>}
    <ManualDraft onDirty={setManualDirty} key={`manual:${packetId}:${packet.current_revision}:${restore}`} packet={packet} revision={revision} {...access} />
  </>;
}
