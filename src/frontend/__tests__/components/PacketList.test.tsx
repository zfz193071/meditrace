import { StrictMode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PacketList } from "../../components/referral/PacketList";
import { workspaceApi as api, WorkspaceError, type PacketList as List } from "../../lib/referral-api/workspace";
import { caps, packet } from "../../test-support/workspace";

jest.mock("../../lib/referral-api/workspace", () => ({
  ...jest.requireActual("../../lib/referral-api/workspace"),
  workspaceApi: { list: jest.fn(), create: jest.fn(), remove: jest.fn() },
}));
const access = { csrf: "test-csrf", capabilities: caps, onError: jest.fn() };
const initial: List = { items: [packet], next_cursor: null };
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
async function mount() {
  const view = render(<PacketList {...access} />);
  await screen.findByRole("link", { name: packet.title });
  return view;
}
function fill() {
  fireEvent.change(screen.getByLabelText("Packet title"), { target: { value: "Synthetic unsaved title" } });
  fireEvent.click(screen.getByLabelText(/I am using synthetic data/));
}
beforeEach(() => { jest.resetAllMocks(); jest.mocked(api.list).mockResolvedValue(initial); });

it("removes a confirmed deletion even when refreshing fails, preserving the create draft", async () => {
  const refresh = deferred<List>();
  jest.mocked(api.list).mockResolvedValueOnce(initial).mockReturnValueOnce(refresh.promise).mockResolvedValue({ items: [], next_cursor: null });
  jest.mocked(api.remove).mockResolvedValue({ id: packet.id, status: "pending_cleanup" });
  await mount(); fill();
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  await waitFor(() => expect(api.list).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole("link", { name: packet.title })).not.toBeInTheDocument();
  expect(screen.getByText(/Packet access ended/)).toBeInTheDocument();
  await act(async () => { refresh.reject(new Error("offline")); });
  expect(screen.getByRole("alert")).toBeInTheDocument();
  expect(screen.getByLabelText("Packet title")).toHaveValue("Synthetic unsaved title");
  expect(screen.getByLabelText(/I am using synthetic data/)).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Refresh list" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(api.remove).toHaveBeenCalledTimes(1);
});

it("does not remove a packet on an uncertain delete response and permits explicit retry", async () => {
  jest.mocked(api.remove).mockRejectedValueOnce(new Error("lost response")).mockResolvedValueOnce({ id: packet.id, status: "pending_cleanup" });
  jest.mocked(api.list).mockResolvedValueOnce(initial).mockResolvedValue({ items: [], next_cursor: null });
  await mount();
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("link", { name: packet.title })).toBeInTheDocument();
  expect(screen.queryByText(/Packet access ended/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  await waitFor(() => expect(screen.queryByRole("link", { name: packet.title })).not.toBeInTheDocument());
  expect(api.remove).toHaveBeenCalledTimes(2);
});

it("serializes create and refresh even before React updates the disabled buttons", async () => {
  const create = deferred<typeof packet>();
  jest.mocked(api.create).mockReturnValue(create.promise);
  await mount(); fill();
  const form = screen.getByRole("button", { name: "Create packet" }).closest("form")!;
  const refresh = screen.getByRole("button", { name: "Refresh list" });
  act(() => { fireEvent.submit(form); fireEvent.submit(form); fireEvent.click(refresh); });
  expect(api.create).toHaveBeenCalledTimes(1);
  expect(api.list).toHaveBeenCalledTimes(1);
  await act(async () => { create.resolve(packet); });
  expect(screen.getByLabelText("Packet title")).toHaveValue("");
});

it.each(["create", "remove"] as const)("ignores a late %s authorization error after unmount", async method => {
  const request = deferred<never>();
  jest.mocked(api[method]).mockReturnValue(request.promise);
  const view = await mount();
  if (method === "create") {
    fill(); fireEvent.click(screen.getByRole("button", { name: "Create packet" }));
  } else {
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  }
  view.unmount();
  await act(async () => { request.reject(new WorkspaceError("AUTH_REQUIRED", 401)); });
  expect(access.onError).not.toHaveBeenCalled();
});

it("does not refresh from a deletion that completes after unmount", async () => {
  const deletion = deferred<Awaited<ReturnType<typeof api.remove>>>();
  jest.mocked(api.remove).mockReturnValue(deletion.promise);
  const view = await mount();
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  view.unmount();
  await act(async () => { deletion.resolve({ id: packet.id, status: "pending_cleanup" }); });
  expect(api.list).toHaveBeenCalledTimes(1);
});

it("ignores a stale StrictMode load after a confirmed deletion", async () => {
  const old = deferred<List>();
  jest.mocked(api.list).mockReturnValueOnce(old.promise).mockResolvedValueOnce(initial).mockResolvedValue({ items: [], next_cursor: null });
  jest.mocked(api.remove).mockResolvedValue({ id: packet.id, status: "pending_cleanup" });
  render(<StrictMode><PacketList {...access} /></StrictMode>);
  await screen.findByRole("link", { name: packet.title });
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  await screen.findByText("No packets yet");
  await act(async () => { old.resolve(initial); });
  expect(screen.queryByRole("link", { name: packet.title })).not.toBeInTheDocument();
});
