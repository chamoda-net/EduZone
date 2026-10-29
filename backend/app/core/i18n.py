"""Server-side user-facing text (SMS, emails). Keys only in code; text lives here.

`si` and `ta` catalogues are added in v1.1; missing keys fall back to `en`.
"""

from typing import Literal

Language = Literal["en", "si", "ta"]

_CATALOGUES: dict[str, dict[str, str]] = {
    "en": {
        "sms.login_code": "{code} is your {org} login code. It expires in {minutes} minutes. Do not share it.",
        "sms.admin_code": "{code} is your EduZone admin sign-in code. It expires in {minutes} minutes. Never share it.",
    },
}


def t(key: str, lang: str = "en", **params: object) -> str:
    template = _CATALOGUES.get(lang, {}).get(key) or _CATALOGUES["en"][key]
    return template.format(**params)
