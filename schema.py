"""Tiny JSON-schema-style validator (stdlib only).

Supports the subset ORIGIN needs to validate structured proposals coming from
LLM providers or mission specs: type, required, properties, enum, minimum,
maximum, minLength, maxLength, items, additionalProperties.

`validate(value, schema)` returns a list of problem strings ([] == valid).
Nothing here executes or interprets content — it only checks shape.
"""
from __future__ import annotations

_TYPES = {"object": dict, "array": list, "string": str,
          "number": (int, float), "integer": int, "boolean": bool}


def validate(value, schema: dict, path: str = "$") -> list[str]:
    probs: list[str] = []
    t = schema.get("type")
    if t:
        py = _TYPES.get(t)
        if py is None:
            return [f"{path}: unknown schema type {t!r}"]
        if t == "number" and isinstance(value, bool):
            probs.append(f"{path}: expected number, got bool")
        elif not isinstance(value, py) or (t == "integer" and isinstance(value, bool)):
            return [f"{path}: expected {t}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        probs.append(f"{path}: {value!r} not in allowed {schema['enum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            probs.append(f"{path}: shorter than {schema['minLength']} chars")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            probs.append(f"{path}: longer than {schema['maxLength']} chars")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            probs.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            probs.append(f"{path}: {value} > maximum {schema['maximum']}")
    if isinstance(value, dict) and (schema.get("properties") or schema.get("required")):
        for req in schema.get("required", []):
            if req not in value:
                probs.append(f"{path}: missing required field {req!r}")
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                probs.extend(validate(v, props[k], f"{path}.{k}"))
            elif schema.get("additionalProperties") is False:
                probs.append(f"{path}: unexpected field {k!r}")
    if isinstance(value, list) and "items" in schema:
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            probs.append(f"{path}: more than {schema['maxItems']} items")
        for i, item in enumerate(value):
            probs.extend(validate(item, schema["items"], f"{path}[{i}]"))
    return probs
