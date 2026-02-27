import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getJob, evaluateJD, updateJob, getEvents, addEvent } from "../api/jobs";
import { JOB_STATUSES } from "../constants/statuses";
import type { Job, JobEvent } from "../types/job";

/** Extract domain from URL for display */
function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace("www.", "");
  } catch {
    return url;
  }
}

type TouchpointRow = {
  timestamp: string;
  eventType: string;
  detail: string;
  sortMs: number;
};

function parseDateToMs(value: string): number {
  const normalized = value.includes(" ") ? value.replace(" ", "T") : `${value}T00:00:00`;
  const ms = Date.parse(normalized);
  return Number.isNaN(ms) ? 0 : ms;
}

export default function JobCard() {
  const { rowNum } = useParams<{ rowNum: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [scoring, setScoring] = useState(false);
  const [scoreResult, setScoreResult] = useState<Record<string, string> | null>(null);
  const [scoreError, setScoreError] = useState("");
  const [jdOverride, setJdOverride] = useState("");
  const [status, setStatus] = useState("");
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [showTouchForm, setShowTouchForm] = useState(false);
  const [touchNote, setTouchNote] = useState("");
  const [touchChannel, setTouchChannel] = useState("Email");
  const [touchDirection, setTouchDirection] = useState("Outbound");
  const [statusMessage, setStatusMessage] = useState("");
  const [statusMessageKind, setStatusMessageKind] = useState<"success" | "error" | "info">("info");
  const [statusUpdating, setStatusUpdating] = useState(false);

  useEffect(() => {
    if (rowNum) {
      getJob(Number(rowNum)).then((j) => {
        setJob(j);
        setStatus(j.status);
      });
      getEvents(Number(rowNum)).then(setEvents).catch(() => {});
    }
  }, [rowNum]);

  useEffect(() => {
    if (!statusMessage || statusUpdating) return;
    const timeoutId = window.setTimeout(() => setStatusMessage(""), 3500);
    return () => window.clearTimeout(timeoutId);
  }, [statusMessage, statusMessageKind, statusUpdating]);

  const handleScore = async () => {
    if (!job) return;
    setScoring(true);
    setScoreError("");
    try {
      const override = jdOverride.trim();
      const hasSource = !!job.source?.trim();
      const hasComment = !!job.comment?.trim();

      if (!override && !hasSource && !hasComment) {
        setScoreError("Paste JD text or add a source URL before scoring.");
        return;
      }

      const payload = override
        ? { jd_text: override }
        : hasSource
        ? { source_url: job.source }
        : { jd_text: job.comment };

      const res = await evaluateJD(payload);
      setScoreResult(res);
      await updateJob(job.row_num, {
        role_fit: res.role_fit || "",
        stop_flags: res.stop_flags === "NONE" ? "" : res.stop_flags || "",
      });
      setJob((prev) =>
        prev
          ? {
              ...prev,
              role_fit: res.role_fit || "",
              stop_flags: res.stop_flags === "NONE" ? "" : res.stop_flags || "",
            }
          : prev
      );
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || "Scoring failed")
          : "Scoring failed. Check that the backend is running.";
      setScoreError(msg);
    } finally {
      setScoring(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!job) return;
    if (newStatus === status) return;
    const prevStatus = status;
    setStatus(newStatus);
    setStatusUpdating(true);
    setStatusMessageKind("info");
    setStatusMessage(`Updating status: ${prevStatus} -> ${newStatus}...`);
    try {
      await updateJob(job.row_num, { status: newStatus });
      setJob((prev) => (prev ? { ...prev, status: newStatus } : prev));
      const updatedEvents = await getEvents(job.row_num);
      setEvents(updatedEvents);
      setStatusMessageKind("success");
      setStatusMessage(`Status updated: ${newStatus}`);
    } catch {
      setStatus(prevStatus);
      setStatusMessageKind("error");
      setStatusMessage("Failed to update status.");
    } finally {
      setStatusUpdating(false);
    }
  };

  const handlePrepare = async () => {
    if (!job) return;
    await updateJob(job.row_num, { status: "In Progress" });
    navigate(`/job/${job.row_num}/cv`);
  };

  const handleAddTouchpoint = async () => {
    if (!job || !touchNote.trim()) return;
    const data = JSON.stringify({
      channel: touchChannel,
      direction: touchDirection,
      note: touchNote,
    });
    await addEvent(job.row_num, "touchpoint", data);
    setEvents(await getEvents(job.row_num));
    setTouchNote("");
    setShowTouchForm(false);
  };

  if (!job) return <div className="p-6 text-muted">Loading...</div>;

  const stopFlags = job.stop_flags || "";
  const roleFit = job.role_fit || "";
  const fitBadgeClass = stopFlags
    ? "border-red-200 bg-red-50 text-red-700"
    : roleFit.toLowerCase() === "strong"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : roleFit.toLowerCase() === "stretch" || roleFit.toLowerCase() === "partial"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-border bg-surface text-muted";
  const eventRows: TouchpointRow[] = events.map((ev) => {
    let detail = "";
    try {
      const d = JSON.parse(ev.data);
      if (ev.event_type === "status_change") {
        detail = `${d.from} → ${d.to}`;
      } else if (ev.event_type === "touchpoint") {
        detail = `${d.direction || ""} ${d.channel || ""}: ${d.note || ""}`;
      } else {
        detail = ev.data;
      }
    } catch {
      detail = ev.data;
    }
    return {
      timestamp: ev.timestamp,
      eventType: ev.event_type,
      detail,
      sortMs: parseDateToMs(ev.timestamp),
    };
  });

  const timelineRows: TouchpointRow[] = [
    ...(job.followup_1
      ? [{ timestamp: job.followup_1, eventType: "followup_1", detail: "Follow-up 1 sent", sortMs: parseDateToMs(job.followup_1) }]
      : []),
    ...(job.followup_2
      ? [{ timestamp: job.followup_2, eventType: "followup_2", detail: "Follow-up 2 sent", sortMs: parseDateToMs(job.followup_2) }]
      : []),
    ...(job.response_date
      ? [{ timestamp: job.response_date, eventType: "response", detail: "Response received", sortMs: parseDateToMs(job.response_date) }]
      : []),
  ];

  const touchpointRows = [...eventRows, ...timelineRows].sort((a, b) => b.sortMs - a.sortMs);

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <button
        onClick={() => navigate("/")}
        className="text-accent hover:text-accent-hover text-sm mb-4 inline-block cursor-pointer font-semibold"
      >
        &larr; Pipeline
      </button>

      {/* Header */}
      <div className="mb-6">
        <span className="tag-chip mb-2">Job Card</span>
        <h1 className="text-3xl font-extrabold text-text tracking-tight">
          {job.company} — {job.role}
        </h1>
        <p className="text-muted">{job.region}</p>

        {/* Source link — domain only, full URL on hover */}
        {job.source && (
          <a
            href={job.source}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent text-sm hover:text-accent-hover cursor-pointer font-medium"
            title={job.source}
          >
            {extractDomain(job.source)}
          </a>
        )}

        <div className="flex items-center gap-3 mt-2 text-sm">
          <span className="text-muted">
            <span>Fit {roleFit || "Not scored"}</span>
            <span className="mx-1 text-border">|</span>
            <span className={job.operator_vs_contractor ? "text-muted" : "text-muted/50"}>
              {job.operator_vs_contractor || "Type"}
            </span>
            <span className="mx-1 text-border">|</span>
            <span className={job.seniority ? "text-muted" : "text-muted/50"}>
              {job.seniority || "Level"}
            </span>
          </span>
          <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${fitBadgeClass}`}>
            FIT: {roleFit || "N/A"}
          </span>
          <span className="text-border">|</span>

          {/* Status dropdown */}
          <div className="relative inline-block">
            <select
              value={status}
              onChange={(e) => handleStatusChange(e.target.value)}
              disabled={statusUpdating}
              className="appearance-none bg-surface border border-border rounded-full px-3 py-1 pr-7 text-sm font-semibold cursor-pointer hover:border-muted text-text"
            >
              {JOB_STATUSES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-muted pointer-events-none text-xs">
              ▼
            </span>
          </div>

          {job.submission_count && Number(job.submission_count) > 1 && (
            <span className="bg-orange-50 text-orange-700 text-xs px-2 py-0.5 rounded-full border border-orange-200">
              Submission #{job.submission_count}
            </span>
          )}

          {job.possible_duplicate && (
            <span
              className="bg-amber-50 text-amber-700 text-xs px-2 py-0.5 rounded-full border border-amber-200 cursor-help"
              title={job.duplicate_of || "Duplicate detected"}
            >
              Duplicate of: {job.duplicate_of || "?"}
            </span>
          )}

          {job.needs_followup && (
            <span className="bg-red-50 text-red-700 text-xs px-2 py-0.5 rounded-full border border-red-200">
              🔔 Needs follow-up
            </span>
          )}
        </div>
        {statusMessage && (
          <div
            className={`mt-2 inline-flex items-center rounded-full border px-3 py-1 text-xs ${
              statusMessageKind === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : statusMessageKind === "error"
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-border bg-surface text-muted"
            }`}
          >
            {statusMessage}
          </div>
        )}
      </div>

      {/* Timeline */}
      {(job.applied_date || job.followup_1 || job.followup_2 || job.response_date) && (
        <div className="mb-4 p-4 surface-card">
          <div className="grid grid-cols-2 gap-2 text-sm">
            {job.applied_date && <div><span className="text-muted">Applied:</span> <span className="text-text">{job.applied_date}</span></div>}
            {job.followup_1 && <div><span className="text-muted">Follow-up 1:</span> <span className="text-text">{job.followup_1}</span></div>}
            {job.followup_2 && <div><span className="text-muted">Follow-up 2:</span> <span className="text-text">{job.followup_2}</span></div>}
            {job.response_date && <div><span className="text-muted">Response:</span> <span className="text-text">{job.response_date}</span></div>}
            {job.days_to_response && <div><span className="text-muted">Days to response:</span> <span className="text-text">{job.days_to_response}</span></div>}
          </div>
        </div>
      )}

      {/* Stop flags banner */}
      {stopFlags && (
        <div className="mb-4 p-3 border border-red-200 rounded-xl bg-red-50 text-red-700 text-sm">
          <strong>Stop flags:</strong> {stopFlags}
        </div>
      )}

      {/* Scoring result */}
      {scoreResult && (
        <div className="mb-4 p-4 border border-accent/30 rounded-xl bg-emerald-50 text-sm">
          <div className="font-medium mb-1 text-text">
            {scoreResult.role_fit} | CV: {scoreResult.cv_ready === "YES" ? "Ready" : "Needs work"}
            {scoreResult.cv_note && ` — ${scoreResult.cv_note}`}
          </div>
          <p className="text-muted">{scoreResult.summary}</p>
        </div>
      )}

      {/* Scoring input */}
      <div className="mb-4 p-4 surface-card">
        <div className="text-sm font-medium text-text">Scoring Input</div>
        <p className="text-xs text-muted mt-1">
          If the job is from LinkedIn or the page doesn’t parse, paste JD text here.
        </p>
        <textarea
          value={jdOverride}
          onChange={(e) => setJdOverride(e.target.value)}
          placeholder="Paste JD text (optional, but required for LinkedIn)..."
          rows={4}
          className="mt-3 w-full border border-border rounded-xl px-3 py-2 text-sm resize-none bg-input text-text placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
        />
        {scoreError ? (
          <div className="mt-3 text-sm text-red-700">{scoreError}</div>
        ) : null}
      </div>

      {/* Info sections */}
      <div className="space-y-4 mb-6">
        {job.comment && (
          <Section title="Summary / Comment">
            <pre className="whitespace-pre-wrap text-sm leading-relaxed text-text">{job.comment}</pre>
          </Section>
        )}

        {job.contact && (
          <Section title="Contact">
            <p className="text-sm text-text">{job.contact}</p>
          </Section>
        )}

        {job.cl && (
          <Section title="Cover Letter">
            <pre className="whitespace-pre-wrap text-sm leading-relaxed text-text">{job.cl}</pre>
          </Section>
        )}

        {job.cv && (
          <Section title="CV Changes">
            <pre className="whitespace-pre-wrap text-sm leading-relaxed text-text">{job.cv}</pre>
          </Section>
        )}

        {job.reapply_reason && (
          <Section title="Reapply Reason">
            <p className="text-sm text-text">{job.reapply_reason}</p>
          </Section>
        )}

        {/* Touchpoints / Events history */}
        <Section title="Touchpoints">
          {touchpointRows.length > 0 ? (
            <div className="space-y-2">
              {touchpointRows.map((row, i) => {
                return (
                  <div key={i} className="flex gap-2 text-sm">
                    <span className="text-muted shrink-0 w-36">{row.timestamp}</span>
                    <span className="text-muted shrink-0 w-28">{row.eventType}</span>
                    <span className="text-text">{row.detail}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-muted">No events yet</p>
          )}

          {/* Add touchpoint */}
          {!showTouchForm ? (
            <button
              onClick={() => setShowTouchForm(true)}
              className="mt-2 text-sm text-accent hover:text-accent-hover cursor-pointer"
            >
              + Touchpoint
            </button>
          ) : (
            <div className="mt-3 p-3 bg-surface-alt rounded-xl space-y-2 border border-border/70">
              <div className="flex gap-2">
                <select
                  value={touchChannel}
                  onChange={(e) => setTouchChannel(e.target.value)}
                  className="border border-border bg-input text-text rounded-full px-3 py-1 text-sm cursor-pointer"
                >
                  <option>Email</option>
                  <option>LinkedIn</option>
                  <option>Phone</option>
                  <option>Portal</option>
                  <option>Other</option>
                </select>
                <select
                  value={touchDirection}
                  onChange={(e) => setTouchDirection(e.target.value)}
                  className="border border-border bg-input text-text rounded-full px-3 py-1 text-sm cursor-pointer"
                >
                  <option>Outbound</option>
                  <option>Inbound</option>
                </select>
              </div>
              <textarea
                value={touchNote}
                onChange={(e) => setTouchNote(e.target.value)}
                placeholder="Note..."
                rows={2}
                className="w-full border border-border bg-input rounded-xl px-3 py-2 text-sm text-text resize-none placeholder:text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleAddTouchpoint}
                  className="px-3 py-1 text-sm bg-accent text-white rounded-full hover:bg-accent-hover cursor-pointer font-semibold"
                >
                  Save
                </button>
                <button
                  onClick={() => setShowTouchForm(false)}
                  className="px-3 py-1 text-sm border border-border rounded-full hover:bg-surface-alt cursor-pointer text-muted"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </Section>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3 border-t border-border pt-4">
        <button
          onClick={handlePrepare}
          className="px-4 py-2 bg-emerald-100 text-emerald-700 border border-emerald-300 rounded-full hover:bg-emerald-200 text-sm font-semibold cursor-pointer"
        >
          Prepare Application &rarr;
        </button>
        {!roleFit && (
          <button
            onClick={handleScore}
            disabled={scoring}
            className="px-4 py-2 border border-border rounded-full hover:bg-surface-alt disabled:opacity-40 text-sm cursor-pointer text-muted hover:text-text font-medium"
          >
            {scoring ? "Scoring..." : "Evaluate Fit"}
          </button>
        )}
        <button
          onClick={() => navigate(`/job/${job.row_num}/letter`)}
          className="px-4 py-2 border border-border rounded-full hover:bg-surface-alt text-sm cursor-pointer text-muted hover:text-text font-medium"
        >
          {job.cl?.trim() ? "Open Saved Letter" : "Letter Only"}
        </button>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="surface-card overflow-hidden">
      <div className="bg-surface-alt px-4 py-2 text-sm font-semibold text-muted">{title}</div>
      <div className="px-4 py-3">{children}</div>
    </div>
  );
}
