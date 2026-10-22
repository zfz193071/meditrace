import type { Packet, Revision, Run, Membership, Capabilities, Session } from "../lib/referral-api/workspace";
export const pid = "11111111-1111-4111-8111-111111111111";
export const did = "22222222-2222-4222-8222-222222222222";
export const rid = "33333333-3333-4333-8333-333333333333";
const now = new Date().toISOString();
export const caps: Capabilities = { contract_version: "0.1.0", stage: "foundation", synthetic_data_only: true, demo_cases_available: false, demo_mode_available: true, payment_environment: "test", payments_available: false, mode: "sandbox", workspace_available: true, sandbox_execution_available: true, real_ai_execution_available: false };
export const session: Session = { user: { id: "44444444-4444-4444-8444-444444444444", display_name: "Synthetic reviewer" }, csrf_token: "test-csrf", expires_at: new Date(Date.now() + 3600_000).toISOString(), login_available: true };
export const packet: Packet = { id: pid, title: "Synthetic referral review", state: "ready", current_revision: 1, review_version: 0,
  synthetic_data_ack: true, created_at: now, updated_at: now, expires_at: new Date(Date.now() + 6 * 86400_000).toISOString(), current_document_ids: [did],
  documents: [{ id: did, packet_id: pid, kind: "text", filename: "Synthetic referral letter.txt", byte_size: 100, sha256: "a".repeat(64), parse_status: "ready", parser_version: "text-v1", page_count: 1, created_at: now },
    { id: "55555555-5555-4555-8555-555555555555", packet_id: pid, kind: "pdf", filename: "Synthetic report awaiting readable text.pdf", byte_size: 200, sha256: "b".repeat(64), parse_status: "rejected", parser_version: "pdf-v1", page_count: 1, parse_error_code: "PDF_NO_TEXT", parse_error_page: 1, created_at: now }],
  draft: { packet_id: pid, selected_document_ids: [did], last_location: "documents", base_revision: 1, draft_version: 1, updated_at: now } };
export const revision: Revision = { id: rid, packet_id: pid, revision_number: 1, manifest_hash: "c".repeat(64), is_current: true, created_at: now,
  documents: [{ id: did, kind: "text", filename: packet.documents[0].filename, sha256: "a".repeat(64), parser_version: "text-v1", page_count: 1, byte_size: 100 }] };
export const membership: Membership = { remaining: 4, reserved: 0, real_ai_allowed: false, environment: "test", valid_until: new Date(Date.now() + 86400_000).toISOString() };
export const unknownRun: Run = { id: "66666666-6666-4666-8666-666666666666", packet_id: pid, revision_id: rid, state: "outcome_unknown", mode: "fake", stale: false, phase: "unknown",
  checklist_version: "outpatient-referral-demo@1", prompt_version: "synthetic", schema_version: "0.1.0", model_requested: "fake-extraction-v1", model_reported: null,
  created_at: new Date(Date.now() - 120_000).toISOString(), finished_at: null, lease_expires_at: null, error_code: "PROVIDER_TIMEOUT", usage: null, result: null };
