import { useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router";
import { useMimirStore } from "@/store";
import { ChatInput } from "@/components/chat/ChatInput";
import { MessageStream } from "@/components/chat/MessageStream";

export function ChatScreen() {
    const { conversationId } = useParams();
    const navigate = useNavigate();
    const { loadConversation, setActiveConversation, activeConversationId } =
        useMimirStore();

    // Load conversation when URL param changes
    useEffect(() => {
        if (conversationId) {
            loadConversation(conversationId);
        } else {
            setActiveConversation(null);
        }
    }, [conversationId]); // eslint-disable-line react-hooks/exhaustive-deps

    // Navigate to the new conversation URL once the backend assigns an ID
    const prevActiveIdRef = useRef<string | null>(null);
    useEffect(() => {
        const prev = prevActiveIdRef.current;
        prevActiveIdRef.current = activeConversationId ?? null;

        if (activeConversationId && !conversationId && prev === null) {
            navigate(`/c/${activeConversationId}`, { replace: true });
        }
    }, [activeConversationId, conversationId, navigate]);

    return (
        <div className="flex h-full flex-col overflow-hidden">
            <MessageStream />
            <ChatInput />
        </div>
    );
}
