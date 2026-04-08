import { Outlet, NavLink, useNavigate, useParams } from "react-router-dom";
import { signOut } from "firebase/auth";
import { auth } from "./lib/firebase";

export default function App() {
  const navigate = useNavigate();
  const { projectId } = useParams();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b px-6 py-3 flex items-center justify-between">
        <div className="font-semibold">C2 Intelligence</div>
        <nav className="flex gap-4 text-sm">
          <NavLink to="/projects">Projects</NavLink>
          {projectId && (
            <>
              <NavLink to={`/project/${projectId}/upload`}>Upload</NavLink>
              <NavLink to={`/project/${projectId}/query`}>Query</NavLink>
              <NavLink to={`/project/${projectId}/audit`}>Audit</NavLink>
            </>
          )}
          <button
            type="button"
            onClick={async () => {
              await signOut(auth);
              navigate("/login");
            }}
          >
            Sign out
          </button>
        </nav>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
