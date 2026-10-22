import type { Evidence, Page, Revision } from "./workspace";

// Offsets are Unicode code points, never UTF-16 indices or a quote search.
export function evidenceSlice(evidence: Evidence, page: Page, revision: Revision) {
  const doc = revision.documents.find(doc => doc.id === evidence.document_id);
  const chars = Array.from(page.normalized_text);
  if (!doc || doc.parser_version !== page.parser_version || page.parse_quality !== "ready" ||
      page.document_id !== evidence.document_id || page.page_number !== evidence.page_number ||
      page.text_hash !== evidence.text_hash || (doc.page_count === null || evidence.page_number > doc.page_count) ||
      !Number.isInteger(evidence.start_cp) || !Number.isInteger(evidence.end_cp) ||
      evidence.start_cp < 0 || evidence.end_cp <= evidence.start_cp || evidence.end_cp > chars.length ||
      chars.slice(evidence.start_cp, evidence.end_cp).join("") !== evidence.quote) return null;
  return { before: chars.slice(Math.max(0, evidence.start_cp - 180), evidence.start_cp).join(""),
    quote: evidence.quote, after: chars.slice(evidence.end_cp, evidence.end_cp + 180).join("") };
}

export async function verifyPageHash(page: Page): Promise<boolean> {
  const bytes = new TextEncoder().encode(page.normalized_text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("") === page.text_hash;
}
export function originalDocumentUrl(packetId: string, documentId: string) {
  return `/api/v1/packets/${encodeURIComponent(packetId)}/documents/${encodeURIComponent(documentId)}/original`;
}

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
