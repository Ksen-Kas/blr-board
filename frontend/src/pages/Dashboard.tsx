import { useEffect, useState } from "react";
import { getStats, getJobs } from "../api/jobs";
import type { PipelineStats, Job } from "../types/job";

const STATUS_CARDS = [
  { key: "New", label: "New", color: "bg-blue-500" },
  { key: "Screening", label: "Screening", color: "bg-cyan-500" },
  { key: "Screening req", label: "Screening req", color: "bg-cyan-400" },
  { key: "In Progress", label: "In Progress", color: "bg-yellow-500" },
  { key: "Applied", label: "Applied", color: "bg-green-500" },
  { key: "Waiting", label: "Waiting", color: "bg-orange-500" },
  { key: "Response", label: "Response", color: "bg-purple-500" },
  { key: "HR Screen", label: "HR Screen", color: "bg-purple-400" },
  { key: "Interview", label: "Interview", color: "bg-indigo-500" },
  { key: "No Response", label: "No Response", color: "bg-gray-400" },
  { key: "[No response]", label: "No Response", color: "bg-gray-400" },
  { key: "Rejected", label: "Rejected", color: "bg-red-400" },
  { key: "[Rejected]", label: "Rejected", color: "bg-red-400" },
  { key: "Closed", label: "Closed", color: "bg-red-500" },
];

export default function Dashboard() {
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    getStats().then(setStats);
    getJobs().then(setJobs);
  }, []);

  if (!stats) return <div className="p-6 text-muted">Loading...</div>;

  // Active statuses for funnel (skip zero counts except key ones)
  const funnel = STATUS_CARDS.filter((s) => (stats.by_status[s.key] || 0) > 0);
  const maxCount = Math.max(...funnel.map((s) => stats.by_status[s.key] || 0), 1);

  // Recent activity: jobs with response_date or applied_date, sorted by most recent
  const recent = [...jobs]
    .filter((j) => j.applied_date || j.response_date)
    .sort((a, b) => {
      const da = a.response_date || a.applied_date || "";
      const db = b.response_date || b.applied_date || "";
      return db.localeCompare(da);
    })
    .slice(0, 10);

  // Jobs needing attention: New for >3 days or no follow-up
  const needsAttention = jobs.filter(
    (j) => j.status === "New" || (j.status === "Applied" && !j.followup_1)
  ).length;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <span className="tag-chip mb-2">Insights</span>
      <h1 className="text-3xl font-extrabold mb-6 text-text tracking-tight">Dashboard</h1>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total" value={stats.total} accent="bg-blue-500" />
        <StatCard
          label="Active"
          value={
            (stats.by_status["Applied"] || 0) +
            (stats.by_status["Waiting"] || 0) +
            (stats.by_status["Screening"] || 0) +
            (stats.by_status["Screening req"] || 0) +
            (stats.by_status["In Progress"] || 0)
          }
          accent="bg-green-500"
        />
        <StatCard
          label="Responses"
          value={
            (stats.by_status["Response"] || 0) +
            (stats.by_status["HR Screen"] || 0) +
            (stats.by_status["Interview"] || 0)
          }
          accent="bg-purple-500"
        />
        <StatCard label="Needs Attention" value={needsAttention} accent="bg-orange-500" />
      </div>

      {/* Funnel */}
      <div className="surface-card mb-8 p-5">
        <h2 className="text-lg font-bold mb-4 text-text">Pipeline Funnel</h2>
        <div className="space-y-2">
          {funnel.map((s) => {
            const count = stats.by_status[s.key] || 0;
            const pct = Math.round((count / maxCount) * 100);
            return (
              <div key={s.key} className="flex items-center gap-3">
                <div className="w-28 text-sm text-muted text-right">{s.label}</div>
                <div className="flex-1 bg-surface-alt rounded-full h-7 overflow-hidden border border-border/80">
                  <div
                    className={`${s.color} h-full rounded-full flex items-center justify-end pr-3 text-white text-xs font-semibold`}
                    style={{ width: `${Math.max(pct, 8)}%` }}
                  >
                    {count}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent activity */}
      {recent.length > 0 && (
        <div>
          <h2 className="text-lg font-bold mb-4 text-text">Recent Activity</h2>
          <div className="surface-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-alt text-left text-muted">
                  <th className="px-3 py-2 font-medium">Company</th>
                  <th className="px-3 py-2 font-medium">Role</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Applied</th>
                  <th className="px-3 py-2 font-medium">Response</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((j) => (
                  <tr key={j.row_num} className="border-t border-border">
                    <td className="px-3 py-2 font-medium text-text">{j.company}</td>
                    <td className="px-3 py-2 text-text">{j.role}</td>
                    <td className="px-3 py-2 text-muted">{j.status}</td>
                    <td className="px-3 py-2 text-muted">{j.applied_date || "—"}</td>
                    <td className="px-3 py-2 text-muted">{j.response_date || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="surface-card overflow-hidden">
      <div className={`${accent} h-1`} />
      <div className="p-4">
        <div className="text-3xl font-extrabold text-text tracking-tight">{value}</div>
        <div className="text-sm text-muted font-medium">{label}</div>
      </div>
    </div>
  );
}
