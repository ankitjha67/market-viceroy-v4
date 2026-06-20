/** The Operator token, held in session memory only — never in code, never
 * persisted to disk. Used to authorize the kill-switch (the UI's only write). */

const KEY = "mv-operator-token";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(KEY) ?? "";
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(KEY, token);
}
