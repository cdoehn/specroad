"""Small fresh schema factories; never load external resources."""
def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties if required is None else required),
            "additionalProperties": False}

def arr(items):
    return {"type": "array", "items": items}

def text():
    return {"type": "string", "minLength": 1}

def digest():
    return {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}

def revision():
    return {"type": "integer", "minimum": 1}

def expected(properties, required):
    result = obj({**properties, "expected_revision": revision(), "expected_sha256": digest()}, required)
    result["anyOf"] = [{"required": ["expected_revision"]}, {"required": ["expected_sha256"]}]
    return result

def patch_schema():
    # Shape only. RFC 6902 execution/array bounds belong to the next plan step.
    kinds = []
    for name in ("add", "remove", "replace", "move", "copy", "test"):
        fields = {"op": {"const": name}, "path": {"type": "string"}}
        if name in ("add", "replace", "test"):
            fields["value"] = True
        if name in ("move", "copy"):
            fields["from"] = {"type": "string"}
        # RFC 6902 permits additional members; they remain passive and hashed.
        branch = obj(fields); branch["additionalProperties"] = True; kinds.append(branch)
    return arr({"anyOf": kinds})

