from dataclasses import dataclass


@dataclass
class ResponseToken:
    content: str


@dataclass
class ThinkingToken:
    content: str


@dataclass
class ToolPending:
    name: str
    call_id: str


@dataclass
class ToolStart:
    name: str
    call_id: str
    arguments: dict


@dataclass
class ToolDone:
    name: str
    call_id: str
    result: str


@dataclass
class ApprovalRequired:
    action_id: str
    tool_name: str
    arguments: dict


type AgentEvent = (
    ResponseToken
    | ThinkingToken
    | ToolPending
    | ToolStart
    | ToolDone
    | ApprovalRequired
)
