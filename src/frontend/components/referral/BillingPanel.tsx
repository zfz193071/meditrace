"use client";

import { useEffect, useRef, useState } from "react";
import { workspaceApi as api, errorMessage, operationKey, type Membership } from "../../lib/referral-api/workspace";
import type { components } from "../../lib/referral-api/generated";

type Order = components["schemas"]["OrderResponse"];
export function safeBillingReturn(value: string) {
  return value === "/workspace" || value === "/account" || /^\/workspace\/packets\/[0-9a-f-]{36}$/.test(value) ? value : "/account";
}
export function safeCheckout(value: string) {
  try { const url = new URL(value); return url.protocol === "https:" && url.hostname === "checkout.stripe.com" && !url.username && !url.password && !url.port; }
  catch { return false; }
}

export default function BillingPanel({ csrf, returnPath = "/account" }: { csrf: string; returnPath?: string }) {
  const [member, setMember] = useState<Membership | null>(null);
  const [available, setAvailable] = useState(false);
  const [error, setError] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [busy, setBusy] = useState(false);
  const key = useRef<string | null>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    let stopped = false;
    Promise.all([api.membership(), api.capabilities()]).then(([m, caps]) => {
      if (!stopped) { setMember(m); setAvailable(caps.payments_available); }
    }).catch(e => { if (!stopped) setError(errorMessage(e)); });
    return () => { stopped = true; };
  }, []);
  const active = !!member?.valid_until && Date.parse(member.valid_until) > Date.now();
  async function buy() {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError("");
    key.current ??= operationKey();
    try { setOrder(await api.checkout(safeBillingReturn(returnPath), csrf, key.current)); }
    catch (e) { setError(errorMessage(e)); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <section aria-label="Test membership" className="space-y-4 border-t border-slate-600 pt-6">
    <h2 className="text-xl font-semibold">Test membership</h2>
    <p>Test payment — no real charge. 30 days, 20 simulated checks. No automatic renewal.</p>
    <p>Public test purchases do not grant real AI access. Manual review and export remain available after membership expires.</p>
    {member && <p>{active ? `Active until ${new Date(member.valid_until!).toISOString().slice(0, 10)}. ${member.remaining} credits remaining; ${member.reserved} reserved.` : "No active test membership."}</p>}
    {error && <p role="alert">{error}</p>}
    {!available && <p>Test checkout is unavailable.</p>}
    <button className="rounded border px-4 py-2 disabled:opacity-50" disabled={busy || !available || !member || active || !!order} onClick={buy}>
      {busy ? "Preparing test checkout…" : "Prepare test checkout"}
    </button>
    {order && <div className="space-y-2">
      <p>Server order: {order.state}. Test amount: {new Intl.NumberFormat("en", { style: "currency", currency: order.currency }).format(order.amount / 10 ** (new Intl.NumberFormat("en", { style: "currency", currency: order.currency }).resolvedOptions().maximumFractionDigits ?? 2))}.</p>
      {order.checkout_url && safeCheckout(order.checkout_url) && <a className="block underline" href={order.checkout_url}>Continue to Stripe test checkout</a>}
      <a className="block underline" href={`/account/payment?order=${order.id}`}>Check this order</a>
    </div>}
    <p><a className="underline" href={safeBillingReturn(returnPath)}>Return to saved workspace or account</a>. Saved drafts are retained; no check starts after payment.</p>
  </section>;
}
