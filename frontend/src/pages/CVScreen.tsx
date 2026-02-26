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
    if (result) navigator.clipboard.writeText(result.tailored_cv);
  };

  const handleCopyChanges = () => {
    if (result) navigator.clipboard.writeText(result.changes_summary);
  };

  if (!job) return <div className="p-6 text-gray-500">Loading...</div>;

  // Canon check color
  const canonColor = result
    ? result.canon_check.startsWith("OK")
      ? "bg-green-50 border-green-200 text-green-800"
      : result.canon_check.startsWith("WARN")
        ? "bg-yellow-50 border-yellow-200 text-yellow-800"
        : "bg-red-50 border-red-200 text-red-800"
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
        className="text-blue-600 hover:underline text-sm mb-4 inline-block cursor-pointer"
      >
        &larr; {job.company} — {job.role}
      </button>

      {/* Recommendation */}
      {recommendation && !result && !tailoring && (
        <div className="mb-4 p-3 border rounded-lg bg-blue-50 text-blue-800 text-sm">
          {recommendation}
        </div>
      )}

      {/* Before tailoring — two buttons */}
      {!result && !tailoring && (
        <div className="border rounded-lg p-6 text-center space-y-4">
          <p className="text-gray-600">
            Joe will make minimal adjustments to your canonical resume for this role.
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => navigate(`/job/${rowNum}/letter`)}
              className="px-5 py-2.5 border rounded-lg hover:bg-gray-50 text-sm cursor-pointer"
            >
              Use Canon CV
            </button>
            <button
              onClick={handleTailor}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium cursor-pointer"
            >
              Tailor CV &rarr;
            </button>
          </div>
        </div>
      )}

      {/* Loading */}
      {tailoring && (
        <div className="border rounded-lg p-6 text-center">
          <div className="animate-pulse text-gray-500">Tailoring CV against JD...</div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border border-red-200 rounded-lg p-4 bg-red-50 text-red-700 text-sm mb-4">
          {error}
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
          <div className="border rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">Changes</span>
              <button
                onClick={handleCopyChanges}
                className="text-xs text-blue-600 hover:underline cursor-pointer"
              >
                Copy changes
              </button>
            </div>
            <div className="px-4 py-3">
              <pre className="whitespace-pre-wrap text-sm leading-relaxed">
                {result.changes_summary}
              </pre>
            </div>
          </div>

          {/* Full tailored CV */}
          <div className="border rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">Tailored CV</span>
              <div className="flex gap-3">
                <button
                  onClick={() =>
                    result &&
                    job &&
                    downloadCvPdf({
                      tailored_cv: result.tailored_cv,
                      company: job.company,
                      role: job.role,
                    })
                  }
                  className="text-xs text-blue-600 hover:underline cursor-pointer"
                >
                  Download PDF
                </button>
                <button
                  onClick={handleCopyCV}
                  className="text-xs text-blue-600 hover:underline cursor-pointer"
                >
                  Copy full CV
                </button>
              </div>
            </div>
            <div className="px-4 py-3 max-h-[500px] overflow-y-auto">
              <pre className="whitespace-pre-wrap text-sm leading-relaxed">
                {result.tailored_cv}
              </pre>
            </div>
          </div>

          {/* Actions — primary left, secondary right, no Back */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => navigate(`/job/${rowNum}/letter`)}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm font-medium cursor-pointer"
            >
              Next: Letter &rarr;
            </button>
            <button
              onClick={() => setShowRetailorInput(true)}
              className="px-4 py-2 border rounded hover:bg-gray-50 text-sm cursor-pointer"
            >
              Re-tailor
            </button>
          </div>

          {/* Re-tailor input modal */}
          {showRetailorInput && (
            <div className="border rounded-lg p-4 bg-gray-50 space-y-3">
              <label className="block text-sm font-medium text-gray-700">
                What to change?
              </label>
              <textarea
                value={retailorNotes}
                onChange={(e) => setRetailorNotes(e.target.value)}
                rows={3}
                placeholder="e.g., emphasize data analytics more, remove mention of X..."
                className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-200"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleRetailor}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm cursor-pointer"
                >
                  Apply
                </button>
                <button
                  onClick={() => { setShowRetailorInput(false); setRetailorNotes(""); }}
                  className="px-4 py-2 border rounded hover:bg-gray-50 text-sm cursor-pointer"
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
