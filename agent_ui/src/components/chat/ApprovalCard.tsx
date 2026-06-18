import { useState } from "react";
import type { Icon } from "@phosphor-icons/react";
import {
    CheckCircle,
    Clock,
    Hourglass,
    PencilSimple,
    Warning,
    WarningCircle,
    XCircle,
} from "@phosphor-icons/react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { useMimirStore } from "@/store";
import type { ApprovalCard as ApprovalCardType } from "@/types";

interface Props {
    card: ApprovalCardType;
}

function StatusBadge({
    icon: Icon,
    text,
    className,
}: {
    icon: Icon;
    text: string;
    className: string;
}) {
    return (
        <div
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs ${className}`}
        >
            <Icon className="h-3.5 w-3.5 shrink-0" weight="fill" />
            <span>{text}</span>
        </div>
    );
}

export function ApprovalCard({ card }: Props) {
    const { approveAction, rejectAction } = useMimirStore();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [editOpen, setEditOpen] = useState(false);
    const [editedArgs, setEditedArgs] = useState(
        JSON.stringify(card.arguments, null, 2)
    );
    const [editError, setEditError] = useState<string | null>(null);

    if (card.status === "approved") {
        return (
            <StatusBadge
                icon={Hourglass}
                text="Approved — executing…"
                className="border-amber-900/60 bg-amber-950/30 text-amber-400"
            />
        );
    }
    if (card.status === "completed") {
        return (
            <StatusBadge
                icon={CheckCircle}
                text="Completed"
                className="border-green-900/60 bg-green-950/30 text-green-400"
            />
        );
    }
    if (card.status === "failed") {
        return (
            <StatusBadge
                icon={WarningCircle}
                text="Execution failed"
                className="border-red-900/60 bg-red-950/30 text-red-400"
            />
        );
    }
    if (card.status === "rejected") {
        return (
            <StatusBadge
                icon={XCircle}
                text="Rejected"
                className="border-red-900/60 bg-red-950/30 text-red-400"
            />
        );
    }
    if (card.status === "timeout") {
        return (
            <StatusBadge
                icon={Clock}
                text="Timed out"
                className="border-zinc-700/60 bg-zinc-900/30 text-zinc-400"
            />
        );
    }

    async function handleApprove() {
        if (isSubmitting) return;
        setIsSubmitting(true);
        try {
            await approveAction(card.action_id);
        } finally {
            setIsSubmitting(false);
        }
    }

    async function handleReject() {
        if (isSubmitting) return;
        setIsSubmitting(true);
        try {
            await rejectAction(card.action_id);
        } finally {
            setIsSubmitting(false);
        }
    }

    async function handleConfirmEdit() {
        if (isSubmitting) return;
        try {
            const parsed: unknown = JSON.parse(editedArgs);
            setIsSubmitting(true);
            setEditOpen(false);
            try {
                await approveAction(
                    card.action_id,
                    parsed as Record<string, unknown>
                );
            } finally {
                setIsSubmitting(false);
            }
        } catch {
            setEditError("Invalid JSON — fix before approving");
        }
    }

    return (
        <>
            <Alert className="border-amber-800/60 bg-amber-950/20">
                <Warning className="h-4 w-4 text-amber-400" />
                <AlertTitle className="text-sm text-amber-200">
                    Approval Required
                </AlertTitle>
                <AlertDescription className="mt-1 space-y-3">
                    <p className="font-mono text-xs text-amber-300/90">
                        {card.tool_name}
                    </p>
                    <pre className="max-h-32 overflow-auto rounded border border-amber-900/40 bg-amber-950/30 p-2 font-mono text-xs whitespace-pre-wrap text-amber-200/70">
                        {JSON.stringify(card.arguments, null, 2)}
                    </pre>
                    <div className="flex flex-wrap gap-2">
                        <Button
                            size="sm"
                            disabled={isSubmitting}
                            onClick={handleApprove}
                        >
                            {isSubmitting ? (
                                <Spinner className="h-3 w-3" />
                            ) : (
                                <>
                                    <CheckCircle className="h-4 w-4" />
                                    Approve
                                </>
                            )}
                        </Button>
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={isSubmitting}
                            onClick={() => setEditOpen(true)}
                        >
                            <PencilSimple className="h-4 w-4" />
                            Edit &amp; approve
                        </Button>
                        <Button
                            size="sm"
                            variant="destructive"
                            disabled={isSubmitting}
                            onClick={handleReject}
                        >
                            {isSubmitting ? (
                                <Spinner className="h-3 w-3" />
                            ) : (
                                <>
                                    <XCircle className="h-4 w-4" />
                                    Reject
                                </>
                            )}
                        </Button>
                    </div>
                </AlertDescription>
            </Alert>

            <Dialog open={editOpen} onOpenChange={setEditOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>
                            Edit arguments — {card.tool_name}
                        </DialogTitle>
                    </DialogHeader>
                    <div className="space-y-2">
                        <Textarea
                            value={editedArgs}
                            onChange={(e) => {
                                setEditedArgs(e.target.value);
                                setEditError(null);
                            }}
                            className="min-h-50 font-mono text-xs"
                            spellCheck={false}
                        />
                        {editError && (
                            <p className="text-destructive text-xs">
                                {editError}
                            </p>
                        )}
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setEditOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            disabled={isSubmitting}
                            onClick={handleConfirmEdit}
                        >
                            {isSubmitting ? (
                                <Spinner className="h-3 w-3" />
                            ) : (
                                "Approve with edits"
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
