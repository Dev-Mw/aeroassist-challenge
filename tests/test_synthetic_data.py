from pathlib import Path


def test_every_policy_is_explicitly_synthetic() -> None:
    for path in Path("knowledge_base").glob("*.md"):
        text = path.read_text(encoding="utf-8").lower()
        assert "synthetic: true" in text
        assert "fictic" in text or "sintético" in text

