import golden from "../../../../fixtures/referral-review/offsets-golden.json";
import { locateQuoteV1, normalizeTextV1, sliceCodePoints } from "../../lib/referral-api/evidence";

test("text-v1 offsets use Unicode code points across a surrogate pair and NFC", () => {
  const page = normalizeTextV1(golden.source);
  expect(page).toBe(golden.normalized);
  expect(locateQuoteV1(page, golden.quote, golden.before)).toEqual({
    start_cp: golden.start_cp, end_cp: golden.end_cp,
  });
  expect(sliceCodePoints(page, golden.start_cp, golden.end_cp)).toBe(golden.quote);
  expect(() => locateQuoteV1(page, golden.quote)).toThrow("ambiguous");
});
