"""Enforce certificate references in student preferences.

Використання ШІ: Codex додав очищення сиріт і зовнішній ключ.
Перевірка: регресія міграції на PostgreSQL і тести побажань.
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_FK = "fk_plan_preferences_certificate_program_id_certificate_programs"


def upgrade() -> None:
    op.execute(
        """
        UPDATE plan_preferences
        SET certificate_program_id = NULL
        WHERE certificate_program_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM certificate_programs
              WHERE certificate_programs.id = plan_preferences.certificate_program_id
          )
        """
    )
    with op.batch_alter_table("plan_preferences") as batch:
        batch.create_foreign_key(_FK, "certificate_programs", ["certificate_program_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("plan_preferences") as batch:
        batch.drop_constraint(_FK, type_="foreignkey")
