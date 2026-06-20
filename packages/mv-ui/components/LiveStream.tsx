"use client";

import { useStream } from "@/lib/stream";

/** Mounts the real-time stream subscription for the whole app (renders nothing). */
export function LiveStream() {
  useStream();
  return null;
}
