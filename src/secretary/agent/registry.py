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

# Maps JSON schema types to Python cast targets for numeric coercion at dispatch time.
# Booleans are excluded: bool("false") == True in Python, which is semantically wrong.
# Arrays and objects must arrive as proper JSON types, not coerced from strings.
_JSON_COERCIONS: dict[str, type] = {
    "integer": int,
    "number":  float,
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


def _coerce_inputs(inputs: dict[str, Any], schema: dict) -> dict[str, Any]:
    """Cast each input value to the type declared in the tool's JSON schema.

    Guards against LLMs that emit numeric arguments as JSON strings
    (e.g. {"max_results": "10"} instead of {"max_results": 10}).
    Values that cannot be cast are passed through unchanged so the tool
    function can surface a meaningful error.
    """
    properties = schema.get("parameters", {}).get("properties", {})
    coerced: dict[str, Any] = {}
    for key, value in inputs.items():
        prop = properties.get(key, {})
        target = _JSON_COERCIONS.get(prop.get("type", ""))
        if target is not None and not isinstance(value, target):
            try:
                value = target(value)
            except (ValueError, TypeError):
                pass
        coerced[key] = value
    return coerced


def dispatch(name: str, inputs: dict[str, Any]) -> Any:
    entry = _REGISTRY.get(name)
    if not entry:
        raise ValueError(f"Unknown tool: {name!r}")
    return entry["fn"](**_coerce_inputs(inputs, entry["schema"]))


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
