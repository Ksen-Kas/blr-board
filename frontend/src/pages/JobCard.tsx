import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getJob, evaluateJD, getEvents } from "../api/jobs";
import { JOB_STATUSES } from "../constants/statuses";
import type { Job, JobEvent } from "../types/job";
import { canonicalStatusLabel } from "../utils/status";
import { applyQueueDraft, getQueuedRowChange, syncPendingRows } from "../state/syncQueue";

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

type LetterHistoryRow = {
  eventId: number;
  rawTimestamp: string;
  timestamp: string;
  source: string;
  subject: string;
  body: string;
};

type PendingTouchpoint = {
  direction: string;
  note: string;
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

function parseStoredLetter(rawLetter: string): { subject: string; body: string } {
  const text = (rawLetter || "").trim();
  if (!text) return { subject: "", body: "" };
  const match = text.match(/^Subject:\s*(.+)\n\n([\s\S]+)$/i);
  if (match) return { subject: match[1].trim(), body: match[2].trim() };
  return { subject: "", body: text };
}

function formatDateTimeDDMMYY(value: string): string {
  const raw = (value || "").trim();
  if (!raw) return "";
  const normalized = raw.includes(" ") ? raw.replace(" ", "T") : raw;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return formatDateDDMMYY(raw);
  const dd = String(date.getDate()).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const yy = String(date.getFullYear()).slice(-2);
  const hh = String(date.getHours()).padStart(2, "0");
  const mi = String(date.getMinutes()).padStart(2, "0");
  return `${dd}-${mm}-${yy} ${hh}:${mi}`;
}

function parseLetterHistory(events: JobEvent[]): LetterHistoryRow[] {
  const allowed = new Set(["letter_saved", "cl_saved", "letter_snapshot"]);
  const rows: LetterHistoryRow[] = [];

  for (const ev of events) {
    const eventType = (ev.event_type || "").toLowerCase();
    if (!allowed.has(eventType)) continue;
    try {
      const parsed = JSON.parse(ev.data || "{}");
      const subject = String(parsed.subject || "").trim();
      const body = String(parsed.body || "").trim();
      const source = String(parsed.source || (eventType === "letter_saved" ? "manual" : "unknown")).trim();
      if (!body) continue;
      rows.push({
        eventId: Number(ev.event_id || 0),
        rawTimestamp: ev.timestamp || "",
        timestamp: formatDateTimeDDMMYY(ev.timestamp || ""),
        source,
        subject,
        body,
      });
    } catch {
      continue;
    }
  }

  return rows.sort((a, b) => {
    if (a.eventId && b.eventId) return b.eventId - a.eventId;
    return parseDateToMs(b.rawTimestamp) - parseDateToMs(a.rawTimestamp);
  });
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
  const [pendingTouchpoints, setPendingTouchpoints] = useState<PendingTouchpoint[]>([]);
  const [statusMessage, setStatusMessage] = useState("");
  const [statusMessageKind, setStatusMessageKind] = useState<"success" | "error" | "info">("info");
  const [letterActionMessage, setLetterActionMessage] = useState("");
  const [letterActionKind, setLetterActionKind] = useState<"success" | "error" | "info">("info");
  const [loadingLetterEventId, setLoadingLetterEventId] = useState<number | null>(null);
  const [manualLetterSubject, setManualLetterSubject] = useState("");
  const [manualLetterBody, setManualLetterBody] = useState("");
  const [savedManualSnapshot, setSavedManualSnapshot] = useState({ subject: "", body: "" });
  const [isSavingBatch, setIsSavingBatch] = useState(false);
  const loadedRowRef = useRef<number | null>(null);
  const latestDraftRef = useRef({
    job: null as Job | null,
    status: "",
    pendingTouchpoints: [] as PendingTouchpoint[],
    manualLetterSubject: "",
    manualLetterBody: "",
    hasPendingLetterChanges: false,
  });

  useEffect(() => {
    if (!rowNum) {
      loadedRowRef.current = null;
      return;
    }
    const numericRow = Number(rowNum);
    if (!Number.isFinite(numericRow)) return;
    if (loadedRowRef.current === numericRow) return;
    loadedRowRef.current = numericRow;
    getJob(numericRow).then((j) => {
      const queued = getQueuedRowChange(j.row_num);
      const queuedStatus = queued?.updates?.status;
      const queuedLetter = queued?.letterSave;
      setJob(j);
      setStatus(
        queuedStatus
          ? String(queuedStatus)
          : (canonicalStatusLabel(j.status) || j.status),
      );
      const stored = parseStoredLetter(j.cl || "");
      setManualLetterSubject(queuedLetter?.subject ?? stored.subject);
      setManualLetterBody(queuedLetter?.body ?? stored.body);
      setSavedManualSnapshot({ subject: stored.subject, body: stored.body });
      setPendingTouchpoints(queued?.touchpoints || []);
    });
    getEvents(numericRow).then(setEvents).catch(() => {});
  }, [rowNum]);

  useEffect(() => {
    if (!statusMessage || isSavingBatch) return;
    const timeoutId = window.setTimeout(() => setStatusMessage(""), 3500);
    return () => window.clearTimeout(timeoutId);
  }, [statusMessage, statusMessageKind, isSavingBatch]);

  useEffect(() => {
    if (!letterActionMessage) return;
    const timeoutId = window.setTimeout(() => setLetterActionMessage(""), 3500);
    return () => window.clearTimeout(timeoutId);
  }, [letterActionMessage, letterActionKind]);

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
      applyQueueDraft(job.row_num, {
        setUpdates: {
          role_fit: res.role_fit || "",
          stop_flags: res.stop_flags === "NONE" ? "" : res.stop_flags || "",
        },
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

  const hasPendingStatusChange = useMemo(() => {
    if (!job) return false;
    const current = canonicalStatusLabel(job.status) || job.status;
    return status !== current;
  }, [job, status]);

  const hasPendingLetterChanges = useMemo(() => {
    return (
      manualLetterSubject.trim() !== savedManualSnapshot.subject ||
      manualLetterBody.trim() !== savedManualSnapshot.body
    );
  }, [manualLetterSubject, manualLetterBody, savedManualSnapshot]);

  useEffect(() => {
    latestDraftRef.current = {
      job,
      status,
      pendingTouchpoints,
      manualLetterSubject,
      manualLetterBody,
      hasPendingLetterChanges,
    };
  }, [
    job,
    status,
    pendingTouchpoints,
    manualLetterSubject,
    manualLetterBody,
    hasPendingLetterChanges,
  ]);

  const enqueueCurrentDraft = useCallback((overrideStatus?: string) => {
    if (!job) return false;
    const nextStatus = overrideStatus || status;
    const currentStatus = canonicalStatusLabel(job.status) || job.status;
    const hasStatus = nextStatus !== currentStatus;

    const subject = manualLetterSubject.trim();
    const body = manualLetterBody.trim();
    const hasLetter = hasPendingLetterChanges && Boolean(body);

    applyQueueDraft(job.row_num, {
      setUpdates: hasStatus ? { status: nextStatus } : undefined,
      clearUpdateKeys: hasStatus ? undefined : ["status"],
      touchpoints: pendingTouchpoints,
      letterSave: hasLetter
        ? {
            subject,
            body,
            source: "manual",
          }
        : null,
    });

    return hasStatus || hasLetter || pendingTouchpoints.length > 0;
  }, [
    job,
    status,
    manualLetterSubject,
    manualLetterBody,
    hasPendingLetterChanges,
    pendingTouchpoints,
  ]);

  useEffect(() => {
    enqueueCurrentDraft();
  }, [enqueueCurrentDraft]);

  useEffect(() => {
    return () => {
      const latest = latestDraftRef.current;
      if (!latest.job) return;
      const currentStatus = canonicalStatusLabel(latest.job.status) || latest.job.status;
      const hasStatus = latest.status !== currentStatus;
      const subject = latest.manualLetterSubject.trim();
      const body = latest.manualLetterBody.trim();
      const hasLetter = latest.hasPendingLetterChanges && Boolean(body);
      applyQueueDraft(latest.job.row_num, {
        setUpdates: hasStatus ? { status: latest.status } : undefined,
        clearUpdateKeys: hasStatus ? undefined : ["status"],
        touchpoints: latest.pendingTouchpoints,
        letterSave: hasLetter
          ? {
              subject,
              body,
              source: "manual",
            }
          : null,
      });
      void syncPendingRows([latest.job.row_num]);
    };
  }, [rowNum]);

  const commitQueuedChanges = async (
    options: { overrideStatus?: string; silent?: boolean } = {},
  ): Promise<boolean> => {
    if (!job || isSavingBatch) return false;
    const nextStatus = options.overrideStatus || status;
    const currentStatus = canonicalStatusLabel(job.status) || job.status;
    const shouldApplyStatus = nextStatus !== currentStatus;
    const shouldApplyLetter = hasPendingLetterChanges && Boolean(manualLetterBody.trim());
    const syncedCl = manualLetterSubject.trim()
      ? `Subject: ${manualLetterSubject.trim()}\n\n${manualLetterBody.trim()}`
      : manualLetterBody.trim();

    if (hasPendingLetterChanges && !manualLetterBody.trim()) {
      setLetterActionKind("error");
      setLetterActionMessage("Custom CL body is empty. Fill it or revert changes before save.");
      return false;
    }

    const queuedAny = enqueueCurrentDraft(options.overrideStatus);
    if (!queuedAny) {
      if (!options.silent) {
        setStatusMessageKind("info");
        setStatusMessage("No pending changes.");
      }
      return true;
    }

    setIsSavingBatch(true);
    if (!options.silent) {
      setStatusMessageKind("info");
      setStatusMessage("Saving queued changes...");
    }

    try {
      const res = await syncPendingRows([job.row_num]);
      if (res.failedRows > 0) {
        setStatusMessageKind("error");
        setStatusMessage("Failed to sync changes. They stay queued.");
        return false;
      }
      setSavedManualSnapshot({
        subject: manualLetterSubject.trim(),
        body: manualLetterBody.trim(),
      });
      setJob((prev) =>
        prev
          ? {
              ...prev,
              status: shouldApplyStatus ? nextStatus : prev.status,
              cl: shouldApplyLetter ? syncedCl : prev.cl,
            }
          : prev,
      );
      setStatus(nextStatus);
      setPendingTouchpoints([]);
      if (!options.silent) {
        setStatusMessageKind("success");
        setStatusMessage("Changes synced.");
      }
      return true;
    } catch {
      setStatusMessageKind("error");
      setStatusMessage("Failed to sync changes.");
      return false;
    } finally {
      setIsSavingBatch(false);
    }
  };

  const handleStatusChange = (newStatus: string) => {
    if (!job) return;
    setStatus(newStatus);
    if (newStatus !== (canonicalStatusLabel(job.status) || job.status)) {
      setStatusMessageKind("info");
      setStatusMessage(`Status queued: ${newStatus}`);
    }
  };

  const handlePrepare = async () => {
    if (!job) return;
    setStatus("In Progress");
    const ok = await commitQueuedChanges({ overrideStatus: "In Progress", silent: true });
    if (!ok) return;
    navigate(`/job/${job.row_num}/cv`);
  };

  const handleAddTouchpoint = () => {
    if (!touchNote.trim()) return;
    setPendingTouchpoints((prev) => [
      ...prev,
      { direction: touchDirection, note: touchNote.trim() },
    ]);
    setTouchNote("");
    setShowTouchForm(false);
    setStatusMessageKind("info");
    setStatusMessage("Touchpoint queued.");
  };

  const handleLoadLetterVersion = (row: LetterHistoryRow) => {
    if (!job || loadingLetterEventId === row.eventId) return;
    setLoadingLetterEventId(row.eventId);
    setLetterActionKind("info");
    setLetterActionMessage("Loading selected CL version (local)...");
    setManualLetterSubject(row.subject);
    setManualLetterBody(row.body);
    setLetterActionKind("success");
    setLetterActionMessage("CL version loaded. It will auto-sync when you leave.");
    setLoadingLetterEventId(null);
  };

  const handleCopyLetterVersion = async (row: LetterHistoryRow) => {
    if (!navigator.clipboard) {
      setLetterActionKind("error");
      setLetterActionMessage("Clipboard not available in this browser.");
      return;
    }
    try {
      await navigator.clipboard.writeText(row.subject ? `Subject: ${row.subject}\n\n${row.body}` : row.body);
      setLetterActionKind("success");
      setLetterActionMessage("CL history version copied.");
    } catch {
      setLetterActionKind("error");
      setLetterActionMessage("Copy failed.");
    }
  };

  const handleSaveManualLetter = () => {
    if (!manualLetterBody.trim()) {
      setLetterActionKind("error");
      setLetterActionMessage("Custom CL body is empty.");
      return;
    }
    setLetterActionKind("info");
    setLetterActionMessage("CL queued.");
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
  const hasPendingChanges =
    hasPendingStatusChange || hasPendingLetterChanges || pendingTouchpoints.length > 0;
  const eventRows: TouchpointRow[] = events
    .filter((ev) => ev.event_type === "touchpoint" || ev.event_type === "status_change")
    .map((ev) => {
    let detail = "";
    const touchpoint: TouchpointRow["touchpoint"] =
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
  const letterHistoryRows = parseLetterHistory(events);

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
              disabled={isSavingBatch}
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
          {hasPendingStatusChange && (
            <span className="bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full border border-blue-200">
              Status queued
            </span>
          )}
          {pendingTouchpoints.length > 0 && (
            <span className="bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full border border-blue-200">
              Touchpoints queued: {pendingTouchpoints.length}
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

        <Section title="Save Custom CL">
          <div className="space-y-3">
            <input
              value={manualLetterSubject}
              onChange={(e) => setManualLetterSubject(e.target.value)}
              className="w-full border border-border bg-input rounded-xl px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/20"
              placeholder="Subject (optional)"
            />
            <textarea
              value={manualLetterBody}
              onChange={(e) => setManualLetterBody(e.target.value)}
              rows={8}
              className="w-full border border-border bg-input rounded-xl px-3 py-2 text-sm text-text resize-y placeholder:text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/20"
              placeholder="Paste your custom cover letter text here..."
            />
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveManualLetter}
                disabled={!manualLetterBody.trim()}
                className="px-4 py-2 border border-border rounded-full hover:bg-surface-alt text-sm cursor-pointer text-muted hover:text-text font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Queue CL Change
              </button>
              <button
                onClick={() => navigate(`/job/${job.row_num}/letter`)}
                className="px-4 py-2 bg-surface-alt rounded-full hover:bg-border text-sm cursor-pointer text-muted font-medium"
              >
                Open Letter Editor
              </button>
            </div>
          </div>
        </Section>

        {job.cl && (
          <Section title="Cover Letter">
            <pre className="whitespace-pre-wrap text-sm leading-relaxed text-text">{job.cl}</pre>
            {letterActionMessage && (
              <div
                className={`mt-3 inline-flex items-center rounded-full border px-3 py-1 text-xs ${
                  letterActionKind === "success"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : letterActionKind === "error"
                      ? "border-red-200 bg-red-50 text-red-700"
                      : "border-border bg-surface text-muted"
                }`}
              >
                {letterActionMessage}
              </div>
            )}
          </Section>
        )}

        {letterHistoryRows.length > 0 && (
          <Section title="CL History">
            <div className="space-y-2">
              {letterHistoryRows.slice(0, 10).map((row) => (
                <div key={`${row.eventId}-${row.rawTimestamp}`} className="border-b border-border/70 pb-2 last:border-b-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs text-muted">
                      {row.timestamp} • {row.source}
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => handleLoadLetterVersion(row)}
                        disabled={loadingLetterEventId === row.eventId}
                        className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {loadingLetterEventId === row.eventId ? "Loading..." : "Load"}
                      </button>
                      <button
                        onClick={() => handleCopyLetterVersion(row)}
                        className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold"
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                  <div className="text-sm font-medium text-text mt-1 truncate">{row.subject || "(No subject)"}</div>
                  <div className="text-xs text-muted line-clamp-2">{row.body}</div>
                </div>
              ))}
            </div>
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
                  disabled={!touchNote.trim()}
                  className="px-3 py-1 text-sm bg-accent text-white rounded-full hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer font-semibold"
                >
                  Queue
                </button>
                <button
                  onClick={() => setShowTouchForm(false)}
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
          onClick={() => void commitQueuedChanges()}
          disabled={!hasPendingChanges || isSavingBatch}
          className="px-4 py-2 bg-accent text-white rounded-full hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed text-sm font-semibold cursor-pointer"
        >
          {isSavingBatch ? "Syncing..." : "Sync now"}
        </button>
        <button
          onClick={handlePrepare}
          disabled={isSavingBatch}
          className="px-4 py-2 bg-emerald-100 text-emerald-700 border border-emerald-300 rounded-full hover:bg-emerald-200 text-sm font-semibold cursor-pointer"
        >
          Prepare Application &rarr;
        </button>
        {!roleFit && (
          <button
            onClick={handleScore}
            disabled={scoring || isSavingBatch}
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
