import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { webcrypto } from "node:crypto";
import { TextEncoder } from "node:util";
import { ReviewWorkspace } from "../../components/referral/ReviewWorkspace";
import { workspaceApi as api, WorkspaceError } from "../../lib/referral-api/workspace";
import { packet, did, pid } from "../../test-support/workspace";
import { reviewRun, reviewState, pageOne, pageTwo, findingId, snapshot, handoffView } from "../../test-support/review";
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
