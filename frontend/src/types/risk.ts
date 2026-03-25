export interface CircuitBreakerStatus {
  level: 0 | 1 | 2 | 3
  level_name: 'NORMAL' | 'WARNING' | 'SUSPENDED' | 'EMERGENCY'
  triggered_at: string | null
  trigger_value: number | null
  can_execute: boolean
}

export interface RiskEvent {
  id: string
  event_type: string
  severity: 'warning' | 'critical' | 'emergency'
  description: string
  triggered_value: number | null
  threshold_value: number | null
  created_at: string
  resolved_at: string | null
}

export interface RiskStatus {
  circuit_breaker: CircuitBreakerStatus
  emergency_stop_active: boolean
  recent_risk_events: RiskEvent[]
}

export interface RuleCondition {
  field: string
  operator: string
  value: number
}

export interface AutoApprovalRule {
  id: string
  name: string
  description: string | null
  is_active: boolean
  priority: number
  logic_operator: 'AND' | 'OR'
  conditions: RuleCondition[]
  action: string
  trigger_count: number
  last_triggered_at: string | null
  created_at: string
  updated_at: string
}

export interface RiskParams {
  max_position_weight: number
  daily_loss_warning_threshold: number
  daily_loss_suspend_threshold: number
  max_drawdown_emergency: number
}
