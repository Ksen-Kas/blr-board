import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getJob, evaluateJD, updateJob, getEvents, addEvent } from "../api/jobs";
import { JOB_STATUSES } from "../constants/statuses";
import type { Job, JobEvent } from "../types/job";
import { canonicalStatusLabel } from "../utils/status";

/** Extract domain from URL for display */
function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace("www.", "");
  } catch {
    return url;
  }
}

function extractVacancyId(url: string): string {
  const value = (url || "").trim();
  if (!value) return "";
  const patterns = [
    /\/jobs\/view\/(\d{6,})/i,
    /[?&](?:currentJobId|jobId|jk|vjk)=([A-Za-z0-9_-]{5,})/i,
    /\/vacanc(?:y|ies)\/(\d{4,})/i,
    /\/jobs?\/(\d{4,})/i,
  ];
  for (const pattern of patterns) {
    const match = value.match(pattern);
    if (match?.[1]) return match[1];
  }
  return "";
}

function parseContactDisplay(contact: string): { label: string; href: string } {
  const value = (contact || "").trim();
  if (!value) return { label: "", href: "" };

  const fullUrlMatch = value.match(/https?:\/\/[^\s|]+/i);
  const shortLinkedinMatch = value.match(
    /(?:[a-z]{2,3}\.)?linkedin\.com\/in\/[A-Za-z0-9\-_%]+\/?/i
  );
  const href = fullUrlMatch
    ? fullUrlMatch[0]
    : shortLinkedinMatch
      ? `https://${shortLinkedinMatch[0].replace(/^https?:\/\//i, "")}`
      : "";

  if (!href) return { label: value, href: "" };

  const parts = value.split("|").map((part) => part.trim()).filter(Boolean);
  const labelFromParts = parts.find(
    (part) => !/^https?:\/\//i.test(part) && !/linkedin\.com\/in\//i.test(part)
  );
  const label = labelFromParts || href.replace(/^https?:\/\//i, "");
  return { label, href };
}

type TouchpointRow = {
  eventId?: number;
  rawTimestamp: string;
  timestamp: string;
  eventType: string;
  detail: string;
  sortMs: number;
  editable: boolean;
  touchpoint?: {
    channel: string;
    direction: string;
    note: string;
  };
};

function parseDateToMs(value: string): number {
  const raw = (value || "").trim();
  if (!raw) return 0;

  const dotted = raw.match(
    /^(\d{2})[.](\d{2})[.](\d{2,4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/
  );
  if (dotted) {
    const dd = Number(dotted[1]);
    const mm = Number(dotted[2]);
    const yy = dotted[3].length === 2 ? 2000 + Number(dotted[3]) : Number(dotted[3]);
    const hh = Number(dotted[4] || "0");
    const mi = Number(dotted[5] || "0");
    const ss = Number(dotted[6] || "0");
    return new Date(yy, mm - 1, dd, hh, mi, ss).getTime();
  }

  const normalized = raw.includes(" ") ? raw.replace(" ", "T") : `${raw}T00:00:00`;
  const ms = Date.parse(normalized);
  return Number.isNaN(ms) ? 0 : ms;
}

function formatDateDDMMYY(value: string): string {
  const raw = (value || "").trim();
  if (!raw) return "";

  const isoMatch = raw.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) return `${isoMatch[3]}-${isoMatch[2]}-${isoMatch[1].slice(-2)}`;

  const dotted = raw.match(/^(\d{2})[.](\d{2})[.](\d{2,4})/);
  if (dotted) {
    const yy = dotted[3].slice(-2);
    return `${dotted[1]}-${dotted[2]}-${yy}`;
  }

  const normalized = raw.includes(" ") ? raw.replace(" ", "T") : `${raw}T00:00:00`;
  const date = new Date(normalized);
  if (!Number.isNaN(date.getTime())) {
    const dd = String(date.getDate()).padStart(2, "0");
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const yy = String(date.getFullYear()).slice(-2);
    return `${dd}-${mm}-${yy}`;
  }
  return raw;
}

function parseTouchpointData(data: string): { channel: string; direction: string; note: string } {
  try {
    const parsed = JSON.parse(data || "{}");
    return {
      channel: String(parsed.channel || "Other"),
      direction: String(parsed.direction || "Outbound"),
      note: String(parsed.note || ""),
    };
  } catch {
    return {
      channel: "Other",
      direction: "Outbound",
      note: data || "",
    };
  }
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
  const [touchDirection, setTouchDirection] = useState("Outbound");
  const [touchSaving, setTouchSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [statusMessageKind, setStatusMessageKind] = useState<"success" | "error" | "info">("info");
  const [statusUpdating, setStatusUpdating] = useState(false);

  useEffect(() => {
    if (rowNum) {
      getJob(Number(rowNum)).then((j) => {
        setJob(j);
        setStatus(canonicalStatusLabel(j.status) || j.status);
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
    if (!job || !touchNote.trim() || touchSaving) return;
    setTouchSaving(true);
    const data = JSON.stringify({
      channel: "Manual",
      direction: touchDirection,
      note: touchNote.trim(),
    });
    try {
      await addEvent(job.row_num, "touchpoint", data);
      setEvents(await getEvents(job.row_num));
      setTouchNote("");
      setShowTouchForm(false);
    } finally {
      setTouchSaving(false);
    }
  };

  if (!job) return <div className="p-6 text-muted">Loading...</div>;

  const stopFlags = job.stop_flags || "";
  const hasEligibilityAlert =
    stopFlags.includes("visa_required") || stopFlags.includes("citizenship");
  const vacancyId = extractVacancyId(job.source || "");
  const contactBadge = parseContactDisplay(job.contact || "");
  const roleFit = job.role_fit || "";
  const fitBadgeClass = hasEligibilityAlert
    ? "border-amber-200 bg-amber-50 text-amber-700"
    : roleFit.toLowerCase() === "strong"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : roleFit.toLowerCase() === "stretch" || roleFit.toLowerCase() === "partial"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-border bg-surface text-muted";
  const eventRows: TouchpointRow[] = events.map((ev) => {
    let detail = "";
    let touchpoint: TouchpointRow["touchpoint"] =
      ev.event_type === "touchpoint" ? parseTouchpointData(ev.data) : undefined;
    try {
      const d = JSON.parse(ev.data);
      if (ev.event_type === "status_change") {
        detail = `${d.from} → ${d.to}`;
      } else if (ev.event_type === "touchpoint") {
        detail = `${touchpoint?.direction || ""} ${touchpoint?.channel || ""}: ${touchpoint?.note || ""}`;
      } else {
        detail = ev.data;
      }
    } catch {
      if (ev.event_type === "touchpoint") {
        detail = `${touchpoint?.direction || ""} ${touchpoint?.channel || ""}: ${touchpoint?.note || ""}`;
      } else {
        detail = ev.data;
      }
    }
    return {
      eventId: ev.event_id,
      rawTimestamp: ev.timestamp,
      timestamp: formatDateDDMMYY(ev.timestamp),
      eventType: ev.event_type,
      detail,
      sortMs: parseDateToMs(ev.timestamp),
      editable: ev.event_type === "touchpoint" && typeof ev.event_id === "number",
      touchpoint,
    };
  });

  const timelineRows: TouchpointRow[] = [
    ...(job.followup_1
      ? [{
          rawTimestamp: job.followup_1,
          timestamp: formatDateDDMMYY(job.followup_1),
          eventType: "followup_1",
          detail: "Follow-up 1 sent",
          sortMs: parseDateToMs(job.followup_1),
        }]
      : []),
    ...(job.followup_2
      ? [{
          rawTimestamp: job.followup_2,
          timestamp: formatDateDDMMYY(job.followup_2),
          eventType: "followup_2",
          detail: "Follow-up 2 sent",
          sortMs: parseDateToMs(job.followup_2),
        }]
      : []),
    ...(job.response_date
      ? [{
          rawTimestamp: job.response_date,
          timestamp: formatDateDDMMYY(job.response_date),
          eventType: "response",
          detail: "Response received",
          sortMs: parseDateToMs(job.response_date),
        }]
      : []),
  ].map((item) => ({ ...item, editable: false }));

  const touchpointRows = [...eventRows, ...timelineRows]
    .sort((a, b) => b.sortMs - a.sortMs)
    .filter((row, index, all) => {
      const key = `${row.rawTimestamp}|${row.eventType}|${row.detail}`;
      return (
        index ===
        all.findIndex(
          (candidate) => `${candidate.rawTimestamp}|${candidate.eventType}|${candidate.detail}` === key
        )
      );
    });
  const lastTouchpointDate = touchpointRows[0]?.timestamp || "";

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <span className="tag-chip mb-2">Job Card</span>
        <h1 className="text-3xl font-extrabold text-text tracking-tight">
          {job.company} — {job.role}
        </h1>
        <p className="text-muted">{job.region}</p>

        {/* Source link — domain only, full URL on hover */}
        {(job.source || contactBadge.label) && (
          <div className="mt-2 flex items-center gap-2 flex-wrap">
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
            {vacancyId && (
              <span className="text-[11px] rounded-full border border-border px-2 py-0.5 text-muted">
                Vacancy ID {vacancyId}
              </span>
            )}
            <span className="text-[11px] rounded-full border border-border px-2 py-0.5 text-muted">
              Pipeline ID #{job.row_num}
            </span>
            {contactBadge.label &&
              (contactBadge.href ? (
                <a
                  href={contactBadge.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-sky-700 hover:bg-sky-100"
                  title={contactBadge.href}
                >
                  Contact: {contactBadge.label}
                </a>
              ) : (
                <span className="text-[11px] rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-sky-700">
                  Contact: {contactBadge.label}
                </span>
              ))}
          </div>
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
      {(job.applied_date || job.followup_2 || job.response_date || lastTouchpointDate) && (
        <div className="mb-4 p-4 surface-card">
          <div className="grid grid-cols-2 gap-2 text-sm">
            {job.applied_date && <div><span className="text-muted">Applied:</span> <span className="text-text">{job.applied_date}</span></div>}
            {lastTouchpointDate && <div><span className="text-muted">Last touchpoint:</span> <span className="text-text">{lastTouchpointDate}</span></div>}
            {job.followup_2 && <div><span className="text-muted">Follow-up 2:</span> <span className="text-text">{job.followup_2}</span></div>}
            {job.response_date && <div><span className="text-muted">Response:</span> <span className="text-text">{job.response_date}</span></div>}
            {job.days_to_response && <div><span className="text-muted">Days to response:</span> <span className="text-text">{job.days_to_response}</span></div>}
          </div>
        </div>
      )}

      {/* Eligibility alert banner */}
      {hasEligibilityAlert && (
        <div className="mb-4 p-3 border border-amber-300 rounded-xl bg-amber-50 text-amber-800 text-sm">
          <strong>Eligibility alert:</strong> explicit citizenship/visa requirement in JD.
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
            {contactBadge.href ? (
              <a
                href={contactBadge.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-accent hover:text-accent-hover"
              >
                {job.contact}
              </a>
            ) : (
              <p className="text-sm text-text">{job.contact}</p>
            )}
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
                  <div key={`${row.eventId || "row"}-${i}`} className="text-sm border-b border-border/70 pb-2 last:border-b-0">
                    <div className="flex gap-2">
                      <span className="text-muted shrink-0 w-36">{row.timestamp}</span>
                      <span className="text-muted shrink-0 w-28">{row.eventType}</span>
                      <span className="text-text flex-1">{row.detail}</span>
                    </div>
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
                  disabled={touchSaving || !touchNote.trim()}
                  className="px-3 py-1 text-sm bg-accent text-white rounded-full hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer font-semibold"
                >
                  {touchSaving ? "Saving..." : "Save"}
                </button>
                <button
                  onClick={() => setShowTouchForm(false)}
                  disabled={touchSaving}
                  className="px-3 py-1 text-sm border border-border rounded-full hover:bg-surface-alt disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer text-muted"
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
