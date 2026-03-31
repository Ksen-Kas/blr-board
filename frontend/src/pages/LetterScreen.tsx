import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  downloadLetterPdf,
  generateLetter,
  getEvents,
  getJob,
} from "../api/jobs";
import type { Job, JobEvent } from "../types/job";
import { applyQueueDraft, getQueuedRowChange, syncPendingRows } from "../state/syncQueue";

type LetterResult = {
  subject: string;
  body: string;
};

type LetterHistoryItem = {
  eventId: number;
  timestamp: string;
  source: string;
  subject: string;
  body: string;
};

function parseStoredLetter(rawLetter: string): LetterResult | null {
  const text = rawLetter.trim();
  if (!text) return null;

  const match = text.match(/^Subject:\s*(.+)\n\n([\s\S]+)$/i);
  if (match) {
    return {
      subject: match[1].trim(),
      body: match[2].trim(),
    };
  }

  return {
    subject: "",
    body: text,
  };
}

function extractJdText(comment: string): string {
  const raw = (comment || "").trim();
  if (!raw) return "";
  if (raw.toLowerCase().startsWith("jd unavailable")) return "";
  return raw;
}

function buildSnapshot(letter: LetterResult): string {
  const subject = (letter.subject || "").trim();
  const body = (letter.body || "").trim();
  return `${subject}\n\n${body}`;
}

function formatEventTimestamp(raw: string): string {
  const value = (raw || "").trim();
  if (!value) return "";
  const normalized = value.includes(" ") ? value.replace(" ", "T") : value;
  const dt = new Date(normalized);
  if (Number.isNaN(dt.getTime())) return value;
  const dd = String(dt.getDate()).padStart(2, "0");
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const yy = String(dt.getFullYear()).slice(-2);
  const hh = String(dt.getHours()).padStart(2, "0");
  const mi = String(dt.getMinutes()).padStart(2, "0");
  return `${dd}-${mm}-${yy} ${hh}:${mi}`;
}

function parseLetterHistory(events: JobEvent[]): LetterHistoryItem[] {
  const allowed = new Set(["letter_saved", "cl_saved", "letter_snapshot"]);
  const items: LetterHistoryItem[] = [];

  for (const ev of events) {
    const eventType = (ev.event_type || "").toLowerCase();
    if (!allowed.has(eventType)) continue;

    try {
      const data = JSON.parse(ev.data || "{}");
      const subject = String(data.subject || "").trim();
      const body = String(data.body || "").trim();
      const source = String(data.source || (eventType === "letter_saved" ? "manual" : "unknown")).trim();
      if (!body) continue;
      items.push({
        eventId: Number(ev.event_id || 0),
        timestamp: ev.timestamp || "",
        subject,
        body,
        source,
      });
    } catch {
      continue;
    }
  }

  return items.sort((a, b) => {
    if (a.eventId && b.eventId) return b.eventId - a.eventId;
    return b.timestamp.localeCompare(a.timestamp);
  });
}

export default function LetterScreen() {
  const { rowNum } = useParams<{ rowNum: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [notes, setNotes] = useState("");
  const [generating, setGenerating] = useState(false);
  const [syncingDraft, setSyncingDraft] = useState(false);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionKind, setActionKind] = useState<"success" | "error" | "info">("info");
  const [result, setResult] = useState<LetterResult | null>(null);
  const [history, setHistory] = useState<LetterHistoryItem[]>([]);
  const [lastSavedSnapshot, setLastSavedSnapshot] = useState("");
  const [pendingCommentUpdate, setPendingCommentUpdate] = useState("");
  const [pendingStatus, setPendingStatus] = useState("");
  const [draftSource, setDraftSource] = useState("manual");
  const loadedRowRef = useRef<number | null>(null);
  const latestDraftRef = useRef({
    job: null as Job | null,
    result: null as LetterResult | null,
    lastSavedSnapshot: "",
    pendingCommentUpdate: "",
    pendingStatus: "",
    draftSource: "manual",
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

    getJob(numericRow).then((loadedJob) => {
      const queued = getQueuedRowChange(loadedJob.row_num);
      const queuedLetter = queued?.letterSave;
      const queuedComment = queued?.updates?.comment;
      const queuedStatus = queued?.updates?.status;
      setJob(loadedJob);
      const stored = parseStoredLetter(loadedJob.cl || "");
      if (queuedStatus) {
        setPendingStatus(String(queuedStatus));
      } else {
        setPendingStatus("");
      }
      setPendingCommentUpdate(
        queuedComment ? String(queuedComment) : "",
      );
      if (stored) {
        setResult({
          subject: queuedLetter?.subject ?? stored.subject,
          body: queuedLetter?.body ?? stored.body,
        });
        setLastSavedSnapshot(buildSnapshot(stored));
        setDraftSource(queuedLetter?.source || "manual");
      } else if (queuedLetter) {
        setResult({ subject: queuedLetter.subject || "", body: queuedLetter.body || "" });
        setLastSavedSnapshot("");
        setDraftSource(queuedLetter.source || "manual");
      }
    });

    getEvents(numericRow)
      .then((events) => setHistory(parseLetterHistory(events)))
      .catch(() => setHistory([]));
  }, [rowNum]);

  useEffect(() => {
    if (!actionMessage) return;
    const timeoutId = window.setTimeout(() => setActionMessage(""), 3500);
    return () => window.clearTimeout(timeoutId);
  }, [actionMessage, actionKind]);

  const isDirty = useMemo(() => {
    if (!result) return false;
    return buildSnapshot(result) !== lastSavedSnapshot;
  }, [result, lastSavedSnapshot]);

  const enqueueDraft = useCallback((overrideStatus?: string) => {
    if (!job) return false;
    const setUpdates: Partial<Job> = {};
    const clearUpdateKeys: Array<keyof Job> = [];

    const comment = pendingCommentUpdate.trim();
    if (comment && comment !== (job.comment || "").trim()) {
      setUpdates.comment = comment;
    } else {
      clearUpdateKeys.push("comment");
    }

    const currentStatus = job.status || "";
    const nextStatus = (overrideStatus || pendingStatus || "").trim();
    if (nextStatus && nextStatus !== currentStatus) {
      setUpdates.status = nextStatus;
    } else {
      clearUpdateKeys.push("status");
    }

    const letterBody = (result?.body || "").trim();
    const hasLetter = Boolean(result) && isDirty && Boolean(letterBody);

    applyQueueDraft(job.row_num, {
      setUpdates: Object.keys(setUpdates).length > 0 ? setUpdates : undefined,
      clearUpdateKeys: clearUpdateKeys.length > 0 ? clearUpdateKeys : undefined,
      letterSave: hasLetter
        ? {
            subject: (result?.subject || "").trim(),
            body: letterBody,
            source: draftSource || "manual",
          }
        : null,
    });

    return Object.keys(setUpdates).length > 0 || hasLetter;
  }, [job, pendingCommentUpdate, pendingStatus, result, isDirty, draftSource]);

  useEffect(() => {
    latestDraftRef.current = {
      job,
      result,
      lastSavedSnapshot,
      pendingCommentUpdate,
      pendingStatus,
      draftSource,
    };
  }, [job, result, lastSavedSnapshot, pendingCommentUpdate, pendingStatus, draftSource]);

  useEffect(() => {
    enqueueDraft();
  }, [enqueueDraft]);

  useEffect(() => {
    return () => {
      const latest = latestDraftRef.current;
      if (!latest.job) return;
      const setUpdates: Partial<Job> = {};
      const clearUpdateKeys: Array<keyof Job> = [];
      const comment = latest.pendingCommentUpdate.trim();
      if (comment && comment !== (latest.job.comment || "").trim()) {
        setUpdates.comment = comment;
      } else {
        clearUpdateKeys.push("comment");
      }
      const nextStatus = latest.pendingStatus.trim();
      if (nextStatus && nextStatus !== (latest.job.status || "")) {
        setUpdates.status = nextStatus;
      } else {
        clearUpdateKeys.push("status");
      }
      const hasDirtyLetter =
        Boolean(latest.result) &&
        buildSnapshot(latest.result as LetterResult) !== latest.lastSavedSnapshot &&
        Boolean((latest.result?.body || "").trim());
      applyQueueDraft(latest.job.row_num, {
        setUpdates: Object.keys(setUpdates).length > 0 ? setUpdates : undefined,
        clearUpdateKeys: clearUpdateKeys.length > 0 ? clearUpdateKeys : undefined,
        letterSave: hasDirtyLetter
          ? {
              subject: (latest.result?.subject || "").trim(),
              body: (latest.result?.body || "").trim(),
              source: latest.draftSource || "manual",
            }
          : null,
      });
      void syncPendingRows([latest.job.row_num]);
    };
  }, [rowNum]);

  const syncRowNow = async (options: { silent?: boolean } = {}): Promise<boolean> => {
    if (!job || syncingDraft) return false;
    if (result && isDirty && !(result.body || "").trim()) {
      setActionKind("error");
      setActionMessage("Letter body is empty.");
      return false;
    }
    const hasDraft = enqueueDraft();
    if (!hasDraft) {
      if (!options.silent) {
        setActionKind("info");
        setActionMessage("Nothing to sync.");
      }
      return true;
    }
    setSyncingDraft(true);
    try {
      const res = await syncPendingRows([job.row_num]);
      if (res.failedRows > 0) {
        setActionKind("error");
        setActionMessage("Sync failed. Draft stays queued.");
        return false;
      }
      if (result) {
        setLastSavedSnapshot(buildSnapshot(result));
      }
      setJob((prev) =>
        prev
          ? {
              ...prev,
              status: pendingStatus || prev.status,
              comment: pendingCommentUpdate || prev.comment,
              cl: result
                ? ((result.subject || "").trim()
                    ? `Subject: ${(result.subject || "").trim()}\n\n${(result.body || "").trim()}`
                    : (result.body || "").trim())
                : prev.cl,
            }
          : prev,
      );
      setPendingCommentUpdate("");
      setPendingStatus("");
      if (!options.silent) {
        setActionKind("success");
        setActionMessage("Draft synced.");
      }
      return true;
    } catch {
      setActionKind("error");
      setActionMessage("Sync failed. Draft stays queued.");
      return false;
    } finally {
      setSyncingDraft(false);
    }
  };

  const persistLetter = async (
    payload: { subject: string; body: string; source: string },
    options: { silent?: boolean } = {},
  ): Promise<boolean> => {
    if (!job || syncingDraft) return false;
    const subject = (payload.subject || "").trim();
    const body = (payload.body || "").trim();
    if (!body) {
      if (!options.silent) {
        setActionKind("error");
        setActionMessage("Letter body is empty.");
      }
      return false;
    }

    setSyncingDraft(true);
    if (!options.silent) {
      setActionKind("info");
      setActionMessage("Queueing letter draft...");
    }

    try {
      applyQueueDraft(job.row_num, {
        letterSave: {
          subject,
          body,
          source: payload.source,
        },
      });
      setHistory((prev) => {
        const nextItem: LetterHistoryItem = {
          eventId: Date.now(),
          timestamp: new Date().toISOString().replace("T", " ").slice(0, 19),
          source: payload.source,
          subject,
          body,
        };
        return [nextItem, ...prev].slice(0, 30);
      });
      setDraftSource(payload.source || "manual");

      const syncRes = await syncPendingRows([job.row_num]);
      if (syncRes.failedRows > 0) {
        if (!options.silent) {
          setActionKind("error");
          setActionMessage("Sync failed. Draft stays queued.");
        }
        return false;
      }

      setLastSavedSnapshot(buildSnapshot({ subject, body }));

      if (!options.silent) {
        setActionKind("success");
        setActionMessage("Letter synced.");
      }
      return true;
    } catch {
      if (!options.silent) {
        setActionKind("error");
        setActionMessage("Failed to sync letter draft.");
      }
      return false;
    } finally {
      setSyncingDraft(false);
    }
  };

  const handleGenerate = async () => {
    if (!job) return;
    const jdText = extractJdText(job.comment || "");
    if (!jdText && !job.source?.trim()) {
      setError("To generate a letter, add JD text in the job card first.");
      return;
    }

    setGenerating(true);
    setError("");
    try {
      const res = await generateLetter({
        jd_text: jdText,
        source_url: jdText ? "" : (job.source || ""),
        notes,
      });

      const generated: LetterResult = {
        subject: res.subject || "",
        body: res.body || "",
      };
      setResult(generated);
      setDraftSource("generated");

      const updates: Partial<Job> = {};
      if (!jdText && (res.jd_text_used || "").trim()) {
        updates.comment = (res.jd_text_used || "").trim();
      }
      if (Object.keys(updates).length > 0) {
        setJob((prev) => (prev ? { ...prev, ...updates } : prev));
        setPendingCommentUpdate(updates.comment || "");
      }

      const saved = await persistLetter(
        {
          subject: generated.subject,
          body: generated.body,
          source: "generated",
        },
        { silent: true },
      );
      if (saved) {
        setActionKind("success");
        setActionMessage("Letter generated and synced.");
      } else {
        setActionKind("info");
        setActionMessage("Letter generated and queued.");
      }
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || "Letter generation failed")
          : "Letter generation failed. Check that the backend is running and Claude API key is configured.";
      setError(msg);
    } finally {
      setGenerating(false);
    }
  };

  const handleDone = async () => {
    if (!job) return;

    if (result && isDirty && !(result.body || "").trim()) {
      setError("Letter body is empty.");
      return;
    }

    if (result && isDirty) {
      applyQueueDraft(job.row_num, {
        letterSave: {
          subject: result.subject,
          body: result.body,
          source: "manual",
        },
      });
    }

    setPendingStatus("Applied");
    applyQueueDraft(job.row_num, { setUpdates: { status: "Applied" } });
    const synced = await syncRowNow({ silent: true });
    if (!synced) {
      setError("Failed to sync latest changes. Try again.");
      return;
    }
    navigate(`/job/${rowNum}`);
  };

  const handleCopyAll = () => {
    if (!result) return;
    if (!navigator.clipboard) {
      setActionKind("error");
      setActionMessage("Clipboard not available in this browser.");
      return;
    }
    navigator.clipboard
      .writeText(`Subject: ${result.subject}\n\n${result.body}`)
      .then(() => {
        setActionKind("success");
        setActionMessage("Letter copied with subject.");
      })
      .catch(() => {
        setActionKind("error");
        setActionMessage("Copy failed.");
      });
  };

  const handleCopyBody = () => {
    if (!result) return;
    if (!navigator.clipboard) {
      setActionKind("error");
      setActionMessage("Clipboard not available in this browser.");
      return;
    }
    navigator.clipboard
      .writeText(result.body)
      .then(() => {
        setActionKind("success");
        setActionMessage("Letter body copied.");
      })
      .catch(() => {
        setActionKind("error");
        setActionMessage("Copy failed.");
      });
  };

  const handleDownloadPdf = async () => {
    if (!result || !job) return;
    try {
      setActionKind("info");
      setActionMessage("Preparing PDF...");
      await downloadLetterPdf({
        subject: result.subject,
        body: result.body,
        company: job.company,
        role: job.role,
      });
      setActionKind("success");
      setActionMessage("PDF download started.");
    } catch {
      setActionKind("error");
      setActionMessage("PDF generation failed. Try again or use Copy.");
    }
  };

  const handleRegenerate = () => {
    setResult(null);
    setError("");
  };

  const handleSaveCurrent = async () => {
    if (!result) return;
    setDraftSource("manual");
    await persistLetter({
      subject: result.subject,
      body: result.body,
      source: "manual",
    });
  };

  const handleLoadHistory = (item: LetterHistoryItem) => {
    setResult({ subject: item.subject, body: item.body });
    setDraftSource("manual");
    setActionKind("info");
    setActionMessage("Loaded from history. It will sync automatically when you leave.");
  };

  const handleCopyHistory = (item: LetterHistoryItem) => {
    if (!navigator.clipboard) {
      setActionKind("error");
      setActionMessage("Clipboard not available in this browser.");
      return;
    }
    navigator.clipboard
      .writeText(`Subject: ${item.subject}\n\n${item.body}`)
      .then(() => {
        setActionKind("success");
        setActionMessage("History version copied.");
      })
      .catch(() => {
        setActionKind("error");
        setActionMessage("Copy failed.");
      });
  };

  if (!job) return <div className="p-6 text-muted">Loading...</div>;
  const hasJdText = Boolean(extractJdText(job.comment || ""));
  const canGenerate = hasJdText || Boolean(job.source?.trim());

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <button
        onClick={() => navigate(`/job/${rowNum}`)}
        className="text-accent hover:text-accent-hover text-sm mb-4 inline-block cursor-pointer font-semibold"
      >
        &larr; {job.company} — {job.role}
      </button>

      {!result && !generating && (
        <div className="space-y-4">
          {!canGenerate && (
            <div className="border border-amber-200 rounded-xl p-4 bg-amber-50 text-amber-800 text-sm">
              Letter cannot be generated yet. Add JD text in Job Card first (Summary / Comment or Scoring Input), then come back.
            </div>
          )}
          {!hasJdText && Boolean(job.source?.trim()) && (
            <div className="border border-blue-200 rounded-xl p-4 bg-blue-50 text-blue-800 text-sm">
              JD text is missing in card comment. The backend will try to parse the source URL for generation.
            </div>
          )}
          <div className="surface-card p-4">
            <label className="block text-sm font-semibold text-muted mb-2">
              Notes for the letter (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full border border-border bg-input rounded-xl p-3 text-sm text-text resize-none placeholder:text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/20"
              rows={3}
              placeholder="What to emphasize? Leave empty — Joe generates by canon rules."
            />
          </div>
          <button
            onClick={handleGenerate}
            disabled={!canGenerate}
            className="px-6 py-2.5 bg-accent text-white rounded-full hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed font-semibold cursor-pointer"
          >
            Generate Letter
          </button>
        </div>
      )}

      {generating && (
        <div className="surface-card p-6 text-center">
          <div className="text-muted">Generating cover letter...</div>
        </div>
      )}

      {error && (
        <div className="border border-red-200 rounded-xl p-4 bg-red-50 text-red-700 text-sm mb-4">
          {error}
        </div>
      )}

      {actionMessage && (
        <div
          className={`mb-4 border rounded-lg p-3 text-sm ${
            actionKind === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : actionKind === "error"
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-border bg-surface text-muted"
          }`}
        >
          {actionMessage}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="surface-card overflow-hidden">
            <div className="bg-surface-alt px-4 py-2 text-sm font-semibold text-muted">Subject</div>
            <div className="px-4 py-3">
              <input
                value={result.subject}
                onChange={(e) => setResult((prev) => (prev ? { ...prev, subject: e.target.value } : prev))}
                className="w-full border border-border bg-input rounded-xl p-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/20"
                placeholder="Letter subject"
              />
            </div>
          </div>

          <div className="surface-card overflow-hidden">
            <div className="bg-surface-alt px-4 py-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-muted">
                Letter {isDirty ? <span className="text-amber-600">• unsaved changes</span> : null}
              </span>
              <div className="flex gap-3">
                <button
                  onClick={handleDownloadPdf}
                  className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold"
                >
                  Download PDF
                </button>
                <button onClick={handleCopyBody} className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold">
                  Copy body
                </button>
                <button onClick={handleCopyAll} className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold">
                  Copy with subject
                </button>
              </div>
            </div>
            <div className="px-4 py-3">
              <textarea
                value={result.body}
                onChange={(e) => setResult((prev) => (prev ? { ...prev, body: e.target.value } : prev))}
                rows={14}
                className="w-full border border-border bg-input rounded-xl p-3 text-sm leading-relaxed text-text resize-y focus:outline-none focus:ring-2 focus:ring-accent/20"
                placeholder="Write your custom letter here"
              />
            </div>
          </div>

          <div className="text-xs text-muted">
            {result.body.trim() ? result.body.trim().split(/\s+/).length : 0} words
          </div>

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              onClick={handleSaveCurrent}
              disabled={syncingDraft || !result.body.trim()}
              className="px-4 py-2 border border-border rounded-full hover:bg-surface-alt text-sm cursor-pointer text-muted hover:text-text font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {syncingDraft ? "Syncing..." : "Sync now"}
            </button>
            <button
              onClick={handleDone}
              className="px-4 py-2 bg-emerald-100 text-emerald-700 border border-emerald-300 rounded-full hover:bg-emerald-200 text-sm font-semibold cursor-pointer"
            >
              Done &rarr; Mark Applied
            </button>
            <button
              onClick={() => navigate(`/job/${rowNum}`)}
              className="px-4 py-2 bg-surface-alt rounded-full hover:bg-border text-sm cursor-pointer text-muted font-medium"
            >
              Done (keep status)
            </button>
            <button
              onClick={handleRegenerate}
              className="px-4 py-2 border border-border rounded-full hover:bg-surface-alt text-sm cursor-pointer text-muted hover:text-text font-medium"
            >
              Regenerate
            </button>
          </div>

          {history.length > 0 && (
            <div className="surface-card overflow-hidden">
              <div className="bg-surface-alt px-4 py-2 text-sm font-semibold text-muted">Saved CL History</div>
              <div className="divide-y divide-border/70">
                {history.slice(0, 12).map((item) => (
                  <div key={`${item.eventId}-${item.timestamp}`} className="px-4 py-3 flex flex-col gap-2">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-xs text-muted">
                        {formatEventTimestamp(item.timestamp)} • {item.source}
                      </div>
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => handleLoadHistory(item)}
                          className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold"
                        >
                          Load
                        </button>
                        <button
                          onClick={() => handleCopyHistory(item)}
                          className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold"
                        >
                          Copy
                        </button>
                      </div>
                    </div>
                    <div className="text-sm font-medium text-text truncate">{item.subject || "(No subject)"}</div>
                    <div className="text-xs text-muted line-clamp-2">{item.body}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
