import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { webcrypto } from "node:crypto";
import { TextEncoder } from "node:util";
import { ReviewWorkspace } from "../../components/referral/ReviewWorkspace";
import { workspaceApi as api, WorkspaceError, type ReviewEvent, type Snapshot } from "../../lib/referral-api/workspace";
import { packet, did, pid } from "../../test-support/workspace";
import { reviewRun, reviewState, pageOne, pageTwo, findingId, missingId, snapshot, handoffView } from "../../test-support/review";
jest.mock("../../lib/referral-api/workspace", () => {
  const original = jest.requireActual("../../lib/referral-api/workspace");
  return { ...original, workspaceApi: Object.fromEntries(Object.keys(original.workspaceApi).map(key => [key, jest.fn()])) };
});
const mock = jest.mocked(api);
const onError = jest.fn();
const props = { packet, run: reviewRun, csrf: "test-csrf", sourceDirty: false, onError, onDirty: jest.fn() };
beforeAll(() => { Object.defineProperty(globalThis, "TextEncoder", { value: TextEncoder }); Object.defineProperty(crypto, "subtle", { value: webcrypto.subtle }); });
beforeEach(() => {
  jest.clearAllMocks(); mock.reviewState.mockResolvedValue(reviewState); mock.history.mockResolvedValue({ items: [], next_cursor: null });
  mock.page.mockImplementation(async (_pid, id) => id === did ? pageOne : pageTwo);
  mock.resolve.mockImplementation(async (_rid, fid, body) => ({ id: did, packet_id: pid, revision_id: reviewRun.revision_id, run_id: reviewRun.id, actor_id: did, review_version: body.expected_review_version + 1, kind: "resolution", created_at: packet.created_at, content: { finding_id: fid, ...body } }));
  mock.confirm.mockResolvedValue(snapshot); mock.handoff.mockResolvedValue(handoffView);
});
async function ready() { render(<ReviewWorkspace {...props} />); await screen.findByText(/Saved decisions loaded/); }

function pending<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function savedHistory() {
  mock.history.mockResolvedValue({ items: [{ id: snapshot.id, packet_id: pid, revision_id: snapshot.revision_id,
    run_id: reviewRun.id, actor_id: did, review_version: 3, kind: "confirmation", created_at: packet.created_at,
    content: { snapshot_id: snapshot.id } }], next_cursor: null });
  mock.run.mockResolvedValue(reviewRun);
}

test.each(["success", "failure"])("pending decision prevents context changes until %s settles", async outcome => {
  savedHistory(); await ready();
  fireEvent.click(screen.getByText("Review history and confirmed handoffs"));
  fireEvent.click(screen.getByRole("button", { name: "View this run" }));
  await screen.findByRole("button", { name: "Return to latest run" });
  const save = pending<ReviewEvent>(); mock.resolve.mockReturnValueOnce(save.promise);
  fireEvent.change(screen.getByLabelText("Reviewer supplied correction (optional)"), { target: { value: "Pending synthetic correction" } });
  fireEvent.click(screen.getByRole("button", { name: "Save decision" }));
  for (const name of ["Discard review edits", "Return to latest run", "View this run", "View confirmed handoff"]) {
    expect(screen.getByRole("button", { name })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name }));
  }
  const anotherItem = screen.getByRole("button", { name: /Missing information.*referrer.contact/ });
  expect(anotherItem).toBeDisabled(); fireEvent.click(anotherItem);
  expect(screen.getByDisplayValue("Pending synthetic correction")).toBeInTheDocument();
  expect(mock.run).toHaveBeenCalledTimes(1); expect(mock.handoff).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Reload history" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Reload history" })).toBeEnabled());
  expect(screen.getByRole("button", { name: "View this run" })).toBeDisabled();
  expect(mock.resolve).toHaveBeenCalledTimes(1);
  await act(async () => {
    if (outcome === "failure") save.reject(new WorkspaceError("REVIEW_CONFLICT", 409));
    else save.resolve({ id: did, packet_id: pid, revision_id: reviewRun.revision_id, run_id: reviewRun.id,
      actor_id: did, review_version: 1, kind: "resolution", created_at: packet.created_at, content: {} });
  });
  expect(screen.getByRole("button", { name: "View this run" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Return to latest run" })).toBeEnabled();
  if (outcome === "failure") {
    expect(screen.getByDisplayValue("Pending synthetic correction")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save decision" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Discard review edits" })).toBeEnabled();
  } else {
    expect(screen.getByText("Reviewer supplied: Pending synthetic correction")).toBeInTheDocument();
    fireEvent.click(anotherItem);
    expect(anotherItem).toHaveAttribute("aria-pressed", "true");
  }
});

test("a history click in the same update as saving cannot bypass the pending write guard", async () => {
  savedHistory(); await ready(); fireEvent.click(screen.getByText("Review history and confirmed handoffs"));
  const save = pending<ReviewEvent>(); mock.resolve.mockReturnValueOnce(save.promise);
  fireEvent.change(screen.getByLabelText("Reviewer supplied correction (optional)"), { target: { value: "Synthetic correction" } });
  const saveButton = screen.getByRole("button", { name: "Save decision" });
  const historyButton = screen.getByRole("button", { name: "View this run" });
  const confirmDiscard = jest.spyOn(window, "confirm").mockReturnValue(true);
  try {
    act(() => { fireEvent.click(saveButton); fireEvent.click(historyButton); });
    expect(mock.resolve).toHaveBeenCalledTimes(1);
    expect(mock.run).not.toHaveBeenCalled(); expect(confirmDiscard).not.toHaveBeenCalled();
    await act(async () => { save.reject(new WorkspaceError("REVIEW_CONFLICT", 409)); });
    expect(screen.getByDisplayValue("Synthetic correction")).toBeInTheDocument();
  } finally { confirmDiscard.mockRestore(); }
});

test.each(["success", "failure"])("pending confirmation blocks history and restores it after %s", async outcome => {
  savedHistory();
  mock.reviewState.mockResolvedValue({ ...reviewState, decisions: [findingId, missingId].map(id => ({ finding_id: id,
    status: "resolved", action: "resolve", reason: "Synthetic reviewed decision", corrected_value: null,
    linked_evidence_ids: [], review_version: 0 })) });
  await ready(); fireEvent.click(screen.getByText("Review history and confirmed handoffs"));
  const confirmation = pending<Snapshot>(); mock.confirm.mockReturnValueOnce(confirmation.promise);
  fireEvent.click(screen.getByRole("button", { name: "Confirm reviewed handoff" }));
  fireEvent.click(screen.getByRole("button", { name: "Create confirmed snapshot" }));
  expect(screen.getByRole("button", { name: "View this run" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "View confirmed handoff" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Keep reviewing" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "View confirmed handoff" }));
  expect(mock.handoff).not.toHaveBeenCalled();
  await act(async () => {
    if (outcome === "failure") confirmation.reject(new Error("response lost"));
    else confirmation.resolve(snapshot);
  });
  if (outcome === "success") {
    await screen.findByRole("article", { name: "Confirmed handoff" });
    expect(mock.handoff).toHaveBeenCalledWith(pid, snapshot.id);
  } else {
    expect(screen.queryByRole("article", { name: "Confirmed handoff" })).not.toBeInTheDocument();
    expect(mock.handoff).not.toHaveBeenCalled();
  }
  expect(screen.getByRole("button", { name: "View this run" })).toBeEnabled();
  expect(mock.confirm).toHaveBeenCalledTimes(1); expect(mock.execute).not.toHaveBeenCalled();
});

test("DOB shows both verified citations; source HTML remains inert", async () => {
  await ready();
  await waitFor(() => expect(document.querySelectorAll(".rr-source-excerpt mark")).toHaveLength(2));
  expect([...document.querySelectorAll(".rr-source-excerpt mark")].map(x => x.textContent)).toEqual(["1980-04-03", "1981-04-03"]);
  expect(screen.getAllByText(/<script>alert/)[0]).toBeInTheDocument(); expect(document.querySelector("script")).toBeNull();
  expect(mock.execute).not.toHaveBeenCalled(); expect(mock.createRun).not.toHaveBeenCalled();
  const links = screen.getAllByRole("link", { name: /Download original/ });
  expect(links[0]).toHaveAttribute("href", `/api/v1/packets/${pid}/documents/${did}/original`);
});

test("missing information shows scope and no fabricated citation", async () => {
  await ready(); fireEvent.click(screen.getByRole("button", { name: /Missing information.*referrer.contact/ }));
  expect(screen.getByText(/Absence has no source quote/)).toBeInTheDocument();
  expect(document.querySelectorAll(".rr-source-excerpt mark")).toHaveLength(0);
  expect(screen.getByText(/Checked successfully parsed sources/)).toHaveTextContent("Synthetic intake note.txt");
});

test("tampered hash or stale source context never receives a highlight", async () => {
  mock.page.mockResolvedValue({ ...pageOne, normalized_text: pageOne.normalized_text + "tampered" });
  await ready(); await screen.findAllByText(/Source verification failed/);
  expect(document.querySelectorAll(".rr-source-excerpt mark")).toHaveLength(0);
});

test("review decision, explicit unresolved reason, confirmation and export are one path", async () => {
  await ready(); expect(screen.getByRole("button", { name: "Confirm reviewed handoff" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Action"), { target: { value: "defer" } });
  expect(screen.getByRole("button", { name: "Save decision" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Reason (required)"), { target: { value: "Verify identity with referrer" } });
  fireEvent.click(screen.getByRole("button", { name: "Save decision" }));
  await screen.findByText("Saved decision: unresolved");
  fireEvent.click(screen.getByRole("button", { name: /Missing information.*referrer.contact/ }));
  fireEvent.change(screen.getByLabelText("Reviewer supplied correction (optional)"), { target: { value: "Synthetic contact supplied by reviewer" } });
  fireEvent.click(screen.getByRole("button", { name: "Save decision" })); await screen.findByText("Saved decision: resolved");
  expect(mock.resolve.mock.calls[1][2].expected_review_version).toBe(1);
  expect(mock.resolve.mock.calls[1][2].corrected_value).toBe("Synthetic contact supplied by reviewer");
  fireEvent.click(screen.getByRole("button", { name: "Confirm reviewed handoff" })); expect(mock.confirm).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Create confirmed snapshot" }));
  await screen.findByRole("article", { name: "Confirmed handoff" });
  expect(mock.confirm).toHaveBeenCalledWith(pid, expect.objectContaining({ mode: "assisted", run_id: reviewRun.id, expected_review_version: 2 }), "test-csrf");
  expect(screen.getByRole("link", { name: "Download confirmed PDF" })).toHaveAttribute("href", expect.stringContaining(snapshot.id));
  expect(screen.getByText("Identity unresolved")).toBeInTheDocument();
});

test("409 retains correction and allows comparison with newly saved decision", async () => {
  await ready(); mock.resolve.mockRejectedValueOnce(new WorkspaceError("REVIEW_CONFLICT", 409));
  fireEvent.change(screen.getByLabelText("Reviewer supplied correction (optional)"), { target: { value: "My unsaved date" } });
  fireEvent.click(screen.getByRole("button", { name: "Save decision" })); await screen.findByText(/Your unsaved correction is retained/);
  expect(screen.getByDisplayValue("My unsaved date")).toBeInTheDocument();
  mock.reviewState.mockResolvedValue({ ...reviewState, review_version: 5, decisions: [{ finding_id: findingId, status: "resolved", action: "resolve", reason: "Other tab", corrected_value: "Other date", linked_evidence_ids: [], review_version: 5 }] });
  fireEvent.click(screen.getByRole("button", { name: "Reload saved decisions" })); await screen.findByText("Reviewer supplied: Other date");
  expect(screen.getByDisplayValue("My unsaved date")).toBeInTheDocument(); expect(mock.resolve).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Save decision" })); await screen.findByText("Reviewer supplied: My unsaved date");
  expect(mock.resolve.mock.calls[1][2].expected_review_version).toBe(5);
});

test("historical result stays visible with disabled decisions and confirmation", async () => {
  mock.reviewState.mockResolvedValue({ ...reviewState, stale: true, revision: { ...reviewState.revision, is_current: false } });
  await ready(); expect(screen.getByText(/Historical source version. Review decisions/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save decision" })).toBeDisabled(); expect(screen.getByRole("button", { name: "Confirm reviewed handoff" })).toBeDisabled();
});

test("dismiss and reopen persist explicit statuses; filters never clear edits", async () => {
  await ready(); fireEvent.change(screen.getByLabelText("Action"), { target: { value: "dismiss" } });
  fireEvent.change(screen.getByLabelText("Reason (required)"), { target: { value: "Synthetic dismissal rationale" } });
  fireEvent.change(screen.getByLabelText("Filter by status"), { target: { value: "resolved" } });
  expect(screen.getByDisplayValue("Synthetic dismissal rationale")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Save decision" })); await screen.findByText("Saved decision: dismissed");
  expect(screen.getByText(/Identity unresolved —/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Action"), { target: { value: "reopen" } });
  fireEvent.click(screen.getByRole("button", { name: "Save decision" })); await screen.findByText("Saved decision: open");
});

test("history paginates and loads an authorized historical snapshot", async () => {
  mock.history.mockResolvedValueOnce({ items: [], next_cursor: "next" }).mockResolvedValue({ items: [{ id: snapshot.id, packet_id: pid, revision_id: snapshot.revision_id, run_id: reviewRun.id, actor_id: did, review_version: 3, kind: "confirmation", created_at: packet.created_at, content: { snapshot_id: snapshot.id } }], next_cursor: null });
  mock.handoff.mockResolvedValue({ ...handoffView, historical: true });
  await ready(); fireEvent.click(screen.getByText("Review history and confirmed handoffs"));
  fireEvent.click(await screen.findByRole("button", { name: "Load older history" }));
  fireEvent.click(await screen.findByRole("button", { name: "View confirmed handoff" }));
  await screen.findByText(/Historical — not the current review/);
  expect(mock.history).toHaveBeenLastCalledWith(pid, "next");
});

test("reloading history discovers saved snapshots without discarding or submitting review edits", async () => {
  await ready();
  fireEvent.change(screen.getByLabelText("Reviewer supplied correction (optional)"), { target: { value: "Keep this local correction" } });
  mock.history.mockResolvedValue({ items: [{ id: snapshot.id, packet_id: pid, revision_id: snapshot.revision_id,
    run_id: reviewRun.id, actor_id: did, review_version: 3, kind: "confirmation", created_at: packet.created_at,
    content: { snapshot_id: snapshot.id } }], next_cursor: null });
  fireEvent.click(screen.getByText("Review history and confirmed handoffs"));
  fireEvent.click(screen.getByRole("button", { name: "Reload history" }));
  await screen.findByRole("button", { name: "View confirmed handoff" });
  expect(screen.getByDisplayValue("Keep this local correction")).toBeInTheDocument();
  expect(mock.resolve).not.toHaveBeenCalled(); expect(mock.confirm).not.toHaveBeenCalled();
  expect(mock.execute).not.toHaveBeenCalled(); expect(mock.handoff).not.toHaveBeenCalled();
  expect(mock.reviewState).toHaveBeenCalledTimes(1);
});
