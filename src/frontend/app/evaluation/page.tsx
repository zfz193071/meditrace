import Link from "next/link";
import data from "../../public/evaluation/offline-summary.json";
import "../workspace/workspace.css";
import "../portfolio.css";
import "./evaluation.css";

export const metadata = { title: "Offline evaluation and limitations | MediTrace" };
const fraction = (metric: { numerator: number; denominator: number; value: number | null }) => metric.value === null ? "Not measured" : `${metric.numerator} / ${metric.denominator} (${(metric.value * 100).toFixed(1)}%)`;
const names: Record<string, string> = { baseline: "Simple line-reader baseline", fake: "Fake extraction + checklist", replay: "Replay of the Fake recording" };

export default function EvaluationPage() {
  return <main className="rr-workspace"><div className="rr-shell">
    <header className="rr-topbar"><Link prefetch={false} href="/">MediTrace<span>Evaluation evidence</span></Link><Link prefetch={false} href="/demo">Try demo</Link></header>
    <section><p className="demo-eyebrow">Development split · Offline measurements</p><h1>What we measured. What remains unknown.</h1><p>Ten synthetic development packets: nine readable packets and one deliberately unsupported scan. These are provisional annotations awaiting operator review.</p>
      <p className="rr-alert"><strong>Release evaluation is blocked.</strong> No real model was called. These numbers are not model accuracy, clinical validation or evidence of time saved.</p>
      <p>The 20-packet frozen test split was not evaluated in this run. Human-verified citation support, real input/output tokens, cost and model latency are <strong>not measured</strong>.</p>
    </section>
    <section aria-label="Offline comparison" className="eval-comparison">{data.reports.map(report => <article className="rr-card" key={report.provider}>
      <p className="demo-eyebrow">{report.provider}</p><h2>{names[report.provider]}</h2>
      <p>{report.summary.successful} succeeded · {report.summary.rejected} rejected · {report.summary.failed} failed / {report.summary.packets_total} total packets</p>
      <dl className="eval-metrics">
        <dt>Fact tuple precision / recall</dt><dd>{fraction(report.summary.facts.precision)}<br />{fraction(report.summary.facts.recall)}</dd>
        <dt>Finding precision / recall</dt><dd>{fraction(report.summary.findings.precision)}<br />{fraction(report.summary.findings.recall)}</dd>
        <dt>Finding TP / FP / FN</dt><dd>{report.summary.findings.tp} / {report.summary.findings.fp} / {report.summary.findings.fn}</dd>
        <dt>Citation integrity</dt><dd>{fraction(report.summary.citation_integrity)}</dd>
        <dt>Provisional support agreement</dt><dd>{fraction(report.summary.provisional_support)}</dd>
        <dt>Clean packets with false positives</dt><dd>{fraction(report.summary.negative_packets)}</dd>
        <dt>False-positive items / identity items in clean packets</dt><dd>{report.summary.negative_false_positive_items} / {report.summary.negative_identity_false_positives}</dd>
      </dl>
      <p className="rr-muted">{report.provider === "baseline" ? "A line-prefix reader with no temporal extraction, followed by deterministic rules." : report.provider === "fake" ? "Scripted output based on source lines passes through the production extraction validator and checklist. It is not an LLM." : "The recorded Fake output is revalidated without an adapter call. Aggregate and per-case counts reproduce the original run."}</p>
    </article>)}</section>
    <section className="rr-card"><h2>How to read the counts</h2><p>Facts match on field, raw value, assertion status and temporal context. Only the literal Medications: and Report: labels are stripped for comparison; dates, doses, units and negation are not guessed or normalized away. Duplicate predictions count as extras.</p><p>Findings match by packet, rule, kind and field. TP means matched, FP means unmatched prediction, and FN means missed annotation. Failed readable packets retain their missed facts and findings. Unsupported-input packets stay in the total and rejection counts.</p><p>Citation integrity checks source page, exact quote, code-point offsets and hash. Provisional support agreement also checks the annotated fact and supported span. It is not an independent human judgment. An annotation mismatch is not automatically a hallucination; missing citations, invalid citations, unsupported citations and values absent from source text are separate counters in the downloadable summary.</p><p>Fact-by-field and finding-by-kind denominators are included in the JSON. These small, regular synthetic examples do not measure performance on real referrals.</p></section>
    <section aria-label="Reproducible limitations"><h2>Observed failures and limits</h2><div className="eval-limitations">{data.limitations.map(item => <article id={item.id} className="rr-card" key={item.id}>
      <p className="demo-eyebrow">{item.category}</p><h3>{item.case} · {item.mode}</h3><dl className="eval-metrics"><dt>Expected</dt><dd>{item.expected}</dd><dt>Observed</dt><dd>{item.actual}</dd><dt>User impact</dt><dd>{item.impact}</dd><dt>Handling</dt><dd>{item.handling}</dd></dl>
    </article>)}</div></section>
    <section className="rr-card"><h2>Reproduce and inspect</h2><p>Run the offline runner under <code>evals/referral-review</code> in the repository. The reports include per-case differences, raw synthetic recordings, parser/prompt/checklist versions, source hashes and local timing. Local execution timing is not provider latency; Fake token counters are not billing measurements.</p>
      <p><a href="/evaluation/offline-summary.json" download>Download aggregate report and evidence index (JSON)</a></p>
      <details><summary>Version manifest</summary>{data.reports.map(report => <div key={report.provider} className="rr-fact"><h3>{report.provider}</h3><p>Recorded: {report.created_at}</p><p>Base commit: <code>{report.commit}</code>{report.working_tree_dirty ? " + working changes" : ""}</p><p>Implementation SHA-256: <code>{report.versions.implementation_sha256}</code></p><p>Corpus SHA-256: <code>{report.corpus_sha256}</code></p><p>{report.versions.prompt} · {report.versions.checklist} · {report.versions.parser}</p></div>)}</details>
      <p>Still required: operator annotation review, a separately authorized real evaluation with an independent ledger using global spending reservations, frozen-set quality gates, and at least 20 real latency measurements. The CLI refuses real calls, including when a cost cap is supplied, until that accounting path exists.</p>
      <Link prefetch={false} href="/project#architecture">Read the architecture</Link>
    </section>
  </div></main>;
}
