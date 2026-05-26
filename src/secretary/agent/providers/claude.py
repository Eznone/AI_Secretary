"""
Anthropic Claude adapter.

Translation — neutral → Anthropic wire format:

  Tool schema:
    {"name":…, "description":…, "parameters": {…}}
    → {"name":…, "description":…, "input_schema": {…}}   (key renamed)

  Conversation turns:
    user          → {"role": "user",      "content": "<text>"}
    assistant/txt → {"role": "assistant", "content": "<text>"}
    assistant/tcs → {"role": "assistant", "content": [{"type":"tool_use","id":…,"name":…,"input":{…}}]}
    tool_results  → {"role": "user",      "content": [{"type":"tool_result","tool_use_id":…,"content":…}]}
                    (Anthropic batches all results into a single user turn, unlike OpenAI)

  Stop condition: response.stop_reason == "tool_use"
"""

from __future__ import annotations

import anthropic

from secretary.agent.providers.base import Conversation, ToolCall, TurnResult
from secretary.config import settings


class ClaudeAdapter:
    """Wraps the Anthropic SDK to satisfy the ProviderAdapter protocol."""

    def __init__(self) -> None:
        key = settings.anthropic_api_key
        if not key:
            raise RuntimeError(
                "No Anthropic API key configured. Run /authenticate to set one up."
            )
        self._client = anthropic.Anthropic(api_key=key)
        self._model = settings.anthropic_model

    def complete(
        self,
        system: str,
        conversation: Conversation,
        tools: list[dict],
    ) -> TurnResult:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            tools=[self._translate_schema(t) for t in tools],
            messages=self._translate_conversation(conversation),
        )

        if response.stop_reason == "tool_use":
            return TurnResult(
                done=False,
                tool_calls=[
                    ToolCall(id=b.id, name=b.name, inputs=b.input)
                    for b in response.content
                    if b.type == "tool_use"
                ],
            )

        final_text = next((b.text for b in response.content if hasattr(b, "text")), "")
        return TurnResult(done=True, text=final_text)

    # ------------------------------------------------------------------
    # Translation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _translate_schema(neutral: dict) -> dict:
        # Anthropic calls this field "input_schema"; the registry stores "parameters".
        return {
            "name": neutral["name"],
            "description": neutral["description"],
            "input_schema": neutral["parameters"],
        }

    @staticmethod
    def _translate_conversation(conversation: Conversation) -> list[dict]:
        messages = []
        for turn in conversation:
            role = turn["role"]

            if role == "user":
                messages.append({"role": "user", "content": turn["text"]})

            elif role == "assistant":
                if turn.get("tool_calls"):
                    messages.append(
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "input": tc["inputs"],
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
                # Anthropic expects all results as a single user turn with tool_result blocks.
                # This differs from OpenAI/Groq, which uses one "tool" role message per result.
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": r["id"],
                                "content": r["content"],
                            }
                            for r in turn["results"]
                        ],
                    }
                )

        return messages
