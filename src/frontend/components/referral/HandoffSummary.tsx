"use client";

import { useState } from "react";
import { handoffPrintHtml, handoffText, type HandoffView } from "../../lib/referral-api/handoff";

/** Shared confirmed-summary surface for MT-15 workspace and MT-16 local demo. */
export function HandoffSummary({ view }: { view: HandoffView }) {
  const [message, setMessage] = useState("");

  async function copy() {
    try {
      await navigator.clipboard.writeText(handoffText(view));
      setMessage("Confirmed text copied.");
    } catch {
      setMessage("Copy is unavailable. Download the text instead.");
    }
  }

  function downloadText() {
    const url = URL.createObjectURL(new Blob([handoffText(view)], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `referral-${view.snapshot_id}.txt`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function print() {
    const frame = document.createElement("iframe");
    frame.title = "Printable confirmed handoff";
    frame.style.cssText = "position:fixed;left:-10000px;width:800px;height:1100px;border:0";
    frame.onload = () => {
      const target = frame.contentWindow;
      if (!target) { frame.remove(); return; }
      target.addEventListener("afterprint", () => frame.remove(), { once: true });
      target.print();
    };
    frame.srcdoc = handoffPrintHtml(view);
    document.body.appendChild(frame);
    setTimeout(() => frame.remove(), 60000);
  }

  return <article aria-label="Confirmed handoff" className="space-y-6 break-words">
    <header>
      <h2 className="text-2xl font-semibold">{view.title}</h2>
      <p>{view.status}</p>
      {view.warnings.map(warning => <p key={warning} className="font-semibold text-amber-800">{warning}</p>)}
    </header>
    <div className="flex flex-wrap gap-4 print:hidden">
      <button type="button" onClick={copy}>Copy text</button>
      <button type="button" onClick={downloadText}>Download text</button>
      <button type="button" onClick={print}>Print / Save PDF</button>
      <p role="status">{message}</p>
    </div>
    {view.sections.map(section => <section key={section.heading} className="space-y-3">
      <h3 className="text-lg font-semibold">{section.heading}</h3>
      {section.paragraphs.map((paragraph, index) => <p key={index} className="whitespace-pre-wrap">{paragraph}</p>)}
    </section>)}
  </article>;
}
