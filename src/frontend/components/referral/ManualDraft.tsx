"use client";
import { useEffect, useRef, useState } from "react";
import { workspaceApi as api, WorkspaceError, errorMessage, type Packet, type Revision, type HandoffDraft, type Snapshot } from "../../lib/referral-api/workspace";
import { handoffDownloadUrl } from "../../lib/referral-api/handoff";
import { type Access, useUnsavedChanges } from "./WorkspaceGate";

function savedFields(draft: HandoffDraft | null, revision: Revision | null): Record<string, string> {
  if (!draft?.draft || draft.stale || draft.draft.run_id || draft.draft.revision_id !== revision?.id) return {};
  const fields = draft.draft.content.fields;
  if (typeof fields !== "object" || !fields) return {};
  return Object.fromEntries(Object.entries(fields).flatMap(([name, field]) =>
    typeof field === "object" && field && "value" in field && typeof field.value === "string" ? [[name, field.value]] : []));
}
export function ManualDraft({ packet, revision, csrf, onError, onDirty }: Access & { packet: Packet; revision: Revision | null; onDirty: (dirty: boolean) => void }) {
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState("");
  const [otherFields, setOtherFields] = useState<Record<string, string>>({});
  const [version, setVersion] = useState(packet.review_version);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [compared, setCompared] = useState(false);
  const request = useRef(0);
  const lock = useRef(false);
  useUnsavedChanges(note !== saved);
  useEffect(() => { onDirty(note !== saved); return () => onDirty(false); }, [note, saved, onDirty]);
  useEffect(() => {
    const current = ++request.current;
    api.handoffDraft(packet.id).then(draft => {
      if (current !== request.current) return;
      const fields = savedFields(draft, revision);
      const value = fields["handoff.notes"] ?? "";
      const rest = { ...fields }; delete rest["handoff.notes"]; setOtherFields(rest);
      setNote(value); setSaved(value); setReady(true);
      if (draft?.draft && (draft.stale || draft.draft.run_id)) setMessage("A previous draft belongs to another review. This manual note starts separately.");
    }).catch(e => { if (current === request.current) { setBlocked(true); setError(errorMessage(e)); onError(e); } });
    return () => { request.current += 1; };
  }, [packet.id, revision?.id, onError]); // eslint-disable-line react-hooks/exhaustive-deps
  async function reload() {
    if (!revision || lock.current) return;
    lock.current = true; const current = ++request.current;
    setBusy(true); setError(""); setMessage(""); setConfirming(false); setSnapshot(null);
    try {
      // Bracket the draft read with the packet's monotonic versions. A newer
      // version must never authorize saving fields read before another edit.
      const before = await api.packet(packet.id);
      if (current !== request.current) return;
      const draft = await api.handoffDraft(packet.id);
      if (current !== request.current) return;
      const after = await api.packet(packet.id);
      if (current !== request.current) return;
      if (before.current_revision !== packet.current_revision || after.current_revision !== packet.current_revision) throw new WorkspaceError("SOURCE_CHANGED", 409);
      if (before.review_version !== after.review_version) throw new WorkspaceError("REVIEW_CONFLICT", 409);
      const fields = savedFields(draft, revision);
      const value = fields["handoff.notes"] ?? "";
      const rest = { ...fields }; delete rest["handoff.notes"];
      if (!ready) setNote(value);
      setSaved(value); setOtherFields(rest); setVersion(after.review_version);
      setReady(true); setBlocked(false); setCompared(true);
      setMessage("Saved manual note loaded for comparison. Your local note is retained; review the saved fields before saving again.");
    } catch (e) { if (current === request.current) { setBlocked(true); setError(errorMessage(e)); onError(e); } }
    finally { if (current === request.current) { lock.current = false; setBusy(false); } }
  }
  async function save() {
    if (!revision || !ready || blocked || note === saved || lock.current) return;
    lock.current = true; const current = ++request.current;
    setBusy(true); setError(""); setMessage(""); setSnapshot(null); setConfirming(false);
    try {
      const event = await api.saveManual(packet.id, { mode: "manual", expected_revision: packet.current_revision,
        expected_review_version: version, fields: { ...otherFields, ...(note.trim() ? { "handoff.notes": note } : {}) } }, csrf);
      if (current !== request.current) return;
      setSaved(note); setVersion(event.review_version); setCompared(false); setMessage("Manual note saved. Reviewer supplied; not automatically checked.");
    } catch (e) { if (current === request.current) { setBlocked(true); setError(errorMessage(e)); onError(e); } }
    finally { if (current === request.current) { lock.current = false; setBusy(false); } }
  }
  async function confirm() {
    if (!revision || !ready || blocked || note !== saved || lock.current) return;
    lock.current = true; const current = ++request.current;
    setBusy(true); setError(""); setMessage(""); setSnapshot(null);
    try {
      const next = await api.confirm(packet.id, { mode: "manual", revision_id: revision.id, expected_review_version: version }, csrf);
      if (current !== request.current) return;
      setSnapshot(next); setVersion(next.review_version); setConfirming(false); setMessage("Manual confirmation saved. No AI check was performed.");
    } catch (e) { if (current === request.current) { setBlocked(true); setConfirming(false); setError(errorMessage(e)); onError(e); } }
    finally { if (current === request.current) { lock.current = false; setBusy(false); } }
  }
  return <section id="manual-review" className="rr-card"><h2>Manual handoff</h2>
    <p>No membership or AI call required. Notes are marked “Reviewer supplied” and “Not automatically checked”.</p>
    {revision && <p>Applies to saved source version {packet.current_revision}. Unsaved source selections are not included.</p>}
    {!revision && <p>Save a source version before adding a handoff note.</p>}
    {error && <p role="alert" className="rr-alert">{error} Your local note is retained below. Reload the saved manual note and compare before retrying. If sources changed, keep a copy of your note before reloading the packet.</p>}
    {message && <p role="status">{message}</p>}
    <button disabled={busy || !revision} onClick={reload}>Reload saved manual note</button>
    {busy && <p role="status">Reading or saving manual handoff…</p>}
    {compared && <div className="rr-notice" aria-label="Saved manual note for comparison"><h3>Saved manual note · Review version {version}</h3>
      <p>{saved || "No manual note is saved for this source version."}</p>
      {Object.entries(otherFields).map(([name, value]) => <div key={name}><strong>{name.replace(/[_.]/g, " ")} · Reviewer supplied</strong><p>{value}</p></div>)}
      <button disabled={busy || blocked || note === saved} onClick={() => { setNote(saved); setConfirming(false); }}>Use saved manual note</button>
    </div>}
    <label htmlFor="manual-note">Reviewer supplied note</label><textarea id="manual-note" rows={5} maxLength={4000} value={note} disabled={busy || !ready || !revision} onChange={e => { setNote(e.target.value); setConfirming(false); }} />
    <div className="rr-actions"><button disabled={busy || blocked || !ready || !revision || note === saved} onClick={save}>Save manual note</button>
      <button disabled={busy || blocked || !ready || !revision || note !== saved} onClick={() => setConfirming(true)}>Confirm manual handoff</button></div>
    {confirming && <div className="rr-notice"><p>This confirmation does not establish completeness or resolve an automated finding. The exported handoff will say “Not automatically checked”.</p>
      <button disabled={busy || blocked || note !== saved} onClick={confirm}>Confirm without automated check</button><button disabled={busy} onClick={() => setConfirming(false)}>Keep editing</button></div>}
    {snapshot && <div className="rr-actions"><a href={handoffDownloadUrl(packet.id, snapshot.id, "txt")}>Download confirmed text</a><a href={handoffDownloadUrl(packet.id, snapshot.id, "pdf")}>Download confirmed PDF</a></div>}
  </section>;
}
