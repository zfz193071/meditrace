import { useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { WorkspaceGate, type Access } from "../../components/referral/WorkspaceGate";
import { workspaceApi as api, WorkspaceError, type Session } from "../../lib/referral-api/workspace";
import { caps, session, pid } from "../../test-support/workspace";

jest.mock("../../lib/referral-api/workspace", () => ({
  ...jest.requireActual("../../lib/referral-api/workspace"),
  workspaceApi: { session: jest.fn(), capabilities: jest.fn() },
}));
function Editor({ csrf, onError }: Access) {
  const [text, setText] = useState("");
  return <><label>Unsaved note<input value={text} onChange={event => setText(event.target.value)} /></label>
    <output aria-label="Current CSRF">{csrf}</output>
    <button onClick={() => onError(new WorkspaceError("AUTH_REQUIRED", 401))}>Report ended session</button></>;
}
function mount() { return render(<WorkspaceGate packetId={pid}>{access => <Editor {...access} />}</WorkspaceGate>); }
async function edit() {
  fireEvent.change(await screen.findByLabelText("Unsaved note"), { target: { value: "Synthetic unsaved note" } });
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const anonymous: Session = { user: null, csrf_token: null, expires_at: null, login_available: true };
beforeEach(() => {
  jest.resetAllMocks();
  jest.mocked(api.session).mockResolvedValue(session);
  jest.mocked(api.capabilities).mockResolvedValue(caps);
});
afterEach(() => jest.useRealTimers());

it("preserves an unexpired editor after a transient session failure and refreshes credentials on retry", async () => {
  mount(); await edit();
  jest.mocked(api.session).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ ...session, csrf_token: "fresh-csrf" });
  fireEvent(window, new Event("focus"));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Unsaved note")).toHaveValue("Synthetic unsaved note");
  expect(screen.queryByRole("link", { name: "Sign in again" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry session check" }));
  await screen.findByText("fresh-csrf");
  expect(screen.getByLabelText("Unsaved note")).toHaveValue("Synthetic unsaved note");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("preserves the same user's editor when only capabilities fail", async () => {
  mount(); await edit();
  jest.mocked(api.capabilities).mockRejectedValueOnce(new Error("offline"));
  fireEvent(window, new Event("focus"));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Unsaved note")).toHaveValue("Synthetic unsaved note");
  fireEvent.click(screen.getByRole("button", { name: "Retry session check" }));
  await act(async () => {});
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Unsaved note")).toHaveValue("Synthetic unsaved note");
});

it("removes the previous user's editor immediately when the account changes, even if capabilities are pending", async () => {
  const pendingCaps = deferred<typeof caps>();
  mount(); await edit();
  const next: Session = { ...session, user: { id: "new-synthetic-user", display_name: "Another reviewer" } };
  jest.mocked(api.session).mockResolvedValue(next);
  jest.mocked(api.capabilities).mockReturnValueOnce(pendingCaps.promise);
  fireEvent(window, new Event("focus"));
  await act(async () => {});
  expect(screen.queryByLabelText("Unsaved note")).not.toBeInTheDocument();
  await act(async () => { pendingCaps.reject(new Error("offline")); });
  expect(screen.queryByDisplayValue("Synthetic unsaved note")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry session check" }));
  expect(await screen.findByLabelText("Unsaved note")).toHaveValue("");
});

it("handles a verified sign-out without waiting for the capabilities service", async () => {
  mount(); await edit();
  jest.mocked(api.session).mockResolvedValue(anonymous);
  jest.mocked(api.capabilities).mockReturnValue(new Promise(() => {}));
  fireEvent(window, new Event("focus"));
  await act(async () => {});
  expect(screen.queryByLabelText("Unsaved note")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Continue with GitHub" })).toBeInTheDocument();
});

it.each([
  ["session", 401], ["session", 403], ["capabilities", 401], ["capabilities", 403],
] as const)("clears private input on an explicit %s rejection (%s)", async (endpoint, status) => {
  mount(); await edit();
  jest.mocked(api[endpoint]).mockRejectedValueOnce(new WorkspaceError(status === 401 ? "AUTH_REQUIRED" : "FORBIDDEN", status));
  fireEvent(window, new Event("focus"));
  await screen.findByRole("alert");
  expect(screen.queryByLabelText("Unsaved note")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sign in again" })).toBeInTheDocument();
});

it("removes private input at the verified expiry while a new session read is still pending", async () => {
  jest.useFakeTimers();
  const read = deferred<Session>();
  jest.mocked(api.session).mockResolvedValueOnce({ ...session, expires_at: new Date(Date.now() + 1000).toISOString() })
    .mockRejectedValueOnce(new Error("offline")).mockReturnValueOnce(read.promise);
  mount(); await act(async () => {});
  fireEvent.change(screen.getByLabelText("Unsaved note"), { target: { value: "Synthetic unsaved note" } });
  fireEvent(window, new Event("focus"));
  await act(async () => {});
  expect(screen.getByLabelText("Unsaved note")).toHaveValue("Synthetic unsaved note");
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.queryByLabelText("Unsaved note")).not.toBeInTheDocument();
  await act(async () => { read.reject(new Error("offline")); });
  expect(screen.queryByLabelText("Unsaved note")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sign in again" })).toBeInTheDocument();
});

it.each(["success", "failure"] as const)("ignores a late background %s after a child reports an ended session", async result => {
  const read = deferred<Session>();
  mount(); await edit();
  jest.mocked(api.session).mockReturnValueOnce(read.promise);
  fireEvent(window, new Event("focus"));
  fireEvent.click(screen.getByRole("button", { name: "Report ended session" }));
  await act(async () => { if (result === "success") read.resolve(session); else read.reject(new Error("offline")); });
  expect(screen.queryByLabelText("Unsaved note")).not.toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Your session ended");
});

it("does not display an editor before the first successful session and capabilities check", async () => {
  jest.mocked(api.session).mockRejectedValueOnce(new Error("offline"));
  mount();
  await screen.findByRole("alert");
  expect(screen.queryByLabelText("Unsaved note")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry session check" }));
  expect(await screen.findByLabelText("Unsaved note")).toHaveValue("");
});
