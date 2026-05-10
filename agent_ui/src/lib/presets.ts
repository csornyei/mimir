import type { LLMSettings } from "@/types";
// TODO: these presets are currently hardcoded. they should be fetched from the server and come from a config file, to allow users to customize them
export type Mode = "precise" | "balanced" | "creative" | "fast";

export const MODE_PRESETS: Record<Mode, LLMSettings> = {
    precise: {
        mode: "precise",
        enable_thinking: true,
        thinking_budget: 2000,
        temperature: 0.2,
        top_p: 0.9,
        min_p: 0.05,
        repetition_penalty: 1.0,
        max_tokens: 4096,
    },
    balanced: {
        mode: "balanced",
        enable_thinking: true,
        thinking_budget: 2000,
        temperature: 0.5,
        top_p: 0.9,
        min_p: 0.05,
        repetition_penalty: 1.0,
        max_tokens: 4096,
    },
    creative: {
        mode: "creative",
        enable_thinking: true,
        thinking_budget: 8000,
        temperature: 0.8,
        top_p: 0.95,
        min_p: 0.02,
        repetition_penalty: 1.05,
        max_tokens: 4096,
    },
    fast: {
        mode: "fast",
        enable_thinking: false,
        thinking_budget: 0,
        temperature: 0.3,
        top_p: 0.9,
        min_p: 0.05,
        repetition_penalty: 1.0,
        max_tokens: 2048,
    },
};
