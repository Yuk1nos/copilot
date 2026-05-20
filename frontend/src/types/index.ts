export interface TraceEvent {
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  event_type: string;
  status: "running" | "done" | "error";
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  mime_type: string;
  char_count: number;
  chunk_count: number;
  status: string;
  created_at: string;
}

export interface TraceData {
  trace_id: string;
  events: TraceEvent[];
}
