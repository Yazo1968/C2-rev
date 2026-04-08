import { signInWithPopup } from "firebase/auth";
import { useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { auth, googleProvider } from "../lib/firebase";
import { useFirebaseUser } from "../lib/auth";

export default function Login() {
  const navigate = useNavigate();
  const { user, loading } = useFirebaseUser();

  useEffect(() => {
    if (!loading && user) navigate("/projects", { replace: true });
  }, [user, loading, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="border rounded p-8 w-96 space-y-4">
        <h1 className="text-xl font-semibold">C2 Intelligence</h1>
        <p className="text-sm text-gray-600">Sign in with your Google account.</p>
        <button
          type="button"
          className="w-full border rounded py-2"
          onClick={async () => {
            await signInWithPopup(auth, googleProvider);
            navigate("/projects", { replace: true });
          }}
        >
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
