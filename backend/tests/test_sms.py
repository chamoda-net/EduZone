import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.integrations.sms import get_sms_sender
from app.integrations.sms.file import FileSmsSender


async def test_file_outbox_appends_json_lines(tmp_path: Path) -> None:
    outbox = tmp_path / "nested" / "outbox.jsonl"
    sender = FileSmsSender(outbox)
    await sender.send("+94771234567", "Your code is 123456")
    await sender.send("+94770000000", "Your code is 654321")
    lines = [json.loads(x) for x in outbox.read_text(encoding="utf-8").splitlines()]
    assert [x["phone"] for x in lines] == ["+94771234567", "+94770000000"]
    assert lines[0]["message"] == "Your code is 123456"


def test_file_outbox_is_refused_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "file")
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="not available"):
            get_sms_sender()
    finally:
        get_settings.cache_clear()
