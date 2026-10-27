import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ManualDraft } from "../../components/referral/ManualDraft";
import { workspaceApi as api, WorkspaceError, type ReviewEvent } from "../../lib/referral-api/workspace";
import { caps, packet, revision, pid, did } from "../../test-support/workspace";
import { snapshot } from "../../test-support/review";

jest.mock("../../lib/referral-api/workspace", () => {
  const original = jest.requireActual("../../lib/referral-api/workspace");
  return { ...original, workspaceApi: Object.fromEntries(Object.keys(original.workspaceApi).map(key => [key, jest.fn()])) };
});
const mock = jest.mocked(api);
const props = { packet, revision, csrf: "test-csrf", capabilities: caps, onError: jest.fn(), onDirty: jest.fn() };
function draft(version: number, note: string, patient = "Synthetic patient"): ReviewEvent {
  return { id: did, packet_id: pid, revision_id: revision.id, run_id: null, actor_id: did,
    review_version: version, kind: "draft", created_at: packet.created_at,
    content: { fields: { "handoff.notes": { value: note, provenance: "Reviewer supplied" }, "patient.name": { value: patient, provenance: "Reviewer supplied" } } } };
}
beforeEach(() => {
  jest.resetAllMocks();
  mock.handoffDraft.mockResolvedValue({ draft: null, stale: false });
  mock.packet.mockResolvedValue(packet);
  mock.saveManual.mockImplementation(async (_id, body) => draft(body.expected_review_version + 1, body.fields["handoff.notes"] ?? ""));
});
async function ready() {
  render(<ManualDraft {...props} />);
  await waitFor(() => expect(screen.getByLabelText("Reviewer supplied note")).toBeEnabled());
}
async function failedSave(error: Error = new WorkspaceError("REVIEW_CONFLICT", 409)) {
  await ready();
  fireEvent.change(screen.getByLabelText("Reviewer supplied note"), { target: { value: "My unsaved note" } });
  mock.saveManual.mockRejectedValueOnce(error);
  fireEvent.click(screen.getByRole("button", { name: "Save manual note" }));
  await screen.findByRole("alert");
}

test("conflict recovery keeps the local note and compares current saved fields before explicit save", async () => {
  await failedSave();
  expect(screen.getByRole("button", { name: "Save manual note" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Confirm manual handoff" })).toBeDisabled();
  mock.packet.mockResolvedValue({ ...packet, review_version: 5 });
  mock.handoffDraft.mockResolvedValue({ draft: draft(4, "Other tab note", "Updated synthetic name"), stale: false });
  fireEvent.click(screen.getByRole("button", { name: "Reload saved manual note" }));
  await screen.findByText("Other tab note");
  expect(screen.getByDisplayValue("My unsaved note")).toBeInTheDocument();
  expect(screen.getByText("Updated synthetic name")).toBeInTheDocument();
  expect(mock.saveManual).toHaveBeenCalledTimes(1);
  expect(mock.confirm).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Save manual note" }));
  await screen.findByText(/Manual note saved/);
  expect(mock.saveManual).toHaveBeenLastCalledWith(pid, expect.objectContaining({ expected_review_version: 5,
    fields: { "handoff.notes": "My unsaved note", "patient.name": "Updated synthetic name" } }), "test-csrf");
});

test("an uncertain save that actually committed is discovered without resubmitting it", async () => {
  await failedSave(new Error("response lost"));
  mock.packet.mockResolvedValue({ ...packet, review_version: 1 });
  mock.handoffDraft.mockResolvedValue({ draft: draft(1, "My unsaved note"), stale: false });
  fireEvent.click(screen.getByRole("button", { name: "Reload saved manual note" }));
  await screen.findByText("My unsaved note", { selector: "p" });
  expect(screen.getByRole("button", { name: "Save manual note" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Confirm manual handoff" })).toBeEnabled();
  expect(mock.saveManual).toHaveBeenCalledTimes(1);
  expect(mock.confirm).not.toHaveBeenCalled();
  expect(props.onDirty).toHaveBeenLastCalledWith(false);
});

test("the reviewer can explicitly use the saved note and confirm the latest review version", async () => {
  await failedSave();
  mock.packet.mockResolvedValue({ ...packet, review_version: 6 });
  mock.handoffDraft.mockResolvedValue({ draft: draft(5, "Saved note selected by reviewer"), stale: false });
  mock.confirm.mockResolvedValue({ ...snapshot, run_id: null, review_version: 7 });
  fireEvent.click(screen.getByRole("button", { name: "Reload saved manual note" }));
  fireEvent.click(await screen.findByRole("button", { name: "Use saved manual note" }));
  expect(screen.getByDisplayValue("Saved note selected by reviewer")).toBeInTheDocument();
  expect(mock.saveManual).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Confirm manual handoff" }));
  expect(mock.confirm).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Confirm without automated check" }));
  await screen.findByRole("link", { name: "Download confirmed PDF" });
  expect(mock.confirm).toHaveBeenCalledWith(pid, { mode: "manual", revision_id: revision.id, expected_review_version: 6 }, "test-csrf");
});

test("an uncertain confirmation blocks repeated writes and never displays a false export success", async () => {
  await ready();
  mock.confirm.mockRejectedValue(new Error("response lost"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm manual handoff" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm without automated check" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Confirm manual handoff" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "Download confirmed PDF" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirm without automated check" })).not.toBeInTheDocument();
  expect(mock.confirm).toHaveBeenCalledTimes(1);
  expect(mock.execute).not.toHaveBeenCalled();
});

test.each(["source", "review"])("a %s change during reload keeps edits and blocks stale writes", async kind => {
  await failedSave();
  mock.packet.mockResolvedValueOnce({ ...packet, review_version: 4 }).mockResolvedValue({ ...packet,
    review_version: kind === "review" ? 5 : 4, current_revision: kind === "source" ? 2 : 1 });
  mock.handoffDraft.mockResolvedValue({ draft: draft(4, "Concurrent note"), stale: false });
  fireEvent.click(screen.getByRole("button", { name: "Reload saved manual note" }));
  await waitFor(() => expect(mock.packet).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.getByRole("button", { name: "Reload saved manual note" })).toBeEnabled());
  expect(screen.getByDisplayValue("My unsaved note")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save manual note" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Confirm manual handoff" })).toBeDisabled();
  expect(screen.queryByText("Concurrent note")).not.toBeInTheDocument();
  expect(mock.saveManual).toHaveBeenCalledTimes(1);
});

test("an initial read failure can be retried without reloading the packet editor", async () => {
  mock.handoffDraft.mockRejectedValueOnce(new Error("offline"));
  render(<ManualDraft {...props} />);
  await screen.findByRole("alert");
  mock.handoffDraft.mockResolvedValue({ draft: draft(2, "Saved note"), stale: false });
  mock.packet.mockResolvedValue({ ...packet, review_version: 2 });
  fireEvent.click(screen.getByRole("button", { name: "Reload saved manual note" }));
  await screen.findByDisplayValue("Saved note");
  expect(screen.getByLabelText("Reviewer supplied note")).toBeEnabled();
  expect(mock.saveManual).not.toHaveBeenCalled();
});

test("a failed reload retains the note and does not enable confirmation", async () => {
  await failedSave(); mock.packet.mockRejectedValue(new Error("offline"));
  fireEvent.click(screen.getByRole("button", { name: "Reload saved manual note" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Reload saved manual note" })).toBeEnabled());
  expect(screen.getByDisplayValue("My unsaved note")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirm manual handoff" })).toBeDisabled();
  expect(mock.saveManual).toHaveBeenCalledTimes(1);
});

test("late save failures after unmount do not affect the next workspace", async () => {
  let rejectSave!: (error: Error) => void;
  mock.saveManual.mockReturnValue(new Promise((_resolve, reject) => { rejectSave = reject; }));
  const view = render(<ManualDraft {...props} />);
  await waitFor(() => expect(screen.getByLabelText("Reviewer supplied note")).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Reviewer supplied note"), { target: { value: "Synthetic note" } });
  fireEvent.click(screen.getByRole("button", { name: "Save manual note" }));
  view.unmount();
  await act(async () => { rejectSave(new WorkspaceError("NOT_FOUND", 404)); });
  expect(props.onError).not.toHaveBeenCalled();
});
