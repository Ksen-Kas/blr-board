import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import Pipeline from "./pages/Pipeline";
import JobCard from "./pages/JobCard";
import CVScreen from "./pages/CVScreen";
import LetterScreen from "./pages/LetterScreen";
import Dashboard from "./pages/Dashboard";
import api, { clearAuth, setBasicAuth, setUnauthorizedHandler } from "./api/client";

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation();
  const active = location.pathname === to;
  return (
    <Link
      to={to}
      className={`text-sm font-medium px-3 py-1.5 rounded-lg ${
        active
          ? "bg-accent/15 text-accent"
          : "text-muted hover:text-text"
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

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthed(false);
      setAuthError("Session expired. Please log in again.");
    });
    return () => setUnauthorizedHandler(null);
  }, []);

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
      <div className="min-h-screen bg-bg flex items-center justify-center px-6">
        <div className="w-full max-w-md rounded-2xl border border-border bg-surface p-8">
          <div className="mb-6">
            <h1 className="text-2xl font-semibold text-text">Joe v2</h1>
            <p className="mt-2 text-sm text-muted">
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
      <nav className="border-b border-border px-8 py-3 flex items-center justify-between bg-surface">
        <span className="font-bold text-lg text-text">Joe v2</span>
        <div className="flex items-center gap-2">
          <NavLink to="/">Pipeline</NavLink>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <button
            type="button"
            onClick={handleLogout}
            className="text-sm text-muted hover:text-text ml-4"
          >
            Log out
          </button>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<Pipeline />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/job/:rowNum" element={<JobCard />} />
        <Route path="/job/:rowNum/cv" element={<CVScreen />} />
        <Route path="/job/:rowNum/letter" element={<LetterScreen />} />
      </Routes>
    </BrowserRouter>
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
          className="mt-2 w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
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
          className="mt-2 w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-text focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
          placeholder="••••••••"
          autoComplete="current-password"
        />
      </div>
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-bg hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
      >
        {loading ? "Checking..." : "Log in"}
      </button>
    </form>
  );
}

export default App;
