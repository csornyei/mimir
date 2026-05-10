import { create } from "zustand";
import { persist } from "zustand/middleware";
import { toast } from "sonner";
import type {
    Message,
    ConversationSummary,
    LLMSettings,
    ServerEvent,
    ApprovalCard,
    ToolCall,
    ResponseMetadata,
} from "@/types";
import { MODE_PRESETS } from "@/lib/presets";
import type { Mode } from "@/lib/presets";

// Module-level state — not reactive, just bookkeeping
let _wasDisconnected = false;
const _approvalTimers = new Map<
    string,
    [ReturnType<typeof setTimeout>, ReturnType<typeof setTimeout>]
>();

interface MimirStore {
    // WebSocket
    ws: WebSocket | null;
    wsStatus: "connecting" | "connected" | "disconnected";
    initWs: () => void;

    // Conversations
    conversations: ConversationSummary[];
    activeConversationId: string | null;
    messages: Message[];
    isStreaming: boolean;
    conversationLoading: boolean;
    conversationTitles: Record<string, string>;
    setActiveConversation: (id: string | null) => void;
    loadConversation: (id: string) => Promise<void>;
    loadConversations: () => Promise<void>;
    createConversation: () => Promise<string>;
    deleteConversation: (id: string) => Promise<void>;
    renameConversation: (id: string, title: string) => void;
    sendMessage: (text: string) => void;
    appendStreamEvent: (event: ServerEvent) => void;

    // Settings (persisted)
    settings: LLMSettings;
    thinkingBudgetDirty: boolean;
    setMode: (mode: Mode) => void;
    setThinkingBudget: (budget: number | null) => void;
    setEnableThinking: (enabled: boolean) => void;

    // Pending approvals
    pendingApprovals: string[];
    approveAction: (
        actionId: string,
        editedArgs?: Record<string, unknown>
    ) => Promise<void>;
    rejectAction: (actionId: string) => Promise<void>;

    // Detail panel
    selectedMessageId: string | null;
    rightPanelTab: "config" | "detail";
    setSelectedMessage: (id: string | null) => void;
    setRightPanelTab: (tab: "config" | "detail") => void;
}

function apiMessageToUiMessage(m: {
    id: number;
    role: string;
    content: string;
    timestamp: string;
}): Message {
    return {
        id: String(m.id),
        role: m.role as "user" | "assistant",
        content: m.content,
        thinkingContent: "",
        toolCalls: [],
        approvalCard: null,
        metadata: null,
        isStreaming: false,
        createdAt: m.timestamp,
    };
}

export const useMimirStore = create<MimirStore>()(
    persist(
        (set, get) => ({
            // WebSocket
            ws: null,
            wsStatus: "disconnected",
            initWs: () => {
                const existing = get().ws;
                if (existing && existing.readyState === WebSocket.OPEN) return;

                const protocol =
                    window.location.protocol === "https:" ? "wss:" : "ws:";
                const ws = new WebSocket(
                    `${protocol}//${window.location.host}/ws`
                );
                set({ ws, wsStatus: "connecting" });

                ws.onopen = () => {
                    set({ wsStatus: "connected" });
                    if (_wasDisconnected) {
                        toast.success("Reconnected to Mimir", {
                            id: "ws-disconnect",
                        });
                        _wasDisconnected = false;
                    }
                };

                ws.onmessage = (ev) => {
                    try {
                        const event = JSON.parse(
                            ev.data as string
                        ) as ServerEvent;
                        get().appendStreamEvent(event);
                    } catch (err) {
                        console.error(
                            "[mimir] malformed WS frame:",
                            err,
                            ev.data
                        );
                    }
                };

                ws.onerror = () => {
                    // onclose fires after onerror, so reconnect is handled there
                };

                ws.onclose = () => {
                    set({ wsStatus: "disconnected", ws: null });
                    _wasDisconnected = true;
                    toast.warning("Disconnected from Mimir — reconnecting…", {
                        id: "ws-disconnect",
                    });
                    setTimeout(() => get().initWs(), 3000);
                };
            },

            // Conversations
            conversations: [],
            activeConversationId: null,
            messages: [],
            isStreaming: false,
            conversationLoading: false,
            conversationTitles: {},

            setActiveConversation: (id) =>
                set((s) => ({
                    activeConversationId: id,
                    messages: id === null ? [] : s.messages,
                })),

            loadConversations: async () => {
                const res = await fetch("/api/conversations");
                const data: ConversationSummary[] = await res.json();
                const titles = get().conversationTitles;
                const conversations = data.map((c) =>
                    titles[c.id] ? { ...c, title: titles[c.id] } : c
                );
                // Prune titles for conversations that no longer exist on the server
                const validIds = new Set(data.map((c) => c.id));
                const prunedTitles = Object.fromEntries(
                    Object.entries(titles).filter(([id]) => validIds.has(id))
                );
                set({ conversations, conversationTitles: prunedTitles });
            },

            loadConversation: async (id) => {
                set({
                    conversationLoading: true,
                    messages: [],
                    activeConversationId: id,
                });
                try {
                    const res = await fetch(`/api/conversations/${id}`);
                    if (!res.ok) {
                        toast.error("Failed to load conversation");
                        return;
                    }
                    const data = await res.json();
                    const uiMessages = data.messages.map(apiMessageToUiMessage);
                    const firstUser = uiMessages.find(
                        (m: Message) => m.role === "user"
                    );
                    const title = firstUser
                        ? firstUser.content.substring(0, 60)
                        : "New conversation";
                    set((s) => ({
                        messages: uiMessages,
                        conversations: s.conversations.map((c) =>
                            c.id === id ? { ...c, title } : c
                        ),
                    }));
                } finally {
                    set({ conversationLoading: false });
                }
            },

            createConversation: async () => {
                const res = await fetch("/api/conversations", {
                    method: "POST",
                });
                const conv: ConversationSummary = await res.json();
                set((s) => ({ conversations: [conv, ...s.conversations] }));
                return conv.id;
            },

            deleteConversation: async (id) => {
                await fetch(`/api/conversations/${id}`, { method: "DELETE" });
                set((s) => {
                    const { [id]: _removed, ...remainingTitles } =
                        s.conversationTitles;
                    return {
                        conversations: s.conversations.filter(
                            (c) => c.id !== id
                        ),
                        activeConversationId:
                            s.activeConversationId === id
                                ? null
                                : s.activeConversationId,
                        messages:
                            s.activeConversationId === id ? [] : s.messages,
                        conversationTitles: remainingTitles,
                    };
                });
            },

            renameConversation: (id, title) => {
                set((s) => ({
                    conversationTitles: {
                        ...s.conversationTitles,
                        [id]: title,
                    },
                    conversations: s.conversations.map((c) =>
                        c.id === id ? { ...c, title } : c
                    ),
                }));
            },

            sendMessage: (text) => {
                const { ws, activeConversationId, settings } = get();
                if (!ws || ws.readyState !== WebSocket.OPEN) return;

                const userMessage: Message = {
                    id: crypto.randomUUID(),
                    role: "user",
                    content: text,
                    thinkingContent: "",
                    toolCalls: [],
                    approvalCard: null,
                    metadata: null,
                    isStreaming: false,
                    createdAt: new Date().toISOString(),
                };
                const assistantMessage: Message = {
                    id: crypto.randomUUID(),
                    role: "assistant",
                    content: "",
                    thinkingContent: "",
                    toolCalls: [],
                    approvalCard: null,
                    metadata: null,
                    isStreaming: true,
                    createdAt: new Date().toISOString(),
                };

                set((s) => ({
                    messages: [...s.messages, userMessage, assistantMessage],
                    isStreaming: true,
                }));

                ws.send(
                    JSON.stringify({
                        type: "chat",
                        conversation_id: activeConversationId,
                        message: text,
                        settings,
                    })
                );
            },

            appendStreamEvent: (event) => {
                set((s) => {
                    const msgs = [...s.messages];
                    const lastIdx = msgs.length - 1;
                    if (lastIdx < 0) return {};
                    const last = msgs[lastIdx];

                    switch (event.type) {
                        case "thinking":
                            msgs[lastIdx] = {
                                ...last,
                                thinkingContent:
                                    last.thinkingContent + event.content,
                            };
                            return { messages: msgs };

                        case "response": {
                            msgs[lastIdx] = {
                                ...last,
                                content: last.content + event.content,
                            };
                            const updates: Partial<MimirStore> = {
                                messages: msgs,
                            };
                            // Capture conversation_id created by backend for new chats
                            if (
                                event.conversation_id &&
                                !s.activeConversationId
                            ) {
                                updates.activeConversationId =
                                    event.conversation_id;
                            }
                            return updates;
                        }

                        case "tool_pending": {
                            // Pre-create the tool card as soon as the LLM names a tool during streaming
                            const alreadyExists = last.toolCalls.some(
                                (tc) => tc.call_id === event.call_id
                            );
                            if (alreadyExists) return {};
                            const pending: ToolCall = {
                                call_id: event.call_id,
                                name: event.name,
                                arguments: {},
                                result: null,
                            };
                            msgs[lastIdx] = {
                                ...last,
                                toolCalls: [...last.toolCalls, pending],
                            };
                            return { messages: msgs };
                        }

                        case "tool_call": {
                            // Update existing pending card if present, otherwise append
                            const existingIdx = last.toolCalls.findIndex(
                                (tc) => tc.call_id === event.call_id
                            );
                            if (existingIdx !== -1) {
                                const updated = last.toolCalls.map((tc) =>
                                    tc.call_id === event.call_id
                                        ? { ...tc, arguments: event.arguments }
                                        : tc
                                );
                                msgs[lastIdx] = {
                                    ...last,
                                    toolCalls: updated,
                                };
                            } else {
                                const tc: ToolCall = {
                                    call_id: event.call_id,
                                    name: event.name,
                                    arguments: event.arguments,
                                    result: null,
                                };
                                msgs[lastIdx] = {
                                    ...last,
                                    toolCalls: [...last.toolCalls, tc],
                                };
                            }
                            return { messages: msgs };
                        }

                        case "tool_result": {
                            const toolCalls = last.toolCalls.map((tc) =>
                                tc.call_id === event.call_id
                                    ? { ...tc, result: event.result }
                                    : tc
                            );
                            msgs[lastIdx] = { ...last, toolCalls };
                            return { messages: msgs };
                        }

                        case "approval_required": {
                            const card: ApprovalCard = {
                                action_id: event.action_id,
                                tool_name: event.tool_name,
                                arguments: event.arguments,
                                status: "pending",
                            };
                            msgs[lastIdx] = { ...last, approvalCard: card };

                            // Client-side timeout mirrors the backend's APPROVAL_TIMEOUT_MINUTES (default 10m)
                            const { action_id: actionId, tool_name: toolName } =
                                event;
                            const warn = setTimeout(
                                () => {
                                    toast.warning(
                                        `Approval for "${toolName}" expires in 1 minute`
                                    );
                                },
                                9 * 60 * 1000
                            );
                            const expire = setTimeout(
                                () => {
                                    toast.error(
                                        `Approval for "${toolName}" expired`
                                    );
                                    set((s) => ({
                                        messages: s.messages.map((m) =>
                                            m.approvalCard?.action_id ===
                                            actionId
                                                ? {
                                                      ...m,
                                                      approvalCard: {
                                                          ...m.approvalCard!,
                                                          status: "rejected" as const,
                                                      },
                                                  }
                                                : m
                                        ),
                                        pendingApprovals:
                                            s.pendingApprovals.filter(
                                                (id) => id !== actionId
                                            ),
                                    }));
                                    _approvalTimers.delete(actionId);
                                },
                                10 * 60 * 1000
                            );
                            _approvalTimers.set(actionId, [warn, expire]);

                            return {
                                messages: msgs,
                                pendingApprovals: [
                                    ...s.pendingApprovals,
                                    event.action_id,
                                ],
                            };
                        }

                        case "approval_result": {
                            const {
                                action_id: actionId,
                                status,
                                result,
                                error,
                            } = event;
                            const timers = _approvalTimers.get(actionId);
                            if (timers) {
                                clearTimeout(timers[0]);
                                clearTimeout(timers[1]);
                                _approvalTimers.delete(actionId);
                            }
                            if (status === "completed")
                                toast.success("Action completed");
                            else if (status === "failed")
                                toast.error(
                                    `Action failed: ${error ?? "unknown error"}`
                                );
                            else if (status === "rejected")
                                toast.info("Action rejected");
                            else if (status === "timeout")
                                toast.warning("Approval timed out");
                            void result;
                            return {
                                messages: s.messages.map((m) =>
                                    m.approvalCard?.action_id === actionId
                                        ? {
                                              ...m,
                                              approvalCard: {
                                                  ...m.approvalCard!,
                                                  status,
                                              },
                                          }
                                        : m
                                ),
                                pendingApprovals: s.pendingApprovals.filter(
                                    (id) => id !== actionId
                                ),
                            };
                        }

                        case "error":
                            toast.error(event.message);
                            msgs[lastIdx] = { ...last, isStreaming: false };
                            return { messages: msgs, isStreaming: false };

                        case "done":
                            msgs[lastIdx] = {
                                ...last,
                                metadata: event.metadata as ResponseMetadata,
                                isStreaming: false,
                            };
                            // Refresh sidebar so new conversations appear
                            setTimeout(() => get().loadConversations(), 0);
                            return { messages: msgs, isStreaming: false };

                        default:
                            return {};
                    }
                });
            },

            // Settings
            settings: MODE_PRESETS.balanced,
            thinkingBudgetDirty: false,

            setMode: (mode) => {
                set({
                    settings: MODE_PRESETS[mode],
                    thinkingBudgetDirty: false,
                });
            },

            setThinkingBudget: (budget) => {
                set((s) => ({
                    settings: { ...s.settings, thinking_budget: budget },
                    thinkingBudgetDirty: true,
                }));
            },

            setEnableThinking: (enabled) => {
                set((s) => ({
                    settings: { ...s.settings, enable_thinking: enabled },
                    thinkingBudgetDirty: true,
                }));
            },

            // Approvals
            pendingApprovals: [],

            approveAction: async (actionId, editedArgs) => {
                const timers = _approvalTimers.get(actionId);
                if (timers) {
                    clearTimeout(timers[0]);
                    clearTimeout(timers[1]);
                    _approvalTimers.delete(actionId);
                }
                const res = await fetch(`/api/approvals/${actionId}/approve`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(
                        editedArgs ? { edited_arguments: editedArgs } : {}
                    ),
                });
                if (!res.ok) {
                    const msg = await res.text().catch(() => "Unknown error");
                    toast.error(`Failed to approve action: ${msg}`);
                    return;
                }
                set((s) => ({
                    messages: s.messages.map((m) =>
                        m.approvalCard?.action_id === actionId
                            ? {
                                  ...m,
                                  approvalCard: {
                                      ...m.approvalCard!,
                                      status: "approved" as const,
                                  },
                              }
                            : m
                    ),
                    pendingApprovals: s.pendingApprovals.filter(
                        (id) => id !== actionId
                    ),
                }));
            },

            rejectAction: async (actionId) => {
                const timers = _approvalTimers.get(actionId);
                if (timers) {
                    clearTimeout(timers[0]);
                    clearTimeout(timers[1]);
                    _approvalTimers.delete(actionId);
                }
                const res = await fetch(`/api/approvals/${actionId}/reject`, {
                    method: "POST",
                });
                if (!res.ok) {
                    const msg = await res.text().catch(() => "Unknown error");
                    toast.error(`Failed to reject action: ${msg}`);
                    return;
                }
                set((s) => ({
                    messages: s.messages.map((m) =>
                        m.approvalCard?.action_id === actionId
                            ? {
                                  ...m,
                                  approvalCard: {
                                      ...m.approvalCard!,
                                      status: "rejected" as const,
                                  },
                              }
                            : m
                    ),
                    pendingApprovals: s.pendingApprovals.filter(
                        (id) => id !== actionId
                    ),
                }));
            },

            // Detail panel
            selectedMessageId: null,
            rightPanelTab: "config",

            setSelectedMessage: (id) =>
                set({
                    selectedMessageId: id,
                    rightPanelTab: id ? "detail" : "config",
                }),
            setRightPanelTab: (tab) => set({ rightPanelTab: tab }),
        }),
        {
            name: "mimir-settings",
            partialize: (s) => ({
                settings: s.settings,
                thinkingBudgetDirty: s.thinkingBudgetDirty,
                conversationTitles: s.conversationTitles,
            }),
        }
    )
);
