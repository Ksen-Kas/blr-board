import axios from "axios";

const encodeBasic = (value: string) => btoa(unescape(encodeURIComponent(value)));

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api",
});

let onUnauthorized: (() => void) | null = null;
let requestSeq = 1;

type TrackedRequest = {
  id: number;
  startedAt: number;
  estimatedMs: number;
  method: string;
  url: string;
};

export type NetworkActivitySnapshot = {
  pendingCount: number;
  visible: boolean;
  progress: number; // 0..1
  etaMs: number;
  label: string;
};

const pendingRequests = new Map<number, TrackedRequest>();
const activityListeners = new Set<(snapshot: NetworkActivitySnapshot) => void>();

function _estimateDurationMs(method: string, url: string): number {
  const key = `${method.toUpperCase()} ${url}`.toLowerCase();
  if (key.includes("/cv/tailor")) return 26000;
  if (key.includes("/scoring/evaluate")) return 15000;
  if (key.includes("/letter/generate")) return 17000;
  if (key.includes("/cv/tailored-pdf") || key.includes("/cv/canonical-pdf") || key.includes("/letter/pdf")) return 12000;
  if (key.includes("/jobs/refresh")) return 7000;
  if (key.includes("/jobs/")) return 6000;
  return 8000;
}

function _buildSnapshot(now: number = Date.now()): NetworkActivitySnapshot {
  if (pendingRequests.size === 0) {
    return {
      pendingCount: 0,
      visible: false,
      progress: 0,
      etaMs: 0,
      label: "",
    };
  }

  let totalProgress = 0;
  let maxEta = 0;
  let maxElapsed = 0;

  for (const req of pendingRequests.values()) {
    const elapsed = Math.max(0, now - req.startedAt);
    maxElapsed = Math.max(maxElapsed, elapsed);

    let remaining = req.estimatedMs - elapsed;
    if (remaining < 0) {
      // Still running beyond estimate: keep a short rolling ETA.
      remaining = Math.min(6000, 1200 + Math.floor(Math.abs(remaining) * 0.35));
    }

    const progress = elapsed / Math.max(elapsed + remaining, 1);
    totalProgress += Math.min(0.97, Math.max(0.05, progress));
    maxEta = Math.max(maxEta, Math.max(800, remaining));
  }

  const avgProgress = Math.min(0.97, totalProgress / pendingRequests.size);
  const visible = maxElapsed > 350; // avoid flicker for instant requests
  const label = pendingRequests.size > 1 ? "System is processing requests..." : "System is thinking...";

  return {
    pendingCount: pendingRequests.size,
    visible,
    progress: avgProgress,
    etaMs: maxEta,
    label,
  };
}

function _notifyActivity(): void {
  const snapshot = _buildSnapshot();
  for (const listener of activityListeners) {
    listener(snapshot);
  }
}

function _finishTrackedRequest(config?: unknown): void {
  if (!config || typeof config !== "object") return;
  const id = (config as { __requestTrackerId?: number }).__requestTrackerId;
  if (!id) return;
  pendingRequests.delete(id);
}

export const subscribeNetworkActivity = (
  listener: (snapshot: NetworkActivitySnapshot) => void,
) => {
  activityListeners.add(listener);
  listener(_buildSnapshot());
  return () => {
    activityListeners.delete(listener);
  };
};

export const getNetworkActivitySnapshot = () => _buildSnapshot();

export const setUnauthorizedHandler = (handler: (() => void) | null) => {
  onUnauthorized = handler;
};

export const setBasicAuth = (username: string, password: string) => {
  const token = encodeBasic(`${username}:${password}`);
  api.defaults.headers.common.Authorization = `Basic ${token}`;
};

export const clearAuth = () => {
  delete api.defaults.headers.common.Authorization;
};

api.interceptors.request.use((config) => {
  const method = (config.method || "GET").toString();
  const url = (config.url || "").toString();
  const id = requestSeq++;
  const tracked: TrackedRequest = {
    id,
    startedAt: Date.now(),
    estimatedMs: _estimateDurationMs(method, url),
    method,
    url,
  };
  pendingRequests.set(id, tracked);
  (config as { __requestTrackerId?: number }).__requestTrackerId = id;
  _notifyActivity();
  return config;
});

api.interceptors.response.use(
  (response) => {
    _finishTrackedRequest(response?.config);
    _notifyActivity();
    return response;
  },
  (error) => {
    _finishTrackedRequest(error?.config);
    _notifyActivity();
    if (error?.response?.status === 401) {
      clearAuth();
      onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);

export default api;
