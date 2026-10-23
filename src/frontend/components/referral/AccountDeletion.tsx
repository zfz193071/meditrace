"use client";
import { useState } from "react";
import { deleteAccount } from "../../lib/referral-api";

export default function AccountDeletion({ csrf, onDeleted }: { csrf: string; onDeleted: () => void }) {
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function remove() {
    if (busy || confirmation !== "DELETE") return;
    setBusy(true); setError("");
    try { await deleteAccount(csrf); onDeleted(); }
    catch { setError("Deletion could not be confirmed. Refresh your session before retrying; access may already have ended."); }
    finally { setBusy(false); }
  }
  return <section className="space-y-3 border-t border-slate-700 pt-6" aria-label="Data retention and account deletion">
    <h2 className="text-lg font-semibold">Data retention and deletion</h2>
    <p>Packets expire 7 days after creation. Unused uploads are removed after 24 hours.
      Deletion ends access immediately and queues all source versions, review history and exports for cleanup, targeted within 24 hours.</p>
    <p>Deleting your account signs out every session and revokes membership. Minimal payment deduplication records are kept for 90 days;
      anonymous cost totals remain. Previously downloaded files cannot be recalled. Provider backups may outlive application deletion;
      their retention is not yet verified for this deployment.</p>
    <form onSubmit={event => { event.preventDefault(); void remove(); }} className="space-y-3">
      <label className="block" htmlFor="delete-account-confirmation">Type DELETE to delete your account and all packets</label>
      <input id="delete-account-confirmation" className="rounded border border-slate-500 bg-slate-900 px-3 py-2" autoComplete="off"
        value={confirmation} disabled={busy} onChange={event => setConfirmation(event.target.value)} />
      <button className="block rounded border border-red-400 px-5 py-3 disabled:opacity-50" disabled={busy || confirmation !== "DELETE"}>
        {busy ? "Deleting account…" : "Delete account and all packets"}
      </button>
    </form>
    {error && <p role="alert">{error}</p>}
  </section>;
}
