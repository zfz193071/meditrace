"use client";

import { useEffect, useState } from "react";
import { workspaceApi as api, errorMessage } from "../../lib/referral-api/workspace";
import type { components } from "../../lib/referral-api/generated";
import { safeBillingReturn } from "./BillingPanel";

type Order = components["schemas"]["OrderResponse"];
export default function PaymentReturn({ orderId }: { orderId: string }) {
  return <OrderStatus key={orderId} orderId={orderId} />;
}

function OrderStatus({ orderId }: { orderId: string }) {
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");
  const [cycle, setCycle] = useState(0);
  const [waiting, setWaiting] = useState(true);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let count = 0;
    async function poll() {
      try {
        const saved = await api.order(orderId);
        if (stopped) return;
        setOrder(saved); setError("");
        if (saved.state === "pending" && ++count < 10) timer = setTimeout(poll, 3000);
        else setWaiting(false);
      } catch (e) { if (!stopped) { setOrder(null); setError(errorMessage(e)); setWaiting(false); } }
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [orderId, cycle]);
  return <main lang="en" className="min-h-screen bg-slate-950 p-8 text-slate-100">
    <section className="mx-auto max-w-xl space-y-5">
      <h1 className="text-2xl font-semibold">Test payment status</h1>
      <p>Test payment — no real charge. This page only reads the server order; returning here does not activate membership or start AI.</p>
      {error && <p role="alert">{error}</p>}
      {order && <p role="status">Server order: {order.state}</p>}
      {order?.state === "pending" && <p>Payment has not been confirmed. If you cancelled or payment is delayed, your saved materials remain available. Do not pay again while this order is pending.</p>}
      {order?.state === "paid" && <p>Payment was verified. Check your account for current membership and credits.</p>}
      {order && ["refunded", "revoked", "expired", "failed"].includes(order.state) && <p>This order does not grant active membership. Saved material and manual review are unaffected.</p>}
      {waiting ? <p>Checking server status…</p> : <button className="rounded border px-4 py-2" onClick={() => { setOrder(null); setError(""); setWaiting(true); setCycle(c => c + 1); }}>Refresh order status</button>}
      {order && <a className="block underline" href={safeBillingReturn(order.return_path)}>Return to saved work</a>}
      <a className="block underline" href="/account">Account / sign in</a>
      {error && <a className="block underline" href={`/api/v1/auth/github/start?return_path=${encodeURIComponent(`/account/payment?order=${orderId}`)}`}>Sign in and return to this order</a>}
    </section>
  </main>;
}
