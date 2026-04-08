import { useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Citation, streamQuery } from "../lib/api";

interface Turn {
  role: "user" | "assistant";
  content: string;
  domain?: string;
  citations?: Citation[];
  cannotAssess?: boolean;
}

export default function Query() {
  const { projectId } = useParams();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const abortRef = useRef<AbortController | null>(null);

  async function send() {
    if (!input.trim() || !projectId) return;
    const userTurn: Turn = { role: "user", content: input };
    const assistantTurn: Turn = { role: "assistant", content: "", citations: [] };
    setTurns((prev) => [...prev, userTurn, assistantTurn]);
    setInput("");
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamQuery(
        { project_id: projectId, query: userTurn.content, session_id: sessionId },
        {
          onMeta: (meta) => {
            setSessionId(meta.session_id);
            setTurns((prev) => {
              const next = [...prev];
              next[next.length - 1] = {
                ...next[next.length - 1],
                domain: meta.domain,
                citations: meta.citations,
              };
              return next;
            });
          },
          onToken: (delta) => {
            setTurns((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              const content = last.content + delta;
              next[next.length - 1] = {
                ...last,
                content,
                cannotAssess: content.includes("CANNOT ASSESS"),
              };
              return next;
            });
          },
          onDone: () => setStreaming(false),
          onError: (msg) => {
            setStreaming(false);
            setTurns((prev) => {
              const next = [...prev];
              next[next.length - 1] = { ...next[next.length - 1], content: `Error: ${msg}` };
              return next;
            });
          },
        },
        controller.signal,
      );
    } catch {
      setStreaming(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <h1 className="text-xl font-semibold">Query</h1>
      <div className="space-y-4">
        {turns.map((turn, idx) => (
          <TurnView key={idx} turn={turn} />
        ))}
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2"
          placeholder="Ask a question grounded in this project's documents…"
          value={input}
          disabled={streaming}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button type="button" className="border rounded px-4 py-2" onClick={send} disabled={streaming}>
          {streaming ? "Streaming…" : "Send"}
        </button>
      </div>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  if (turn.role === "user") {
    return (
      <div className="border rounded p-3 bg-gray-50">
        <div className="text-xs text-gray-500 mb-1">You</div>
        {turn.content}
      </div>
    );
  }
  return (
    <div className="border rounded p-3">
      <div className="text-xs text-gray-500 mb-1 flex items-center gap-2">
        <span>Assistant</span>
        {turn.domain && <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-700">{turn.domain}</span>}
      </div>
      {turn.cannotAssess ? (
        <div className="border-l-4 border-red-600 bg-red-50 p-2 whitespace-pre-wrap text-red-900">
          {turn.content}
        </div>
      ) : (
        <div className="whitespace-pre-wrap">{turn.content}</div>
      )}
      {turn.citations && turn.citations.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer">Citations ({turn.citations.length})</summary>
          <ul className="mt-2 space-y-1">
            {turn.citations.map((c) => (
              <li key={c.chunk_id} className="border rounded p-2">
                <div className="font-medium">{c.file_name}</div>
                <div className="text-xs text-gray-600">
                  Layer {c.layer} · Page {c.page_number ?? "?"}
                  {c.section_ref ? ` · Clause ${c.section_ref}` : ""}
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
