"use client";

import { useEffect } from "react";
import { mutate } from "swr";
import { getToken } from "./token";

const WS_BASE =
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/^http/, "ws") +
  "/ws/stream";

/**
 * Subscribe to the real-time stream (Phase 9). On each event we revalidate every
 * SWR key so the screens update immediately. The stream is Operator-authed, so we
 * only connect once a token is present (entered for the kill-switch) and pass it
 * as a query param. If there is no token, or the socket can't open or drops, this
 * is a silent no-op — the screens keep polling, so the stream is purely an
 * optimization, never the only path to the data.
 */
export function useStream(): void {
  useEffect(() => {
    if (typeof WebSocket === "undefined") return;
    const token = getToken();
    if (!token) return; // unauthenticated -> rely on REST polling
    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(`${WS_BASE}?token=${encodeURIComponent(token)}`);
      socket.onmessage = () => {
        void mutate(() => true);
      };
      socket.onerror = () => {
        /* polling continues */
      };
    } catch {
      /* polling continues */
    }
    return () => socket?.close();
  }, []);
}
