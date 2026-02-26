import api from "./client";
import type { Job, PipelineStats, JobEvent } from "../types/job";

export const getJobs = () => api.get<Job[]>("/jobs/").then((r) => r.data);

export const getJob = (rowNum: number) =>
  api.get<Job>(`/jobs/${rowNum}`).then((r) => r.data);

export const createJob = (data: Partial<Job>) =>
  api.post("/jobs/", data).then((r) => r.data);

export const updateJob = (rowNum: number, data: Partial<Job>) =>
  api.patch<Job>(`/jobs/${rowNum}`, data).then((r) => r.data);

export const refreshCache = () =>
  api.post("/jobs/refresh").then((r) => r.data);

export const getStatuses = () =>
  api.get<string[]>("/jobs/statuses").then((r) => r.data);

export const getStats = () =>
  api.get<PipelineStats>("/pipeline/stats").then((r) => r.data);

// Events
export const getEvents = (rowNum: number) =>
  api.get<JobEvent[]>(`/jobs/${rowNum}/events`).then((r) => r.data);

export const addEvent = (rowNum: number, event_type: string, data: string = "{}") =>
  api.post(`/jobs/${rowNum}/events`, { event_type, data }).then((r) => r.data);

// Scoring — same output as Telegram bot's joe.evaluate()
export const evaluateJD = (data: {
  jd_text?: string;
  source_url?: string;
  add_to_tracker?: boolean;
}) => api.post("/scoring/evaluate", data).then((r) => r.data);

export const tailorCV = (jd_text: string) =>
  api
    .post<{ tailored_cv: string; changes_summary: string; canon_check: string }>(
      "/cv/tailor",
      { jd_text }
    )
    .then((r) => r.data);

export const generateLetter = (jd_text: string, notes = "") =>
  api
    .post<{ subject: string; body: string }>("/letter/generate", {
      jd_text,
      notes,
    })
    .then((r) => r.data);

// PDF downloads

export const downloadCvPdf = async (data: {
  tailored_cv: string;
  company: string;
  role: string;
}) => {
  const res = await api.post("/cv/pdf", data, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `CV_${data.company}_${data.role}.pdf`.replace(/ /g, "_");
  a.click();
  URL.revokeObjectURL(url);
};

export const downloadLetterPdf = async (data: {
  subject: string;
  body: string;
  company: string;
  role: string;
}) => {
  const res = await api.post("/letter/pdf", data, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `CL_${data.company}_${data.role}.pdf`.replace(/ /g, "_");
  a.click();
  URL.revokeObjectURL(url);
};
