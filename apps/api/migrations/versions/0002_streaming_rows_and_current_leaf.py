"""streaming rows, current_leaf_id, text checks instead of enums, usage jsonb

Revision ID: 0002
Revises: 0001

The assistant row is now inserted up front as 'streaming' and finalized with one UPDATE,
so status gains a non-terminal value. Role and status move from Postgres ENUMs to text +
CHECK: adding a value to an ENUM cannot run inside a transaction on older Postgres and
can never be removed, while a CHECK is just dropped and re-added.
"""

from alembic import op

revision = "0002"
down_revision = "0001"

# Frozen snapshots, as in 0001; tests/test_schema_drift.py compares them with the code.
ROLES = ("user", "assistant")
STATUSES = ("streaming", "complete", "error", "cancelled")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    # These name the old status values, so they go before the type change.
    op.execute(
        """
        ALTER TABLE messages
            DROP CONSTRAINT messages_assistant_done_iff_stop_reason,
            DROP CONSTRAINT messages_failed_iff_error_kind,
            DROP CONSTRAINT messages_user_is_plain_done
        """
    )
    op.execute(
        """
            ALTER TABLE messages
                ALTER COLUMN role TYPE text USING role::text,
                ALTER COLUMN status TYPE text USING (
                    CASE status::text WHEN 'done' THEN 'complete'
                                    WHEN 'failed' THEN 'error'
                                    ELSE status::text END
                )
        """
    )
    op.execute("DROP TYPE message_status")
    op.execute("DROP TYPE message_role")

    op.execute("ALTER TABLE messages ADD COLUMN usage jsonb")
    op.execute(
        """
        UPDATE messages
        SET usage = jsonb_build_object('input_tokens', input_tokens,
                                       'output_tokens', output_tokens)
        WHERE input_tokens IS NOT NULL
        """
    )
    op.execute("ALTER TABLE messages DROP COLUMN input_tokens, DROP COLUMN output_tokens")

    op.execute(
        f"""
        ALTER TABLE messages
            ADD CONSTRAINT messages_role_check CHECK ({_in_list("role", ROLES)}),
            ADD CONSTRAINT messages_status_check CHECK ({_in_list("status", STATUSES)}),
            -- Scoped to assistant rows: user rows are 'complete' but never carry a stop_reason.
            ADD CONSTRAINT messages_assistant_complete_iff_stop_reason
                CHECK (role <> 'assistant' OR (status = 'complete') = (stop_reason IS NOT NULL)),
            ADD CONSTRAINT messages_error_iff_error_kind
                CHECK ((status = 'error') = (error_kind IS NOT NULL)),
            ADD CONSTRAINT messages_user_is_plain_complete
                CHECK (role <> 'user'
                        OR (status = 'complete' AND stop_reason IS NULL AND error_kind IS NULL
                            AND usage IS NULL)),
            ADD CONSTRAINT messages_finished_iff_not_streaming
                CHECK ((status = 'streaming') = (finished_at IS NULL))
        """
    )
    # The startup sweep looks for these; normally there are none, so the index stays tiny.
    op.execute("CREATE INDEX messages_streaming_idx ON messages (id) WHERE status = 'streaming'")

    op.execute("ALTER TABLE conversations ADD COLUMN current_leaf_id uuid")
    op.execute(
        """
        UPDATE conversations c
        SET current_leaf_id = m.id
        FROM messages m
        WHERE m.conversation_id = c.id
          AND NOT EXISTS (SELECT 1 FROM messages k WHERE k.parent_id = m.id)
        """
    )
    # Composite, like messages_parent_fk, so the leaf cannot belong to another conversation.
    # Deferred because the two tables point at each other: the check runs at COMMIT.
    op.execute(
        """
        ALTER TABLE conversations
            ADD CONSTRAINT conversations_current_leaf_fk
            FOREIGN KEY (id, current_leaf_id) REFERENCES messages (conversation_id, id)
            DEFERRABLE INITIALLY DEFERRED
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE conversations DROP CONSTRAINT conversations_current_leaf_fk")
    op.execute("ALTER TABLE conversations DROP COLUMN current_leaf_id")

    op.execute("DROP INDEX messages_streaming_idx")
    op.execute(
        """
        ALTER TABLE messages
            DROP CONSTRAINT messages_role_check,
            DROP CONSTRAINT messages_status_check,
            DROP CONSTRAINT messages_assistant_complete_iff_stop_reason,
            DROP CONSTRAINT messages_error_iff_error_kind,
            DROP CONSTRAINT messages_user_is_plain_complete,
            DROP CONSTRAINT messages_finished_iff_not_streaming
        """
    )

    op.execute(
        "ALTER TABLE messages ADD COLUMN input_tokens integer, ADD COLUMN output_tokens integer"
    )
    op.execute(
        """
        UPDATE messages
        SET input_tokens = (usage->>'input_tokens')::integer,
            output_tokens = (usage->>'output_tokens')::integer
        WHERE usage IS NOT NULL
        """
    )
    op.execute("ALTER TABLE messages DROP COLUMN usage")

    # 0001 has no in-flight state: an unfinished reply becomes a failed one.
    op.execute(
        """
        UPDATE messages
        SET status = 'error', error_kind = 'unexpected', finished_at = now()
        WHERE status = 'streaming'
        """
    )
    op.execute("CREATE TYPE message_role AS ENUM ('user', 'assistant')")
    op.execute("CREATE TYPE message_status AS ENUM ('done', 'failed', 'cancelled')")
    op.execute(
        """
        ALTER TABLE messages
            ALTER COLUMN role TYPE message_role USING role::message_role,
            ALTER COLUMN status TYPE message_status USING (
                CASE status WHEN 'complete' THEN 'done'
                            WHEN 'error' THEN 'failed'
                            ELSE status END
            )::message_status
        """
    )
    op.execute(
        """
        ALTER TABLE messages
            ADD CONSTRAINT messages_assistant_done_iff_stop_reason
                CHECK (role <> 'assistant' OR (status = 'done') = (stop_reason IS NOT NULL)),
            ADD CONSTRAINT messages_failed_iff_error_kind
                CHECK ((status = 'failed') = (error_kind IS NOT NULL)),
            ADD CONSTRAINT messages_user_is_plain_done
                CHECK (role <> 'user'
                        OR (status = 'done' AND stop_reason IS NULL AND error_kind IS NULL))
        """
    )
