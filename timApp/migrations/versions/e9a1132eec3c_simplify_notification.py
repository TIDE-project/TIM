"""Simplify notification

Revision ID: e9a1132eec3c
Revises: 0c0ed7527991
Create Date: 2022-02-22 15:32:23.116295

"""

# revision identifiers, used by Alembic.
revision = "e9a1132eec3c"
down_revision = "0c0ed7527991"

import sqlalchemy as sa
from alembic import op

e = sa.Enum(
    "DocModified",
    "ParAdded",
    "ParModified",
    "ParDeleted",
    "CommentAdded",
    "CommentModified",
    "CommentDeleted",
    name="notificationtype",
)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    t_notification = sa.Table(
        "notification",
        sa.MetaData(),
        sa.Column("user_id", sa.Integer()),
        sa.Column("doc_id", sa.Integer()),
        sa.Column("email_doc_modify", sa.Boolean()),
        sa.Column("email_comment_add", sa.Boolean()),
        sa.Column("email_comment_modify", sa.Boolean()),
    )

    con = op.get_bind()

    notifications = con.execute(
        sa.select(
            [
                t_notification.c.user_id,
                t_notification.c.doc_id,
                t_notification.c.email_doc_modify,
                t_notification.c.email_comment_add,
                t_notification.c.email_comment_modify,
            ]
        )
    ).fetchall()

    for (
        user_id,
        doc_id,
        email_doc_modify,
        email_comment_add,
        email_comment_modify,
    ) in notifications:
        con.execute(
            sa.delete(t_notification).where(
                (t_notification.c.user_id == user_id)
                & (t_notification.c.doc_id == doc_id)
            )
        )

    op.add_column("notification", sa.Column("block_id", sa.Integer(), nullable=False))
    op.drop_constraint("notification_pkey", "notification", type_="primary")
    op.drop_constraint("notification_doc_id_fkey", "notification", type_="foreignkey")
    op.create_foreign_key(None, "notification", "block", ["block_id"], ["id"])
    op.add_column(
        "notification",
        sa.Column(
            "notification_type",
            e,
            nullable=False,
        ),
    )
    op.drop_column("notification", "doc_id")
    op.drop_column("notification", "email_comment_modify")
    op.drop_column("notification", "email_comment_add")
    op.drop_column("notification", "email_doc_modify")
    op.create_primary_key(
        "notification_pkey",
        "notification",
        ["user_id", "block_id", "notification_type"],
    )

    t_notification_new = sa.Table(
        "notification",
        sa.MetaData(),
        sa.Column("user_id", sa.Integer()),
        sa.Column("block_id", sa.Integer()),
        sa.Column("notification_type", e),
    )

    for (
        user_id,
        doc_id,
        email_doc_modify,
        email_comment_add,
        email_comment_modify,
    ) in notifications:
        new_notifications = []
        if email_doc_modify:
            new_notifications.extend(
                [
                    "DocModified",
                    "ParAdded",
                    "ParModified",
                    "ParDeleted",
                ]
            )
        if email_comment_add:
            new_notifications.extend(
                [
                    "CommentAdded",
                ]
            )
        if email_comment_modify:
            new_notifications.extend(
                [
                    "CommentModified",
                    "CommentDeleted",
                ]
            )

        for notification_type in new_notifications:
            con.execute(
                t_notification_new.insert().values(
                    user_id=user_id,
                    block_id=doc_id,
                    notification_type=notification_type,
                )
            )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    t_notification_new = sa.Table(
        "notification",
        sa.MetaData(),
        sa.Column("user_id", sa.Integer()),
        sa.Column("block_id", sa.Integer()),
        sa.Column("notification_type", e),
    )

    con = op.get_bind()
    notifications = con.execute(
        sa.select(
            [
                t_notification_new.c.user_id,
                t_notification_new.c.block_id,
                t_notification_new.c.notification_type,
            ]
        )
    ).fetchall()

    for user_id, block_id, notification_type in notifications:
        con.execute(
            sa.delete(t_notification_new).where(
                (t_notification_new.c.user_id == user_id)
                & (t_notification_new.c.block_id == block_id)
            )
        )

    old_notifications = dict()

    for user_id, block_id, notification_type in notifications:
        if (user_id, block_id) not in old_notifications:
            old_notifications[(user_id, block_id)] = {
                "user_id": user_id,
                "doc_id": block_id,
                "email_doc_modify": False,
                "email_comment_add": False,
                "email_comment_modify": False,
            }
        match notification_type:
            case "DocModified" | "ParAdded" | "ParModified" | "ParDeleted":
                old_notifications[(user_id, block_id)]["email_doc_modify"] = True
            case "CommentAdded":
                old_notifications[(user_id, block_id)]["email_comment_add"] = True
            case "CommentModified" | "CommentDeleted":
                old_notifications[(user_id, block_id)]["email_comment_modify"] = True

    # Drop the new primary key constraint
    op.add_column(
        "notification",
        sa.Column(
            "email_doc_modify", sa.BOOLEAN(), autoincrement=False, nullable=False
        ),
    )
    op.add_column(
        "notification",
        sa.Column(
            "email_comment_add", sa.BOOLEAN(), autoincrement=False, nullable=False
        ),
    )
    op.add_column(
        "notification",
        sa.Column(
            "email_comment_modify", sa.BOOLEAN(), autoincrement=False, nullable=False
        ),
    )
    op.drop_constraint("notification_pkey", "notification", type_="primary")
    op.add_column("notification", sa.Column("doc_id", sa.Integer(), nullable=False))
    op.create_foreign_key(None, "notification", "block", ["doc_id"], ["id"])
    op.drop_column("notification", "notification_type")
    op.drop_constraint("notification_block_id_fkey", "notification", type_="foreignkey")
    op.drop_column("notification", "block_id")
    op.create_primary_key("notification_pkey", "notification", ["user_id", "doc_id"])

    t_notification = sa.Table(
        "notification",
        sa.MetaData(),
        sa.Column("user_id", sa.Integer()),
        sa.Column("doc_id", sa.Integer()),
        sa.Column("email_doc_modify", sa.Boolean()),
        sa.Column("email_comment_add", sa.Boolean()),
        sa.Column("email_comment_modify", sa.Boolean()),
    )

    for old_notif in old_notifications.values():
        con.execute(
            t_notification.insert().values(
                user_id=old_notif["user_id"],
                doc_id=old_notif["doc_id"],
                email_doc_modify=old_notif["email_doc_modify"],
                email_comment_add=old_notif["email_comment_add"],
                email_comment_modify=old_notif["email_comment_modify"],
            )
        )

    # ### end Alembic commands ###
