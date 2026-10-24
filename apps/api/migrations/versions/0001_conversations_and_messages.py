"""conversations and messages

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None

# Frozen snapshots of the Python enums at the time of this migration. A later enum change
# needs its own migration; tests/test_schema_drift.py fails until the two agree again.
STOP_REASONS = ("max_tokens", "complete", "refusal")
ERROR_KINDS = (
    "rate_limited",
    "invalid_request",
    "auth_failed",
    "overloaded",
    "unexpected",
    "refusal",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.execute("CREATE TYPE message_role AS ENUM ('user', 'assistant')")
    op.execute("CREATE TYPE message_status AS ENUM ('done', 'failed', 'cancelled')")

    op.execute(
        """
        CREATE TABLE conversations (
            id uuid PRIMARY KEY,
            title text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE messages (
            id uuid PRIMARY KEY,
            conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
            parent_id uuid,
            role message_role NOT NULL,
            status message_status NOT NULL,
            content jsonb NOT NULL DEFAULT '[]',
            stop_reason text,
            error_kind text,
            model text,
            input_tokens integer,
            output_tokens integer,
            created_at timestamptz NOT NULL,
            finished_at timestamptz,

            CONSTRAINT messages_conversation_id_id_key UNIQUE (conversation_id, id),
            CONSTRAINT messages_parent_fk FOREIGN KEY (conversation_id, parent_id)
                REFERENCES messages (conversation_id, id),

            CONSTRAINT messages_stop_reason_check CHECK ({_in_list("stop_reason", STOP_REASONS)}),
            CONSTRAINT messages_error_kind_check CHECK ({_in_list("error_kind", ERROR_KINDS)}),

            -- Scoped to assistant rows: user rows are 'done' but never carry a stop_reason.
            CONSTRAINT messages_assistant_done_iff_stop_reason
                CHECK (role <> 'assistant' OR (status = 'done') = (stop_reason IS NOT NULL)),
            CONSTRAINT messages_failed_iff_error_kind
                CHECK ((status = 'failed') = (error_kind IS NOT NULL)),
            CONSTRAINT messages_user_is_plain_done
                CHECK (role <> 'user'
                        OR (status = 'done' AND stop_reason IS NULL AND error_kind IS NULL))
        )
        """
    )

    op.execute("CREATE UNIQUE INDEX one_child_per_parent ON messages (parent_id)")
    op.execute(
        "COMMENT ON INDEX one_child_per_parent IS "
        "'M2a linear-chain backstop; dropped in M5 (message tree)'"
    )
    op.execute(
        "CREATE UNIQUE INDEX one_root_per_conversation "
        "ON messages (conversation_id) WHERE parent_id IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE messages")
    op.execute("DROP TABLE conversations")
    op.execute("DROP TYPE message_status")
    op.execute("DROP TYPE message_role")
