"""Add support for different reading types (new column to readparagraphs).

Revision ID: 504a7d9779b9
Revises: None
Create Date: 2016-10-10 14:43:14.044658

"""

# revision identifiers, used by Alembic.

from timdb.readparagraphtype import ReadParagraphType

revision = '504a7d9779b9'
down_revision = None

from alembic import op
import sqlalchemy as sa

e = sa.Enum('on_screen', 'hover_par', 'click_par', 'click_red', name='readparagraphtype')


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    e.create(op.get_bind(), checkfirst=True)
    op.add_column('readparagraphs',
                  sa.Column('type',
                            e,
                            nullable=False,
                            server_default=ReadParagraphType.click_red.name))
    op.execute('ALTER TABLE readparagraphs DROP CONSTRAINT IF EXISTS readparagraphs_pkey')
    op.execute("""ALTER TABLE readparagraphs
                  ADD CONSTRAINT readparagraphs_pkey
                  PRIMARY KEY (usergroup_id, doc_id, par_id, type)""")
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('readparagraphs', 'type')
    e.drop(op.get_bind())
    ### end Alembic commands ###
