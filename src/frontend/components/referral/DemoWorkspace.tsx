"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { createDemoSession, type DemoCase } from "../../lib/referral-api/demo";
import { ReviewTransportProvider } from "./ReviewTransport";
import { ReviewWorkspace } from "./ReviewWorkspace";
import { errorMessage } from "../../lib/referral-api/workspace";

const cases: { key: DemoCase; title: string; description: string }[] = [
  { key: "identity", title: "01 / Conflicting dates of birth", description: "Compare two source quotes. Keep the identity issue unresolved to see its warning in the handoff. This packet also has a missing report." },
  { key: "missing", title: "02 / Missing claimed report", description: "A referral says an echo report is attached, but it is absent. Load the prepared revision to see how source updates invalidate an old result." },
  { key: "normal", title: "03 / Complete referral", description: "No checklist findings. Inspect the extracted facts, then confirm a handoff. A clean checklist is not a clinical assessment." },
];

export function DemoWorkspace() {
  const [choice, setChoice] = useState<DemoCase>("identity");
  const [generation, setGeneration] = useState(0);
  const [dirty, setDirty] = useState(false);
  function reset(next: DemoCase) {
    if (dirty && !window.confirm("Discard unsaved review edits and reset this demo?")) return;
    setDirty(false); setChoice(next); setGeneration(n => n + 1);
  }
  return <div className="rr-shell">
    <header className="rr-topbar"><Link prefetch={false} href="/">MediTrace<span>Referral Review Copilot</span></Link><Link prefetch={false} href="/workspace">Open workspace</Link></header>
    <section><p className="demo-eyebrow">Interactive portfolio · Synthetic / precomputed</p><h1>Follow the evidence. Make the human decision.</h1><p>No account, payment or model key needed. These fixed examples run locally. Your edits disappear when you reset, switch cases or refresh.</p></section>
    <nav className="demo-cases" aria-label="Choose a demo case">{cases.map(c => <button key={c.key} aria-pressed={choice === c.key} onClick={() => reset(c.key)}>{c.title}</button>)}</nav>
    <section className="rr-card"><div className="rr-heading"><h2>{cases.find(c => c.key === choice)!.title}</h2><button onClick={() => reset(choice)}>Reset demo</button></div><p>{cases.find(c => c.key === choice)!.description}</p>
      <ol className="demo-steps"><li><strong>Inspect.</strong> Select an item and read its highlighted source quotes.</li><li><strong>Decide.</strong> Choose Keep unresolved and enter a reason when verification is still needed. Save each decision.</li><li><strong>Export.</strong> Once no items are open, confirm and copy, download or print the handoff.</li></ol>
      <p className="rr-muted">Suggested 60–90 second walkthrough: inspect both birth dates, keep both issues unresolved with reasons, then confirm and export. No real patient information should be entered.</p>
    </section>
    <DemoReview key={`${choice}:${generation}`} choice={choice} onDirty={setDirty} />
    <footer><p>Public development fixtures, including an explicitly authored report-recovery variant. These examples are not evaluation results.</p><Link prefetch={false} href="/evaluation">Evaluation status</Link> · <Link prefetch={false} href="/project#architecture">Architecture</Link></footer>
  </div>;
}

function DemoReview({ choice, onDirty }: { choice: DemoCase; onDirty: (dirty: boolean) => void }) {
  const [session] = useState(() => createDemoSession(choice));
  const [packet, setPacket] = useState(() => session.packet());
  const [run, setRun] = useState(() => session.initialRun());
  const [prepared, setPrepared] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const onError = useCallback((e: unknown) => setError(errorMessage(e)), []);
  const dirtyChanged = useCallback((value: boolean) => { setDirty(value); onDirty(value); }, [onDirty]);
  function advance(result: boolean) {
    if (dirty && !window.confirm("Discard unsaved review edits before loading prepared material?")) return;
    if (result) { setRun(session.preparedRun()); setPrepared(true); }
    else { setPacket(session.loadPreparedRevision()); setRun(old => ({ ...old, stale: true })); }
    dirtyChanged(false); setError("");
  }
  return <ReviewTransportProvider value={session.api}>
    {choice === "missing" && <section className="rr-card"><h2>Prepared attachment recovery</h2><p>Version 1 has no echo report. Version 2 adds an authored synthetic report; its fixed result contains no attachment finding. Neither action calls AI.</p>
      {packet.current_revision === 1 ? <button onClick={() => advance(false)}>Load prepared revision</button> : <><p role="status">Source version 2 loaded. The version 1 result is historical and cannot accept decisions.</p><button disabled={prepared} onClick={() => advance(true)}>{prepared ? "Prepared result loaded" : "Load prepared result"}</button></>}
    </section>}
    {error && <p role="alert" className="rr-alert">{error}</p>}
    <ReviewWorkspace key={`${run.id}:${packet.current_revision}`} packet={packet} run={run} csrf="" sourceDirty={false} onError={onError} onDirty={dirtyChanged} />
  </ReviewTransportProvider>;
}
