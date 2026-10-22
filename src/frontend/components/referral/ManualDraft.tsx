"use client";
import { useEffect, useState } from "react";
import { workspaceApi as api, errorMessage, type Packet, type Revision, type HandoffDraft, type Snapshot } from "../../lib/referral-api/workspace";
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
  useUnsavedChanges(note !== saved);
  useEffect(() => { onDirty(note !== saved); return () => onDirty(false); }, [note, saved, onDirty]);
  useEffect(() => {
    let alive = true;
    api.handoffDraft(packet.id).then(draft => {
      if (!alive) return;
      const fields = savedFields(draft, revision);
      const value = fields["handoff.notes"] ?? "";
      const rest = { ...fields }; delete rest["handoff.notes"]; setOtherFields(rest);
      setNote(value); setSaved(value); setReady(true);
      if (draft?.draft && (draft.stale || draft.draft.run_id)) setMessage("A previous draft belongs to another review. This manual note starts separately.");
    }).catch(e => { if (alive) { setError(errorMessage(e)); onError(e); } });
    return () => { alive = false; };
  }, [packet.id, revision?.id, onError]); // eslint-disable-line react-hooks/exhaustive-deps
  async function save() {
    if (!revision || busy) return;
    setBusy(true); setError("");
    try {
      const event = await api.saveManual(packet.id, { mode: "manual", expected_revision: packet.current_revision,
        expected_review_version: version, fields: { ...otherFields, ...(note.trim() ? { "handoff.notes": note } : {}) } }, csrf);
      setSaved(note); setVersion(event.review_version); setMessage("Manual note saved. Reviewer supplied; not automatically checked."); setSnapshot(null);
    } catch (e) { setError(errorMessage(e)); onError(e); } finally { setBusy(false); }
  }
  async function confirm() {
    if (!revision || busy) return;
    setBusy(true); setError("");
    try {
      const next = await api.confirm(packet.id, { mode: "manual", revision_id: revision.id, expected_review_version: version }, csrf);
      setSnapshot(next); setVersion(next.review_version); setConfirming(false); setMessage("Manual confirmation saved. No AI check was performed.");
    } catch (e) { setError(errorMessage(e)); onError(e); } finally { setBusy(false); }
  }
  return <section id="manual-review" className="rr-card"><h2>Manual handoff</h2>
    <p>No membership or AI call required. Notes are marked “Reviewer supplied” and “Not automatically checked”.</p>
    {revision && <p>Applies to saved source version {packet.current_revision}. Unsaved source selections are not included.</p>}
    {!revision && <p>Save a source version before adding a handoff note.</p>}
    {error && <p role="alert" className="rr-alert">{error} Reload saved material above before retrying.</p>}
    {message && <p role="status">{message}</p>}
    <label htmlFor="manual-note">Reviewer supplied note</label><textarea id="manual-note" rows={5} maxLength={4000} value={note} disabled={busy || !ready || !revision} onChange={e => { setNote(e.target.value); setConfirming(false); }} />
    <div className="rr-actions"><button disabled={busy || !ready || !revision || note === saved} onClick={save}>Save manual note</button>
      <button disabled={busy || !ready || !revision || note !== saved} onClick={() => setConfirming(true)}>Confirm manual handoff</button></div>
    {confirming && <div className="rr-notice"><p>This confirmation does not establish completeness or resolve an automated finding. The exported handoff will say “Not automatically checked”.</p>
      <button disabled={busy} onClick={confirm}>Confirm without automated check</button><button disabled={busy} onClick={() => setConfirming(false)}>Keep editing</button></div>}
    {snapshot && <div className="rr-actions"><a href={handoffDownloadUrl(packet.id, snapshot.id, "txt")}>Download confirmed text</a><a href={handoffDownloadUrl(packet.id, snapshot.id, "pdf")}>Download confirmed PDF</a></div>}
  </section>;
}
