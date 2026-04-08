import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";

interface AuditEntry {
  log_id: string;
  session_id: string | null;
  user_email: string | null;
  action: string;
  domain: string | null;
  query_text: string | null;
  chunks_retrieved: number | null;
  model_used: string | null;
  latency_ms: number | null;
  logged_at: string;
}

export default function Audit() {
  const { projectId } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["audit", projectId],
    queryFn: async () =>
      (await api.get<{ entries: AuditEntry[] }>(`/api/v1/audit/${projectId}`)).data,
    enabled: !!projectId,
  });

  function exportCsv() {
    if (!data?.entries.length) return;
    const headers = Object.keys(data.entries[0]);
    const csv = [
      headers.join(","),
      ...data.entries.map((e) =>
        headers
          .map((h) => {
            const v = (e as Record<string, unknown>)[h];
            const s = v == null ? "" : String(v).replace(/"/g, '""');
            return `"${s}"`;
          })
          .join(","),
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-${projectId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (isLoading) return <div>Loading audit…</div>;
  if (error) return <div className="text-red-600">Failed to load audit log.</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Audit</h1>
        <button type="button" className="border rounded px-3 py-1 text-sm" onClick={exportCsv}>
          Export CSV
        </button>
      </div>
      <table className="w-full text-sm border">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left p-2">Time</th>
            <th className="text-left p-2">User</th>
            <th className="text-left p-2">Action</th>
            <th className="text-left p-2">Domain</th>
            <th className="text-left p-2">Query</th>
            <th className="text-right p-2">Chunks</th>
            <th className="text-right p-2">Latency (ms)</th>
          </tr>
        </thead>
        <tbody>
          {data?.entries.map((e) => (
            <tr key={e.log_id} className="border-t">
              <td className="p-2 whitespace-nowrap">{e.logged_at}</td>
              <td className="p-2">{e.user_email}</td>
              <td className="p-2">{e.action}</td>
              <td className="p-2">{e.domain}</td>
              <td className="p-2">{e.query_text}</td>
              <td className="p-2 text-right">{e.chunks_retrieved}</td>
              <td className="p-2 text-right">{e.latency_ms}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
