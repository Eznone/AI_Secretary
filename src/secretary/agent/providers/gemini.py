"""
Google Gemini adapter — uses the current google-genai SDK (google.genai).

Note: the older `google-generativeai` package is deprecated; this adapter uses
the replacement `google-genai` package (import path: `google.genai`).

Gemini's SDK has the most distinctive shape of the three providers:

  Tool schema:
    Neutral dicts → types.FunctionDeclaration objects bundled in a
    types.Tool(function_declarations=[…]) wrapper, passed via GenerateContentConfig.

  Conversation:
    Uses types.Content(role=…, parts=[…]) objects instead of plain dicts.
    Role must be "user" or "model" (not "assistant").
    System prompt goes in GenerateContentConfig(system_instruction=…).

  Tool calls (response → neutral):
    Detected by checking response parts for a part.function_call that has a name.
    Gemini does NOT assign call IDs — we generate short UUIDs so the neutral
    format stays uniform and results can be correlated.

  Tool results (neutral → Gemini):
    types.Part.from_function_response(name=…, response={…}) requires the function
    NAME, not an ID. That's why neutral tool_results entries carry a "name" field
    in addition to "id" and "content".
"""

from __future__ import annotations

import uuid

from google import genai
from google.genai import types

from secretary.agent.providers.base import Conversation, ToolCall, TurnResult
from secretary.config import settings


class GeminiAdapter:
    """Wraps the google-genai SDK to satisfy the ProviderAdapter protocol."""

    def __init__(self) -> None:
        key = settings.gemini_api_key
        if not key:
            raise RuntimeError(
                "No Gemini API key configured. Run /auth-llm to set one up."
            )
        # The new SDK uses a Client instance rather than module-level configure().
        self._client = genai.Client(api_key=key)
        self._model_name = settings.gemini_model

    def complete(
        self,
        system: str,
        conversation: Conversation,
        tools: list[dict],
    ) -> TurnResult:
        gemini_tools = self._translate_schemas(tools)
        history = self._translate_conversation(conversation)

        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=gemini_tools,
        )

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=history,
            config=config,
        )

        parts = response.candidates[0].content.parts
        fc_parts = [p for p in parts if p.function_call and p.function_call.name]

        if fc_parts:
            tool_calls = []
            for part in fc_parts:
                fc = part.function_call
                # Generate a short ID since Gemini assigns none natively.
                call_id = f"gc_{uuid.uuid4().hex[:8]}"
                tool_calls.append(ToolCall(
                    id=call_id,
                    name=fc.name,
                    inputs=dict(fc.args),  # MapComposite → plain dict
                ))
            return TurnResult(done=False, tool_calls=tool_calls)

        return TurnResult(done=True, text=response.text or "")

    # ------------------------------------------------------------------
    # Translation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _translate_schemas(neutral_schemas: list[dict]) -> list[types.Tool]:
        # Build FunctionDeclaration for each tool, then bundle them in one Tool.
        declarations = []
        for s in neutral_schemas:
            params = s["parameters"]
            # Convert JSON Schema properties to Gemini Schema objects.
            properties = {
                name: types.Schema(
                    type=prop.get("type", "string").upper(),
                    description=prop.get("description", ""),
                )
                for name, prop in params.get("properties", {}).items()
            }
            declarations.append(
                types.FunctionDeclaration(
                    name=s["name"],
                    description=s["description"],
                    parameters=types.Schema(
                        type="OBJECT",
                        properties=properties,
                        required=params.get("required", []),
                    ),
                )
            )
        return [types.Tool(function_declarations=declarations)]

    @staticmethod
    def _translate_conversation(conversation: Conversation) -> list[types.Content]:
        contents: list[types.Content] = []

        for turn in conversation:
            role = turn["role"]

            if role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(turn["text"])],
                ))

            elif role == "assistant":
                if turn.get("tool_calls"):
                    # Tool-calling turns use function_call parts with role="model".
                    parts = [
                        types.Part.from_function_call(name=tc["name"], args=tc["inputs"])
                        for tc in turn["tool_calls"]
                    ]
                    contents.append(types.Content(role="model", parts=parts))
                else:
                    contents.append(types.Content(
                        role="model",
                        parts=[types.Part.from_text(turn["text"] or "")],
                    ))

            elif role == "tool_results":
                # All results for a single assistant turn go into one user Content.
                # The "name" field in each result is required by Gemini here
                # (it matches the result to the FunctionDeclaration by name, not by ID).
                parts = [
                    types.Part.from_function_response(
                        name=r["name"],
                        response={"content": r["content"]},
                    )
                    for r in turn["results"]
                ]
                contents.append(types.Content(role="user", parts=parts))

        return contents
