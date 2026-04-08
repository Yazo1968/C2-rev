// Thin axios wrapper plus an SSE helper for /api/v1/query.
// SSE: we use @microsoft/fetch-event-source so we can attach an
// Authorization header (the browser's native EventSource cannot).
import axios from "axios";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { auth } from "./firebase";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function authHeader(): Promise<Record<string, string>> {
  const token = await auth.currentUser?.getIdToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use(async (config) => {
  const headers = await authHeader();
  Object.assign(config.headers, headers);
  return config;
});

export interface Citation {
  chunk_id: string;
  file_name: string | null;
  page_number: number | null;
  section_ref: string | null;
  layer: string | null;
  document_id: string | null;
  distance: number | null;
}

export interface QueryStreamCallbacks {
  onMeta: (meta: { session_id: string; domain: string; domains: string[]; citations: Citation[]; model: string }) => void;
  onToken: (delta: string) => void;
  onDone: (final: { latency_ms: number }) => void;
  onError: (msg: string) => void;
}

export async function streamQuery(
  body: { project_id: string; query: string; session_id?: string; layer_filter?: string; top_k?: number },
  callbacks: QueryStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
    ...(await authHeader()),
  };
  await fetchEventSource(`${API_BASE}/api/v1/query`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
    onmessage(ev) {
      switch (ev.event) {
        case "meta":
          callbacks.onMeta(JSON.parse(ev.data));
          break;
        case "token":
          callbacks.onToken(ev.data);
          break;
        case "done":
          callbacks.onDone(JSON.parse(ev.data));
          break;
        case "error":
          callbacks.onError(ev.data);
          break;
      }
    },
    onerror(err) {
      callbacks.onError(String(err));
      throw err; // stop reconnect attempts
    },
  });
}
