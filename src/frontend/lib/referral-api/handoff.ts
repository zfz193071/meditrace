import type { components } from "./generated";
import { REFERRAL_API_PREFIX } from "./index";

export type HandoffView = components["schemas"]["HandoffView"];

export function handoffText(view: HandoffView): string {
  return [view.title, view.status, ...view.warnings,
    ...view.sections.flatMap(section => [section.heading, ...section.paragraphs])].join("\n\n") + "\n";
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, value => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[value]!);
}

// Pure local rendering for bundled demo printing; no network, scripts, or raw HTML from sources.
export function handoffPrintHtml(view: HandoffView): string {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${escapeHtml(view.title)}</title>
<style>@page{size:A4;margin:18mm}body{font:12pt/1.5 sans-serif;color:#192630;overflow-wrap:anywhere}
h1{font-size:24pt;color:#144150}h2{font-size:15pt;color:#144150;break-after:avoid}
p{white-space:pre-wrap;orphans:3;widows:3}.warning{color:#963714;font-weight:bold}
header{font-size:9pt;color:#374b5a}@media print{header{position:fixed;top:-12mm}}section{margin-bottom:1.5em}</style></head><body>
<header>MEDITRACE / REFERRAL HANDOFF${view.historical ? " / Historical revision" : ""}</header>
<h1>${escapeHtml(view.title)}</h1><p>${escapeHtml(view.status)}</p>
${view.warnings.map(w => `<p class="warning">${escapeHtml(w)}</p>`).join("")}
${view.sections.map(s => `<section><h2>${escapeHtml(s.heading)}</h2>${s.paragraphs.map(p => `<p>${escapeHtml(p)}</p>`).join("")}</section>`).join("")}</body></html>`;
}

export async function getHandoff(packetId: string, snapshotId: string, signal?: AbortSignal): Promise<HandoffView> {
  const response = await fetch(`${REFERRAL_API_PREFIX}/packets/${encodeURIComponent(packetId)}/snapshots/${encodeURIComponent(snapshotId)}/handoff`, {
    credentials: "same-origin", cache: "no-store", signal,
  });
  if (!response.ok) throw new Error("Confirmed handoff is unavailable.");
  return response.json();
}

export function handoffDownloadUrl(packetId: string, snapshotId: string, format: "pdf" | "txt"): string {
  return `${REFERRAL_API_PREFIX}/packets/${encodeURIComponent(packetId)}/snapshots/${encodeURIComponent(snapshotId)}/export?format=${format}`;
}
