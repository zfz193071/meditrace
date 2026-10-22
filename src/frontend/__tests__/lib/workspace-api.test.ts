import { workspaceApi as api, WorkspaceError } from "../../lib/referral-api/workspace";
import { packet } from "../../test-support/workspace";
beforeEach(() => jest.clearAllMocks());
test("writes use CSRF, caller key, same origin and no-store", async () => {
  (fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => packet });
  await api.create({ title: "Synthetic", synthetic_data_ack: true }, "csrf", "persistent-key");
  expect(fetch).toHaveBeenCalledWith("/api/v1/packets", expect.objectContaining({ method: "POST", credentials: "same-origin", cache: "no-store", headers: expect.objectContaining({ "X-CSRF-Token": "csrf", "Idempotency-Key": "persistent-key" }) }));
});
test("execute failure never retries and never logs a raw response", async () => {
  (fetch as jest.Mock).mockResolvedValue({ ok: false, status: 503, json: async () => ({ error: { code: "SERVICE_NOT_READY", message: "secret raw source" } }) });
  await expect(api.execute("run", "csrf", "key")).rejects.toThrow(WorkspaceError); expect(fetch).toHaveBeenCalledTimes(1);
});
test("request timeout aborts without a retry", async () => {
  jest.useFakeTimers();
  (fetch as jest.Mock).mockImplementation((_url, init) => new Promise((_resolve, reject) => init.signal.addEventListener("abort", () => reject(new Error("aborted")))));
  const result = expect(api.latestRun("packet")).rejects.toThrow("aborted");
  jest.advanceTimersByTime(20_000); await result; expect(fetch).toHaveBeenCalledTimes(1); jest.useRealTimers();
});
test("PDF multipart leaves boundary generation to the browser", async () => {
  (fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => packet.documents[0] });
  await api.uploadPdf("packet", new File(["PDF"], "test.pdf"), "csrf", "key");
  const init = jest.mocked(fetch).mock.calls[0]?.[1];
  expect(new Headers(init?.headers).has("Content-Type")).toBe(false); expect(init?.body).toBeInstanceOf(FormData);
});
