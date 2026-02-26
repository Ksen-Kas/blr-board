import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getJob, generateLetter, updateJob, downloadLetterPdf } from "../api/jobs";
import type { Job } from "../types/job";

export default function LetterScreen() {
  const { rowNum } = useParams<{ rowNum: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [notes, setNotes] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    subject: string;
    body: string;
  } | null>(null);

  useEffect(() => {
    if (rowNum) getJob(Number(rowNum)).then(setJob);
  }, [rowNum]);

  const handleGenerate = async () => {
    if (!job) return;
    setGenerating(true);
    setError("");
    try {
      const jdText = job.comment || `${job.role} at ${job.company}, ${job.region}`;
      const res = await generateLetter(jdText, notes);
      setResult(res);
      await updateJob(job.row_num, { cl: `Subject: ${res.subject}\n\n${res.body}` });
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
    if (result) {
      navigator.clipboard.writeText(`Subject: ${result.subject}\n\n${result.body}`);
    }
  };

  const handleCopyBody = () => {
    if (result) navigator.clipboard.writeText(result.body);
  };

  const handleRegenerate = () => {
    setResult(null);
    setError("");
  };

  if (!job) return <div className="p-6 text-muted">Loading...</div>;

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <button
        onClick={() => navigate(`/job/${rowNum}`)}
        className="text-accent hover:text-accent-hover text-sm mb-4 inline-block cursor-pointer"
      >
        &larr; {job.company} — {job.role}
      </button>

      {/* Input: notes */}
      {!result && !generating && (
        <div className="space-y-4">
          <div className="border border-border rounded-lg p-4 bg-surface">
            <label className="block text-sm font-medium text-muted mb-2">
              Notes for the letter (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full border border-border bg-input rounded-lg p-3 text-sm text-text resize-none placeholder:text-muted/50 focus:outline-none focus:ring-2 focus:ring-accent/30"
              rows={3}
              placeholder="What to emphasize? Leave empty — Joe generates by canon rules."
            />
          </div>
          <button
            onClick={handleGenerate}
            className="px-6 py-2.5 bg-accent text-bg rounded-lg hover:bg-accent-hover font-medium cursor-pointer"
          >
            Generate Letter
          </button>
        </div>
      )}

      {/* Loading */}
      {generating && (
        <div className="border border-border rounded-lg p-6 text-center bg-surface">
          <div className="animate-pulse text-muted">Generating cover letter...</div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border border-red-500/30 rounded-lg p-4 bg-red-500/10 text-red-300 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Subject */}
          <div className="border border-border rounded-lg overflow-hidden">
            <div className="bg-surface px-4 py-2 text-sm font-medium text-muted">Subject</div>
            <div className="px-4 py-3">
              <p className="text-sm font-medium text-text">{result.subject}</p>
            </div>
          </div>

          {/* Body */}
          <div className="border border-border rounded-lg overflow-hidden">
            <div className="bg-surface px-4 py-2 flex items-center justify-between">
              <span className="text-sm font-medium text-muted">Letter</span>
              <div className="flex gap-3">
                <button
                  onClick={() =>
                    result &&
                    job &&
                    downloadLetterPdf({
                      subject: result.subject,
                      body: result.body,
                      company: job.company,
                      role: job.role,
                    })
                  }
                  className="text-xs text-accent hover:text-accent-hover cursor-pointer"
                >
                  Download PDF
                </button>
                <button onClick={handleCopyBody} className="text-xs text-accent hover:text-accent-hover cursor-pointer">
                  Copy body
                </button>
                <button onClick={handleCopyAll} className="text-xs text-accent hover:text-accent-hover cursor-pointer">
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
              className="px-4 py-2 bg-green-500/20 text-green-300 border border-green-500/30 rounded-lg hover:bg-green-500/30 text-sm font-medium cursor-pointer"
            >
              Done &rarr; Mark Applied
            </button>
            <button
              onClick={() => navigate(`/job/${rowNum}`)}
              className="px-4 py-2 bg-surface-alt rounded-lg hover:bg-border text-sm cursor-pointer text-muted"
            >
              Done (keep status)
            </button>
            <button
              onClick={handleRegenerate}
              className="px-4 py-2 border border-border rounded-lg hover:bg-surface-alt text-sm cursor-pointer text-muted hover:text-text"
            >
              Regenerate
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
