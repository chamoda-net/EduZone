"""Create (or reset) an EduZone platform admin and print their authenticator setup.

    python scripts/create_platform_admin.py --phone 0771234567 --name "Chamoda"

Prints an otpauth:// link: open it on the phone, or turn it into a QR code, to add the account
to an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password, ...).
Running it again for the same phone issues a NEW secret; the old authenticator entry stops working.
Run it from a trusted machine; the secret is shown once and never logged by the app.
"""

import argparse
import asyncio

from sqlalchemy import text

from app.core.db import AdminSession, dispose_engines
from app.modules.auth.phone import normalize_phone
from app.modules.platform import totp


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    phone = normalize_phone(args.phone)
    secret = totp.new_secret()
    try:
        async with AdminSession() as s, s.begin():
            user_id = (await s.execute(text("""
                INSERT INTO users (phone, full_name, is_platform_admin) VALUES (:p, :n, true)
                ON CONFLICT (phone) DO UPDATE SET is_platform_admin = true
                RETURNING id
            """), {"p": phone, "n": args.name})).scalar_one()
            await s.execute(text("""
                INSERT INTO platform_admins (user_id, totp_secret) VALUES (:u, :s)
                ON CONFLICT (user_id) DO UPDATE SET totp_secret = EXCLUDED.totp_secret, last_totp_step = 0
            """), {"u": user_id, "s": secret})
            # A new secret ends every existing admin session for this person.
            await s.execute(text("""
                UPDATE platform_admin_sessions SET revoked_at = now(), revoke_reason = 'admin reset'
                WHERE user_id = :u AND revoked_at IS NULL
            """), {"u": user_id})
    finally:
        await dispose_engines()
    print(f"Platform admin ready: {args.name} ({phone})")
    print(f"Authenticator secret: {secret}")
    print(f"Setup link:           {totp.provisioning_uri(secret, phone)}")


if __name__ == "__main__":
    asyncio.run(main())
