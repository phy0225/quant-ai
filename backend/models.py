"""SQLAlchemy ORM models."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

def gen_id() -> str:
    return str(uuid.uuid4())

def now() -> datetime:
    return datetime.now()

# ─── Decision ────────────────────────────────────────────────────────────────

class DecisionRun(Base):
    __tablename__ = "decision_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    status: Mapped[str] = mapped_column(String(20), default="running")   # running|completed|failed
    triggered_by: Mapped[str] = mapped_column(String(100), default="user")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    symbols: Mapped[list] = mapped_column(JSON, default=list)
    current_portfolio: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    agent_signals: Mapped[list] = mapped_column(JSON, default=list)
    hallucination_events: Mapped[list] = mapped_column(JSON, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    final_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    approvals: Mapped[list["ApprovalRecord"]] = relationship("ApprovalRecord", back_populates="decision_run")

# ─── Approval ─────────────────────────────────────────────────────────────────

class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    decision_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_runs.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|auto_approved|modified
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_rule_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    decision_run: Mapped["DecisionRun"] = relationship("DecisionRun", back_populates="approvals")

# ─── Backtest ─────────────────────────────────────────────────────────────────

class BacktestReport(Base):
    __tablename__ = "backtest_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    symbols: Mapped[list] = mapped_column(JSON, default=list)
    start_date: Mapped[str] = mapped_column(String(10))
    end_date: Mapped[str] = mapped_column(String(10))
    initial_capital: Mapped[float] = mapped_column(Float, default=1_000_000)
    benchmark: Mapped[str] = mapped_column(String(30), default="buy_and_hold")
    commission_rate: Mapped[float] = mapped_column(Float, default=0.003)
    slippage: Mapped[float] = mapped_column(Float, default=0.001)
    rebalance_frequency: Mapped[str] = mapped_column(String(10), default="weekly")
    nav_curve: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    monthly_returns: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    total_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annualized_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_holding_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_commission: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_slippage_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

# ─── Risk ─────────────────────────────────────────────────────────────────────

class RiskConfig(Base):
    __tablename__ = "risk_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    max_position_weight: Mapped[float] = mapped_column(Float, default=0.20)
    daily_loss_warning_threshold: Mapped[float] = mapped_column(Float, default=0.03)
    daily_loss_suspend_threshold: Mapped[float] = mapped_column(Float, default=0.06)
    max_drawdown_emergency: Mapped[float] = mapped_column(Float, default=0.15)
    circuit_breaker_level: Mapped[int] = mapped_column(Integer, default=0)
    circuit_breaker_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    circuit_breaker_trigger_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    emergency_stop_active: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_stop_activated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    emergency_stop_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    event_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))  # warning|critical|emergency
    description: Mapped[str] = mapped_column(Text)
    triggered_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

# ─── Rules ────────────────────────────────────────────────────────────────────

class AutoApprovalRule(Base):
    __tablename__ = "auto_approval_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    logic_operator: Mapped[str] = mapped_column(String(3), default="AND")
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    action: Mapped[str] = mapped_column(String(50), default="auto_approve")
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

# ─── Graph ────────────────────────────────────────────────────────────────────

class GraphNode(Base):
    __tablename__ = "graph_nodes"

    node_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    approval_id: Mapped[str] = mapped_column(String(36), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=now)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome_return: Mapped[float] = mapped_column(Float, default=0.0)
    outcome_sharpe: Mapped[float] = mapped_column(Float, default=0.0)
    symbols: Mapped[list] = mapped_column(JSON, default=list)
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)


# ─── Portfolio（持仓记录）────────────────────────────────────────────────────

class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id:             Mapped[str]            = mapped_column(String, primary_key=True, default=gen_id)
    symbol:         Mapped[str]            = mapped_column(String, nullable=False, index=True)
    symbol_name:    Mapped[Optional[str]]  = mapped_column(String, nullable=True)   # 股票名称
    weight:         Mapped[float]          = mapped_column(Float, default=0.0)       # 当前权重
    cost_price:     Mapped[Optional[float]]= mapped_column(Float, nullable=True)     # 成本价
    quantity:       Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)   # 持股数量
    market_value:   Mapped[Optional[float]]= mapped_column(Float, nullable=True)     # 市值（定期更新）
    current_price:  Mapped[Optional[float]]= mapped_column(Float, nullable=True)     # 最新价（定期更新）
    pnl_pct:        Mapped[Optional[float]]= mapped_column(Float, nullable=True)     # 浮动盈亏%
    note:           Mapped[Optional[str]]  = mapped_column(String, nullable=True)    # 备注
    updated_at:     Mapped[datetime]       = mapped_column(DateTime, default=now, onupdate=now)
    created_at:     Mapped[datetime]       = mapped_column(DateTime, default=now)

class PortfolioSnapshot(Base):
    """每次审批通过后自动保存一份持仓快照，用于回溯"""
    __tablename__ = "portfolio_snapshots"

    id:            Mapped[str]  = mapped_column(String, primary_key=True, default=gen_id)
    decision_id:   Mapped[str]  = mapped_column(String, nullable=True)
    approval_id:   Mapped[str]  = mapped_column(String, nullable=True)
    holdings:      Mapped[dict] = mapped_column(JSON, default=dict)   # {symbol: weight}
    total_mv:      Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime, default=now)