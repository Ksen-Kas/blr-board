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

function hasEligibilityAlert(stopFlags: string) {
  const flags = stopFlags.toLowerCase();
  return flags.includes("visa_required") || flags.includes("citizenship");
}

/** Fit color for non-alert states */
function fitColor(roleFit: string) {
  const fit = roleFit.toLowerCase();
  if (fit === "strong") return "text-emerald-600";
  if (fit === "stretch" || fit === "partial") return "text-teal-600";
  return "text-muted";
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
        <div>
          <span className="tag-chip mb-2">Jobs Tracker</span>
          <h1 className="text-3xl font-extrabold text-text tracking-tight">Pipeline</h1>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={() => {
              refreshCache();
              loadJobs();
            }}
            className="px-3 py-2 text-sm border border-border rounded-full hover:bg-surface-alt cursor-pointer text-muted hover:text-text font-semibold"
          >
            Refresh
          </button>
          <span className="tag-chip">
            {filtered.length} jobs
          </span>
        </div>
      </div>

      <AddJobBar onAdded={loadJobs} />

      {loading ? (
        <div className="text-muted py-8 text-center">Loading...</div>
      ) : (
        <div className="surface-card overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left bg-surface-alt text-muted">
                <th className="px-3 py-2.5 font-medium w-8">#</th>
                <th
                  className="px-3 py-2.5 font-semibold cursor-pointer hover:text-text select-none"
                  onClick={() => handleSort("company")}
                >
                  Company{sortIndicator("company")}
                </th>
                <th className="px-3 py-2.5 font-semibold">Role</th>
                <th
                  className="px-3 py-2.5 font-semibold cursor-pointer hover:text-text select-none"
                  onClick={() => handleSort("region")}
                >
                  Region{sortIndicator("region")}
                </th>
                <th className="px-3 py-2.5 font-semibold w-28">Fit</th>
                <th className="px-3 py-2.5 font-semibold w-32">
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="font-semibold text-muted bg-transparent border-none outline-none cursor-pointer text-sm p-0"
                  >
                    <option value="All">Status ▼</option>
                    {JOB_STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </th>
                <th className="px-3 py-2.5 font-semibold w-24">Applied</th>
                <th
                  className="px-3 py-2.5 font-semibold w-16 cursor-pointer hover:text-text select-none"
                  onClick={() => handleSort("days")}
                >
                  Days{sortIndicator("days")}
                </th>
                <th className="px-3 py-2.5 font-semibold w-16">DTR</th>
                <th className="px-3 py-2.5 font-semibold w-48">CL</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((job) => {
                const days = daysSince(job.applied_date);

                return (
                  <tr
                    key={job.row_num}
                    className="border-t border-border/80 cursor-pointer hover:bg-surface-alt/70"
                    onClick={() => navigate(`/job/${job.row_num}`)}
                  >
                    <td className="px-3 py-2 text-muted">
                      {job.row_num}
                      {job.needs_followup && (
                        <span className="ml-1" title="Needs follow-up">🔔</span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-medium text-text">
                      <span className="inline-flex items-center gap-2">
                        <span className="text-[15px]">{job.company}</span>
                        {job.possible_duplicate && (
                          <span
                            className="inline-flex items-center text-muted cursor-help"
                            title={`Duplicate of: ${job.duplicate_of}`}
                            aria-label="Possible duplicate"
                          >
                            <svg
                              width="14"
                              height="14"
                              viewBox="0 0 20 20"
                              fill="none"
                              xmlns="http://www.w3.org/2000/svg"
                            >
                              <rect
                                x="7"
                                y="3"
                                width="10"
                                height="10"
                                rx="2"
                                stroke="currentColor"
                                strokeWidth="1.5"
                              />
                              <rect
                                x="3"
                                y="7"
                                width="10"
                                height="10"
                                rx="2"
                                stroke="currentColor"
                                strokeWidth="1.5"
                                opacity="0.7"
                              />
                            </svg>
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-text">{job.role}</td>
                    <td className="px-3 py-2 text-muted">{job.region}</td>
                    <td className="px-3 py-2">
                      {hasEligibilityAlert(job.stop_flags || "") ? (
                        <span className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-amber-300 bg-amber-50 text-[11px] font-bold text-amber-700 leading-none">
                          !
                        </span>
                      ) : (
                        <span className={fitColor(job.role_fit)}>●</span>
                      )}{" "}
                      <span className="text-muted font-medium">{job.role_fit || "—"}</span>
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-3 py-2 text-muted">
                      {job.applied_date || "—"}
                    </td>
                    <td className="px-3 py-2 text-muted">
                      {days !== null ? days : "—"}
                    </td>
                    <td className="px-3 py-2 text-muted">
                      {job.days_to_response || "—"}
                    </td>
                    <td
                      className="px-3 py-2 max-w-[200px] truncate text-muted"
                      onClick={(e) => {
                        if (job.cl) {
                          e.stopPropagation();
                          setLetterPopup(job);
                        }
                      }}
                    >
                      {job.cl ? (
                        <span className="underline decoration-dotted cursor-pointer text-accent/70 hover:text-accent">
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
        <p className="text-muted mt-4 text-center">
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
    <div className="mb-6 surface-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-text">Quick Evaluate</span>
        <span className="tag-chip">URL or JD text</span>
      </div>
      <div className="flex gap-2">
        <div className="flex-1 flex flex-col gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Paste job description text or URL..."
            rows={4}
            className="w-full border border-border rounded-xl px-3 py-2 text-sm resize-none bg-input text-text placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
          />
          <textarea
            value={contact}
            onChange={(e) => setContact(e.target.value)}
            placeholder="Recruiter name, email, LinkedIn... (optional)"
            rows={2}
            className="w-full border border-border rounded-xl px-3 py-2 text-sm resize-none bg-input text-text placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
          />
        </div>
        <div className="flex flex-col gap-1">
          <button
            onClick={handleEvaluate}
            disabled={evaluating || !input.trim()}
            className="px-3 py-1.5 text-sm bg-accent text-white rounded-full hover:bg-accent-hover disabled:opacity-40 cursor-pointer font-semibold"
          >
            {evaluating ? "..." : "Evaluate"}
          </button>
          <button
            onClick={handleAdd}
            disabled={evaluating || !input.trim()}
            className="px-3 py-1.5 text-sm bg-emerald-100 text-emerald-700 border border-emerald-300 rounded-full hover:bg-emerald-200 disabled:opacity-40 cursor-pointer font-semibold"
          >
            + Add
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {error}
        </div>
      )}

      {result && !("error" in result) && (
        <div className="mt-3 p-3 bg-surface-alt rounded-xl text-sm">
          <div className="font-medium text-text">
            {result.company as string} — {result.role as string} (
            {result.region as string})
          </div>
          <div className="mt-1 text-muted">
            Role Fit: <strong className="text-text">{result.role_fit as string}</strong>
          </div>
          {typeof result.stop_flags === "string" &&
            result.stop_flags !== "" &&
            result.stop_flags !== "NONE" &&
            hasEligibilityAlert(result.stop_flags as string) && (
            <div className="mt-2 inline-flex items-center gap-2 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-amber-400 bg-amber-100 text-[11px] leading-none">!</span>
              Eligibility restriction in JD (citizenship/visa).
            </div>
          )}
          {typeof result.summary === "string" && result.summary && (
            <div className="mt-1 text-muted">{result.summary as string}</div>
          )}
          {typeof result.duplicate === "object" && result.duplicate !== null && (
            <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded-xl text-amber-700">
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
      className="fixed inset-0 bg-slate-900/35 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-surface border border-border rounded-2xl shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="font-bold text-text">
            {job.company} — {job.role}
          </h2>
          <button onClick={onClose} className="text-muted hover:text-text text-xl cursor-pointer">
            &times;
          </button>
        </div>
        <div className="p-4 overflow-y-auto flex-1">
          <pre className="whitespace-pre-wrap text-sm leading-relaxed text-text">
            {job.cl}
          </pre>
        </div>
        <div className="flex gap-2 p-4 border-t border-border">
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 text-sm bg-accent text-white rounded-full hover:bg-accent-hover cursor-pointer font-semibold"
          >
            Copy
          </button>
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm border border-border rounded-full hover:bg-surface-alt cursor-pointer text-muted"
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
  let color = "bg-surface-alt text-muted border border-border";
  if (s === "new") color = "bg-blue-50 text-blue-700 border border-blue-200";
  else if (s === "screening") color = "bg-cyan-50 text-cyan-700 border border-cyan-200";
  else if (s === "screening req") color = "bg-cyan-100 text-cyan-700 border border-cyan-300";
  else if (s === "in progress") color = "bg-amber-50 text-amber-700 border border-amber-200";
  else if (s === "applied") color = "bg-emerald-50 text-emerald-700 border border-emerald-200";
  else if (s === "waiting") color = "bg-orange-50 text-orange-700 border border-orange-200";
  else if (s === "response") color = "bg-violet-50 text-violet-700 border border-violet-200";
  else if (s === "interview") color = "bg-indigo-50 text-indigo-700 border border-indigo-200";
  else if (s === "no response") color = "bg-slate-100 text-slate-600 border border-slate-200";
  else if (s === "closed") color = "bg-rose-50 text-rose-700 border border-rose-200";

  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}>
      {status}
    </span>
  );
}
