import assets from "./demo-assets.json";
import type { ReviewTransport } from "../../components/referral/ReviewTransport";
import { WorkspaceError, type Packet, type Run, type Revision, type Page, type ReviewState, type ReviewEvent, type Snapshot } from "./workspace";
import type { HandoffView } from "./handoff";

type Asset = { packet: Packet; revision: Revision; run: Run; pages: Page[]; originals: Record<string, string> };
// Generated JSON is validated by scripts/referral_demo_assets.py against backend contracts.
const data = assets as Record<"normal" | "missing" | "identity" | "prepared", Asset>;
export type DemoCase = "normal" | "missing" | "identity";
const clone = <T,>(value: T): T => structuredClone(value);
const status = { resolve: "resolved", dismiss: "dismissed", defer: "unresolved", reopen: "open" } as const;
const actor = "27f38907-8e6e-4ffb-bda3-43f261716710";

/** A fresh, isolated session. No fetch, persistence, provider or private workspace API. */
export function createDemoSession(key: DemoCase) {
  let current = clone(data[key]);
  const versions = new Map([[current.run.id, current]]);
  const decisions = new Map<string, ReviewState["decisions"]>();
  const events: ReviewEvent[] = [];
  const snapshots = new Map<string, { snapshot: Snapshot; view: HandoffView }>();
  const operations = new Map<string, { signature: string; event: ReviewEvent }>();
  let reviewVersion = 0;
  const fail = (code: string): never => { throw new WorkspaceError(code, 409); };
  const owned = (pid: string) => { if (pid !== current.packet.id) fail("NOT_FOUND"); };
  const get = (rid: string) => versions.get(rid) ?? fail("NOT_FOUND");
  const isStale = (a: Asset) => a.revision.id !== current.revision.id;
  const check = (a: Asset, expected: number) => {
    if (isStale(a)) fail("STALE_RUN");
    if (expected !== reviewVersion) fail("REVIEW_CONFLICT");
  };
  function event(a: Asset, kind: ReviewEvent["kind"], content: ReviewEvent["content"]): ReviewEvent {
    const e: ReviewEvent = { id: crypto.randomUUID(), packet_id: a.packet.id, revision_id: a.revision.id, run_id: a.run.id, actor_id: actor, review_version: ++reviewVersion, kind, created_at: new Date().toISOString(), content };
    events.unshift(e); return e;
  }
  const api: ReviewTransport = {
    async run(rid) { const a = get(rid); return clone({ ...a.run, stale: isStale(a) }); },
    async reviewState(rid) {
      const a = get(rid);
      return clone({ run_id: rid, revision: { ...a.revision, is_current: !isStale(a) }, review_version: reviewVersion, stale: isStale(a), decisions: decisions.get(rid) ?? [], parser_version: "text-v1" });
    },
    async page(pid, did, number) {
      owned(pid);
      const page = [...versions.values()].flatMap(a => a.pages).find(p => p.document_id === did && p.page_number === number);
      return clone(page ?? fail("NOT_FOUND"));
    },
    originalUrl(pid, did) { owned(pid); return [...versions.values()].find(a => a.originals[did])?.originals[did] ?? fail("NOT_FOUND"); },
    snapshotUrl: null,
    async resolve(rid, fid, body, _csrf, operation) {
      const a = get(rid), signature = JSON.stringify({ rid, fid, body });
      const prior = operations.get(operation);
      if (prior) { if (prior.signature !== signature) fail("REVIEW_CONFLICT"); return clone(prior.event); }
      check(a, body.expected_review_version);
      if (!a.run.result!.findings.some(f => f.id === fid)) fail("NOT_FOUND");
      if (!Object.hasOwn(status, body.action) || ((body.action === "defer" || body.action === "dismiss") && !body.reason?.trim()) || (body.reason?.length ?? 0) > 4000 || (body.corrected_value !== null && body.corrected_value !== undefined && (!body.corrected_value.trim() || body.corrected_value.length > 4000)) || (body.linked_evidence_ids ?? []).some(id => !a.run.result!.evidence.some(e => e.id === id))) fail("SCHEMA_INVALID");
      const content = { finding_id: fid, action: body.action, status: status[body.action], reason: body.reason ?? "", corrected_value: body.corrected_value ?? null, linked_evidence_ids: [...(body.linked_evidence_ids ?? [])] };
      const e = event(a, "resolution", content);
      decisions.set(rid, [...(decisions.get(rid) ?? []).filter(d => d.finding_id !== fid), { ...content, review_version: e.review_version }]);
      operations.set(operation, { signature, event: e }); return clone(e);
    },
    async history(pid) { owned(pid); return clone({ items: events, next_cursor: null }); },
    async confirm(pid, body) {
      owned(pid);
      if (body.mode !== "assisted" || !body.run_id) fail("SCHEMA_INVALID");
      const a = get(body.run_id!); check(a, body.expected_review_version);
      if (body.revision_id !== a.revision.id) fail("SOURCE_CHANGED");
      const saved = decisions.get(a.run.id) ?? [];
      if (a.run.result!.findings.some(f => !saved.some(d => d.finding_id === f.id && d.status !== "open"))) fail("OPEN_FINDINGS");
      // Freeze before yielding to hashing so concurrent requests cannot confirm the same version.
      const id = crypto.randomUUID(), e = event(a, "confirmation", { snapshot_id: id });
      const payload = clone({ synthetic: true, mode: "precomputed", result: a.run.result!, revision: a.revision, decisions: saved, review_version: e.review_version, confirmed_at: e.created_at });
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(payload)))), b => b.toString(16).padStart(2, "0")).join("");
      const unresolved = saved.some(d => d.status !== "resolved");
      const snapshot: Snapshot = { id, packet_id: pid, revision_id: a.revision.id, run_id: a.run.id, review_version: e.review_version, confirmed_by: actor, confirmed_at: e.created_at, payload, payload_hash: hash, has_unresolved: unresolved, historical: false };
      const identity = a.run.result!.findings.some(f => f.kind === "identity_mismatch" && saved.find(d => d.finding_id === f.id)?.status !== "resolved");
      const view: HandoffView = {
        schema_version: "handoff-v1", snapshot_id: id, packet_id: pid, revision_id: a.revision.id, review_version: e.review_version, confirmed_at: e.created_at, payload_hash: hash, historical: false,
        title: "Referral handoff — synthetic demo", status: unresolved ? "Reviewed — unresolved items remain" : "Reviewed",
        warnings: [...(identity ? ["Identity unresolved — verify dates of birth before using these records together."] : []), "Precomputed synthetic example. Local illustrative confirmation only; not clinical guidance."],
        sections: [
          { heading: "Recorded source facts", paragraphs: a.run.result!.facts.map(f => `${f.field_key}: ${f.value_raw} (${f.assertion_status}${f.temporal_context ? `; ${f.temporal_context}` : ""}) [${f.evidence_ids.join(", ")}]`) },
          { heading: "Human review decisions", paragraphs: a.run.result!.findings.length ? a.run.result!.findings.map(f => { const d = saved.find(d => d.finding_id === f.id)!; return `${f.rule_id} · ${f.message}\nStatus: ${d.status}\nReason: ${d.reason || "Not provided"}${d.corrected_value ? `\nReviewer supplied: ${d.corrected_value}` : ""}\nLinked citations: ${d.linked_evidence_ids.join(", ") || "None"}\nDecision review version: ${d.review_version}`; }) : ["No checklist findings in this prepared result. Reviewed does not mean clinically complete."] },
          { heading: "Source index", paragraphs: a.run.result!.evidence.map(ev => `[${ev.id}] ${a.revision.documents.find(d => d.id === ev.document_id)!.filename} · page ${ev.page_number} · characters ${ev.start_cp}–${ev.end_cp}\n${ev.quote}`) },
          { heading: "Confirmation", paragraphs: [`Source version ${a.revision.revision_number} · Review version ${e.review_version}\n${e.created_at}\nSHA-256 ${hash}`, "This is a local demo snapshot. Refreshing or resetting discards all edits and snapshots. No diagnosis, triage or clinical accuracy claim is made."] },
        ],
      };
      snapshots.set(id, { snapshot: clone(snapshot), view }); return clone(snapshot);
    },
    async handoff(pid, sid) {
      owned(pid); const item = snapshots.get(sid) ?? fail("NOT_FOUND");
      const historical = item.snapshot.revision_id !== current.revision.id || item.snapshot.review_version !== reviewVersion;
      return clone({ ...item.view, historical, warnings: [...(historical ? ["Historical snapshot — not the current review."] : []), ...item.view.warnings] });
    },
  };
  return {
    api,
    packet: () => clone({ ...current.packet, review_version: reviewVersion }),
    initialRun: () => clone(data[key].run),
    loadPreparedRevision() {
      if (key !== "missing" || current.revision.revision_number !== 1) fail("SOURCE_CHANGED");
      current = clone(data.prepared); versions.set(current.run.id, current);
      return clone(current.packet);
    },
    preparedRun: () => { if (key !== "missing" || current.revision.revision_number !== 2) fail("SOURCE_CHANGED"); return clone(current.run); },
  };
}
