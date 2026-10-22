import type { components, operations } from "./generated";
import { REFERRAL_API_PREFIX } from "./index";

type Schema = components["schemas"];
export type Packet = Schema["PacketDetailResponse"];
export type PacketList = Schema["PacketListResponse"];
export type Document = Schema["DocumentResponse"];
export type Revision = Schema["RevisionResponse"];
export type Run = Schema["RunResponse"];
export type Membership = Schema["MembershipResponse"];
export type Capabilities = Schema["Capabilities"];
export type Session = Schema["SessionResponse"];
export type Draft = Schema["PacketDraftResponse"];
export type Snapshot = Schema["SnapshotResponse"];
export type ReviewEvent = Schema["ReviewEvent"];
export type ReviewState = Schema["RunReviewState"];
export type Evidence = Schema["Evidence"];
export type Finding = Schema["Finding"];
export type Page = Schema["DocumentPageResponse"];
export type DecisionInput = Schema["ResolutionInput"];
export type ReviewHistory = Schema["ReviewHistory"];
export type HandoffDraft = Schema["HandoffDraftResponse"];

const messages: Partial<Record<Schema["ErrorCode"], string>> = {
  BILLING_DISABLED: "Test payments are not configured yet.",
  PAYMENT_PENDING: "Payment could not be confirmed yet. Retry with the same order; do not make another payment.",
  MEMBERSHIP_ACTIVE: "Your membership is still active. It cannot be extended or repurchased.",
  AUTH_REQUIRED: "Your session ended. Sign in again; saved material is retained until its expiry.",
  FORBIDDEN: "Access could not be verified. Refresh your session before trying again.",
  NOT_FOUND: "This material is unavailable, deleted or expired.",
  REVISION_CONFLICT: "The saved source version changed in another tab. Reload saved material before saving again.",
  DRAFT_CONFLICT: "The saved selection changed in another tab. Reload it before saving again.",
  REVIEW_CONFLICT: "The review changed in another tab. Reload saved decisions before saving again.",
  FILE_TOO_LARGE: "This PDF exceeds 2 MiB. Choose a smaller document.",
  FILE_UNSUPPORTED: "Use a text PDF or paste text. Scans and unsupported files cannot be checked.",
  DOCUMENT_LIMIT: "The document limit has been reached.",
  PACKET_INPUT_LIMIT: "This version exceeds the combined file, page or text limit. Reduce the selection.",
  PARSE_COVERAGE_INCOMPLETE: "Every selected document must finish parsing successfully.",
  PACKET_LIMIT: "You already have 10 active packets. Delete one before creating another.",
  SCHEMA_INVALID: "Check the input and selection limits before saving.",
  MEMBERSHIP_REQUIRED: "An active test membership is required for checks. Manual review remains available.",
  QUOTA_EXHAUSTED: "No check credits remain. You can still organize and review manually.",
  BUDGET_EXHAUSTED: "AI spending is currently unavailable. Manual review remains available.",
  RATE_LIMITED: "Too many requests. Wait a minute, then check the saved state.",
  RUN_ACTIVE: "A check is already active. Query its status instead of starting another.",
  SOURCE_CHANGED: "Sources changed. Save and review the current source version.",
  OPEN_FINDINGS: "Some review items are still open. Reload saved decisions and explicitly handle each item.",
  STALE_RUN: "This run belongs to an earlier source version.",
  SERVICE_NOT_READY: "The service is unavailable. Saved material has not been removed.",
};

export class WorkspaceError extends Error {
  constructor(public code: string, public status = 0) {
    super(messages[code as Schema["ErrorCode"]] ?? "The request could not be confirmed. Reload saved state before retrying.");
  }
}
export function errorMessage(error: unknown): string {
  return error instanceof WorkspaceError ? error.message : "Connection interrupted. Check your connection and reload saved state. No check will restart automatically.";
}
export const operationKey = () => crypto.randomUUID();
const id = encodeURIComponent;

// No retries here, particularly for execute. Every request has a finite deadline.
async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 20_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(REFERRAL_API_PREFIX + path, { ...options, signal: controller.signal,
      credentials: "same-origin", cache: "no-store" });
    if (!response.ok) {
      let code = "REQUEST_FAILED";
      try { const data = await response.json(); if (typeof data?.error?.code === "string") code = data.error.code; } catch { /* Never expose raw error bodies. */ }
      throw new WorkspaceError(code, response.status);
    }
    return await response.json();
  } finally { clearTimeout(timer); }
}
function mutation<T>(path: string, method: string, body: unknown, csrf: string, key = operationKey(), timeoutMs?: number): Promise<T> {
  const form = body instanceof FormData;
  return request<T>(path, { method, headers: { "X-CSRF-Token": csrf, "Idempotency-Key": key,
    ...(form ? {} : { "Content-Type": "application/json" }) },
    ...(body === undefined ? {} : { body: form ? body : JSON.stringify(body) }) }, timeoutMs);
}
export const workspaceApi = {
  session: () => request<Session>("/auth/session"),
  capabilities: () => request<Capabilities>("/capabilities"),
  checkout: (returnPath: string, csrf: string, key: string) => mutation<Schema["OrderResponse"]>("/billing/checkout", "POST", { return_path: returnPath }, csrf, key),
  order: (orderId: string) => request<Schema["OrderResponse"]>(`/billing/orders/${id(orderId)}`),
  membership: () => request<Membership>("/membership"),
  list: (cursor?: string) => request<PacketList>(`/packets${cursor ? `?cursor=${id(cursor)}` : ""}`),
  create: (body: Schema["CreatePacketInput"], csrf: string, key: string) => mutation<Schema["PacketResponse"]>("/packets", "POST", body, csrf, key),
  packet: (pid: string) => request<Packet>(`/packets/${id(pid)}`),
  rename: (pid: string, body: Schema["UpdatePacketInput"], csrf: string) => mutation<Schema["PacketResponse"]>(`/packets/${id(pid)}`, "PATCH", body, csrf),
  remove: (pid: string, csrf: string) => mutation<Schema["PacketDeleteResponse"]>(`/packets/${id(pid)}`, "DELETE", undefined, csrf),
  uploadText: (pid: string, body: operations["upload_document"]["requestBody"]["content"]["application/json"], csrf: string, key: string) => mutation<Document>(`/packets/${id(pid)}/documents`, "POST", body, csrf, key, 75_000),
  uploadPdf: (pid: string, file: File, csrf: string, key: string) => {
    const form = new FormData(); form.append("file", file);
    return mutation<Document>(`/packets/${id(pid)}/documents`, "POST", form, csrf, key, 75_000);
  },
  document: (pid: string, did: string) => request<Document>(`/packets/${id(pid)}/documents/${id(did)}`),
  saveDraft: (pid: string, body: Schema["SavePacketDraftInput"], csrf: string) => mutation<Draft>(`/packets/${id(pid)}/draft`, "PUT", body, csrf),
  saveRevision: (pid: string, body: Schema["SaveRevisionInput"], csrf: string) => mutation<Revision>(`/packets/${id(pid)}/revisions`, "POST", body, csrf),
  revision: (pid: string, version: number) => request<Revision>(`/packets/${id(pid)}/revisions/${version}`),
  latestRun: (pid: string) => request<Run | null>(`/packets/${id(pid)}/runs/latest`),
  run: (rid: string) => request<Run>(`/runs/${id(rid)}`),
  createRun: (pid: string, body: Schema["CreateRunInput"], csrf: string, key: string) => mutation<Run>(`/packets/${id(pid)}/runs`, "POST", body, csrf, key),
  execute: (rid: string, csrf: string, key: string) => mutation<Run>(`/runs/${id(rid)}/execute`, "POST", undefined, csrf, key, 185_000),
  reconcile: (rid: string, csrf: string) => mutation<Run>(`/runs/${id(rid)}/reconcile`, "POST", undefined, csrf),
  cancel: (rid: string, csrf: string) => mutation<Run>(`/runs/${id(rid)}/cancel`, "POST", undefined, csrf),
  handoffDraft: (pid: string) => request<HandoffDraft>(`/packets/${id(pid)}/handoff-draft`),
  saveManual: (pid: string, body: Schema["HandoffDraftInput"], csrf: string) => mutation<ReviewEvent>(`/packets/${id(pid)}/handoff-draft`, "PUT", body, csrf),
  reviewState: (rid: string) => request<ReviewState>(`/runs/${id(rid)}/review`),
  page: (pid: string, did: string, page: number) => request<Page>(`/packets/${id(pid)}/documents/${id(did)}/pages/${page}`),
  resolve: (rid: string, fid: string, body: DecisionInput, csrf: string, key: string) => mutation<ReviewEvent>(`/runs/${id(rid)}/findings/${id(fid)}/resolutions`, "POST", body, csrf, key),
  history: (pid: string, cursor?: string) => request<ReviewHistory>(`/packets/${id(pid)}/review-history${cursor ? `?cursor=${id(cursor)}` : ""}`),
  handoff: (pid: string, sid: string) => request<Schema["HandoffView"]>(`/packets/${id(pid)}/snapshots/${id(sid)}/handoff`),
  confirm: (pid: string, body: Schema["ConfirmInput"], csrf: string) => mutation<Snapshot>(`/packets/${id(pid)}/confirm`, "POST", body, csrf),
};
