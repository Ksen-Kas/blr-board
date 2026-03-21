export interface Job {
  row_num: number;
  company: string;
  role: string;
  region: string;
  seniority: string;
  operator_vs_contractor: string;
  status: string;
  submission_count: string;
  reapply_reason: string;
  applied_date: string;
  followup_1: string;
  followup_2: string;
  response_date: string;
  days_to_response: string;
  source: string;
  channel: string;
  role_fit: string;
  stop_flags: string;
  contact: string;
  cv: string;
  cl: string;
  comment: string;
  // Computed by backend
  possible_duplicate: boolean;
  duplicate_of: string;
  needs_followup: boolean;
}

export interface PipelineStats {
  total: number;
  by_status: Record<string, number>;
}

export interface JobEvent {
  event_id?: number;
  job_id: number;
  timestamp: string;
  event_type: string;
  data: string;
}
