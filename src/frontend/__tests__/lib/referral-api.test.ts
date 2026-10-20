import { getCapabilities, REFERRAL_API_PREFIX } from "../../lib/referral-api";

describe("referral API foundation", () => {
  beforeEach(() => jest.clearAllMocks());

  it("uses same-origin credentials and does not cache private responses", async () => {
    const response = { mode: "bundled_demo", real_ai_execution_available: false };
    (fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => response });
    expect(await getCapabilities()).toEqual(response);
    expect(fetch).toHaveBeenCalledWith(`${REFERRAL_API_PREFIX}/capabilities`, {
      credentials: "same-origin", cache: "no-store", signal: undefined,
    });
  });

  it("does not expose an untrusted error response", async () => {
    const readBody = jest.fn().mockResolvedValue("secret-sentinel");
    (fetch as jest.Mock).mockResolvedValue({ ok: false, text: readBody });
    await expect(getCapabilities()).rejects.toThrow("Referral service is unavailable.");
    expect(readBody).not.toHaveBeenCalled();
  });
});
