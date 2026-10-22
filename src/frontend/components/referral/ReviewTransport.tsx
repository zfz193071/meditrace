"use client";
import { createContext, useContext } from "react";
import { workspaceApi } from "../../lib/referral-api/workspace";
import { originalDocumentUrl } from "../../lib/referral-api/evidence";
import { handoffDownloadUrl } from "../../lib/referral-api/handoff";

export type ReviewTransport = Pick<typeof workspaceApi, "run" | "reviewState" | "page" | "resolve" | "confirm" | "history" | "handoff"> & {
  originalUrl: typeof originalDocumentUrl;
  snapshotUrl: typeof handoffDownloadUrl | null;
};
const context = createContext<ReviewTransport>({ ...workspaceApi, originalUrl: originalDocumentUrl, snapshotUrl: handoffDownloadUrl });
export const ReviewTransportProvider = context.Provider;
export const useReviewTransport = () => useContext(context);
