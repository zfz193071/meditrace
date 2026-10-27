import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { webcrypto } from "node:crypto";
import { TextEncoder } from "node:util";
import { DemoWorkspace } from "../../components/referral/DemoWorkspace";
import { createDemoSession } from "../../lib/referral-api/demo";
import { handoffText } from "../../lib/referral-api/handoff";

beforeAll(() => {
  Object.defineProperty(globalThis, "TextEncoder", { value: TextEncoder });
  Object.defineProperty(crypto, "subtle", { value: webcrypto.subtle });
  globalThis.structuredClone = value => JSON.parse(JSON.stringify(value));
});
beforeEach(() => { jest.clearAllMocks(); jest.mocked(fetch).mockRejectedValue(new Error("Demo network forbidden")); });
afterEach(() => { expect(fetch).not.toHaveBeenCalled(); expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0); });

test("selecting an item moves keyboard focus to evidence without waiting for an animation frame", async () => {
  const frame = jest.spyOn(window, "requestAnimationFrame").mockImplementation(() => 1);
  try {
    render(<DemoWorkspace />);
    await screen.findByText(/Saved decisions loaded/);
    const item = document.querySelector<HTMLButtonElement>(".rr-findings button")!;
    item.focus();
    fireEvent.click(item);
    await waitFor(() => expect(screen.getByRole("region", { name: "Evidence and decision" })).toHaveFocus());
    // Re-selecting the same item must transfer focus too, even if its ID is unchanged.
    item.focus();
    fireEvent.click(item);
    await waitFor(() => expect(screen.getByRole("region", { name: "Evidence and decision" })).toHaveFocus());
  } finally {
    frame.mockRestore();
  }
});

async function deferAll(s: ReturnType<typeof createDemoSession>) {
  const run = s.initialRun();
  for (const f of run.result!.findings) {
    const state = await s.api.reviewState(run.id);
    await s.api.resolve(run.id, f.id, { expected_review_version: state.review_version, action: "defer", reason: "Verify with sender", corrected_value: "Reviewer note <script>unsafe()</script>", linked_evidence_ids: f.evidence_ids }, "", crypto.randomUUID());
  }
}
async function confirm(s: ReturnType<typeof createDemoSession>, run = s.initialRun()) {
  const state = await s.api.reviewState(run.id);
  return s.api.confirm(s.packet().id, { mode: "assisted", run_id: run.id, revision_id: run.revision_id, expected_review_version: state.review_version }, "");
}

test("visitor isolation, decision CAS, retry idempotency and immutable snapshots", async () => {
  const s = createDemoSession("identity"), other = createDemoSession("identity"), run = s.initialRun(), fid = run.result!.findings[0].id;
  await expect(confirm(s)).rejects.toMatchObject({ code: "OPEN_FINDINGS" });
  const body = { expected_review_version: 0, action: "defer" as const, reason: "Ask sender" };
  const first = await s.api.resolve(run.id, fid, body, "", "same-operation");
  expect(await s.api.resolve(run.id, fid, body, "", "same-operation")).toEqual(first);
  await expect(s.api.resolve(run.id, fid, body, "", "new-operation")).rejects.toMatchObject({ code: "REVIEW_CONFLICT" });
  expect((await other.api.reviewState(run.id)).decisions).toHaveLength(0);
  await deferAll(s); const snap = await confirm(s), view = await s.api.handoff(s.packet().id, snap.id);
  expect(handoffText(view)).toContain("Identity unresolved");
  expect(handoffText(view)).toContain("Reviewer supplied: Reviewer note <script>");
  expect(view.payload_hash).toMatch(/^[a-f0-9]{64}$/);
  const state = await s.api.reviewState(run.id);
  await s.api.resolve(run.id, fid, { expected_review_version: state.review_version, action: "reopen", reason: "" }, "", "reopen");
  const historical = await s.api.handoff(s.packet().id, snap.id);
  expect(historical.historical).toBe(true); expect(historical.sections).toEqual(view.sections);
  view.sections[0].paragraphs[0] = "mutated caller";
  expect((await s.api.handoff(s.packet().id, snap.id)).sections).toEqual(historical.sections);
  expect((await createDemoSession("identity").api.reviewState(run.id)).review_version).toBe(0);
});

test("prepared revision invalidates old runs, retains history and never inherits decisions", async () => {
  const s = createDemoSession("missing"), old = s.initialRun();
  await deferAll(s); const snap = await confirm(s);
  s.loadPreparedRevision();
  expect((await s.api.reviewState(old.id)).stale).toBe(true);
  await expect(s.api.resolve(old.id, old.result!.findings[0].id, { expected_review_version: 2, action: "resolve", reason: "" }, "", "stale")).rejects.toMatchObject({ code: "STALE_RUN" });
  await expect(confirm(s)).rejects.toMatchObject({ code: "STALE_RUN" });
  expect((await s.api.handoff(s.packet().id, snap.id)).historical).toBe(true);
  const next = s.preparedRun();
  expect(next.result!.findings).toHaveLength(0); expect((await s.api.reviewState(next.id)).decisions).toHaveLength(0);
  expect((await s.api.history(s.packet().id)).items).toHaveLength(2);
  expect((await confirm(s, next)).revision_id).toBe(next.revision_id);
});

test("shared UI presents verified identity quotes, decisions, handoff warning and reset", async () => {
  render(<DemoWorkspace />);
  await waitFor(() => expect(document.querySelectorAll(".rr-source-excerpt mark")).toHaveLength(2));
  const items = [...document.querySelectorAll<HTMLButtonElement>(".rr-findings button")];
  for (const item of items) {
    fireEvent.click(item);
    fireEvent.change(screen.getByLabelText("Action"), { target: { value: "defer" } });
    fireEvent.change(screen.getByLabelText("Reason (required)"), { target: { value: "Confirm with the sender" } });
    fireEvent.click(screen.getByRole("button", { name: "Save decision" }));
    await screen.findByText("Saved decision: unresolved");
    await waitFor(() => expect(screen.getByRole("button", { name: "Save decision" })).toBeEnabled());
  }
  fireEvent.click(screen.getByRole("button", { name: "Confirm reviewed handoff" }));
  fireEvent.click(screen.getByRole("button", { name: "Create confirmed snapshot" }));
  const handoff = await screen.findByRole("article", { name: "Confirmed handoff" });
  expect(within(handoff).getByText(/Identity unresolved/)).toBeInTheDocument();
  fireEvent.click(within(handoff).getByRole("button", { name: "Copy text" }));
  await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining("Identity unresolved")));
  expect(document.querySelector('a[href^="/api/"]')).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Reset demo" }));
  await screen.findByText(/2 open items/);
  expect(screen.queryByRole("article", { name: "Confirmed handoff" })).not.toBeInTheDocument();
});

test("UI explicitly loads a stale revision before the new prepared result; normal case confirms", async () => {
  render(<DemoWorkspace />); await screen.findByText(/Saved decisions loaded/);
  fireEvent.click(screen.getByRole("button", { name: /02 \/ Missing/ }));
  await screen.findByText(/1 open items/);
  fireEvent.click(screen.getByRole("button", { name: "Load prepared revision" }));
  await screen.findByText(/Historical source version. Review decisions/);
  expect(screen.getByRole("button", { name: "Confirm reviewed handoff" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Load prepared result" }));
  await screen.findByText(/No findings in this saved result/);
  expect(screen.getByRole("button", { name: "Confirm reviewed handoff" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: /03 \/ Complete/ }));
  await screen.findByText(/No findings in this saved result/);
  fireEvent.click(screen.getByRole("button", { name: "Confirm reviewed handoff" }));
  fireEvent.click(screen.getByRole("button", { name: "Create confirmed snapshot" }));
  expect(await screen.findByRole("article", { name: "Confirmed handoff" })).toHaveTextContent("No checklist findings");
});
