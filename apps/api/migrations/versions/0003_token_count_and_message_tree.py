"""token_count per message; drop the linear-chain backstops so messages form a tree

Revision ID: 0003
Revises: 0002

M4: every finished message carries a token_count so the context builder can budget without
re-tokenizing history. Streaming rows have none yet (their text is still arriving).

M5: edits and regenerations create siblings, so one_child_per_parent and
one_root_per_conversation (the M2a linear-chain backstops) go. Siblings are listed by
(parent_id, created_at).
"""

from alembic import op

revision = "0003"
down_revision = "0002"

# Same rule as the providers' estimate_tokens: ceil(characters / 4) over all text blocks.
_ESTIMATE = """
    ceil(COALESCE((SELECT sum(char_length(b->>'text'))
                   FROM jsonb_array_elements(content) b), 0) / 4.0)::integer
"""


def upgrade() -> None:
    op.execute("ALTER TABLE messages ADD COLUMN token_count integer")
    # Replies that completed already know their real size; everything else gets the estimate.
    op.execute(
        f"""
        UPDATE messages
        SET token_count = COALESCE((usage->>'output_tokens')::integer, {_ESTIMATE})
        WHERE status <> 'streaming'
        """
    )
    op.execute(
        """
        ALTER TABLE messages
            ADD CONSTRAINT messages_token_count_iff_not_streaming
                CHECK ((status = 'streaming') = (token_count IS NULL)),
            ADD CONSTRAINT messages_token_count_non_negative CHECK (token_count >= 0)
        """
    )

    op.execute("DROP INDEX one_child_per_parent")
    op.execute("DROP INDEX one_root_per_conversation")
    op.execute("CREATE INDEX messages_parent_id_created_at_idx ON messages (parent_id, created_at)")


def downgrade() -> None:
    # Fails if any branch exists: a tree cannot be squeezed back into the linear-chain rules.
    op.execute("DROP INDEX messages_parent_id_created_at_idx")
    op.execute(
        "CREATE UNIQUE INDEX one_root_per_conversation "
        "ON messages (conversation_id) WHERE parent_id IS NULL"
    )
    op.execute("CREATE UNIQUE INDEX one_child_per_parent ON messages (parent_id)")
    op.execute(
        """
        ALTER TABLE messages
            DROP CONSTRAINT messages_token_count_iff_not_streaming,
            DROP CONSTRAINT messages_token_count_non_negative
        """
    )
    op.execute("ALTER TABLE messages DROP COLUMN token_count")
