import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getJob,
  tailorCV,
  updateJob,
  downloadCvPdf,
  downloadCanonicalCvPdf,
  getTailoredCvPreviewHtml,
} from "../api/jobs";
import type { Job } from "../types/job";

type TrackLine = { type: "same" | "added" | "removed"; text: string };
type TrackSection = { section: string; lines: TrackLine[] };

type TailorResult = {
  tailored_cv: string;
  changes_summary: string;
  canon_check: string;
  track_changes?: TrackSection[];
};

export default function CVScreen() {
  const { rowNum } = useParams<{ rowNum: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionKind, setActionKind] = useState<"success" | "error" | "info">("info");
  const [result, setResult] = useState<TailorResult | null>(null);
  const [showRetailorInput, setShowRetailorInput] = useState(false);
  const [retailorNotes, setRetailorNotes] = useState("");
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (rowNum) getJob(Number(rowNum)).then(setJob);
  }, [rowNum]);

  useEffect(() => {
    if (!actionMessage) return;
    const timeoutId = window.setTimeout(() => setActionMessage(""), 3500);
    return () => window.clearTimeout(timeoutId);
  }, [actionMessage, actionKind]);

  const runTailor = async (extraNotes = "") => {
    if (!job) return;
    setTailoring(true);
    setError("");
    try {
      const jdText = job.comment || `${job.role} at ${job.company}, ${job.region}`;
      const fullText = extraNotes
        ? `${jdText}\n\n[Adjustments requested]: ${extraNotes}`
        : jdText;
      const res = await tailorCV(fullText);
      setResult(res);
      setPreviewLoading(true);
      try {
        const html = await getTailoredCvPreviewHtml(res.tailored_cv);
        setPreviewHtml(html);
      } catch {
        setPreviewHtml("");
      } finally {
        setPreviewLoading(false);
      }
      await updateJob(job.row_num, { cv: res.changes_summary });
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || "CV tailoring failed")
          : "CV tailoring failed. Check backend and template settings.";
      setError(msg);
    } finally {
      setTailoring(false);
    }
  };

  const handleTailor = async () => {
    setActionMessage("");
    await runTailor();
  };

  const handleRetailor = async () => {
    setActionMessage("");
    setShowRetailorInput(false);
    const notes = retailorNotes.trim();
    setRetailorNotes("");
    await runTailor(notes);
  };

  const handleUseCanon = async () => {
    if (!job) return;
    try {
      setActionKind("info");
      setActionMessage("Preparing canonical PDF...");
      await downloadCanonicalCvPdf({ company: job.company, role: job.role });
      setActionKind("success");
      setActionMessage("Canonical PDF download started.");
    } catch {
      setActionKind("error");
      setActionMessage("Failed to download canonical PDF.");
    }
  };

  const handleDownloadTailored = async () => {
    if (!result || !job) return;
    try {
      setActionKind("info");
      setActionMessage("Preparing tailored PDF...");
      await downloadCvPdf({
        tailored_cv: result.tailored_cv,
        company: job.company,
        role: job.role,
      });
      setActionKind("success");
      setActionMessage("Tailored PDF download started.");
    } catch {
      setActionKind("error");
      setActionMessage("PDF generation failed.");
    }
  };

  if (!job) return <div className="p-6 text-muted">Loading...</div>;

  const trackSections = result?.track_changes || [];
  const actionStatusClass =
    actionKind === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : actionKind === "error"
        ? "border-red-200 bg-red-50 text-red-700"
        : "border-border bg-surface text-muted";

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <button
        onClick={() => navigate(`/job/${rowNum}`)}
        className="text-accent hover:text-accent-hover text-sm mb-4 inline-block cursor-pointer font-semibold"
      >
        &larr; {job.company} — {job.role}
      </button>

      {!result && !tailoring && (
        <div className="surface-card p-6">
          <h1 className="text-2xl font-extrabold tracking-tight text-text">
            Resume for {job.company} — {job.role}
          </h1>
          <p className="text-sm text-muted mt-2">
            Choose an action: download canonical PDF or tailor the resume for this role.
          </p>
          <div className="flex flex-wrap gap-3 mt-6">
            <button
              onClick={handleUseCanon}
              className="px-5 py-2.5 border border-border rounded-full hover:bg-surface-alt text-sm cursor-pointer text-muted hover:text-text font-semibold"
            >
              Use Canon CV
            </button>
            <button
              onClick={handleTailor}
              className="px-5 py-2.5 bg-accent text-white rounded-full hover:bg-accent-hover text-sm font-semibold cursor-pointer"
            >
              Tailor CV &rarr;
            </button>
          </div>
          {actionMessage && (
            <div className={`mt-4 inline-flex items-center rounded-full border px-3 py-1 text-sm ${actionStatusClass}`}>
              Status: {actionMessage}
            </div>
          )}
        </div>
      )}

      {tailoring && (
        <div className="surface-card p-6 text-center">
          <div className="text-muted">Tailoring CV against JD...</div>
        </div>
      )}

      {error && (
        <div className="mt-4 border border-red-200 rounded-xl p-4 bg-red-50 text-red-700 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-5 space-y-4">
          <div className="surface-card overflow-hidden">
            <div className="bg-surface-alt border-b border-border px-4 py-3 text-sm font-bold text-text uppercase tracking-wide">
              Preview
            </div>
            <div className="p-4">
              <div className="text-xs text-muted mb-2">
                Green highlight marks added or changed lines.
              </div>
              {previewLoading ? (
                <div className="text-sm text-muted">Preparing HTML preview...</div>
              ) : previewHtml ? (
                <iframe
                  title="Tailored CV preview"
                  srcDoc={previewHtml}
                  className="w-full h-[720px] border border-border rounded-xl bg-white"
                />
              ) : (
                <div className="text-sm text-muted">Preview unavailable. You can still download the PDF.</div>
              )}
            </div>
          </div>

          {(trackSections.length > 0 ? trackSections : [{ section: "Changes", lines: [] }]).map((section) => (
            <div key={section.section} className="surface-card overflow-hidden">
              <div className="bg-surface-alt border-b border-border px-4 py-3 text-sm font-bold text-text uppercase tracking-wide">
                {section.section}
              </div>
              <div className="p-4 space-y-2">
                {section.lines.length > 0 ? (
                  section.lines.map((line, idx) => (
                    <div
                      key={`${section.section}-${idx}`}
                      className={`px-2 py-1 rounded text-sm ${
                        line.type === "added"
                          ? "bg-emerald-100 text-emerald-800"
                          : line.type === "removed"
                            ? "bg-red-100 text-red-700 line-through"
                            : "text-text"
                      }`}
                    >
                      <span className="mr-2 text-muted">●</span>
                      {line.text}
                    </div>
                  ))
                ) : (
                  <pre className="whitespace-pre-wrap text-sm text-text">{result.changes_summary}</pre>
                )}
              </div>
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button
              onClick={handleDownloadTailored}
              className="px-4 py-2 bg-accent text-white rounded-full hover:bg-accent-hover text-sm font-semibold cursor-pointer"
            >
              Download PDF
            </button>
            <button
              onClick={() => setShowRetailorInput(true)}
              className="px-4 py-2 border border-border rounded-full hover:bg-surface-alt text-sm cursor-pointer text-muted hover:text-text font-medium"
            >
              Re-tailor
            </button>
            <button
              onClick={() => navigate(`/job/${rowNum}/letter`)}
              className="px-4 py-2 bg-emerald-100 text-emerald-700 border border-emerald-300 rounded-full hover:bg-emerald-200 text-sm font-semibold cursor-pointer"
            >
              Next: Letter &rarr;
            </button>
            {actionMessage && (
              <span className={`inline-flex items-center rounded-full border px-3 py-1 text-sm ${actionStatusClass}`}>
                PDF status: {actionMessage}
              </span>
            )}
          </div>

          {showRetailorInput && (
            <div className="surface-card p-4 space-y-3">
              <label className="block text-sm font-semibold text-muted">What should be changed?</label>
              <textarea
                value={retailorNotes}
                onChange={(e) => setRetailorNotes(e.target.value)}
                rows={3}
                placeholder="For example: emphasize the reservoir simulation governance block."
                className="w-full border border-border bg-input rounded-xl px-3 py-2 text-sm text-text resize-none placeholder:text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleRetailor}
                  className="px-4 py-2 bg-accent text-white rounded-full hover:bg-accent-hover text-sm font-semibold cursor-pointer"
                >
                  Apply
                </button>
                <button
                  onClick={() => {
                    setShowRetailorInput(false);
                    setRetailorNotes("");
                  }}
                  className="px-4 py-2 border border-border rounded-full hover:bg-surface-alt text-sm cursor-pointer text-muted"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
