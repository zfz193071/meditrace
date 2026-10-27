import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ReviewHistory } from "../../components/referral/ReviewHistory";
import { workspaceApi as api, WorkspaceError, type ReviewEvent, type ReviewHistory as HistoryPage } from "../../lib/referral-api/workspace";
import { packet, pid, did, rid } from "../../test-support/workspace";

jest.mock("../../lib/referral-api/workspace", () => {
  const original = jest.requireActual("../../lib/referral-api/workspace");
  return { ...original, workspaceApi: Object.fromEntries(Object.keys(original.workspaceApi).map(key => [key, jest.fn()])) };
});
const mock = jest.mocked(api);
const props = { packetId: pid, refresh: 0, onRun: jest.fn(), onSnapshot: jest.fn(), onError: jest.fn() };
function event(id: string, reason: string): ReviewEvent {
  return { id, packet_id: pid, revision_id: rid, run_id: rid, actor_id: did, review_version: 1,
    kind: "resolution", created_at: packet.created_at, content: { action: "defer", reason } };
}
function pending() {
  let resolve!: (value: HistoryPage) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<HistoryPage>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
beforeEach(() => { jest.resetAllMocks(); mock.history.mockResolvedValue({ items: [event("first", "Initial history")], next_cursor: "old-cursor" }); });
async function ready() {
  const view = render(<ReviewHistory {...props} />);
  fireEvent.click(screen.getByText("Review history and confirmed handoffs"));
  await screen.findByText("defer: Initial history");
  return view;
}

test.each(["success", "failure"])("old pagination %s cannot change a refreshed history", async outcome => {
  const view = await ready(); const oldPage = pending();
  mock.history.mockReturnValueOnce(oldPage.promise);
  fireEvent.click(screen.getByRole("button", { name: "Load older history" }));
  mock.history.mockResolvedValue({ items: [event("new", "New history")], next_cursor: "new-cursor" });
  view.rerender(<ReviewHistory {...props} refresh={1} />);
  await screen.findByText("defer: New history");
  await act(async () => {
    if (outcome === "success") oldPage.resolve({ items: [event("old", "Obsolete page")], next_cursor: "obsolete-cursor" });
    else oldPage.reject(new WorkspaceError("NOT_FOUND", 404));
  });
  expect(screen.queryByText("defer: Obsolete page")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(props.onError).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Load older history" }));
  await waitFor(() => expect(mock.history).toHaveBeenLastCalledWith(pid, "new-cursor"));
});

test("switching packet clears the old list even when the new read fails", async () => {
  const view = await ready(); const newPage = pending();
  mock.history.mockReturnValue(newPage.promise);
  view.rerender(<ReviewHistory {...props} packetId={did} />);
  expect(screen.queryByText("defer: Initial history")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "View this run" })).not.toBeInTheDocument();
  await act(async () => { newPage.reject(new Error("offline")); });
  await screen.findByRole("alert");
  expect(screen.queryByText("defer: Initial history")).not.toBeInTheDocument();
});

test("unmounted pagination errors cannot invalidate the active workspace", async () => {
  const view = await ready(); const oldPage = pending();
  mock.history.mockReturnValue(oldPage.promise);
  fireEvent.click(screen.getByRole("button", { name: "Load older history" }));
  view.unmount();
  await act(async () => { oldPage.reject(new WorkspaceError("NOT_FOUND", 404)); });
  expect(props.onError).not.toHaveBeenCalled();
});

test("explicit reload supersedes pagination without letting its completion unlock the new read", async () => {
  await ready(); const oldPage = pending(); const newPage = pending();
  mock.history.mockReturnValueOnce(oldPage.promise).mockReturnValueOnce(newPage.promise);
  fireEvent.click(screen.getByRole("button", { name: "Load older history" }));
  fireEvent.click(screen.getByRole("button", { name: "Reload history" }));
  await waitFor(() => expect(mock.history).toHaveBeenCalledTimes(3));
  await act(async () => { oldPage.resolve({ items: [event("old", "Obsolete page")], next_cursor: "obsolete" }); });
  expect(screen.getByRole("button", { name: "Reload history" })).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("Loading review history");
  expect(screen.queryByRole("button", { name: "Load older history" })).not.toBeInTheDocument();
  await act(async () => { newPage.resolve({ items: [event("fresh", "Fresh history")], next_cursor: null }); });
  expect(screen.getByText("defer: Fresh history")).toBeInTheDocument();
  expect(screen.queryByText("defer: Obsolete page")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reload history" })).toBeEnabled();
});

test("current pagination deduplicates events and a read failure remains explicitly retryable", async () => {
  await ready();
  mock.history.mockRejectedValueOnce(new Error("offline"));
  fireEvent.click(screen.getByRole("button", { name: "Load older history" }));
  await screen.findByRole("alert");
  expect(screen.getByText("defer: Initial history")).toBeInTheDocument();
  mock.history.mockResolvedValue({ items: [event("first", "Initial history"), event("second", "Older history")], next_cursor: null });
  fireEvent.click(screen.getByRole("button", { name: "Load older history" }));
  await screen.findByText("defer: Older history");
  expect(screen.getAllByText("defer: Initial history")).toHaveLength(1);
  expect(mock.history).toHaveBeenLastCalledWith(pid, "old-cursor");
  expect(props.onRun).not.toHaveBeenCalled(); expect(props.onSnapshot).not.toHaveBeenCalled();
  expect(mock.execute).not.toHaveBeenCalled();
});
