from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import settings
import re

# Convert sqlite:// to sqlite+aiosqlite:// for async
raw_url = settings.DATABASE_URL
if raw_url.startswith("sqlite:///"):
    async_url = raw_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
else:
    async_url = raw_url

async_engine = create_async_engine(async_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Create all tables and seed default data."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_sqlite_compat_migrations(conn)
    await _seed_defaults()

async def _run_sqlite_compat_migrations(conn):
    if not async_url.startswith("sqlite+aiosqlite:///"):
        return

    async def _get_columns(table_name: str) -> set[str]:
        result = await conn.exec_driver_sql(f"PRAGMA table_info({table_name})")
        rows = result.fetchall()
        return {str(row[1]) for row in rows}

    migrations: dict[str, list[tuple[str, str]]] = {
        "decision_runs": [
            ("mode", "ALTER TABLE decision_runs ADD COLUMN mode VARCHAR(20) DEFAULT 'targeted'"),
            ("candidate_symbols", "ALTER TABLE decision_runs ADD COLUMN candidate_symbols JSON"),
            ("current_portfolio", "ALTER TABLE decision_runs ADD COLUMN current_portfolio JSON"),
            ("agent_signals", "ALTER TABLE decision_runs ADD COLUMN agent_signals JSON DEFAULT '[]'"),
            ("hallucination_events", "ALTER TABLE decision_runs ADD COLUMN hallucination_events JSON DEFAULT '[]'"),
            ("recommendations", "ALTER TABLE decision_runs ADD COLUMN recommendations JSON DEFAULT '[]'"),
            ("final_direction", "ALTER TABLE decision_runs ADD COLUMN final_direction VARCHAR(10)"),
            ("risk_level", "ALTER TABLE decision_runs ADD COLUMN risk_level VARCHAR(10)"),
            ("error_message", "ALTER TABLE decision_runs ADD COLUMN error_message TEXT"),
        ],
        "graph_nodes": [
            ("embedding", "ALTER TABLE graph_nodes ADD COLUMN embedding JSON"),
            ("metadata", "ALTER TABLE graph_nodes ADD COLUMN metadata JSON"),
        ],
    }

    for table_name, table_migrations in migrations.items():
        columns = await _get_columns(table_name)
        for column_name, ddl in table_migrations:
            if column_name not in columns:
                await conn.exec_driver_sql(ddl)
                columns.add(column_name)

async def _seed_defaults():
    from models import RiskConfig, AutoApprovalRule
    import json
    async with AsyncSessionLocal() as db:
        # Seed risk config if not exists
        from sqlalchemy import select
        result = await db.execute(select(RiskConfig))
        if not result.scalars().first():
            db.add(RiskConfig(
                id=1,
                max_position_weight=0.20,
                daily_loss_warning_threshold=0.03,
                daily_loss_suspend_threshold=0.06,
                max_drawdown_emergency=0.15,
                circuit_breaker_level=0,
                emergency_stop_active=False,
            ))
            await db.commit()


def mysql_connection_settings() -> dict[str, object]:
    return {
        "host": settings.DB_HOST,
        "port": settings.DB_PORT,
        "user": settings.DB_USER,
        "password": settings.DB_PASSWORD,
        "database": settings.DB_NAME,
        "dsn": settings.mysql_dsn,
    }
