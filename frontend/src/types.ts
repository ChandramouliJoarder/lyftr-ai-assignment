export interface AssistantMetadata {
  resolution_source: 'LIVE_INFERENCE' | 'LLM_CACHE';
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  key_id: string | null;
  fallback_attempts: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'notice';
  content: string;
  metadata?: AssistantMetadata;
  isError?: boolean;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  metadata: AssistantMetadata;
}

export interface SessionHistoryItem {
  role: 'user' | 'assistant';
  content: string;
  metadata?: AssistantMetadata;
}
