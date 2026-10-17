"""Normalize historical job/artifact records at the read boundary only."""

from copy import deepcopy
from uuid import uuid5, NAMESPACE_URL


def normalize_artifact(data: dict) -> dict:
    result = deepcopy(data)
    for old, new in (("type", "kind"), ("name", "filename")):
        if old in result:
            value = result.pop(old)
            if new in result and result[new] != value:
                raise ValueError(f"Conflicting artifact fields: {old}/{new}")
            result[new] = value
    return result


def normalize_persisted_job(data: dict) -> dict:
    result = deepcopy(data)
    if result.get("result") is not None:
        result["result"]["artifacts"] = [
            normalize_artifact(artifact) for artifact in result["result"].get("artifacts", [])
        ]
    return result


def normalize_persisted_submission(data: dict) -> dict:
    result = deepcopy(data)
    result["artifacts"] = [normalize_artifact(artifact) for artifact in result.get("artifacts", [])]
    return result


def normalize_working_copy(data: dict) -> dict:
    """Legacy IDs are stable across reads, including before the next save."""
    result = deepcopy(data)
    for index, section in enumerate(result.get("sections", [])):
        section.setdefault("id", str(uuid5(NAMESPACE_URL, f"cv:{result['job_id']}:role:{index}")))
        for item_index, item in enumerate(section.get("items", [])):
            item.setdefault("id", str(uuid5(NAMESPACE_URL, f"cv:{section['id']}:bullet:{item_index}")))
            # Old scores have no trustworthy scored-text provenance. Keep them
            # visible, but require rescore before treating an edited score as fresh.
            item.setdefault("scored_text", None)
    return result
