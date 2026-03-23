import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import Pipeline from "./pages/Pipeline";
import JobCard from "./pages/JobCard";
import CVScreen from "./pages/CVScreen";
import LetterScreen from "./pages/LetterScreen";
import Dashboard from "./pages/Dashboard";
import api, {
  clearAuth,
  getNetworkActivitySnapshot,
  setBasicAuth,
  setUnauthorizedHandler,
  subscribeNetworkActivity,
  type NetworkActivitySnapshot,
} from "./api/client";

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation();
  const active = location.pathname === to;
  return (
    <Link
      to={to}
      className={`text-sm font-semibold px-3 py-1.5 rounded-full ${
        active
          ? "bg-accent text-white"
          : "text-muted hover:text-text hover:bg-surface-alt"
      }`}
    >
      {children}
    </Link>
  );
}

function App() {
  const [authed, setAuthed] = useState(false);
  const [authError, setAuthError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [networkActivity, setNetworkActivity] = useState<NetworkActivitySnapshot>(
    getNetworkActivitySnapshot()
  );

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthed(false);
      setAuthError("Session expired. Please log in again.");
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeNetworkActivity(setNetworkActivity);
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (!authed || networkActivity.pendingCount === 0) return;
    const t = window.setInterval(() => {
      setNetworkActivity(getNetworkActivitySnapshot());
    }, 250);
    return () => window.clearInterval(t);
  }, [authed, networkActivity.pendingCount]);

  const handleLogin = async (username: string, password: string) => {
    setIsLoggingIn(true);
    setAuthError("");
    setBasicAuth(username, password);
    try {
      await api.get("/health");
      setAuthed(true);
    } catch (err) {
      clearAuth();
      setAuthError("Invalid credentials.");
      setAuthed(false);
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = () => {
    clearAuth();
    setAuthed(false);
  };

  if (!authed) {
    return (
      <div className="app-shell min-h-screen flex items-center justify-center px-6">
        <div className="surface-card w-full max-w-md p-8">
          <div className="mb-6">
            <span className="tag-chip">Secure Workspace</span>
            <h1 className="text-2xl font-bold text-text mt-3">Joe v2</h1>
            <p className="mt-2 text-sm text-muted leading-relaxed">
              Private workspace. Enter the backend credentials to continue.
            </p>
          </div>
          <LoginForm onLogin={handleLogin} loading={isLoggingIn} error={authError} />
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <div className="app-shell">
        <nav className="sticky top-0 z-30 border-b border-border/80 px-6 py-4 flex items-center justify-between bg-surface/95 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="h-9 w-9 rounded-xl bg-accent/12 border border-accent/25 text-accent font-bold grid place-items-center">J</span>
            <div>
              <p className="font-extrabold text-base tracking-tight text-text">Joe v2</p>
              <p className="text-xs text-muted">Application assistant</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <NavLink to="/">Pipeline</NavLink>
            <NavLink to="/dashboard">Dashboard</NavLink>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="text-sm font-medium text-muted hover:text-text"
          >
            Log out
          </button>
        </nav>
        <GlobalProgressBar snapshot={networkActivity} />
        <main className="pb-8">
          <Routes>
            <Route path="/" element={<Pipeline />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/job/:rowNum" element={<JobCard />} />
            <Route path="/job/:rowNum/cv" element={<CVScreen />} />
            <Route path="/job/:rowNum/letter" element={<LetterScreen />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

function formatEta(etaMs: number): string {
  const sec = Math.max(1, Math.ceil(etaMs / 1000));
  if (sec < 60) return `~${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `~${m}m ${String(s).padStart(2, "0")}s`;
}

function GlobalProgressBar({ snapshot }: { snapshot: NetworkActivitySnapshot }) {
  if (!snapshot.visible) return null;
  const pct = Math.max(5, Math.min(97, Math.round(snapshot.progress * 100)));
  return (
    <div className="px-6 pt-2">
      <div className="surface-card px-4 py-2">
        <div className="flex items-center justify-between text-xs text-muted mb-2">
          <span>{snapshot.label}</span>
          <span>
            ETA {formatEta(snapshot.etaMs)}
            {snapshot.pendingCount > 1 ? ` • ${snapshot.pendingCount} in progress` : ""}
          </span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-surface-alt overflow-hidden">
          <div
            className="h-full bg-accent transition-all duration-300 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

type LoginFormProps = {
  onLogin: (username: string, password: string) => void;
  loading: boolean;
  error: string;
};

function LoginForm({ onLogin, loading, error }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const canSubmit = username.trim().length > 0 && password.trim().length > 0 && !loading;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    onLogin(username.trim(), password);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-muted">Username</label>
        <input
          type="text"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          className="mt-2 w-full rounded-xl border border-border bg-input px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
          placeholder="joe_admin"
          autoComplete="username"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-muted">Password</label>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="mt-2 w-full rounded-xl border border-border bg-input px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
          placeholder="••••••••"
          autoComplete="current-password"
        />
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
      >
        {loading ? "Checking..." : "Log in"}
      </button>
    </form>
  );
}

export default App;
