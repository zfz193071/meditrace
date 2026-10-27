import { act, fireEvent, render, screen } from "@testing-library/react";
import { RunPanel } from "../../components/referral/RunPanel";
import { workspaceApi as api, WorkspaceError, type Run } from "../../lib/referral-api/workspace";
import { caps, membership, pid, revision, unknownRun } from "../../test-support/workspace";

jest.mock("../../lib/referral-api/workspace", () => ({
  ...jest.requireActual("../../lib/referral-api/workspace"),
  workspaceApi: { run: jest.fn(), createRun: jest.fn(), execute: jest.fn(), reconcile: jest.fn(), cancel: jest.fn() },
}));

const pending: Run = { ...unknownRun, state: "pending", phase: "pending", error_code: null };
const complete: Run = { ...pending, state: "succeeded", phase: "complete", finished_at: new Date().toISOString() };
const onError = jest.fn();
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function mount(initialRun = pending) {
  return render(<RunPanel packetId={pid} revision={revision} initialRun={initialRun}
    membership={membership} caps={caps} csrf="test-csrf" sourceDirty={false} onError={onError} />);
}
beforeEach(() => { jest.resetAllMocks(); jest.useFakeTimers(); });
afterEach(() => jest.useRealTimers());

it.each([
  ["Cancel prepared check", "cancel", { ...pending, state: "cancelled", phase: "cancelled" }, "Check cancelled"],
  ["Recover without rerunning", "reconcile", complete, "Result saved"],
  ["Start simulated check - 1 credit", "execute", complete, "Result saved"],
] as const)("ignores a pending poll that arrives after %s completes", async (button, method, result, label) => {
  const old = deferred<Run>();
  jest.mocked(api.run).mockReturnValueOnce(old.promise);
  jest.mocked(api[method]).mockResolvedValue(result);
  mount();
  await act(async () => { jest.advanceTimersByTime(4000); });
  fireEvent.click(screen.getByRole("button", { name: button }));
  await act(async () => {});
  expect(screen.getByText(label)).toBeInTheDocument();
  await act(async () => { old.resolve(pending); });
  expect(screen.getByText(label)).toBeInTheDocument();
  await act(async () => { jest.advanceTimersByTime(20_000); });
  expect(api.run).toHaveBeenCalledTimes(1);
  expect(api[method]).toHaveBeenCalledTimes(1);
});

it("ignores an old authorization error after an explicit status query succeeds", async () => {
  const old = deferred<Run>();
  jest.mocked(api.run).mockReturnValueOnce(old.promise).mockResolvedValueOnce(pending).mockResolvedValueOnce(complete);
  mount();
  await act(async () => { jest.advanceTimersByTime(4000); });
  fireEvent.click(screen.getByRole("button", { name: "Query status" }));
  await act(async () => {});
  await act(async () => { old.reject(new WorkspaceError("Expired session", 401)); });
  expect(onError).not.toHaveBeenCalled();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  await act(async () => { jest.advanceTimersByTime(4000); });
  expect(screen.getByText("Result saved")).toBeInTheDocument();
  expect(api.execute).not.toHaveBeenCalled();
});

it("keeps polling during execution but ignores a read still pending when execution finishes", async () => {
  const execution = deferred<Run>();
  const read = deferred<Run>();
  jest.mocked(api.execute).mockReturnValueOnce(execution.promise);
  jest.mocked(api.run).mockReturnValueOnce(read.promise);
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Start simulated check - 1 credit" }));
  await act(async () => { jest.advanceTimersByTime(4000); });
  expect(api.run).toHaveBeenCalledTimes(1);
  await act(async () => { execution.resolve(complete); });
  await act(async () => { read.resolve(pending); });
  expect(screen.getByText("Result saved")).toBeInTheDocument();
  expect(api.execute).toHaveBeenCalledTimes(1);
});

it("cancels the scheduled poll when a manual query reaches a terminal state", async () => {
  jest.mocked(api.run).mockResolvedValue(complete);
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Query status" }));
  await act(async () => {});
  await act(async () => { jest.advanceTimersByTime(20_000); });
  expect(api.run).toHaveBeenCalledTimes(1);
  expect(screen.getByText("Result saved")).toBeInTheDocument();
});

it("preserves the five-minute polling limit across pending to running", async () => {
  const running: Run = { ...pending, state: "running", phase: "dispatched" };
  jest.mocked(api.run).mockResolvedValueOnce(pending).mockResolvedValue(running);
  mount();
  for (let tick = 0; tick < 75; tick++) {
    await act(async () => { jest.advanceTimersByTime(4000); });
  }
  expect(screen.getByRole("alert")).toHaveTextContent("Automatic status checks paused");
  expect(api.run).toHaveBeenCalledTimes(75);
  await act(async () => { jest.advanceTimersByTime(20_000); });
  expect(api.run).toHaveBeenCalledTimes(75);
  expect(api.execute).not.toHaveBeenCalled();
});

it("queries after an interrupted execution without retrying execution or accepting an older poll", async () => {
  const old = deferred<Run>();
  jest.mocked(api.run).mockReturnValueOnce(old.promise).mockResolvedValueOnce(complete);
  jest.mocked(api.execute).mockRejectedValueOnce(new Error("Lost response"));
  mount();
  await act(async () => { jest.advanceTimersByTime(4000); });
  fireEvent.click(screen.getByRole("button", { name: "Start simulated check - 1 credit" }));
  await act(async () => {});
  await act(async () => { old.resolve(pending); });
  expect(screen.getByText("Result saved")).toBeInTheDocument();
  await act(async () => { jest.advanceTimersByTime(20_000); });
  expect(api.execute).toHaveBeenCalledTimes(1);
  expect(api.run).toHaveBeenCalledTimes(2);
  expect(api.createRun).not.toHaveBeenCalled();
});

it("ignores a poll error after unmount without scheduling another read", async () => {
  const read = deferred<Run>();
  jest.mocked(api.run).mockReturnValueOnce(read.promise);
  const view = mount();
  await act(async () => { jest.advanceTimersByTime(4000); });
  view.unmount();
  await act(async () => { read.reject(new WorkspaceError("AUTH_REQUIRED", 401)); });
  await act(async () => { jest.advanceTimersByTime(20_000); });
  expect(api.run).toHaveBeenCalledTimes(1);
  expect(onError).not.toHaveBeenCalled();
});
