"""
Groq adapter.

Groq's API mirrors the OpenAI Chat Completions shape, so the translation is
straightforward. The main differences from Anthropic:

  Tool schema:
    {"name":…, "description":…, "parameters": {…}}
    → {"type":"function", "function": {"name":…, "description":…, "parameters":{…}}}

  Conversation turns:
    System prompt is prepended as {"role":"system", "content":…} inside messages
    (Anthropic takes it as a separate parameter).

    tool_results  → one {"role":"tool", "tool_call_id":…, "content":…} per result
                    (one message per result, not a batched content array like Anthropic)

    assistant/tcs → {"role":"assistant", "content":None, "tool_calls":[…]}
                    where each tool_call.function.arguments is a JSON *string*.

  Stop condition: choice.finish_reason == "tool_calls"
                  (also check message.tool_calls is not None in case some model
                   variants set finish_reason="stop" even when tools were called)

  Tool call arguments arrive as a JSON string from Groq → json.loads() before
  building the neutral ToolCall.
"""

from __future__ import annotations

import json

from groq import BadRequestError, Groq

from secretary.agent.providers.base import Conversation, ToolCall, TurnResult
from secretary.config import settings


class GroqAdapter:
    """Wraps the Groq SDK to satisfy the ProviderAdapter protocol."""

    def __init__(self) -> None:
        key = settings.groq_api_key
        if not key:
            raise RuntimeError(
                "No Groq API key configured. Run /authenticate to set one up."
            )
        self._client = Groq(api_key=key)
        self._model = settings.groq_model

    def complete(
        self,
        system: str,
        conversation: Conversation,
        tools: list[dict],
    ) -> TurnResult:
        groq_tools = [self._translate_schema(t) for t in tools]
        messages = self._translate_conversation(system, conversation)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=groq_tools,
            )
        except BadRequestError as exc:
            if not _is_tool_generation_error(exc):
                raise
            # Groq rejected the model's own tool-call output because generated
            # arguments didn't match the schema (e.g. integer sent as string).
            # Retry without tools so the model can respond conversationally.
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )

        choice = response.choices[0]
        # Check message.tool_calls first — some model variants return finish_reason="stop"
        # even when tool calls are present.
        raw_tool_calls = choice.message.tool_calls
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                try:
                    inputs = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    inputs = {}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, inputs=inputs)
                )
            return TurnResult(done=False, tool_calls=tool_calls)

        return TurnResult(done=True, text=choice.message.content or "")

    # ------------------------------------------------------------------
    # Translation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _translate_schema(neutral: dict) -> dict:
        # OpenAI/Groq wraps each function in a {"type":"function","function":{…}} envelope.
        return {
            "type": "function",
            "function": {
                "name": neutral["name"],
                "description": neutral["description"],
                "parameters": neutral["parameters"],
            },
        }

    @staticmethod
    def _translate_conversation(system: str, conversation: Conversation) -> list[dict]:
        # System prompt lives inside the messages list for OpenAI/Groq, not as a
        # separate parameter like it does for Anthropic.
        messages: list[dict] = [{"role": "system", "content": system}]

        for turn in conversation:
            role = turn["role"]

            if role == "user":
                messages.append({"role": "user", "content": turn["text"]})

            elif role == "assistant":
                if turn.get("tool_calls"):
                    # Arguments must be serialised to a JSON string per the OpenAI spec.
                    messages.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        "arguments": json.dumps(tc["inputs"]),
                                    },
                                }
                                for tc in turn["tool_calls"]
                            ],
                        }
                    )
                else:
                    messages.append(
                        {"role": "assistant", "content": turn["text"] or ""}
                    )

            elif role == "tool_results":
                # One message per result (OpenAI convention), unlike Anthropic which
                # batches all results into a single user turn.
                for r in turn["results"]:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": r["id"],
                            "content": r["content"],
                        }
                    )

        return messages


def _is_tool_generation_error(exc: BadRequestError) -> bool:
    """Return True for Groq 400s caused by the model generating invalid tool arguments.

    Groq validates model-generated tool-call JSON against the declared schema and
    rejects it with code "tool_use_failed" when types don't match (e.g. an integer
    parameter sent as a string). This is distinct from a malformed API request on
    our side, so only these errors should trigger a tool-free retry.
    """
    return exc.status_code == 400 and "tool_use_failed" in str(exc)
