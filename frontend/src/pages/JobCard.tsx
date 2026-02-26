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

export default function JobCard() {
  const { rowNum } = useParams<{ rowNum: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [scoring, setScoring] = useState(false);
  const [scoreResult, setScoreResult] = useState<Record<string, string> | null>(null);
  const [status, setStatus] = useState("");
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [showTouchForm, setShowTouchForm] = useState(false);
  const [touchNote, setTouchNote] = useState("");
  const [touchChannel, setTouchChannel] = useState("Email");
  const [touchDirection, setTouchDirection] = useState("Outbound");

  useEffect(() => {
    if (rowNum) {
      getJob(Number(rowNum)).then((j) => {
        setJob(j);
        setStatus(j.status);
      });
      getEvents(Number(rowNum)).then(setEvents).catch(() => {});
    }
  }, [rowNum]);

  const handleScore = async () => {
    if (!job) return;
    setScoring(true);
    try {
      const jdText = job.comment || `${job.role} at ${job.company}, ${job.region}`;
      const res = await evaluateJD({ jd_text: jdText });
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
    } finally {
      setScoring(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!job) return;
    setStatus(newStatus);
    await updateJob(job.row_num, { status: newStatus });
    setJob((prev) => (prev ? { ...prev, status: newStatus } : prev));
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

  if (!job) return <div className="p-6 text-gray-500">Loading...</div>;

  const stopFlags = job.stop_flags || "";
  const roleFit = job.role_fit || "";
  let fitIcon = "";
  if (roleFit) {
    const fit = roleFit.toLowerCase();
    if (stopFlags) fitIcon = "🔴";
    else if (fit === "strong") fitIcon = "🟢";
    else if (fit === "stretch" || fit === "partial") fitIcon = "🟡";
    else fitIcon = "⚪";
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <button
        onClick={() => navigate("/")}
        className="text-blue-600 hover:underline text-sm mb-4 inline-block cursor-pointer"
      >
        &larr; Pipeline
      </button>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">
          {fitIcon} {job.company} — {job.role}
        </h1>
        <p className="text-gray-500">{job.region}</p>

        {/* Source link — domain only, full URL on hover */}
        {job.source && (
          <a
            href={job.source}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 text-sm hover:underline cursor-pointer"
            title={job.source}
          >
            {extractDomain(job.source)}
          </a>
        )}

        <div className="flex items-center gap-3 mt-2 text-sm">
          <span className="text-gray-600">
            {roleFit || "Not scored"} | {job.operator_vs_contractor || "—"} | {job.seniority || "—"}
          </span>
          <span className="text-gray-400">|</span>

          {/* Status dropdown with chevron */}
          <div className="relative inline-block">
            <select
              value={status}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="appearance-none bg-white border rounded px-3 py-1 pr-7 text-sm font-medium cursor-pointer hover:border-gray-400 transition-colors"
            >
              {JOB_STATUSES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none text-xs">
              ▼
            </span>
          </div>

          {job.submission_count && Number(job.submission_count) > 1 && (
            <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded">
              Submission #{job.submission_count}
            </span>
          )}

          {job.possible_duplicate && (
            <span
              className="bg-yellow-100 text-yellow-700 text-xs px-2 py-0.5 rounded cursor-help"
              title={job.duplicate_of || "Duplicate detected"}
            >
              Duplicate of: {job.duplicate_of || "?"}
            </span>
          )}

          {job.needs_followup && (
            <span className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded">
              🔔 Needs follow-up
            </span>
          )}
        </div>
      </div>

      {/* Timeline — moved to top */}
      {(job.applied_date || job.followup_1 || job.followup_2 || job.response_date) && (
        <div className="mb-4 p-3 border rounded-lg bg-gray-50">
          <div className="grid grid-cols-2 gap-2 text-sm">
            {job.applied_date && <div><span className="text-gray-500">Applied:</span> {job.applied_date}</div>}
            {job.followup_1 && <div><span className="text-gray-500">Follow-up 1:</span> {job.followup_1}</div>}
            {job.followup_2 && <div><span className="text-gray-500">Follow-up 2:</span> {job.followup_2}</div>}
            {job.response_date && <div><span className="text-gray-500">Response:</span> {job.response_date}</div>}
            {job.days_to_response && <div><span className="text-gray-500">Days to response:</span> {job.days_to_response}</div>}
          </div>
        </div>
      )}

      {/* Stop flags banner */}
      {stopFlags && (
        <div className="mb-4 p-3 border border-red-200 rounded-lg bg-red-50 text-red-800 text-sm">
          <strong>Stop flags:</strong> {stopFlags}
        </div>
      )}

      {/* Scoring result (if just scored) */}
      {scoreResult && (
        <div className="mb-4 p-4 border rounded-lg bg-blue-50 text-sm">
          <div className="font-medium mb-1">
            {scoreResult.role_fit} | CV: {scoreResult.cv_ready === "YES" ? "Ready" : "Needs work"}
            {scoreResult.cv_note && ` — ${scoreResult.cv_note}`}
          </div>
          <p className="text-gray-700">{scoreResult.summary}</p>
        </div>
      )}

      {/* Info sections */}
      <div className="space-y-4 mb-6">
        {job.comment && (
          <Section title="Summary / Comment">
            <pre className="whitespace-pre-wrap text-sm leading-relaxed">{job.comment}</pre>
          </Section>
        )}

        {job.contact && (
          <Section title="Contact">
            <p className="text-sm">{job.contact}</p>
          </Section>
        )}

        {job.cl && (
          <Section title="Cover Letter">
            <pre className="whitespace-pre-wrap text-sm leading-relaxed">{job.cl}</pre>
          </Section>
        )}

        {job.cv && (
          <Section title="CV Changes">
            <pre className="whitespace-pre-wrap text-sm leading-relaxed">{job.cv}</pre>
          </Section>
        )}

        {job.reapply_reason && (
          <Section title="Reapply Reason">
            <p className="text-sm">{job.reapply_reason}</p>
          </Section>
        )}

        {/* Touchpoints / Events history */}
        <Section title="Touchpoints">
          {events.length > 0 ? (
            <div className="space-y-2">
              {events.map((ev, i) => {
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
                return (
                  <div key={i} className="flex gap-2 text-sm">
                    <span className="text-gray-400 shrink-0 w-36">{ev.timestamp}</span>
                    <span className="text-gray-500 shrink-0 w-28">{ev.event_type}</span>
                    <span>{detail}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No events yet</p>
          )}

          {/* Add touchpoint */}
          {!showTouchForm ? (
            <button
              onClick={() => setShowTouchForm(true)}
              className="mt-2 text-sm text-blue-600 hover:underline cursor-pointer"
            >
              + Touchpoint
            </button>
          ) : (
            <div className="mt-3 p-3 bg-gray-50 rounded space-y-2">
              <div className="flex gap-2">
                <select
                  value={touchChannel}
                  onChange={(e) => setTouchChannel(e.target.value)}
                  className="border rounded px-2 py-1 text-sm cursor-pointer"
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
                  className="border rounded px-2 py-1 text-sm cursor-pointer"
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
                className="w-full border rounded px-2 py-1 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-200"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleAddTouchpoint}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 cursor-pointer"
                >
                  Save
                </button>
                <button
                  onClick={() => setShowTouchForm(false)}
                  className="px-3 py-1 text-sm border rounded hover:bg-gray-50 cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </Section>
      </div>

      {/* Actions — simplified: primary left, secondary right, no Back button */}
      <div className="flex flex-wrap gap-3 border-t pt-4">
        <button
          onClick={handlePrepare}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm font-medium cursor-pointer"
        >
          Prepare Application &rarr;
        </button>
        {!roleFit && (
          <button
            onClick={handleScore}
            disabled={scoring}
            className="px-4 py-2 border rounded hover:bg-gray-50 disabled:opacity-40 text-sm cursor-pointer"
          >
            {scoring ? "Scoring..." : "Evaluate Fit"}
          </button>
        )}
        <button
          onClick={() => navigate(`/job/${job.row_num}/letter`)}
          className="px-4 py-2 border rounded hover:bg-gray-50 text-sm cursor-pointer"
        >
          Letter Only
        </button>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-2 text-sm font-medium text-gray-700">{title}</div>
      <div className="px-4 py-3">{children}</div>
    </div>
  );
}
