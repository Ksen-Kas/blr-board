import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getJob, generateLetter, updateJob, downloadLetterPdf } from "../api/jobs";
import type { Job } from "../types/job";

function parseStoredLetter(rawLetter: string): { subject: string; body: string } | null {
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

export default function LetterScreen() {
  const { rowNum } = useParams<{ rowNum: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [notes, setNotes] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionKind, setActionKind] = useState<"success" | "error" | "info">("info");
  const [result, setResult] = useState<{
    subject: string;
    body: string;
  } | null>(null);

  useEffect(() => {
    if (!rowNum) return;
    getJob(Number(rowNum)).then((loadedJob) => {
      setJob(loadedJob);
      const stored = parseStoredLetter(loadedJob.cl || "");
      if (stored) setResult(stored);
    });
  }, [rowNum]);

  useEffect(() => {
    if (!actionMessage) return;
    const timeoutId = window.setTimeout(() => setActionMessage(""), 3500);
    return () => window.clearTimeout(timeoutId);
  }, [actionMessage, actionKind]);

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
      setResult({ subject: res.subject, body: res.body });
      const updates: Partial<Job> = {
        cl: `Subject: ${res.subject}\n\n${res.body}`,
      };
      if (!jdText && (res.jd_text_used || "").trim()) {
        updates.comment = (res.jd_text_used || "").trim();
      }
      await updateJob(job.row_num, updates);
      setJob((prev) => (prev ? { ...prev, ...updates } : prev));
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
    await updateJob(job.row_num, { status: "Applied" });
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

      {/* Input: notes */}
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

      {/* Loading */}
      {generating && (
        <div className="surface-card p-6 text-center">
          <div className="text-muted">Generating cover letter...</div>
        </div>
      )}

      {/* Error */}
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

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Subject */}
          <div className="surface-card overflow-hidden">
            <div className="bg-surface-alt px-4 py-2 text-sm font-semibold text-muted">Subject</div>
            <div className="px-4 py-3">
              <p className="text-sm font-medium text-text">{result.subject || "No subject saved"}</p>
            </div>
          </div>

          {/* Body */}
          <div className="surface-card overflow-hidden">
            <div className="bg-surface-alt px-4 py-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-muted">Letter</span>
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
              <pre className="whitespace-pre-wrap text-sm leading-relaxed text-text">{result.body}</pre>
            </div>
          </div>

          {/* Word count */}
          <div className="text-xs text-muted">
            {result.body.split(/\s+/).length} words
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
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
        </div>
      )}
    </div>
  );
}
