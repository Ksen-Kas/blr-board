import { useEffect, useState } from "react";
import { applyJobBatch } from "../api/jobs";
import type { Job } from "../types/job";

const STORAGE_KEY = "joe_sync_queue_v1";

export type QueuedTouchpoint = {
  direction: string;
  note: string;
  channel?: string;
};

export type QueuedLetterSave = {
  subject?: string;
  body: string;
  source?: string;
};

export type QueuedRow = {
  rowNum: number;
  updates: Partial<Job>;
  touchpoints: QueuedTouchpoint[];
  letterSave?: QueuedLetterSave;
  updatedAt: number;
};

type PersistedQueue = {
  rows: Record<string, QueuedRow>;
  lastSyncAt: number;
};

export type SyncQueueSnapshot = {
  pendingRows: number;
  pendingOps: number;
  isSyncing: boolean;
  lastError: string;
  lastSyncAt: number;
};

const listeners = new Set<(snapshot: SyncQueueSnapshot) => void>();

const queueState: PersistedQueue = loadQueueState();
let isSyncing = false;
let lastError = "";
let activeSyncPromise: Promise<{ syncedRows: number; failedRows: number }> | null = null;

function loadQueueState(): PersistedQueue {
  if (typeof window === "undefined") {
    return { rows: {}, lastSyncAt: 0 };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { rows: {}, lastSyncAt: 0 };
    const parsed = JSON.parse(raw) as PersistedQueue;
    if (!parsed || typeof parsed !== "object") return { rows: {}, lastSyncAt: 0 };
    return {
      rows: parsed.rows || {},
      lastSyncAt: Number(parsed.lastSyncAt || 0),
    };
  } catch {
    return { rows: {}, lastSyncAt: 0 };
  }
}

function persistQueueState(): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(queueState));
}

function snapshot(): SyncQueueSnapshot {
  const rows = Object.values(queueState.rows);
  const pendingOps = rows.reduce((acc, row) => {
    const hasUpdates = Object.keys(row.updates || {}).length > 0 ? 1 : 0;
    const hasLetter = row.letterSave ? 1 : 0;
    return acc + hasUpdates + hasLetter + row.touchpoints.length;
  }, 0);
  return {
    pendingRows: rows.length,
    pendingOps,
    isSyncing,
    lastError,
    lastSyncAt: queueState.lastSyncAt || 0,
  };
}

function emit(): void {
  const s = snapshot();
  for (const listener of listeners) {
    listener(s);
  }
}

function setSyncState(syncing: boolean, error: string = ""): void {
  isSyncing = syncing;
  lastError = error;
  emit();
}

function sanitizeUpdates(updates: Partial<Job>): Partial<Job> {
  const clean: Partial<Job> = {};
  for (const [key, value] of Object.entries(updates || {})) {
    if (value === undefined) continue;
    (clean as Record<string, unknown>)[key] = value;
  }
  return clean;
}

function ensureRow(rowNum: number): QueuedRow {
  const key = String(rowNum);
  const existing = queueState.rows[key];
  if (existing) return existing;
  const created: QueuedRow = {
    rowNum,
    updates: {},
    touchpoints: [],
    updatedAt: Date.now(),
  };
  queueState.rows[key] = created;
  return created;
}

export function getQueuedRowChange(rowNum: number): QueuedRow | null {
  return queueState.rows[String(rowNum)] || null;
}

export function applyQueueDraft(
  rowNum: number,
  draft: {
    setUpdates?: Partial<Job>;
    clearUpdateKeys?: Array<keyof Job>;
    touchpoints?: QueuedTouchpoint[];
    letterSave?: QueuedLetterSave | null;
  },
): void {
  const row = ensureRow(rowNum);

  if (draft.clearUpdateKeys?.length) {
    for (const key of draft.clearUpdateKeys) {
      delete (row.updates as Record<string, unknown>)[key as string];
    }
  }

  if (draft.setUpdates) {
    row.updates = {
      ...row.updates,
      ...sanitizeUpdates(draft.setUpdates),
    };
  }

  if (draft.touchpoints) {
    row.touchpoints = draft.touchpoints.filter((tp) => (tp.note || "").trim().length > 0);
  }

  if (draft.letterSave === null) {
    delete row.letterSave;
  } else if (draft.letterSave) {
    const body = (draft.letterSave.body || "").trim();
    if (body) {
      row.letterSave = {
        subject: (draft.letterSave.subject || "").trim(),
        body,
        source: draft.letterSave.source || "manual",
      };
    }
  }

  const hasUpdates = Object.keys(row.updates).length > 0;
  const hasTouchpoints = row.touchpoints.length > 0;
  const hasLetter = Boolean(row.letterSave);

  if (!hasUpdates && !hasTouchpoints && !hasLetter) {
    delete queueState.rows[String(rowNum)];
  } else {
    row.updatedAt = Date.now();
  }

  persistQueueState();
  emit();
}

export function hasPendingSyncChanges(): boolean {
  return Object.keys(queueState.rows).length > 0;
}

export function subscribeSyncQueue(listener: (snapshot: SyncQueueSnapshot) => void): () => void {
  listeners.add(listener);
  listener(snapshot());
  return () => listeners.delete(listener);
}

export function getSyncQueueSnapshot(): SyncQueueSnapshot {
  return snapshot();
}

async function syncInternal(rowNums?: number[]): Promise<{ syncedRows: number; failedRows: number }> {
  const targetRows = rowNums?.length
    ? rowNums.map((v) => String(v))
    : Object.keys(queueState.rows);

  if (targetRows.length === 0) {
    return { syncedRows: 0, failedRows: 0 };
  }

  setSyncState(true);
  let syncedRows = 0;
  let failedRows = 0;
  let firstError = "";

  for (const key of targetRows) {
    const row = queueState.rows[key];
    if (!row) continue;
    const payload: {
      updates?: Partial<Job>;
      touchpoints?: QueuedTouchpoint[];
      letter_save?: QueuedLetterSave;
    } = {};
    if (Object.keys(row.updates).length > 0) payload.updates = row.updates;
    if (row.touchpoints.length > 0) payload.touchpoints = row.touchpoints;
    if (row.letterSave) payload.letter_save = row.letterSave;

    if (!payload.updates && !payload.touchpoints && !payload.letter_save) {
      delete queueState.rows[key];
      continue;
    }

    try {
      await applyJobBatch(row.rowNum, payload);
      delete queueState.rows[key];
      syncedRows += 1;
    } catch (err: unknown) {
      failedRows += 1;
      if (!firstError) {
        firstError =
          err && typeof err === "object" && "response" in err
            ? String(
                (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
                  "Sync failed",
              )
            : "Sync failed";
      }
    }
  }

  if (syncedRows > 0) {
    queueState.lastSyncAt = Date.now();
  }
  persistQueueState();
  setSyncState(false, firstError);
  return { syncedRows, failedRows };
}

export function syncAllPendingChanges(): Promise<{ syncedRows: number; failedRows: number }> {
  if (activeSyncPromise) return activeSyncPromise;
  activeSyncPromise = syncInternal().finally(() => {
    activeSyncPromise = null;
  });
  return activeSyncPromise;
}

export function syncPendingRows(rowNums: number[]): Promise<{ syncedRows: number; failedRows: number }> {
  if (activeSyncPromise) return activeSyncPromise;
  activeSyncPromise = syncInternal(rowNums).finally(() => {
    activeSyncPromise = null;
  });
  return activeSyncPromise;
}

export function useSyncQueueSnapshot(): SyncQueueSnapshot {
  const [state, setState] = useState<SyncQueueSnapshot>(getSyncQueueSnapshot());
  useEffect(() => subscribeSyncQueue(setState), []);
  return state;
}
