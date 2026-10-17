"""Normalize historical job/artifact records at the read boundary only."""

from copy import deepcopy


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
