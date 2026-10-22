import type { Run, ReviewState, Page, Snapshot } from "../lib/referral-api/workspace";
import type { HandoffView } from "../lib/referral-api/handoff";
import { packet, revision, unknownRun, did, pid } from "./workspace";
export const otherDid = "77777777-7777-4777-8777-777777777777";
export const findingId = "88888888-8888-4888-8888-888888888888";
export const missingId = "99999999-9999-4999-8999-999999999999";
export const pageOne: Page = { document_id: did, page_number: 1, parser_version: "text-v1", parse_quality: "ready", normalized_text: "Synthetic referral letter\nPatient: Alex Example\nDate of birth: 1980-04-03\nReferral reason: specialist review.\n", text_hash: "2ade177d82d0016b19b6f7a95321f7243b94cd0314edc3d133ced14273f5d2a8" };
export const pageTwo: Page = { ...pageOne, document_id: otherDid, normalized_text: "Synthetic intake note\nPatient: Alex Example\nDate of birth: 1981-04-03\n<script>alert('synthetic')</script>\n", text_hash: "3a7b26c3d2823f468a9fbc67d91d2bb4d2b0a3d00613c0a3d87f4fc071f422ea" };
export const reviewState: ReviewState = { run_id: unknownRun.id, review_version: 0, stale: false, decisions: [], revision: { ...revision, documents: [...revision.documents, { ...revision.documents[0], id: otherDid, filename: "Synthetic intake note.txt" }] } };
export const reviewRun: Run = { ...unknownRun, state: "succeeded", phase: "complete", error_code: null, finished_at: packet.created_at, result: {
  run_id: unknownRun.id, revision_id: revision.id, mode: "fake", created_at: packet.created_at, checklist_version: unknownRun.checklist_version, prompt_version: "synthetic", schema_version: "0.1.0",
  evidence: [
    { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", document_id: did, page_number: 1, start_cp: 63, end_cp: 73, quote: "1980-04-03", text_hash: pageOne.text_hash },
    { id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", document_id: otherDid, page_number: 1, start_cp: 59, end_cp: 69, quote: "1981-04-03", text_hash: pageTwo.text_hash }
  ],
  facts: [
    { id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", field_key: "patient.dob", value_raw: "1980-04-03", assertion_status: "stated", temporal_context: null, value_normalized: null, evidence_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"] },
    { id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd", field_key: "patient.dob", value_raw: "1981-04-03", assertion_status: "stated", temporal_context: null, value_normalized: null, evidence_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"] }
  ],
  findings: [
    { id: findingId, kind: "identity_mismatch", rule_id: "C02", checklist_version: unknownRun.checklist_version, field_keys: ["patient.dob"], fact_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc", "dddddddd-dddd-4ddd-8ddd-dddddddddddd"], evidence_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"], checked_document_ids: [did, otherDid], message: "The two sources record different dates of birth. Verify identity before relying on either date." },
    { id: missingId, kind: "missing", rule_id: "C03", checklist_version: unknownRun.checklist_version, field_keys: ["referrer.contact"], fact_ids: [], evidence_ids: [], checked_document_ids: [did, otherDid], message: "Referrer contact information was not found in the supplied material." }
  ]
} };
export const snapshot: Snapshot = { id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", packet_id: pid, revision_id: revision.id, run_id: reviewRun.id, review_version: 3, confirmed_by: did, confirmed_at: packet.created_at, payload: {}, payload_hash: "f".repeat(64), has_unresolved: true, historical: false };
export const handoffView: HandoffView = { schema_version: "handoff-v1", snapshot_id: snapshot.id, packet_id: pid, revision_id: revision.id, review_version: 3, confirmed_at: packet.created_at, payload_hash: snapshot.payload_hash, historical: false, title: "Synthetic referral handoff", status: "Reviewed — unresolved items remain", warnings: ["Identity unresolved"], sections: [{ heading: "Reviewer decisions", paragraphs: ["Date of birth requires verification. Reviewer supplied; unresolved."] }, { heading: "Source index", paragraphs: ["Synthetic referral letter.txt · page 1", "Synthetic intake note.txt · page 1"] }] };
