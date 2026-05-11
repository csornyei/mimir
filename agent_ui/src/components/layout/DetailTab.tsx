import { MessageDetail } from "@/components/detail/MessageDetail";
import { useMimirStore } from "@/store";

export function DetailTab() {
    const { messages, selectedMessageId } = useMimirStore();
    const selectedMessage = messages.find((m) => m.id === selectedMessageId);

    return selectedMessage?.metadata ? (
        <MessageDetail metadata={selectedMessage.metadata} />
    ) : (
        <div className="flex h-full items-center justify-center">
            <p className="text-muted-foreground px-4 text-center text-xs">
                Click a response to see its context.
            </p>
        </div>
    );
}
