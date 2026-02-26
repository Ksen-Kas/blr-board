import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { getJobs, evaluateJD, refreshCache } from "../api/jobs";
import { JOB_STATUSES } from "../constants/statuses";
import type { Job } from "../types/job";

function statusIndex(s: string) {
  const idx = JOB_STATUSES.findIndex(
    (v) => v.toLowerCase() === s.toLowerCase()
  );
  return idx >= 0 ? idx : JOB_STATUSES.length;
}

/** Fit badge color per spec: Strong=green, Stretch=light-green, flags=yellow/red */
function fitColor(roleFit: string, stopFlags: string) {
  const hasFlags = !!stopFlags;
  const fit = roleFit.toLowerCase();
  if (hasFlags) {
    // Stop flags (visa, citizenship) or strong_mismatch → red; warnings → yellow
    const flags = stopFlags.toLowerCase();
    if (flags.includes("visa") || flags.includes("citizenship") || flags.includes("strong_mismatch"))
      return "text-red-500";
    return "text-yellow-500";
  }
  if (fit === "strong") return "text-green-500";
  if (fit === "stretch" || fit === "partial") return "text-emerald-300";
  return "text-gray-400";
}

/** Days since applied */
function daysSince(dateStr: string): number | null {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return null;
    return Math.floor((Date.now() - d.getTime()) / 86400000);
  } catch {
    return null;
  }
}

type SortKey = "status" | "company" | "region" | "days";
type SortDir = "asc" | "desc";

export default function Pipeline() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [letterPopup, setLetterPopup] = useState<Job | null>(null);
  const [statusFilter, setStatusFilter] = useState("All");
  const [sortKey, setSortKey] = useState<SortKey>("status");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const navigate = useNavigate();

  const loadJobs = () => {
    setLoading(true);
    getJobs()
      .then(setJobs)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sortIndicator = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : "";

  // Filter
  const filtered =
    statusFilter === "All"
      ? jobs
      : jobs.filter((j) => j.status.toLowerCase() === statusFilter.toLowerCase());

  // Sort
  const sorted = [...filtered].sort((a, b) => {
    const dir = sortDir === "asc" ? 1 : -1;
    if (sortKey === "status") return (statusIndex(a.status) - statusIndex(b.status)) * dir;
    if (sortKey === "company") return a.company.localeCompare(b.company) * dir;
    if (sortKey === "region") return a.region.localeCompare(b.region) * dir;
    if (sortKey === "days") {
      const da = daysSince(a.applied_date) ?? 9999;
      const db = daysSince(b.applied_date) ?? 9999;
      return (da - db) * dir;
    }
    return 0;
  });

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Pipeline</h1>
        <div className="flex gap-2 items-center">
          <button
            onClick={() => {
              refreshCache();
              loadJobs();
            }}
            className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 cursor-pointer"
          >
            Refresh
          </button>
          <span className="px-3 py-1.5 text-sm text-gray-500">
            {filtered.length} jobs
          </span>
        </div>
      </div>

      <AddJobBar onAdded={loadJobs} />

      {loading ? (
        <div className="text-gray-500 py-8 text-center">Loading...</div>
      ) : (
        <div className="overflow-x-auto border rounded-lg">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left bg-gray-50 text-gray-600">
                <th className="px-3 py-2.5 font-medium w-8">#</th>
                <th
                  className="px-3 py-2.5 font-medium cursor-pointer hover:text-gray-900 select-none"
                  onClick={() => handleSort("company")}
                >
                  Company{sortIndicator("company")}
                </th>
                <th className="px-3 py-2.5 font-medium">Role</th>
                <th
                  className="px-3 py-2.5 font-medium cursor-pointer hover:text-gray-900 select-none"
                  onClick={() => handleSort("region")}
                >
                  Region{sortIndicator("region")}
                </th>
                <th className="px-3 py-2.5 font-medium w-28">Fit</th>
                <th className="px-3 py-2.5 font-medium w-32">
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="font-medium text-gray-600 bg-transparent border-none outline-none cursor-pointer text-sm p-0"
                  >
                    <option value="All">Status ▼</option>
                    {JOB_STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </th>
                <th className="px-3 py-2.5 font-medium w-24">Applied</th>
                <th
                  className="px-3 py-2.5 font-medium w-16 cursor-pointer hover:text-gray-900 select-none"
                  onClick={() => handleSort("days")}
                >
                  Days{sortIndicator("days")}
                </th>
                <th className="px-3 py-2.5 font-medium w-16">DTR</th>
                <th className="px-3 py-2.5 font-medium w-48">CL</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((job) => {
                const days = daysSince(job.applied_date);

                return (
                  <tr
                    key={job.row_num}
                    className="border-t cursor-pointer hover:bg-blue-50/50 transition-colors"
                    onClick={() => navigate(`/job/${job.row_num}`)}
                  >
                    <td className="px-3 py-2 text-gray-400">
                      {job.row_num}
                      {job.possible_duplicate && (
                        <span className="ml-1 cursor-help" title={`Duplicate of: ${job.duplicate_of}`}>🔁</span>
                      )}
                      {job.needs_followup && (
                        <span className="ml-1" title="Needs follow-up">🔔</span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-medium">{job.company}</td>
                    <td className="px-3 py-2">{job.role}</td>
                    <td className="px-3 py-2 text-gray-600">{job.region}</td>
                    <td className="px-3 py-2">
                      <span className={fitColor(job.role_fit, job.stop_flags)}>
                        ●
                      </span>{" "}
                      {job.role_fit || "—"}
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-3 py-2 text-gray-600">
                      {job.applied_date || "—"}
                    </td>
                    <td className="px-3 py-2 text-gray-600">
                      {days !== null ? days : "—"}
                    </td>
                    <td className="px-3 py-2 text-gray-600">
                      {job.days_to_response || "—"}
                    </td>
                    <td
                      className="px-3 py-2 max-w-[200px] truncate text-gray-500"
                      onClick={(e) => {
                        if (job.cl) {
                          e.stopPropagation();
                          setLetterPopup(job);
                        }
                      }}
                    >
                      {job.cl ? (
                        <span className="underline decoration-dotted cursor-pointer">
                          {job.cl.slice(0, 50)}…
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {jobs.length === 0 && !loading && (
        <p className="text-gray-500 mt-4 text-center">
          No jobs yet. Send a JD to the Telegram bot or use the input above.
        </p>
      )}

      {letterPopup && (
        <LetterPopup job={letterPopup} onClose={() => setLetterPopup(null)} />
      )}
    </div>
  );
}

// ─── Add Job Bar ─────────────────────────────────────────────────────────────

function AddJobBar({ onAdded }: { onAdded: () => void }) {
  const [input, setInput] = useState("");
  const [contact, setContact] = useState("");
  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const buildPayload = (addToTracker: boolean) => {
    const text = input.trim();
    const isUrl = text.startsWith("http://") || text.startsWith("https://");
    return {
      ...(isUrl ? { source_url: text } : { jd_text: text }),
      contact: contact.trim(),
      add_to_tracker: addToTracker,
    };
  };

  const handleEvaluate = async () => {
    if (!input.trim()) return;

    setEvaluating(true);
    setResult(null);
    setError("");
    try {
      const res = await evaluateJD(buildPayload(false));
      setResult(res);
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || "Evaluation failed")
          : "Evaluation failed. Check that the backend is running.";
      setError(msg);
    } finally {
      setEvaluating(false);
    }
  };

  const handleAdd = async () => {
    if (!input.trim()) return;

    setEvaluating(true);
    setError("");
    try {
      const res = await evaluateJD(buildPayload(true));
      if (res.duplicate) {
        setResult(res);
      } else {
        setInput("");
        setContact("");
        setResult(null);
        onAdded();
      }
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || "Failed to add job")
          : "Failed to add job. Check that the backend is running.";
      setError(msg);
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div className="mb-6 border rounded-lg p-4 bg-white">
      <div className="flex gap-2">
        <div className="flex-1 flex flex-col gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Paste job description text or URL..."
            rows={4}
            className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-200"
          />
          <textarea
            value={contact}
            onChange={(e) => setContact(e.target.value)}
            placeholder="Recruiter name, email, LinkedIn... (optional)"
            rows={2}
            className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-200"
          />
        </div>
        <div className="flex flex-col gap-1">
          <button
            onClick={handleEvaluate}
            disabled={evaluating || !input.trim()}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-40 cursor-pointer"
          >
            {evaluating ? "..." : "Evaluate"}
          </button>
          <button
            onClick={handleAdd}
            disabled={evaluating || !input.trim()}
            className="px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-40 cursor-pointer"
          >
            + Add
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-3 p-3 bg-red-50 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      {result && !("error" in result) && (
        <div className="mt-3 p-3 bg-gray-50 rounded text-sm">
          <div className="font-medium">
            {result.company as string} — {result.role as string} (
            {result.region as string})
          </div>
          <div className="mt-1">
            Role Fit: <strong>{result.role_fit as string}</strong>
            {typeof result.stop_flags === "string" &&
              result.stop_flags !== "" &&
              result.stop_flags !== "NONE" && (
              <span className="ml-2 text-red-600">
                Flags: {result.stop_flags as string}
              </span>
            )}
          </div>
          {typeof result.summary === "string" && result.summary && (
            <div className="mt-1 text-gray-600">{result.summary as string}</div>
          )}
          {typeof result.duplicate === "object" && result.duplicate !== null && (
            <div className="mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded text-yellow-800">
              Possible duplicate — already in tracker (row{" "}
              {(result.duplicate as { row_num?: number }).row_num ?? "?"})
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Letter Popup ────────────────────────────────────────────────────────────

function LetterPopup({ job, onClose }: { job: Job; onClose: () => void }) {
  const handleCopy = () => {
    navigator.clipboard.writeText(job.cl);
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-bold">
            {job.company} — {job.role}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl cursor-pointer">
            &times;
          </button>
        </div>
        <div className="p-4 overflow-y-auto flex-1">
          <pre className="whitespace-pre-wrap text-sm leading-relaxed">
            {job.cl}
          </pre>
        </div>
        <div className="flex gap-2 p-4 border-t">
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 cursor-pointer"
          >
            Copy
          </button>
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Status Badge ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  let color = "bg-gray-100 text-gray-700";
  if (s === "new") color = "bg-blue-100 text-blue-800";
  else if (s === "in progress") color = "bg-yellow-100 text-yellow-800";
  else if (s === "applied") color = "bg-green-100 text-green-800";
  else if (s === "waiting") color = "bg-orange-100 text-orange-800";
  else if (s === "response") color = "bg-purple-100 text-purple-800";
  else if (s === "interview") color = "bg-indigo-100 text-indigo-800";
  else if (s === "no response") color = "bg-gray-200 text-gray-600";
  else if (s === "closed") color = "bg-red-100 text-red-800";

  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {status}
    </span>
  );
}
