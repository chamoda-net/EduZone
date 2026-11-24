"""Contact form and the support inbox.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-23

- contact_messages: what people send from /contact (platform-level, no tenant). Each one gets a short reference
  (EZ-XXXXXX) that the sender quotes. Status new -> open -> replied -> closed.
- contact_replies: EduZone staff's replies, emailed to the sender and kept with the message.
- The app role has no grant on either table. It submits only through submit_contact_message() (SECURITY DEFINER),
  which enforces the limits: 3 messages per email address and 3 per signed-in account per hour.
"""

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE contact_messages (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            reference     text NOT NULL UNIQUE CHECK (reference ~ '^EZ-[A-Z2-9]{6}$'),
            user_id       uuid REFERENCES users(id) ON DELETE SET NULL,
            name          text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 120),
            email         text NOT NULL CHECK (char_length(email) BETWEEN 3 AND 254),
            phone         text CHECK (char_length(phone) <= 20),
            topic         text NOT NULL CHECK (topic IN ('classes','payments','account','teaching','institutes',
                                                         'courses','partnership','other')),
            subject       text NOT NULL CHECK (char_length(subject) BETWEEN 3 AND 150),
            message       text NOT NULL CHECK (char_length(message) BETWEEN 10 AND 5000),
            status        text NOT NULL DEFAULT 'new' CHECK (status IN ('new','open','replied','closed')),
            staff_note    text CHECK (char_length(staff_note) <= 2000),
            ip            inet,
            user_agent    text,
            created_at    timestamptz NOT NULL DEFAULT now(),
            updated_at    timestamptz NOT NULL DEFAULT now(),
            last_reply_at timestamptz
        )
    """)
    op.execute("CREATE INDEX idx_contact_messages_created ON contact_messages (created_at DESC, id DESC)")
    op.execute("CREATE INDEX idx_contact_messages_email ON contact_messages (lower(email), created_at)")
    op.execute("CREATE INDEX idx_contact_messages_open ON contact_messages (status) WHERE status IN ('new','open')")
    op.execute("""
        CREATE TABLE contact_replies (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            message_id  uuid NOT NULL REFERENCES contact_messages(id) ON DELETE CASCADE,
            author_id   uuid REFERENCES users(id) ON DELETE SET NULL,  -- NULL once that staff account is gone
            body        text NOT NULL CHECK (char_length(body) BETWEEN 2 AND 10000),
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_contact_replies_message ON contact_replies (message_id, created_at)")
    for table in ("contact_messages", "contact_replies"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # Returns the reference, or NULL when a limit is reached. The reference uses no 0/O/1/I.
    op.execute("""
        CREATE FUNCTION submit_contact_message(p_user uuid, p_name text, p_email text, p_phone text, p_topic text,
                                               p_subject text, p_message text, p_ip inet, p_ua text) RETURNS text
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = public, pg_temp AS $$
        DECLARE
            v_ref text;
            v_alphabet constant text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        BEGIN
            IF (SELECT count(*) FROM contact_messages
                WHERE lower(email) = lower(p_email) AND created_at > now() - interval '1 hour') >= 3 THEN
                RETURN NULL;
            END IF;
            IF p_user IS NOT NULL AND (SELECT count(*) FROM contact_messages
                WHERE user_id = p_user AND created_at > now() - interval '1 hour') >= 3 THEN
                RETURN NULL;
            END IF;
            LOOP
                v_ref := 'EZ-' || (SELECT string_agg(substr(v_alphabet, 1 + floor(random() * 32)::int, 1), '')
                                   FROM generate_series(1, 6));
                EXIT WHEN NOT EXISTS (SELECT 1 FROM contact_messages WHERE reference = v_ref);
            END LOOP;
            INSERT INTO contact_messages (reference, user_id, name, email, phone, topic, subject, message, ip, user_agent)
            VALUES (v_ref, p_user, p_name, p_email, p_phone, p_topic, p_subject, p_message, p_ip, p_ua);
            RETURN v_ref;
        END
        $$
    """)
    sig = "submit_contact_message(uuid, text, text, text, text, text, text, inet, text)"
    op.execute(f"ALTER FUNCTION {sig} OWNER TO eduzone_admin")
    op.execute(f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {sig} TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS submit_contact_message(uuid, text, text, text, text, text, text, inet, text)")
    op.execute("DROP TABLE IF EXISTS contact_replies")
    op.execute("DROP TABLE IF EXISTS contact_messages")
