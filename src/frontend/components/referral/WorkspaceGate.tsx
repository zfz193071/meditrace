"use client";
import { Fragment, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { workspaceApi as api, WorkspaceError, errorMessage, type Session, type Capabilities } from "../../lib/referral-api/workspace";

export type Access = { csrf: string; capabilities: Capabilities; onError: (error: unknown) => void };
function validSession(session: Session | null) {
  return Boolean(session?.user && session.csrf_token && session.expires_at && Date.parse(session.expires_at) > Date.now());
}
export function WorkspaceGate({ packetId, children }: { packetId?: string; children: (access: Access) => ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const verifiedSession = useRef<Session | null>(null);
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [error, setError] = useState("");
  const [unavailable, setUnavailable] = useState(false);
  const version = useRef(0);
  const invalidate = useCallback(() => { ++version.current; }, []);
  const clearSession = useCallback(() => {
    verifiedSession.current = null; setSession(null); setCaps(null);
  }, []);
  const refresh = useCallback(async () => {
    const current = ++version.current;
    try {
      const next = await api.session();
      if (current !== version.current) return;
      if (next.user && !validSession(next)) {
        clearSession(); setError(errorMessage(new WorkspaceError("AUTH_REQUIRED", 401))); return;
      }
      // Apply identity before reading capabilities; an unavailable service must not
      // keep another account's editor or delay a verified sign-out.
      if (next.user?.id !== verifiedSession.current?.user?.id) setCaps(null);
      verifiedSession.current = next; setSession(next);
      if (!next.user) { setCaps(null); setError(""); setUnavailable(false); return; }
      const capabilities = await api.capabilities();
      if (current !== version.current) return;
      setCaps(capabilities); setError(""); setUnavailable(false);
    } catch (e) {
      if (current !== version.current) return;
      setError(errorMessage(e));
      const denied = e instanceof WorkspaceError && (e.status === 401 || e.status === 403);
      if (denied || !validSession(verifiedSession.current)) clearSession();
    }
  }, [clearSession]);
  const onError = useCallback((e: unknown) => {
    if (e instanceof WorkspaceError && e.status === 404 && packetId) {
      ++version.current; setUnavailable(true); setError(e.message);
    }
    if (e instanceof WorkspaceError && (e.status === 401 || e.status === 403)) {
      ++version.current; clearSession(); setError(e.message);
    }
  }, [packetId, clearSession]);
  useEffect(() => {
    void refresh();
    const visible = () => { if (document.visibilityState === "visible") void refresh(); };
    window.addEventListener("focus", visible); document.addEventListener("visibilitychange", visible);
    return () => { invalidate(); window.removeEventListener("focus", visible); document.removeEventListener("visibilitychange", visible); };
  }, [refresh, invalidate]);
  useEffect(() => {
    if (!session?.user || !session.expires_at) return;
    const expiresAt = Date.parse(session.expires_at);
    const timer = setTimeout(() => {
      if (expiresAt <= Date.now()) {
        clearSession(); setError(errorMessage(new WorkspaceError("AUTH_REQUIRED", 401)));
      }
      void refresh();
    }, Math.max(0, Math.min(expiresAt - Date.now(), 2_147_483_647)));
    return () => clearTimeout(timer);
  }, [session, refresh, clearSession]);
  const returnPath = packetId ? `/workspace/packets/${packetId}` : "/workspace";
  return <main lang="en" className="rr-workspace"><div className="rr-shell">
    <header className="rr-topbar"><a href="/workspace">MediTrace <span>Referral Review</span></a><a href="/account">Account</a></header>
    <p className="rr-notice">Synthetic data only. Materials expire 7 days after packet creation.</p>
    {error && <div role="alert" className="rr-alert"><p>{error}</p><button onClick={refresh}>Retry session check</button></div>}
    {!session && !error && <p role="status">Checking your session…</p>}
    {session && !session.user && <section className="rr-card"><h1>Sign in to your private workspace</h1>
      <p>Your saved packets and selection drafts are restored after sign-in. Unsaved text is not stored in this browser.</p>
      {session.login_available ? <a className="rr-button" href={`/api/v1/auth/github/start?return_path=${encodeURIComponent(returnPath)}`}>Continue with GitHub</a> : <p>Sign-in is unavailable. Please try again later.</p>}
    </section>}
    {!unavailable && session?.user && caps && session.csrf_token && <Fragment key={session.user.id}>
      <p className="rr-muted">Signed in as {session.user.display_name}</p>
      {!caps.workspace_available ? <section className="rr-card"><h1>Workspace unavailable</h1><p>The private workspace is not configured. No files can be uploaded yet.</p><button onClick={refresh}>Check again</button></section>
        : children({ csrf: session.csrf_token, capabilities: caps, onError })}
    </Fragment>}
    {!unavailable && session?.user && !caps && <p role="status">{error ? "Workspace availability could not be verified. Retry the session check." : "Checking workspace availability…"}</p>}
    {!session && error && <a href={`/login?return_path=${encodeURIComponent(returnPath)}`}>Sign in again</a>}
  </div></main>;
}

export function useUnsavedChanges(dirty: boolean) {
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
}
export function expiryLabel(value: string) {
  const hours = Math.max(0, Math.ceil((Date.parse(value) - Date.now()) / 3_600_000));
  return hours === 0 ? "Expired" : `${hours < 24 ? `${hours} hours` : `${Math.ceil(hours / 24)} days`} remaining`;
}
