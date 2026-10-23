import Link from "next/link";

export default function LegacyRetired() {
  return <main className="rr-page"><section className="rr-card">
    <h1>Previous MediTrace features have been retired</h1>
    <p>The diagnosis chat, history and blockchain verification pages are no longer available. Existing records have not been migrated into referral packets.</p>
    <p>The current product reviews supplied referral material and keeps human decisions separate from source evidence. It does not provide a diagnosis.</p>
    <p><Link href="/demo">Explore the synthetic demo</Link> · <Link href="/workspace">Open the referral workspace</Link></p>
  </section></main>;
}
