import { createHash } from "node:crypto";
import { evidenceSlice, originalDocumentUrl } from "../../lib/referral-api/evidence";
import { pageOne, reviewState, reviewRun } from "../../test-support/review";

test("Unicode code point offsets locate the second repeated quote, not a substring search", () => {
  const text = "😀 e\u0301 same " + "x".repeat(1000) + " same end";
  const start = Array.from(text).length - 8;
  const page = { ...pageOne, normalized_text: text, text_hash: createHash("sha256").update(text).digest("hex") };
  const evidence = { ...reviewRun.result!.evidence[0], start_cp: start, end_cp: start + 4, quote: "same", text_hash: page.text_hash };
  const slice = evidenceSlice(evidence, page, reviewState.revision);
  expect(slice?.quote).toBe("same"); expect(slice?.before).toHaveLength(180); expect(slice?.after).toBe(" end");
  expect(evidenceSlice({ ...evidence, start_cp: start - 1 }, page, reviewState.revision)).toBeNull();
});

test("revision membership, parser version, page and hash must all agree", () => {
  const e = reviewRun.result!.evidence[0];
  expect(evidenceSlice(e, pageOne, reviewState.revision)?.quote).toBe(e.quote);
  expect(evidenceSlice(e, pageOne, { ...reviewState.revision, documents: [] })).toBeNull();
  for (const page of [{ ...pageOne, parser_version: "other" }, { ...pageOne, text_hash: "f".repeat(64) }, { ...pageOne, page_number: 2 }]) expect(evidenceSlice(e, page, reviewState.revision)).toBeNull();
  expect(originalDocumentUrl("a/b", "javascript:alert(1)")).toBe("/api/v1/packets/a%2Fb/documents/javascript%3Aalert(1)/original");
});
