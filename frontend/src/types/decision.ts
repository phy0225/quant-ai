import type { RecommendationItem } from './approval'

export type AgentType = 'technical' | 'fundamental' | 'news' | 'sentiment' | 'risk' | 'executor'

export const AGENT_LABELS: Record<AgentType, string> = {
  technical: '技术分析师',
  fundamental: '基本面分析师',
  news: '新闻分析师',
  sentiment: '情绪分析师',
  risk: '风险管理员',
  executor: '交易执行员',
}

export interface AgentSignal {
  agent_type: AgentType
  direction: 'buy' | 'sell' | 'hold' | null
  confidence: number
  reasoning_summary: string
  signal_weight: number
  created_at: string
  retry_count: number
  support_level?: number | null
  resistance_level?: number | null
  data_sources?: string[]
}

export interface HallucinationEvent {
  agent_type: AgentType
  event_type: 'structure_violation' | 'data_mismatch' | 'logic_contradiction'
  description: string
  retry_count: number
  resolved: boolean
  created_at: string
}

export interface DecisionTriggerRequest {
  symbols: string[]
  current_portfolio?: Record<string, number>
}

export interface DecisionRun {
  id: string
  status: 'running' | 'completed' | 'failed'
  triggered_by: string
  started_at: string
  completed_at: string | null
  symbols: string[]
  recommendations: RecommendationItem[]
  agent_signals?: AgentSignal[]
  hallucination_events?: HallucinationEvent[]
  final_direction?: 'buy' | 'sell' | 'hold' | null
  risk_level?: 'low' | 'medium' | 'high' | null
  error_message?: string | null
}
