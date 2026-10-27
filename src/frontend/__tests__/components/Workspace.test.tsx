import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { workspaceApi as api, WorkspaceError } from "../../lib/referral-api/workspace";
import { PacketWorkspace } from "../../components/referral/PacketWorkspace";
import { PacketList } from "../../components/referral/PacketList";
import { RunPanel } from "../../components/referral/RunPanel";
import Workspace from "../../components/referral/Workspace";
import { caps, session, packet, revision, membership, unknownRun, pid, did } from "../../test-support/workspace";
import { webcrypto } from "node:crypto";

// JSDOM lacks these browser APIs. Read the actual File bytes and use Node's
// Web Crypto implementation so equal-size, equal-name content is not conflated.
beforeAll(() => {
  Object.defineProperty(crypto, "subtle", { configurable: true, value: webcrypto.subtle });
  Object.defineProperty(File.prototype, "arrayBuffer", { configurable: true, value() {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(this);
    });
  } });
});

jest.mock("../../lib/referral-api/workspace", () => {
  const original = jest.requireActual("../../lib/referral-api/workspace");
  return { ...original, workspaceApi: Object.fromEntries(Object.keys(original.workspaceApi).map(key => [key, jest.fn()])) };
});
const mock = jest.mocked(api);
const access = { csrf: "test-csrf", capabilities: caps, onError: jest.fn() };
async function editor() { render(<PacketWorkspace packetId={pid} {...access} />); await screen.findByRole("heading", { name: packet.title }); }
beforeEach(() => {
  jest.clearAllMocks();
  mock.session.mockResolvedValue(session); mock.capabilities.mockResolvedValue(caps);
  mock.packet.mockResolvedValue(packet); mock.revision.mockResolvedValue(revision); mock.latestRun.mockResolvedValue(null);
  mock.membership.mockResolvedValue(membership); mock.handoffDraft.mockResolvedValue({ draft: null, stale: false });
  mock.history.mockResolvedValue({ items: [], next_cursor: null });
  mock.list.mockResolvedValue({ items: [], next_cursor: null });
});

test("restores saved selection, shows parse failure and never executes on load", async () => {
  await editor();
  expect(screen.getByLabelText(packet.documents[0].filename)).toBeChecked();
  expect(screen.getByLabelText(packet.documents[1].filename)).toBeDisabled();
  expect(screen.getByText(/No readable text/)).toBeInTheDocument();
  expect(screen.getByText(/Restored your saved selection/)).toBeInTheDocument();
  expect(mock.execute).not.toHaveBeenCalled(); expect(mock.createRun).not.toHaveBeenCalled();
});

test("selection draft and source version are separate writes", async () => {
  mock.saveDraft.mockResolvedValue({ ...packet.draft, selected_document_ids: [], draft_version: 2 });
  await editor();
  fireEvent.click(screen.getByLabelText(packet.documents[0].filename));
  fireEvent.click(screen.getByRole("button", { name: "Save selection draft" }));
  await waitFor(() => expect(mock.saveDraft).toHaveBeenCalledWith(pid, expect.objectContaining({ selected_document_ids: [], base_revision: 1, expected_draft_version: 1 }), "test-csrf"));
  expect(mock.saveRevision).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Prepare check" })).toBeDisabled();
});

test("409 preserves unsaved selection and existing imported sources", async () => {
  mock.saveRevision.mockRejectedValue(new WorkspaceError("REVISION_CONFLICT", 409));
  await editor(); fireEvent.click(screen.getByLabelText(packet.documents[0].filename));
  fireEvent.click(screen.getByRole("button", { name: "Save source version" }));
  await screen.findByText(/saved source version changed in another tab/);
  expect(screen.getByLabelText(packet.documents[0].filename)).not.toBeChecked();
  expect(screen.getByText(/In saved version/)).toBeInTheDocument();
});

test("pasted text is only uploaded explicitly and never persisted in browser storage", async () => {
  const store = jest.spyOn(Storage.prototype, "setItem");
  mock.uploadText.mockResolvedValue(packet.documents[0]);
  await editor(); fireEvent.change(screen.getByLabelText("Or paste synthetic referral text"), { target: { value: "Synthetic source sentinel" } });
  expect(mock.uploadText).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Import pasted text" }));
  await waitFor(() => expect(mock.uploadText).toHaveBeenCalledWith(pid, { text: "Synthetic source sentinel", filename: "pasted-text.txt" }, "test-csrf", expect.any(String)));
  expect(store).not.toHaveBeenCalled(); expect(window.location.href).not.toContain("sentinel"); store.mockRestore();
});

test("PDFs upload sequentially, reject oversized files, and never generate", async () => {
  let finish: (value: typeof packet.documents[0]) => void = () => {};
  mock.uploadPdf.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; })).mockResolvedValue(packet.documents[0]);
  await editor(); const a = new File(["first"], "first.pdf", { type: "application/pdf" }); const b = new File(["second"], "second.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("Choose PDF files"), { target: { files: [a, b] } });
  await waitFor(() => expect(mock.uploadPdf).toHaveBeenCalledTimes(1));
  await act(async () => finish(packet.documents[0]));
  await waitFor(() => expect(mock.uploadPdf).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.getByLabelText("Choose PDF files")).not.toBeDisabled());
  const huge = new File([new Uint8Array(2 * 1024 * 1024 + 1)], "huge.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("Choose PDF files"), { target: { files: [huge] } });
  await screen.findByText(/huge.pdf: choose a PDF/); expect(mock.uploadPdf).toHaveBeenCalledTimes(2); expect(mock.execute).not.toHaveBeenCalled();
});

test("reselecting an identical PDF after a lost response retains its upload key", async () => {
  mock.uploadPdf.mockRejectedValueOnce(new Error("offline")).mockResolvedValue(packet.documents[0]);
  const store = jest.spyOn(Storage.prototype, "setItem");
  await editor();
  fireEvent.change(screen.getByLabelText("Choose PDF files"), { target: {
    files: [new File(["Synthetic PDF"], "referral.pdf", { type: "application/pdf", lastModified: 1 })],
  } });
  await screen.findByText(/referral.pdf: Connection interrupted/);
  await waitFor(() => expect(screen.getByLabelText("Choose PDF files")).not.toBeDisabled());
  expect(mock.uploadPdf).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText("Choose PDF files"), { target: {
    files: [new File(["Synthetic PDF"], "referral.pdf", { type: "application/pdf", lastModified: 2 })],
  } });
  await waitFor(() => expect(mock.uploadPdf).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.getByLabelText("Choose PDF files")).not.toBeDisabled());
  expect(mock.uploadPdf.mock.calls[0][3]).toBe(mock.uploadPdf.mock.calls[1][3]);
  expect(store).not.toHaveBeenCalled();
  expect(mock.execute).not.toHaveBeenCalled();
  store.mockRestore();
});

test("same-name same-size PDFs with different bytes receive distinct upload keys", async () => {
  mock.uploadPdf.mockResolvedValue(packet.documents[0]);
  await editor();
  for (const content of ["first", "other", "first"]) {
    fireEvent.change(screen.getByLabelText("Choose PDF files"), { target: {
      files: [new File([content], "referral.pdf", { type: "application/pdf", lastModified: 1 })],
    } });
    await waitFor(() => expect(screen.getByLabelText("Choose PDF files")).not.toBeDisabled());
  }
  expect(mock.uploadPdf).toHaveBeenCalledTimes(3);
  const keys = mock.uploadPdf.mock.calls.map(call => call[3]);
  expect(keys[0]).not.toBe(keys[1]);
  expect(keys[0]).toBe(keys[2]);
});

test("manual editing remains available without membership and requires explicit confirmation", async () => {
  mock.membership.mockResolvedValue({ ...membership, remaining: 0 });
  mock.saveManual.mockResolvedValue({ id: did, packet_id: pid, revision_id: revision.id, run_id: null, actor_id: did, review_version: 1, kind: "draft", content: {}, created_at: packet.created_at });
  await editor(); await waitFor(() => expect(screen.getByLabelText("Reviewer supplied note")).not.toBeDisabled());
  expect(screen.getByRole("button", { name: "Prepare check" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Reviewer supplied note"), { target: { value: "Synthetic manual note" } });
  fireEvent.click(screen.getByRole("button", { name: "Save manual note" }));
  await screen.findByText(/Manual note saved/); expect(mock.saveManual).toHaveBeenCalledWith(pid, expect.objectContaining({ mode: "manual", fields: { "handoff.notes": "Synthetic manual note" } }), "test-csrf");
  expect(mock.confirm).not.toHaveBeenCalled(); expect(mock.execute).not.toHaveBeenCalled();
});

test("unsaved source text registers a navigation warning", async () => {
  await editor(); fireEvent.change(screen.getByLabelText("Or paste synthetic referral text"), { target: { value: "Unsaved synthetic text" } });
  const event = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true);
});

test("packet creation retains its key on an uncertain response; deletion is confirmed", async () => {
  mock.create.mockRejectedValueOnce(new Error("offline")).mockResolvedValue(packet);
  render(<PacketList {...access} />); await screen.findByText("No packets yet");
  fireEvent.change(screen.getByLabelText("Packet title"), { target: { value: "Synthetic new packet" } });
  fireEvent.click(screen.getByLabelText(/I am using synthetic data/)); fireEvent.click(screen.getByRole("button", { name: "Create packet" }));
  await screen.findByText(/Connection interrupted/); fireEvent.click(screen.getByRole("button", { name: "Create packet" }));
  await screen.findByRole("link", { name: packet.title }); expect(mock.create.mock.calls[0][2]).toBe(mock.create.mock.calls[1][2]);
  fireEvent.click(screen.getByRole("button", { name: "Delete" })); expect(mock.remove).not.toHaveBeenCalled();
  mock.remove.mockResolvedValue({ id: pid, status: "pending_cleanup" }); fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  await waitFor(() => expect(mock.remove).toHaveBeenCalledWith(pid, "test-csrf"));
});

test("unavailable and expired sessions show bounded recovery states", async () => {
  mock.packet.mockRejectedValue(new WorkspaceError("AUTH_REQUIRED", 401));
  render(<Workspace packetId={pid} />); await screen.findByText(/Your session ended/);
  expect(screen.getByRole("link", { name: "Sign in again" })).toHaveAttribute("href", expect.stringContaining(encodeURIComponent(`/workspace/packets/${pid}`)));
  expect(screen.queryByLabelText("Or paste synthetic referral text")).not.toBeInTheDocument();
});

test("a 404 after returning to a deleted packet removes the loaded editor", async () => {
  render(<Workspace packetId={pid} />);
  await screen.findByRole("heading", { name: packet.title });
  fireEvent.change(screen.getByLabelText("Or paste synthetic referral text"), { target: { value: "Synthetic memory sentinel" } });
  mock.packet.mockRejectedValue(new WorkspaceError("NOT_FOUND", 404));
  fireEvent(window, new Event("pageshow"));
  await screen.findByText(/This material is unavailable, deleted or expired/);
  expect(screen.queryByDisplayValue("Synthetic memory sentinel")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: packet.title })).not.toBeInTheDocument();
  expect(mock.execute).not.toHaveBeenCalled();
});

test("preloaded unknown result offers recovery without executing", async () => {
  mock.reconcile.mockResolvedValue(unknownRun);
  render(<RunPanel packetId={pid} revision={revision} initialRun={unknownRun} membership={membership} caps={caps} csrf="test-csrf" sourceDirty={false} onError={access.onError} />);
  expect(screen.getByText(/provider outcome is unknown/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Recover without rerunning" }));
  await waitFor(() => expect(mock.reconcile).toHaveBeenCalled()); expect(mock.execute).not.toHaveBeenCalled(); expect(mock.createRun).not.toHaveBeenCalled();
});

test("preloaded running result polls GET and stops on a network failure", async () => {
  jest.useFakeTimers(); mock.run.mockRejectedValue(new Error("offline"));
  render(<RunPanel packetId={pid} revision={revision} initialRun={{ ...unknownRun, state: "running", phase: "dispatched" }} membership={membership} caps={caps} csrf="test-csrf" sourceDirty={false} onError={access.onError} />);
  await act(async () => { jest.advanceTimersByTime(4000); });
  expect(mock.run).toHaveBeenCalledTimes(1); expect(screen.getByText(/Connection interrupted/)).toBeInTheDocument();
  await act(async () => { jest.advanceTimersByTime(20_000); }); expect(mock.run).toHaveBeenCalledTimes(1); expect(mock.execute).not.toHaveBeenCalled(); jest.useRealTimers();
});


test("editing the manual note preserves other saved reviewer fields", async () => {
  const draft = { id: did, packet_id: pid, revision_id: revision.id, run_id: null, actor_id: did, review_version: packet.review_version, kind: "draft" as const, content: { fields: { "handoff.notes": { value: "Earlier note", provenance: "Reviewer supplied" }, "patient.name": { value: "Synthetic patient", provenance: "Reviewer supplied" } } }, created_at: packet.created_at };
  mock.handoffDraft.mockResolvedValue({ draft, stale: false }); mock.saveManual.mockResolvedValue(draft);
  await editor(); await screen.findByDisplayValue("Earlier note");
  fireEvent.change(screen.getByLabelText("Reviewer supplied note"), { target: { value: "Updated note" } });
  fireEvent.click(screen.getByRole("button", { name: "Save manual note" }));
  await screen.findByText(/Manual note saved/);
  expect(mock.saveManual).toHaveBeenCalledWith(pid, expect.objectContaining({ fields: { "handoff.notes": "Updated note", "patient.name": "Synthetic patient" } }), "test-csrf");
});

test("manual note edits survive a history-only reload without reloading packet material", async () => {
  await editor();
  await waitFor(() => expect(screen.getByLabelText("Reviewer supplied note")).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Reviewer supplied note"), { target: { value: "Unsaved manual comparison" } });
  const packetReads = mock.packet.mock.calls.length;
  const draftReads = mock.handoffDraft.mock.calls.length;
  mock.history.mockResolvedValue({ items: [{ id: did, packet_id: pid, revision_id: revision.id, run_id: null,
    actor_id: did, review_version: 3, kind: "confirmation", created_at: packet.created_at,
    content: { snapshot_id: did } }], next_cursor: null });
  fireEvent.click(screen.getByText("Review history and confirmed handoffs"));
  fireEvent.click(screen.getByRole("button", { name: "Reload history" }));
  await screen.findByRole("button", { name: "View confirmed handoff" });
  expect(screen.getByDisplayValue("Unsaved manual comparison")).toBeInTheDocument();
  expect(mock.packet).toHaveBeenCalledTimes(packetReads);
  expect(mock.handoffDraft).toHaveBeenCalledTimes(draftReads);
  expect(mock.saveManual).not.toHaveBeenCalled(); expect(mock.confirm).not.toHaveBeenCalled();
  expect(mock.execute).not.toHaveBeenCalled();
});
