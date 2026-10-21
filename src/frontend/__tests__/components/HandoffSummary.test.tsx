import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "fs";
import path from "path";
import { HandoffSummary } from "../../components/referral/HandoffSummary";
import { handoffText, handoffPrintHtml, handoffDownloadUrl, getHandoff, type HandoffView } from "../../lib/referral-api/handoff";
import demo from "../../lib/referral-api/demo-handoffs.json";

const view: HandoffView = { ...demo["dev-01"], schema_version: "handoff-v1" };

describe("confirmed handoff", () => {
  beforeEach(() => jest.clearAllMocks());

  it("renders every section and unresolved identity without a business request", () => {
    render(<HandoffSummary view={view} />);
    expect(screen.getByText("Identity unresolved")).toBeInTheDocument();
    expect(screen.getByText("Reviewed — unresolved items remain")).toBeInTheDocument();
    for (const section of view.sections) {
      expect(screen.getByRole("heading", { name: section.heading })).toBeInTheDocument();
    }
    expect(fetch).not.toHaveBeenCalled();
  });

  it("copies exactly the same text as the server renderer", async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    navigator.clipboard.writeText = writeText;
    render(<HandoffSummary view={view} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy text" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Confirmed text copied."));
    expect(writeText).toHaveBeenCalledWith(handoffText(view));
    const root = path.resolve(process.cwd(), "../../output/pdf");
    const sample: HandoffView = JSON.parse(readFileSync(path.join(root, "handoff-short.json"), "utf8"));
    expect(handoffText(sample)).toBe(readFileSync(path.join(root, "handoff-short.txt"), "utf8"));
    expect(fetch).not.toHaveBeenCalled();
  });

  it("reports clipboard failure without implying success", async () => {
    navigator.clipboard.writeText = jest.fn().mockRejectedValue(new Error("denied"));
    render(<HandoffSummary view={view} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy text" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Download the text instead"));
  });

  it("escapes source content in local print HTML and retains the complete source index", () => {
    const malicious = { ...view, historical: true, sections: [{ heading: "<img src=x>", paragraphs: ["<script>fetch('/evil')</script>"] }, ...view.sections] };
    const html = handoffPrintHtml(malicious);
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("Historical revision");
    expect(html).toContain("Source index");
    expect(html).toContain("Identity unresolved");
  });

  it("uses authenticated no-store reads and stable download routes", async () => {
    (fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => view });
    expect(await getHandoff("packet", "snapshot")).toEqual(view);
    expect(fetch).toHaveBeenCalledWith("/api/v1/packets/packet/snapshots/snapshot/handoff", {
      credentials: "same-origin", cache: "no-store", signal: undefined,
    });
    expect(handoffDownloadUrl("a/b", "id?", "pdf")).toBe("/api/v1/packets/a%2Fb/snapshots/id%3F/export?format=pdf");
  });

  it("does not surface a proxy or server error body", async () => {
    const text = jest.fn().mockResolvedValue("sensitive-body");
    (fetch as jest.Mock).mockResolvedValue({ ok: false, text });
    await expect(getHandoff("p", "s")).rejects.toThrow("Confirmed handoff is unavailable.");
    expect(text).not.toHaveBeenCalled();
  });
});
