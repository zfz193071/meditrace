/** Frozen text-v1 rules. Offsets count Unicode code points, not UTF-16 units. */
export function normalizeTextV1(value: string): string {
  return value.replace(/\r\n?/g, "\n").normalize("NFC");
}

export function sliceCodePoints(value: string, start: number, end: number): string {
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end <= start) {
    throw new Error("Invalid evidence span");
  }
  const points = Array.from(value);
  if (end > points.length) throw new Error("Evidence span exceeds page");
  return points.slice(start, end).join("");
}

export function locateQuoteV1(pageText: string, quote: string, before = "", after = "") {
  if (pageText !== normalizeTextV1(pageText)) throw new Error("Invalid text-v1 page");
  const source = Array.from(pageText);
  const match = Array.from(normalizeTextV1(quote));
  const left = Array.from(normalizeTextV1(before));
  const right = Array.from(normalizeTextV1(after));
  if (!match.length || !quote.trim()) throw new Error("Empty quote");
  const matches: number[] = [];
  for (let start = 0; start <= source.length - match.length; start++) {
    const end = start + match.length;
    if (source.slice(start, end).join("") === match.join("") &&
        source.slice(Math.max(0, start - left.length), start).join("").endsWith(left.join("")) &&
        source.slice(end, end + right.length).join("").startsWith(right.join(""))) {
      matches.push(start);
    }
  }
  if (matches.length !== 1) throw new Error("Quote is absent or ambiguous");
  return { start_cp: matches[0], end_cp: matches[0] + match.length };
}
