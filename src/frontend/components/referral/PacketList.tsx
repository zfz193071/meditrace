"use client";
import { useCallback, useEffect, useState, useRef } from "react";
import { workspaceApi as api, operationKey, errorMessage, type PacketList as List } from "../../lib/referral-api/workspace";
import { type Access, expiryLabel, useUnsavedChanges } from "./WorkspaceGate";

export function PacketList({ csrf, onError }: Access) {
  const [list, setList] = useState<List | null>(null);
  const [title, setTitle] = useState("");
  const [ack, setAck] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const createKey = useRef<string | null>(null);
  const requestVersion = useRef(0);
  const locked = useRef(false);
  const invalidate = useCallback(() => { ++requestVersion.current; locked.current = false; }, []);
  useUnsavedChanges(Boolean(title.trim()));
  async function perform(work: (current: () => boolean) => Promise<void>) {
    if (locked.current) return;
    locked.current = true;
    const version = ++requestVersion.current;
    const current = () => version === requestVersion.current;
    setBusy(true); setError(""); setNotice("");
    try { await work(current); }
    catch (e) { if (current()) { setError(errorMessage(e)); onError(e); } }
    finally { if (current()) { locked.current = false; setBusy(false); } }
  }
  async function readList(cursor: string | undefined, current: () => boolean) {
    const next = await api.list(cursor);
    if (current()) setList(previous => cursor && previous ? { ...next, items: [...previous.items, ...next.items] } : next);
  }
  function load(cursor?: string) { return perform(current => readList(cursor, current)); }
  useEffect(() => {
    void load();
    return invalidate;
  }, [invalidate]); // eslint-disable-line react-hooks/exhaustive-deps
  function create() {
    if (!ack || !title.trim()) return;
    return perform(async current => {
      createKey.current ??= operationKey();
      const packet = await api.create({ title: title.trim(), synthetic_data_ack: true }, csrf, createKey.current);
      if (!current()) return;
      setTitle(""); setAck(false); createKey.current = null;
      setList(previous => ({ items: [packet, ...(previous?.items ?? []).filter(p => p.id !== packet.id)], next_cursor: previous?.next_cursor ?? null }));
    });
  }
  function remove(id: string) {
    return perform(async current => {
      await api.remove(id, csrf);
      if (!current()) return;
      setDeleting(null);
      setList(previous => previous ? { ...previous, items: previous.items.filter(packet => packet.id !== id) } : previous);
      setNotice("Packet access ended. Stored files are queued for cleanup.");
      await readList(undefined, current);
    });
  }
  return <>
    <div className="rr-heading"><div><h1>Your referral packets</h1><p>Prepare sources, check gaps, then review the handoff.</p></div><button disabled={busy} onClick={() => load()}>Refresh list</button></div>
    <p>Packets expire 7 days after creation. Unused uploads expire after 24 hours. Deletion ends access immediately;
      all versions and review history are queued for cleanup within a 24-hour target. Downloaded copies and provider backups may remain.</p>
    {error && <p className="rr-alert" role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <section className="rr-card"><h2>Create a packet</h2>
      <form onSubmit={event => { event.preventDefault(); void create(); }} className="rr-form">
        <label htmlFor="packet-title">Packet title</label><input id="packet-title" maxLength={200} required value={title} disabled={busy} onChange={e => { setTitle(e.target.value); createKey.current = null; }} placeholder="e.g. Synthetic referral - October" />
        <label className="rr-check"><input type="checkbox" checked={ack} disabled={busy} onChange={e => setAck(e.target.checked)} />I am using synthetic data, not real patient information.</label>
        <button className="rr-primary" disabled={busy || !ack || !title.trim()} type="submit">Create packet</button>
      </form>
    </section>
    {!list && !error && <p role="status">Loading packets…</p>}
    {list && list.items.length === 0 && <section className="rr-card"><h2>No packets yet</h2><p>Create a packet to upload text PDFs or paste referral text. Importing does not call AI.</p></section>}
    <div className="rr-packet-grid">{list?.items.map(packet => <section className="rr-card" key={packet.id}>
      <h2><a href={`/workspace/packets/${packet.id}`}>{packet.title}</a></h2>
      <p>{packet.current_revision ? `Saved source version ${packet.current_revision}` : "No saved source version"}</p>
      <p>{expiryLabel(packet.expires_at)} · Expires <time dateTime={packet.expires_at}>{new Date(packet.expires_at).toLocaleString()}</time></p>
      {deleting === packet.id ? <div role="group" aria-label={`Confirm deletion of ${packet.title}`}>
        <p>Delete this packet? Access will end immediately; stored files will be queued for cleanup.</p>
        <div className="rr-actions"><button className="rr-danger" disabled={busy} onClick={() => remove(packet.id)}>Confirm delete</button><button disabled={busy} onClick={() => setDeleting(null)}>Keep packet</button></div>
      </div> : <div className="rr-actions"><a className="rr-button" href={`/workspace/packets/${packet.id}`}>Open packet</a><button disabled={busy} onClick={() => setDeleting(packet.id)}>Delete</button></div>}
    </section>)}</div>
    {list?.next_cursor && <button disabled={busy} onClick={() => load(list.next_cursor ?? undefined)}>Load more packets</button>}
    {busy && <p role="status">Saving or loading…</p>}
  </>;
}
