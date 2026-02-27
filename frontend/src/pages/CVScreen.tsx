import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getJob, tailorCV, updateJob, downloadCvPdf } from "../api/jobs";
import type { Job } from "../types/job";

export default function CVScreen() {
  const { rowNum } = useParams<{ rowNum: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionKind, setActionKind] = useState<"success" | "error" | "info">("info");
  const [result, setResult] = useState<{
    tailored_cv: string;
    changes_summary: string;
    canon_check: string;
  } | null>(null);
  const [showRetailorInput, setShowRetailorInput] = useState(false);
  const [retailorNotes, setRetailorNotes] = useState("");

  useEffect(() => {
    if (rowNum) getJob(Number(rowNum)).then(setJob);
  }, [rowNum]);

  const handleTailor = async () => {
    if (!job) return;
    setTailoring(true);
    setError("");
    try {
      const jdText = job.comment || `${job.role} at ${job.company}, ${job.region}`;
      const res = await tailorCV(jdText);
      setResult(res);
      await updateJob(job.row_num, { cv: res.changes_summary });
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || "CV tailoring failed")
          : "CV tailoring failed. Check that the backend is running and Claude API key is configured.";
      setError(msg);
    } finally {
      setTailoring(false);
    }
  };

  const handleRetailor = async () => {
    if (!job) return;
    setTailoring(true);
    setError("");
    setShowRetailorInput(false);
    try {
      const jdText = job.comment || `${job.role} at ${job.company}, ${job.region}`;
      const fullText = retailorNotes
        ? `${jdText}\n\n[Adjustments requested]: ${retailorNotes}`
        : jdText;
      const res = await tailorCV(fullText);
      setResult(res);
      await updateJob(job.row_num, { cv: res.changes_summary });
      setRetailorNotes("");
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail || "Re-tailoring failed")
          : "Re-tailoring failed.";
      setError(msg);
    } finally {
      setTailoring(false);
    }
  };

  const handleCopyCV = () => {
    if (!result) return;
    if (!navigator.clipboard) {
      setActionKind("error");
      setActionMessage("Clipboard not available in this browser.");
      return;
    }
    navigator.clipboard
      .writeText(result.tailored_cv)
      .then(() => {
        setActionKind("success");
        setActionMessage("Full CV copied.");
      })
      .catch(() => {
        setActionKind("error");
        setActionMessage("Copy failed.");
      });
  };

  const handleCopyChanges = () => {
    if (!result) return;
    if (!navigator.clipboard) {
      setActionKind("error");
      setActionMessage("Clipboard not available in this browser.");
      return;
    }
    navigator.clipboard
      .writeText(result.changes_summary)
      .then(() => {
        setActionKind("success");
        setActionMessage("Changes copied.");
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
      await downloadCvPdf({
        tailored_cv: result.tailored_cv,
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

  if (!job) return <div className="p-6 text-muted">Loading...</div>;

  // Canon check color
  const canonColor = result
    ? result.canon_check.startsWith("OK")
      ? "bg-emerald-50 border-emerald-200 text-emerald-700"
      : result.canon_check.startsWith("WARN")
        ? "bg-amber-50 border-amber-200 text-amber-700"
        : "bg-red-50 border-red-200 text-red-700"
    : "";

  // Joe recommendation based on scoring
  const fitLower = job.role_fit?.toLowerCase() || "";
  const recommendation = fitLower === "strong"
    ? "Canon CV is likely a good match. Tailoring is optional."
    : fitLower === "stretch" || fitLower === "partial"
      ? "Tailoring recommended — highlight relevant experience for this role."
      : "";

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <button
        onClick={() => navigate(`/job/${rowNum}`)}
        className="text-accent hover:text-accent-hover text-sm mb-4 inline-block cursor-pointer font-semibold"
      >
        &larr; {job.company} — {job.role}
      </button>

      {/* Recommendation */}
      {recommendation && !result && !tailoring && (
        <div className="mb-4 p-3 border border-accent/30 rounded-xl bg-emerald-50 text-accent text-sm">
          {recommendation}
        </div>
      )}

      {/* Before tailoring — two buttons */}
      {!result && !tailoring && (
        <div className="surface-card p-6 text-center space-y-4">
          <span className="tag-chip">CV Tailoring</span>
          <p className="text-muted">
            Joe will make minimal adjustments to your canonical resume for this role.
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => navigate(`/job/${rowNum}/letter`)}
              className="px-5 py-2.5 border border-border rounded-full hover:bg-surface-alt text-sm cursor-pointer text-muted hover:text-text font-medium"
            >
              Use Canon CV
            </button>
            <button
              onClick={handleTailor}
              className="px-6 py-2.5 bg-accent text-white rounded-full hover:bg-accent-hover font-semibold cursor-pointer"
            >
              Tailor CV &rarr;
            </button>
          </div>
        </div>
      )}

      {/* Loading */}
      {tailoring && (
        <div className="surface-card p-6 text-center">
          <div className="text-muted">Tailoring CV against JD...</div>
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

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Canon check */}
          <div className={`p-3 border rounded-lg text-sm ${canonColor}`}>
            <strong>CANON CHECK:</strong> {result.canon_check}
          </div>

          {/* Changes */}
          <div className="surface-card overflow-hidden">
            <div className="bg-surface-alt px-4 py-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-muted">Changes</span>
              <button
                onClick={handleCopyChanges}
                className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold"
              >
                Copy changes
              </button>
            </div>
            <div className="px-4 py-3">
              <pre className="whitespace-pre-wrap text-sm leading-relaxed text-text">
                {result.changes_summary}
              </pre>
            </div>
          </div>

          {/* Full tailored CV */}
          <div className="surface-card overflow-hidden">
            <div className="bg-surface-alt px-4 py-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-muted">Tailored CV</span>
              <div className="flex gap-3">
                <button
                  onClick={handleDownloadPdf}
                  className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold"
                >
                  Download PDF
                </button>
                <button
                  onClick={handleCopyCV}
                  className="text-xs text-accent hover:text-accent-hover cursor-pointer font-semibold"
                >
                  Copy full CV
                </button>
              </div>
            </div>
            <div className="px-4 py-3 max-h-[500px] overflow-y-auto">
              <pre className="whitespace-pre-wrap text-sm leading-relaxed text-text">
                {result.tailored_cv}
              </pre>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => navigate(`/job/${rowNum}/letter`)}
              className="px-4 py-2 bg-emerald-100 text-emerald-700 border border-emerald-300 rounded-full hover:bg-emerald-200 text-sm font-semibold cursor-pointer"
            >
              Next: Letter &rarr;
            </button>
            <button
              onClick={() => setShowRetailorInput(true)}
              className="px-4 py-2 border border-border rounded-full hover:bg-surface-alt text-sm cursor-pointer text-muted hover:text-text font-medium"
            >
              Re-tailor
            </button>
          </div>

          {/* Re-tailor input */}
          {showRetailorInput && (
            <div className="surface-card p-4 space-y-3">
              <label className="block text-sm font-semibold text-muted">
                What to change?
              </label>
              <textarea
                value={retailorNotes}
                onChange={(e) => setRetailorNotes(e.target.value)}
                rows={3}
                placeholder="e.g., emphasize data analytics more, remove mention of X..."
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
                  onClick={() => { setShowRetailorInput(false); setRetailorNotes(""); }}
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
