import type { components } from "./generated";

export type Capabilities = components["schemas"]["Capabilities"];
export type Readiness = components["schemas"]["ReadinessResponse"];
export type ApiError = components["schemas"]["ErrorEnvelope"];
export type ReviewResult = components["schemas"]["ReviewResult"];

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
