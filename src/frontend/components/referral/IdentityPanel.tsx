"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import BillingPanel from "./BillingPanel";
import AccountDeletion from "./AccountDeletion";
import Link from "next/link";
import { getSession, signOut, type Session } from "../../lib/referral-api";

export default function IdentityPanel({ workspace = false, returnPath = "/workspace", loginError = "", billingReturnPath }: {
  workspace?: boolean; returnPath?: string; loginError?: string; billingReturnPath?: string;
}) {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const [busy, setBusy] = useState(false);
  const [logoutError, setLogoutError] = useState(false);
  const [expired, setExpired] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const requestVersion = useRef(0);
  const inFlight = useRef<AbortController | null>(null);
  const wasSignedIn = useRef(false);
  const signingOut = useRef(false);
  const refresh = useCallback(async () => {
    if (signingOut.current) return;
    const version = ++requestVersion.current;
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    try {
      const next = await getSession(controller.signal);
      if (controller.signal.aborted || version !== requestVersion.current) return;
      setExpired(wasSignedIn.current && !next.user);
      wasSignedIn.current = Boolean(next.user);
      setSession(next);
      setError(false);
    } catch {
      if (!controller.signal.aborted && version === requestVersion.current) {
        setSession(null);
        setError(true);
      }
    }
  }, []);
  useEffect(() => {
    void refresh();
    const onVisible = () => { if (document.visibilityState === "visible") void refresh(); };
    const onFocus = () => { void refresh(); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      inFlight.current?.abort();
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);
  useEffect(() => {
    if (!session?.expires_at) return;
    const remaining = Date.parse(session.expires_at) - Date.now();
    const timer = setTimeout(() => { void refresh(); }, Math.max(0, Math.min(remaining, 2_147_483_647)));
    return () => clearTimeout(timer);
  }, [session?.expires_at, refresh]);
  async function logout() {
    if (!session?.csrf_token || busy) return;
    signingOut.current = true;
    ++requestVersion.current;
    inFlight.current?.abort();
    setBusy(true);
    setLogoutError(false);
    try {
      await signOut(session.csrf_token);
      setSession({ user: null, csrf_token: null, expires_at: null, login_available: true });
      wasSignedIn.current = false;
      setExpired(false);
      setSignedOut(true);
    } catch {
      setLogoutError(true);
    } finally {
      signingOut.current = false;
      setBusy(false);
    }
  }
  const safePath = returnPath === "/account" || returnPath === "/workspace" ||
    /^\/workspace\/packets\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(returnPath)
    ? returnPath : "/workspace";
  return (
    <main lang="en" className="min-h-screen bg-slate-950 px-6 py-16 text-slate-100">
      <section className="mx-auto max-w-xl space-y-6 rounded-2xl border border-slate-700 p-8">
        <p className="text-sm text-teal-300">MediTrace · Referral Review</p>
        <h1 className="text-2xl font-semibold">{session?.user ? (workspace ? "Private workspace" : "Your account") :
          (workspace ? "Sign in to your private workspace" : "Sign in")}</h1>
        <p>Synthetic data only. Signing in does not authorize a payment or a model request.</p>
        {!session && !error && <p role="status">Checking session…</p>}
        {error && <p role="alert">Sign-in service is unavailable. Please try again later.</p>}
        {(loginError === "oauth_failed" || loginError === "service_unavailable") &&
          <p role="alert">Sign-in did not complete. Please start again; no new session was created.</p>}
        {expired && <p role="alert">Your session ended. Sign in again to continue.</p>}
        {signedOut && <p role="status">You have signed out.</p>}
        {deleted && <p role="status">Account access has ended. Content cleanup is queued; physical deletion is not yet confirmed.</p>}
        {logoutError && <p role="alert">Sign-out could not be confirmed. Please retry.</p>}
        {session?.user && <>
          {billingReturnPath && session.csrf_token && <BillingPanel key={session.user.id} csrf={session.csrf_token} returnPath={billingReturnPath} />}
          <p>Signed in as {session.user.display_name}</p>
          <p><a href="/workspace" className="text-teal-300 underline">Open your referral workspace</a></p>
          <button disabled={busy} onClick={logout} className="rounded border border-teal-300 px-5 py-3 disabled:opacity-50">
            {busy ? "Signing out…" : "Sign out"}
          </button>
          {returnPath === "/account" && session.csrf_token && <AccountDeletion csrf={session.csrf_token} onDeleted={() => {
            ++requestVersion.current; inFlight.current?.abort(); wasSignedIn.current = false;
            setSession({ user: null, csrf_token: null, expires_at: null, login_available: true });
            setExpired(false); setDeleted(true);
          }} />}
        </>}
        {session?.login_available && !session.user && <a className="inline-block rounded bg-teal-300 px-5 py-3 text-slate-950 focus-visible:outline focus-visible:outline-2"
          href={`/api/v1/auth/github/start?return_path=${encodeURIComponent(safePath)}`}>Continue with GitHub</a>}
        {session && !session.login_available && <p role="status">Sign-in is not configured yet.</p>}
        <p><Link href="/" className="text-teal-300 underline">Back to public site</Link></p>
      </section>
    </main>
  );
}
