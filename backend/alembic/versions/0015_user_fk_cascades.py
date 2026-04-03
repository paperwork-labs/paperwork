"""Create missing tables + add ON DELETE cascades to user foreign keys.

Part A: Create 7 tables that exist in ORM models but were missed from
        the 0001_baseline migration (alerts, alert_conditions, notifications,
        notification_preferences, audit_logs, data_change_logs, security_events).

Part B: Add ON DELETE CASCADE/SET NULL to all user foreign keys.
        Policy: CASCADE for user-owned data, SET NULL for audit/tracking.

Lock safety: Sets lock_timeout=10s so the migration fails fast if the
             worker holds locks, instead of hanging until Render kills us.

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


# ── Enum definitions ──────────────────────────────────────────────────

_NOTIFICATION_TYPE_VALS = (
    "portfolio_alert", "strategy_execution", "trade_confirmation",
    "market_alert", "system_status", "user_action",
)
_NOTIFICATION_CHANNEL_VALS = ("discord", "email", "in_app", "sms")
_NOTIFICATION_STATUS_VALS = ("pending", "sent", "failed", "delivered")
_PRIORITY_VALS = ("low", "normal", "high", "urgent")
_AUDIT_EVENT_TYPE_VALS = (
    "user_login", "user_logout", "user_register",
    "portfolio_view", "portfolio_sync",
    "trade_execute", "trade_cancel",
    "strategy_start", "strategy_stop", "strategy_modify",
    "data_import", "data_export", "data_modify", "data_delete",
    "system_start", "system_stop", "system_error",
    "api_call", "settings_change",
)
_AUDIT_LEVEL_VALS = ("debug", "info", "warning", "error", "critical")
_AUDIT_STATUS_VALS = ("success", "failure", "partial", "pending")


# ── FK cascade changes ────────────────────────────────────────────────

_FK_CHANGES = [
    ("watchlists", "user_id", "CASCADE", False),
    ("alerts", "user_id", "CASCADE", False),
    ("notifications", "user_id", "CASCADE", False),
    ("notification_preferences", "user_id", "CASCADE", False),
    ("position_history", "user_id", "CASCADE", False),
    ("portfolio_history", "user_id", "CASCADE", False),
    ("backtest_runs", "user_id", "CASCADE", False),
    ("execution_metrics", "user_id", "CASCADE", False),
    ("agent_actions", "approved_by_id", "SET NULL", False),
    ("signals", "created_by_user_id", "SET NULL", False),
    ("signals", "modified_by_user_id", "SET NULL", False),
    ("strategies", "created_by_user_id", "SET NULL", False),
    ("strategies", "modified_by_user_id", "SET NULL", False),
    ("audit_logs", "user_id", "SET NULL", False),
    ("data_change_logs", "changed_by", "SET NULL", False),
    ("security_events", "investigated_by", "SET NULL", False),
    ("market_tracked_plan", "updated_by_user_id", "SET NULL", False),
    ("categories", "user_id", "SET NULL", False),
    ("strategy_backtests", "user_id", "SET NULL", False),
    ("user_invites", "created_by_user_id", "SET NULL", True),
]


def _fk_name(table: str, column: str) -> str:
    return f"fk_{table}_{column}_users"


def _table_exists(conn, name: str) -> bool:
    result = conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t)"
    ), {"t": name})
    return result.scalar()


def _find_existing_fk(conn, table: str, column: str) -> str | None:
    result = conn.execute(text("""
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = :table
          AND kcu.column_name = :column
          AND ccu.table_name = 'users'
    """), {"table": table, "column": column})
    row = result.fetchone()
    return row[0] if row else None


# ── Part A: create missing tables ─────────────────────────────────────

def _create_tables() -> None:
    # Create all PG enum types first via raw SQL (IF NOT EXISTS)
    conn = op.get_bind()
    enum_defs = [
        ("notificationtype", _NOTIFICATION_TYPE_VALS),
        ("notificationchannel", _NOTIFICATION_CHANNEL_VALS),
        ("notificationstatus", _NOTIFICATION_STATUS_VALS),
        ("priority", _PRIORITY_VALS),
        ("auditeventtype", _AUDIT_EVENT_TYPE_VALS),
        ("auditlevel", _AUDIT_LEVEL_VALS),
        ("auditstatus", _AUDIT_STATUS_VALS),
    ]
    for name, vals in enum_defs:
        vals_sql = ", ".join(f"'{v}'" for v in vals)
        conn.execute(text(
            f"DO $$ BEGIN "
            f"CREATE TYPE {name} AS ENUM ({vals_sql}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; "
            f"END $$;"
        ))

    # Reference existing PG enum types (create_type=False since they exist)
    notif_type = postgresql.ENUM(*_NOTIFICATION_TYPE_VALS, name="notificationtype", create_type=False)
    notif_channel = postgresql.ENUM(*_NOTIFICATION_CHANNEL_VALS, name="notificationchannel", create_type=False)
    notif_status = postgresql.ENUM(*_NOTIFICATION_STATUS_VALS, name="notificationstatus", create_type=False)
    priority_enum = postgresql.ENUM(*_PRIORITY_VALS, name="priority", create_type=False)
    audit_event = postgresql.ENUM(*_AUDIT_EVENT_TYPE_VALS, name="auditeventtype", create_type=False)
    audit_level = postgresql.ENUM(*_AUDIT_LEVEL_VALS, name="auditlevel", create_type=False)
    audit_status = postgresql.ENUM(*_AUDIT_STATUS_VALS, name="auditstatus", create_type=False)

    if not _table_exists(conn, "alerts"):
        op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("is_repeating", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("max_triggers", sa.Integer(), server_default=sa.text("1")),
        sa.Column("current_triggers", sa.Integer(), server_default=sa.text("0")),
        sa.Column("notify_discord", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("notify_email", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("notify_app", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("priority", sa.String(10), server_default=sa.text("'MEDIUM'")),
        sa.Column("sound_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("last_triggered", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("custom_message", sa.Text()),
    )

    if not _table_exists(conn, "alert_conditions"):
        op.create_table(
            "alert_conditions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("condition_type", sa.String(50), nullable=False),
        sa.Column("operator", sa.String(10), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("current_value", sa.Float()),
        sa.Column("indicator_params", sa.JSON()),
        sa.Column("timeframe", sa.String(10), server_default=sa.text("'1D'")),
        sa.Column("is_met", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("last_checked", sa.DateTime(timezone=True)),
        sa.Column("times_met", sa.Integer(), server_default=sa.text("0")),
        sa.Column("logical_operator", sa.String(10), server_default=sa.text("'AND'")),
        sa.Column("group_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    if not _table_exists(conn, "notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("type", notif_type, nullable=False, index=True),
            sa.Column("channel", notif_channel, nullable=False),
            sa.Column("priority", priority_enum, nullable=False, server_default=sa.text("'normal'")),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("formatted_message", sa.Text()),
            sa.Column("status", notif_status, nullable=False, server_default=sa.text("'pending'")),
            sa.Column("source_type", sa.String(50)),
            sa.Column("source_id", sa.String(100)),
            sa.Column("reference_data", sa.JSON()),
            sa.Column("sent_at", sa.DateTime()),
            sa.Column("delivered_at", sa.DateTime()),
            sa.Column("error_message", sa.Text()),
            sa.Column("retry_count", sa.Integer(), server_default=sa.text("0")),
            sa.Column("max_retries", sa.Integer(), server_default=sa.text("3")),
            sa.Column("scheduled_for", sa.DateTime()),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("idx_notifications_user_status", "notifications", ["user_id", "status"])
        op.create_index("idx_notifications_channel", "notifications", ["channel"])
        op.create_index("idx_notifications_scheduled", "notifications", ["scheduled_for"])

    if not _table_exists(conn, "notification_preferences"):
        op.create_table(
            "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("notification_type", notif_type, nullable=False),
        sa.Column("channel", notif_channel, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("min_priority", priority_enum, server_default=sa.text("'normal'")),
        sa.Column("channel_settings", sa.JSON()),
        sa.Column("quiet_hours_start", sa.String(5)),
        sa.Column("quiet_hours_end", sa.String(5)),
        sa.Column("quiet_hours_timezone", sa.String(50), server_default=sa.text("'UTC'")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("idx_preferences_user_type", "notification_preferences", ["user_id", "notification_type"])

    if not _table_exists(conn, "audit_logs"):
        op.create_table(
            "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", audit_event, nullable=False, index=True),
        sa.Column("event_id", sa.String(100)),
        sa.Column("correlation_id", sa.String(100), index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("session_id", sa.String(100)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("level", audit_level, nullable=False, server_default=sa.text("'info'")),
        sa.Column("status", audit_status, nullable=False, server_default="success"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", sa.String(100)),
        sa.Column("action", sa.String(100)),
        sa.Column("request_data", sa.JSON()),
        sa.Column("response_data", sa.JSON()),
        sa.Column("error_details", sa.JSON()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("occurred_at", sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("idx_audit_user_date", "audit_logs", ["user_id", "occurred_at"])
        op.create_index("idx_audit_event_date", "audit_logs", ["event_type", "occurred_at"])
        op.create_index("idx_audit_resource", "audit_logs", ["resource_type", "resource_id"])

    if not _table_exists(conn, "data_change_logs"):
        op.create_table(
            "data_change_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_log_id", sa.Integer(), sa.ForeignKey("audit_logs.id"), index=True),
        sa.Column("table_name", sa.String(100), nullable=False, index=True),
        sa.Column("record_id", sa.String(100), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("old_values", sa.JSON()),
        sa.Column("new_values", sa.JSON()),
        sa.Column("changed_fields", sa.JSON()),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("change_reason", sa.Text()),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("idx_changes_table_record", "data_change_logs", ["table_name", "record_id"])
        op.create_index("idx_changes_date", "data_change_logs", ["changed_at"])

    if not _table_exists(conn, "security_events"):
        op.create_table(
            "security_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_log_id", sa.Integer(), sa.ForeignKey("audit_logs.id"), index=True),
        sa.Column("event_category", sa.String(50), nullable=False),
        sa.Column("severity", audit_level, nullable=False),
        sa.Column("threat_indicators", sa.JSON()),
        sa.Column("risk_score", sa.Integer()),
        sa.Column("action_taken", sa.Text()),
        sa.Column("requires_investigation", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("investigated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("investigation_notes", sa.Text()),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("resolution_notes", sa.Text()),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("idx_security_category", "security_events", ["event_category"])
        op.create_index("idx_security_severity", "security_events", ["severity"])
        op.create_index("idx_security_unresolved", "security_events", ["resolved_at"])


def _drop_tables() -> None:
    for t in [
        "security_events", "data_change_logs", "audit_logs",
        "notification_preferences", "notifications",
        "alert_conditions", "alerts",
    ]:
        op.drop_table(t)
    conn = op.get_bind()
    for name in ("auditstatus", "auditlevel", "auditeventtype",
                 "priority", "notificationstatus", "notificationchannel", "notificationtype"):
        conn.execute(text(f"DROP TYPE IF EXISTS {name}"))


# ── Part B: FK cascade changes ────────────────────────────────────────

def _apply_fk_cascades() -> None:
    conn = op.get_bind()
    for table, column, on_delete, make_nullable in _FK_CHANGES:
        if not _table_exists(conn, table):
            continue

        existing = _find_existing_fk(conn, table, column)
        if existing:
            op.drop_constraint(existing, table, type_="foreignkey")

        if make_nullable:
            op.alter_column(table, column, existing_type=sa.Integer(), nullable=True)

        op.create_foreign_key(
            _fk_name(table, column), table, "users",
            [column], ["id"], ondelete=on_delete,
        )


def _revert_fk_cascades() -> None:
    conn = op.get_bind()
    for table, column, _on_delete, make_nullable in reversed(_FK_CHANGES):
        if not _table_exists(conn, table):
            continue
        existing = _find_existing_fk(conn, table, column)
        if existing:
            op.drop_constraint(existing, table, type_="foreignkey")

        if make_nullable:
            op.alter_column(table, column, existing_type=sa.Integer(), nullable=False)

        op.create_foreign_key(
            _fk_name(table, column), table, "users",
            [column], ["id"],
        )


# ── Entry points ──────────────────────────────────────────────────────

def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("SET lock_timeout = '10s'"))
    conn.execute(text("SET statement_timeout = '120s'"))
    _create_tables()
    _apply_fk_cascades()


def downgrade() -> None:
    _revert_fk_cascades()
    _drop_tables()
