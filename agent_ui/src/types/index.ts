export interface LLMSettings {
    mode: "precise" | "balanced" | "creative" | "fast";
    enable_thinking: boolean;
    thinking_budget: number | null; // null = unlimited; irrelevant when enable_thinking = false
    temperature: number;
    top_p: number;
    min_p: number;
    repetition_penalty: number;
    max_tokens: number;
}

export interface RagSource {
    source_path: string;
    source_type: "markdown" | "pdf" | "kiwix" | "wallabag";
    chunk_index: number;
    similarity_score: number;
    content_preview: string;
}

export interface EpisodicMemory {
    summary: string;
    started_at: string;
    similarity_score: number;
}

export interface ResponseMetadata {
    thinking_tokens: number;
    response_tokens: number;
    prompt_tokens: number;
    latency_ms: number;
    rag_sources: RagSource[];
    episodic_memories: EpisodicMemory[];
}

export interface ToolCall {
    call_id: string;
    name: string;
    arguments: Record<string, unknown>;
    result: string | null;
}

export interface ApprovalCard {
    action_id: string;
    tool_name: string;
    arguments: Record<string, unknown>;
    status:
        | "pending"
        | "approved"
        | "completed"
        | "failed"
        | "rejected"
        | "timeout";
}

export interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    thinkingContent: string;
    toolCalls: ToolCall[];
    approvalCard: ApprovalCard | null;
    metadata: ResponseMetadata | null;
    isStreaming: boolean;
    createdAt: string;
}

export interface ConversationSummary {
    id: string;
    created_at: string;
    last_active: string;
    title?: string;
}

export interface DigestArticle {
    id: number;
    title: string;
    url: string;
    feed_name: string | null;
    category: string | null;
    window: string;
    digest_run_at: string;
}

export interface DigestRun {
    run_at: string;
    window: string;
    article_count: number;
}

export interface BriefMessage {
    id: number;
    role: "user" | "assistant";
    content: string;
    timestamp: string;
}

export interface BriefSummary {
    id: string;
    date: string;
    created_at: string;
}

export interface BriefDetail {
    id: string;
    date: string;
    created_at: string;
    messages: BriefMessage[];
}

// Server → Client
export type ServerEvent =
    | { type: "connected" }
    | { type: "pong" }
    | { type: "thinking"; content: string }
    | {
          type: "response";
          content: string;
          conversation_id?: string;
          request_id?: string | null;
      }
    | { type: "tool_pending"; name: string; call_id: string }
    | {
          type: "tool_call";
          name: string;
          arguments: Record<string, unknown>;
          call_id: string;
      }
    | { type: "tool_result"; name: string; result: string; call_id: string }
    | {
          type: "approval_required";
          action_id: string;
          tool_name: string;
          arguments: Record<string, unknown>;
      }
    | {
          type: "approval_result";
          action_id: string;
          status: "completed" | "failed" | "rejected" | "timeout";
          result?: string;
          error?: string;
      }
    | { type: "error"; message: string }
    | { type: "done"; metadata: ResponseMetadata; request_id?: string | null };

// Client → Server
export type ClientEvent =
    | {
          type: "chat";
          message: string;
          conversation_id: string | null;
          settings: LLMSettings;
      }
    | { type: "ping" };
