"""Pydantic schemas for request/response validation."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, Field, field_validator

# ─── Common ───────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int

# ─── Decision ─────────────────────────────────────────────────────────────────

class DecisionTriggerRequest(BaseModel):
    symbols: List[str]
    current_portfolio: Optional[dict[str, float]] = None

    @field_validator('symbols')
    @classmethod
    def symbols_not_empty(cls, v):
        if not v:
            raise ValueError('symbols 不能为空，至少包含一个标的')
        return v

class AgentSignalOut(BaseModel):
    agent_type: str
    direction: Optional[str] = None
    confidence: float
    reasoning_summary: str
    signal_weight: float
    created_at: str
    retry_count: int = 0
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    data_sources: Optional[List[str]] = None

class HallucinationEventOut(BaseModel):
    agent_type: str
    event_type: str
    description: str
    retry_count: int
    resolved: bool
    created_at: str

class SimilarCase(BaseModel):
    node_id: str
    similarity_score: float
    outcome_return: float
    outcome_sharpe: float
    approved: bool
    timestamp: str

class RecommendationItem(BaseModel):
    symbol: str
    current_weight: float
    recommended_weight: float
    weight_delta: float
    confidence_score: float
    similar_cases: List[SimilarCase] = []

class DecisionRunOut(BaseModel):
    id: str
    status: str
    triggered_by: str
    started_at: str
    completed_at: Optional[str] = None
    symbols: List[str] = []
    recommendations: List[RecommendationItem] = []
    agent_signals: Optional[List[AgentSignalOut]] = None
    hallucination_events: Optional[List[HallucinationEventOut]] = None
    final_direction: Optional[str] = None
    risk_level: Optional[str] = None
    error_message: Optional[str] = None

class DecisionListResponse(BaseModel):
    items: List[DecisionRunOut]
    total: int
    page: int
    page_size: int

# ─── Approval ─────────────────────────────────────────────────────────────────

class ApprovalActionRequest(BaseModel):
    action: str  # approved | rejected
    comment: Optional[str] = None
    reviewed_by: str

class ModifyWeightsRequest(BaseModel):
    modified_weights: dict[str, float]
    reviewed_by: str
    comment: Optional[str] = None

class ApprovalOut(BaseModel):
    id: str
    decision_run_id: str
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    comment: Optional[str] = None
    auto_rule_id: Optional[str] = None
    recommendations: List[RecommendationItem] = []
    created_at: str

class ApprovalListResponse(BaseModel):
    items: List[ApprovalOut]
    total: int
    page: int
    page_size: int

# ─── Backtest ─────────────────────────────────────────────────────────────────

class BacktestRunRequest(BaseModel):
    symbols: List[str]
    start_date: str
    end_date: str
    initial_capital: float = 1_000_000
    benchmark: str = "buy_and_hold"
    rebalance_frequency: str = "weekly"
    commission_rate: float = 0.003
    slippage: float = 0.001
    backtest_mode: Literal["signal_based", "factor_based"] = "signal_based"

class NavPoint(BaseModel):
    date: str
    nav: float
    benchmark_nav: float

class MonthlyReturnPoint(BaseModel):
    year: int
    month: int
    return_: float = Field(alias="return")

    class Config:
        populate_by_name = True

class BacktestReportOut(BaseModel):
    id: str
    status: str
    symbols: List[str]
    start_date: str
    end_date: str
    initial_capital: float
    benchmark: str
    backtest_mode: Optional[str] = None
    commission_rate: Optional[float] = None
    slippage: Optional[float] = None
    nav_curve: Optional[List[dict]] = None
    monthly_returns: Optional[List[dict]] = None
    total_return: Optional[float] = None
    annualized_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    avg_holding_days: Optional[float] = None
    total_commission: Optional[float] = None
    total_slippage_cost: Optional[float] = None
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

# ─── Risk ─────────────────────────────────────────────────────────────────────

class CircuitBreakerStatus(BaseModel):
    level: int
    level_name: str
    triggered_at: Optional[str] = None
    trigger_value: Optional[float] = None
    can_execute: bool

class RiskEventOut(BaseModel):
    id: str
    event_type: str
    severity: str
    description: str
    triggered_value: Optional[float] = None
    threshold_value: Optional[float] = None
    created_at: str
    resolved_at: Optional[str] = None

class RiskStatusOut(BaseModel):
    circuit_breaker: CircuitBreakerStatus
    emergency_stop_active: bool
    recent_risk_events: List[RiskEventOut] = []

class RiskParamsOut(BaseModel):
    max_position_weight: float
    daily_loss_warning_threshold: float
    daily_loss_suspend_threshold: float
    max_drawdown_emergency: float

class RiskParamsUpdate(BaseModel):
    max_position_weight: Optional[float] = None
    daily_loss_warning_threshold: Optional[float] = None
    daily_loss_suspend_threshold: Optional[float] = None
    max_drawdown_emergency: Optional[float] = None

class CircuitBreakerResetRequest(BaseModel):
    target_level: int
    authorized_by: str

class EmergencyStopRequest(BaseModel):
    reason: str
    activated_by: str

class EmergencyDeactivateRequest(BaseModel):
    password: str
    deactivated_by: str

# ─── Rules ────────────────────────────────────────────────────────────────────

class RuleCondition(BaseModel):
    field: str
    operator: str
    value: float

class AutoApprovalRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    priority: int = 0
    logic_operator: str = "AND"
    conditions: List[RuleCondition]
    action: str = "auto_approve"

class AutoApprovalRuleOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_active: bool
    priority: int
    logic_operator: str
    conditions: List[RuleCondition]
    action: str
    trigger_count: int
    last_triggered_at: Optional[str] = None
    created_at: str
    updated_at: str

# ─── Graph ────────────────────────────────────────────────────────────────────

class GraphNodeOut(BaseModel):
    node_id: str
    timestamp: str
    approved: bool
    outcome_return: float
    outcome_sharpe: float
    symbols: List[str]

class GraphNodesResponse(BaseModel):
    nodes: List[GraphNodeOut]
    total: int

class SimilarityTrendPoint(BaseModel):
    timestamp: str
    avg_similarity: float

class OutcomeDistribution(BaseModel):
    positive: int
    negative: int

class GraphStatsOut(BaseModel):
    node_count: int
    edge_count: int
    avg_accuracy: float
    approval_rate: float
    similarity_trend: List[SimilarityTrendPoint] = []
    outcome_distribution: Optional[OutcomeDistribution] = None
    top_symbols: List[dict] = []
    generated_at: str
