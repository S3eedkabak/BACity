"""Private BACity group decision sessions and voting.

Revision ID: 0009
Revises: 0008
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE group_sessions (
            id UUID NOT NULL,
            host_id UUID NOT NULL,
            name VARCHAR(80) NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'open',
            target_date DATE NOT NULL,
            starts_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            ends_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            categories JSONB NOT NULL DEFAULT '[]'::jsonb,
            max_participants INTEGER NOT NULL DEFAULT 8,
            invite_token_hash VARCHAR(64) UNIQUE,
            invite_expires_at TIMESTAMP WITHOUT TIME ZONE,
            expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            purge_after TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(host_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT ck_group_session_status CHECK (status IN ('open','ready','voting','completed','expired','cancelled')),
            CONSTRAINT ck_group_session_participant_limit CHECK (max_participants >= 2 AND max_participants <= 12),
            CONSTRAINT ck_group_session_window CHECK (ends_at > starts_at)
        )
        """
    )
    op.execute("CREATE INDEX ix_group_sessions_host_id ON group_sessions (host_id)")
    op.execute("CREATE INDEX ix_group_sessions_status ON group_sessions (status)")
    op.execute("CREATE INDEX ix_group_sessions_host_status ON group_sessions (host_id, status)")
    op.execute("CREATE INDEX ix_group_sessions_expiration ON group_sessions (expires_at, purge_after)")

    op.execute(
        """
        CREATE TABLE group_participants (
            id UUID NOT NULL,
            group_id UUID NOT NULL,
            user_id UUID NOT NULL,
            liked_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
            disliked_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
            ready BOOLEAN NOT NULL DEFAULT FALSE,
            joined_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(group_id) REFERENCES group_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT uq_group_participant UNIQUE (group_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_group_participants_group_id ON group_participants (group_id)")
    op.execute("CREATE INDEX ix_group_participants_user_id ON group_participants (user_id)")
    op.execute("CREATE INDEX ix_group_participants_user_group ON group_participants (user_id, group_id)")

    op.execute(
        """
        CREATE TABLE group_match_rounds (
            id UUID NOT NULL,
            group_id UUID NOT NULL,
            round_number INTEGER NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'voting',
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            revealed_at TIMESTAMP WITHOUT TIME ZONE,
            PRIMARY KEY (id),
            FOREIGN KEY(group_id) REFERENCES group_sessions(id) ON DELETE CASCADE,
            CONSTRAINT uq_group_match_round_number UNIQUE (group_id, round_number),
            CONSTRAINT ck_group_match_round_status CHECK (status IN ('voting','completed'))
        )
        """
    )
    op.execute("CREATE INDEX ix_group_match_rounds_group_id ON group_match_rounds (group_id)")
    op.execute("CREATE INDEX ix_group_match_rounds_status ON group_match_rounds (status)")
    op.execute("CREATE UNIQUE INDEX uq_group_match_active_round ON group_match_rounds (group_id) WHERE status = 'voting'")

    op.execute(
        """
        CREATE TABLE group_candidates (
            id UUID NOT NULL,
            round_id UUID NOT NULL,
            event_id UUID NOT NULL,
            position INTEGER NOT NULL,
            match_score DOUBLE PRECISION NOT NULL,
            explanations JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(round_id) REFERENCES group_match_rounds(id) ON DELETE CASCADE,
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            CONSTRAINT uq_group_candidate_event UNIQUE (round_id, event_id),
            CONSTRAINT uq_group_candidate_position UNIQUE (round_id, position)
        )
        """
    )
    op.execute("CREATE INDEX ix_group_candidates_round_id ON group_candidates (round_id)")
    op.execute("CREATE INDEX ix_group_candidates_event_id ON group_candidates (event_id)")

    op.execute(
        """
        CREATE TABLE group_votes (
            id UUID NOT NULL,
            candidate_id UUID NOT NULL,
            user_id UUID NOT NULL,
            value INTEGER NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(candidate_id) REFERENCES group_candidates(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT uq_group_vote UNIQUE (candidate_id, user_id),
            CONSTRAINT ck_group_vote_value CHECK (value >= -1 AND value <= 1)
        )
        """
    )
    op.execute("CREATE INDEX ix_group_votes_candidate_id ON group_votes (candidate_id)")
    op.execute("CREATE INDEX ix_group_votes_user_id ON group_votes (user_id)")
    op.execute("CREATE INDEX ix_group_votes_user_candidate ON group_votes (user_id, candidate_id)")


def downgrade():
    op.drop_table("group_votes")
    op.drop_table("group_candidates")
    op.drop_table("group_match_rounds")
    op.drop_table("group_participants")
    op.drop_table("group_sessions")
