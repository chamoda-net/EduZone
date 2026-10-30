"""Server-side user-facing text (SMS, emails). Keys only in code; text lives here.

`si` and `ta` catalogues are added in v1.1; missing keys fall back to `en`.
"""

from typing import Literal

Language = Literal["en", "si", "ta"]

_CATALOGUES: dict[str, dict[str, str]] = {
    "en": {
        "sms.login_code": "{code} is your {org} login code. It expires in {minutes} minutes. Do not share it.",
        "sms.admin_code": "{code} is your EduZone admin sign-in code. It expires in {minutes} minutes. Never share it.",
        "sms.verify_phone": "{code} is your EduZone code to confirm this number. It expires in {minutes} minutes.",
        "sms.new_device": "{code} is your EduZone code to sign in on a new device. It expires in {minutes} minutes. "
                          "If this wasn't you, change your password.",
        "sms.recovery": "{code} is your EduZone code to reset your password. It expires in {minutes} minutes. Never share it.",
        "email.verify.subject": "Confirm your email for EduZone",
        "email.verify.body": "Hi {name},\n\nConfirm your email address by opening this link:\n{link}\n\n"
                             "The link works for {hours} hours. If you didn't create an EduZone account, ignore this email.",
        "email.recovery.subject": "Reset your EduZone password",
        "email.recovery.body": "Hi {name},\n\nSomeone asked to reset the password for your EduZone account. "
                               "To choose a new password, open this link:\n{link}\n\n"
                               "The link works for {minutes} minutes. If this wasn't you, ignore this email; "
                               "your password stays the same.",
    },
}


def t(key: str, lang: str = "en", **params: object) -> str:
    template = _CATALOGUES.get(lang, {}).get(key) or _CATALOGUES["en"][key]
    return template.format(**params)
