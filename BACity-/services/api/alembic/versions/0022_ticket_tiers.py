"""Multiple admission tiers may share the same publisher page."""
from alembic import op
revision='0022'
down_revision='0021'
branch_labels=None
depends_on=None

def upgrade():
    # Existing full offer titles remain in source observations and merge audits.
    op.execute("UPDATE event_offers SET label=substring(label from '(?i)(VIP(?:[[:space:]]+fast[[:space:]]+track)?|FLEXI|STANDARD(?:[[:space:]]+ADMISSION)?|GENERAL ADMISSION|KLASIK|CLASSIC|MEET[[:space:]]*&?[[:space:]]*GREET|BACKSTAGE)[[:space:]]*$') WHERE label ~* '(VIP([[:space:]]+fast[[:space:]]+track)?|FLEXI|STANDARD|GENERAL ADMISSION|KLASIK|CLASSIC|MEET[[:space:]]*&?[[:space:]]*GREET|BACKSTAGE)[[:space:]]*$'")
    op.drop_constraint('uq_offer_event_url','event_offers',type_='unique')
    op.create_unique_constraint('uq_offer_event_url_label','event_offers',['event_id','source_url','label'])

def downgrade():
    op.drop_constraint('uq_offer_event_url_label','event_offers',type_='unique')
    op.create_unique_constraint('uq_offer_event_url','event_offers',['event_id','source_url'])
