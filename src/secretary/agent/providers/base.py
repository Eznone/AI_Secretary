"""
Neutral data types and protocol shared by all provider adapters.

Why a neutral conversation format?
  The original loop.py stored Anthropic SDK objects (ToolUseBlock, etc.) directly
  in the conversation list, making it impossible to swap providers at runtime.
  These plain dicts are provider-agnostic — each adapter translates them into
  whatever wire format its SDK requires.

Conversation — each turn is one of these dict shapes:
  {"role": "user",         "text": "<user message>"}
  {"role": "assistant",    "text": "<reply>",  "tool_calls": None}
  {"role": "assistant",    "text": None,        "tool_calls": [{"id":…, "name":…, "inputs":…}]}
  {"role": "tool_results", "results": [{"id":…, "name":…, "content":…}]}

Note: "name" is carried in tool_results so Gemini's Part.from_function_response()
can match results to declarations by name. Claude and Groq ignore it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# Alias used in function signatures so it reads clearly in adapter code.
Conversation = list[dict[str, Any]]


@dataclass
class ToolCall:
    """A single tool invocation requested by the model.

    id:     Unique call identifier for correlating tool results.
            Claude and Groq assign these natively; Gemini does not, so the
            Gemini adapter generates short UUIDs to keep the format uniform.
    name:   The @tool function name (must match a key in the registry).
    inputs: Keyword arguments as a plain dict, ready for dispatch().
    """

    id: str
    name: str
    inputs: dict[str, Any]


@dataclass
class TurnResult:
    """The outcome of one model inference call.

    done=False: the model wants to call tools — check tool_calls.
    done=True:  the model produced a final text answer — check text.
    """

    done: bool
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Neutral conversation helpers — loop.py uses these so it never builds
# raw turn dicts by hand, keeping the format consistent.
# ---------------------------------------------------------------------------


def make_user_turn(text: str) -> dict[str, Any]:
    return {"role": "user", "text": text}


def make_assistant_turn(
    text: str | None = None,
    tool_calls: list[ToolCall] | None = None,
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "text": text,
        # Store tool_calls as plain dicts so no dataclass objects leak into the
        # conversation list (which may eventually be serialised or inspected).
        "tool_calls": [
            {"id": tc.id, "name": tc.name, "inputs": tc.inputs}
            for tc in (tool_calls or [])
        ],
    }


def make_tool_results_turn(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Each result dict must have keys: id, name, content."""
    return {"role": "tool_results", "results": results}


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ProviderAdapter(Protocol):
    """Interface every LLM backend must satisfy.

    Using a Protocol (structural typing) instead of an ABC means adapters
    don't have to import or subclass anything from this module — they just
    need a matching complete() signature. Type-checkers verify conformance.
    """

    def complete(
        self,
        system: str,
        conversation: Conversation,
        tools: list[dict[str, Any]],
    ) -> TurnResult:
        """Run one inference call and return a normalised result.

        Args:
            system:       System prompt string (injected with today's date).
            conversation: Full neutral-format conversation history so far.
            tools:        Neutral tool schemas from registry.get_tool_schemas().
        """
        ...
