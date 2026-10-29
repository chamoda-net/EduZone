import re

_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")


def normalize_phone(raw: str) -> str:
    """Return E.164, accepting the local forms Sri Lankan users type.

    '077 123 4567' / '0771234567' / '94771234567' / '+94771234567' -> '+94771234567'.
    Raises ValueError for anything else.
    """
    digits = re.sub(r"[\s\-()]", "", raw)
    if re.fullmatch(r"0\d{9}", digits):
        digits = "+94" + digits[1:]
    elif re.fullmatch(r"94\d{9}", digits):
        digits = "+" + digits
    if not _E164.fullmatch(digits):
        raise ValueError("not a valid phone number")
    return digits
