import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

interface Project {
  project_id: string;
  project_name: string;
  client_name: string | null;
  contract_type: string | null;
  jurisdiction: string | null;
}

export default function Projects() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => (await api.get<{ projects: Project[] }>("/api/v1/projects")).data,
  });

  if (isLoading) return <div>Loading projects…</div>;
  if (error) return <div className="text-red-600">Failed to load projects.</div>;

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Projects</h1>
      <ul className="space-y-2">
        {data?.projects.map((p) => (
          <li key={p.project_id} className="border rounded p-3 flex items-center justify-between">
            <div>
              <div className="font-medium">{p.project_name}</div>
              <div className="text-xs text-gray-600">
                {p.client_name} · {p.contract_type} · {p.jurisdiction}
              </div>
            </div>
            <div className="flex gap-2 text-sm">
              <Link to={`/project/${p.project_id}/query`} className="underline">Query</Link>
              <Link to={`/project/${p.project_id}/upload`} className="underline">Upload</Link>
              <Link to={`/project/${p.project_id}/audit`} className="underline">Audit</Link>
            </div>
          </li>
        ))}
        {data?.projects.length === 0 && (
          <li className="text-gray-600">No projects accessible to your account.</li>
        )}
      </ul>
    </div>
  );
}
