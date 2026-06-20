"use client";

import { useEffect } from "react";
import { mutate } from "swr";

const WS_URL =
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/^http/, "ws") +
  "/ws/stream";

/**
 * Subscribe to the real-time stream (Phase 9). On each event we revalidate every
 * SWR key so the screens update immediately. If the socket can't open or drops,
 * this is a silent no-op — the screens keep polling, so the stream is purely an
 * optimization, never the only path to the data.
 */
export function useStream(): void {
  useEffect(() => {
    if (typeof WebSocket === "undefined") return;
    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(WS_URL);
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
