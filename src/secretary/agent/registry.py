"""Tool registry: @tool decorator + provider-neutral JSON-schema builder."""

import inspect
from typing import Any, Callable

_REGISTRY: dict[str, dict[str, Any]] = {}  # name -> {fn, schema}

_PY_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def tool(fn: Callable) -> Callable:
    """Decorator: register a function as an AI-callable tool.

    JSON schema is derived from type annotations. Parameter descriptions
    are parsed from the 'Args:' section of the docstring (Google style).
    """
    sig = inspect.signature(fn)
    param_docs = _parse_args_section(fn.__doc__ or "")
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        ann = param.annotation
        json_type = _PY_TO_JSON.get(ann, "string")
        prop: dict[str, Any] = {"type": json_type}
        if name in param_docs:
            prop["description"] = param_docs[name]
        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)

    description = (fn.__doc__ or "").strip().split("\n")[0].strip()
    schema = {
        "name": fn.__name__,
        "description": description,
        # "parameters" is the neutral key. Each provider adapter renames or wraps
        # this into its own wire format (Anthropic uses "input_schema"; OpenAI/Groq
        # keep "parameters" but add a {"type": "function", "function": {...}} envelope).
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }
    _REGISTRY[fn.__name__] = {"fn": fn, "schema": schema}
    return fn


def get_tool_schemas() -> list[dict[str, Any]]:
    return [v["schema"] for v in _REGISTRY.values()]


def dispatch(name: str, inputs: dict[str, Any]) -> Any:
    entry = _REGISTRY.get(name)
    if not entry:
        raise ValueError(f"Unknown tool: {name!r}")
    return entry["fn"](**inputs)


def list_tools() -> list[str]:
    return list(_REGISTRY.keys())


def _parse_args_section(docstring: str) -> dict[str, str]:
    """Extract param descriptions from a Google-style 'Args:' block."""
    result: dict[str, str] = {}
    in_args = False
    current_param: str | None = None

    for line in docstring.splitlines():
        stripped = line.strip()
        if stripped == "Args:":
            in_args = True
            continue
        if in_args:
            if stripped and not line.startswith(" ") and not line.startswith("\t"):
                # Hit a new top-level section — stop
                break
            if ":" in stripped and not stripped.startswith(" "):
                param, _, desc = stripped.partition(":")
                current_param = param.strip()
                result[current_param] = desc.strip()
            elif current_param and stripped:
                # Continuation line for the same param
                result[current_param] += " " + stripped

    return result
