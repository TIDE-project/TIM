"""Add points and comment columns to peer_review

Revision ID: bccb1595773d
Revises: 3fec5685a240
Create Date: 2023-02-20 10:58:50.254962

"""

# revision identifiers, used by Alembic.
revision = 'bccb1595773d'
down_revision = '3fec5685a240'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('peer_review', sa.Column('points', sa.Float(), nullable=True))
    op.add_column('peer_review', sa.Column('comment', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('peer_review', 'comment')
    op.drop_column('peer_review', 'points')
    # ### end Alembic commands ###
