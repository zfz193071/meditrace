import type { components } from "./generated";

export type Capabilities = components["schemas"]["Capabilities"];
export type Readiness = components["schemas"]["ReadinessResponse"];
export type ApiError = components["schemas"]["ErrorEnvelope"];
export type ReviewResult = components["schemas"]["ReviewResult"];
export type Session = components["schemas"]["SessionResponse"];

// Referral endpoints always use the same origin; runtime secrets never enter this module.
export const REFERRAL_API_PREFIX = "/api/v1";

export async function getCapabilities(signal?: AbortSignal): Promise<Capabilities> {
  const response = await fetch(`${REFERRAL_API_PREFIX}/capabilities`, {
    credentials: "same-origin",
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    // Do not echo arbitrary server/proxy response bodies into the UI or console.
    throw new Error("Referral service is unavailable.");
  }
  return response.json();
}

export async function getSession(signal?: AbortSignal): Promise<Session> {
  const response = await fetch(`${REFERRAL_API_PREFIX}/auth/session`, {
    credentials: "same-origin", cache: "no-store", signal,
  });
  if (!response.ok) throw new Error("Sign-in service is unavailable.");
  return response.json();
}

export async function signOut(csrfToken: string): Promise<void> {
  const response = await fetch(`${REFERRAL_API_PREFIX}/auth/logout`, {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "X-CSRF-Token": csrfToken },
  });
  // An expired/revoked session is already signed out.
  if (!response.ok && response.status !== 401) throw new Error("Sign-out could not be confirmed.");
}
