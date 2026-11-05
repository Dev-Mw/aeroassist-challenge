"""Small dependency-free runner for the public golden set."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def post_json(url: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def normalized(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def check_case(base_url: str, case: dict) -> list[str]:
    status, body = post_json(f"{base_url.rstrip('/')}/v1/chat", case["request"])
    expected = case["expect"]
    errors: list[str] = []
    if status != expected.get("status", 200):
        errors.append(f"status={status}")
        return errors
    tool_names = [item.get("name") for item in body.get("tool_calls", [])]
    citations = [item.get("doc_id") for item in body.get("citations", [])]
    if expected.get("tool_any") and not set(expected["tool_any"]) & set(tool_names):
        errors.append(f"missing tool in {expected['tool_any']}")
    if set(expected.get("forbid_tools", [])) & set(tool_names):
        errors.append("forbidden tool called")
    if expected.get("citation_any") and not set(expected["citation_any"]) & set(citations):
        errors.append(f"missing citation in {expected['citation_any']}")
    if body.get("requires_confirmation") is not expected.get("requires_confirmation", False):
        errors.append("requires_confirmation mismatch")
    text = normalized(body.get("answer", ""))
    if expected.get("must_contain_any") and not any(
        token.lower() in text for token in expected["must_contain_any"]
    ):
        errors.append("answer lacks expected evidence")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("evaluation/public_golden.jsonl"),
    )
    args = parser.parse_args()
    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line]
    passed = 0
    for case in cases:
        errors = check_case(args.base_url, case)
        label = "PASS" if not errors else "FAIL"
        print(f"{label} {case['id']}" + (f": {', '.join(errors)}" if errors else ""))
        passed += not errors
    print(f"public score: {passed}/{len(cases)}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())

