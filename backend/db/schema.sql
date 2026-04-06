CREATE TABLE IF NOT EXISTS factor_definitions (
  id            VARCHAR(36) PRIMARY KEY,
  factor_key    VARCHAR(100) NOT NULL UNIQUE,
  name          VARCHAR(200) NOT NULL,
  entity_type   VARCHAR(20) NOT NULL,
  domain        VARCHAR(30) NOT NULL,
  source        VARCHAR(30) DEFAULT 'builtin',
  formula       TEXT,
  description   TEXT,
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_factor_snapshots (
  id                VARCHAR(36) PRIMARY KEY,
  trade_date        DATE NOT NULL,
  market_regime     VARCHAR(20),
  effective_factors JSON,
  stock_scores      JSON,
  industry_scores   JSON,
  concept_scores    JSON,
  market_factors    JSON,
  created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_daily_factor_snapshot_date (trade_date)
);

CREATE TABLE IF NOT EXISTS factor_performance (
  id           VARCHAR(36) PRIMARY KEY,
  factor_key   VARCHAR(100) NOT NULL,
  trade_date   DATE NOT NULL,
  ic           FLOAT,
  rank_ic      FLOAT,
  ic_ir        FLOAT,
  direction    TINYINT,
  is_effective BOOLEAN,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_factor_performance (factor_key, trade_date)
);

CREATE TABLE IF NOT EXISTS strategy_versions (
  id              VARCHAR(36) PRIMARY KEY,
  version         VARCHAR(20) NOT NULL,
  program_md      TEXT,
  factor_weights  JSON,
  agent_weights   JSON,
  regime_rules    JSON,
  is_active       BOOLEAN DEFAULT FALSE,
  performance     JSON,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strategy_experiments (
  id              VARCHAR(36) PRIMARY KEY,
  base_version_id VARCHAR(36),
  hypothesis      TEXT,
  proposal        JSON,
  new_version_id  VARCHAR(36),
  status          VARCHAR(20) DEFAULT 'running',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decision_runs (
  id                  VARCHAR(36) PRIMARY KEY,
  mode                VARCHAR(20) NOT NULL,
  status              VARCHAR(20) DEFAULT 'running',
  triggered_by        VARCHAR(100) DEFAULT 'user',
  symbols             JSON,
  candidate_symbols   JSON,
  current_portfolio   JSON,
  factor_snapshot_id  VARCHAR(36),
  factor_date         DATE,
  strategy_version_id VARCHAR(36),
  market_regime       VARCHAR(20),
  final_direction     VARCHAR(10),
  risk_level          VARCHAR(10),
  error_message       TEXT,
  started_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at        DATETIME
);

CREATE TABLE IF NOT EXISTS agent_signals (
  id                VARCHAR(36) PRIMARY KEY,
  decision_run_id   VARCHAR(36) NOT NULL,
  agent_type        VARCHAR(50) NOT NULL,
  symbol            VARCHAR(20),
  direction         VARCHAR(10),
  confidence        FLOAT,
  reasoning_summary TEXT,
  signal_weight     FLOAT,
  data_sources      JSON,
  input_snapshot    JSON,
  is_contradictory  BOOLEAN DEFAULT FALSE,
  created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rebalance_orders (
  id               VARCHAR(36) PRIMARY KEY,
  decision_run_id  VARCHAR(36) NOT NULL,
  symbol           VARCHAR(20) NOT NULL,
  symbol_name      VARCHAR(100),
  action           VARCHAR(20) NOT NULL,
  current_weight   FLOAT DEFAULT 0,
  target_weight    FLOAT NOT NULL,
  weight_delta     FLOAT NOT NULL,
  composite_score  FLOAT,
  score_breakdown  JSON,
  reasoning        TEXT,
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_performance (
  id                  VARCHAR(36) PRIMARY KEY,
  decision_run_id     VARCHAR(36) NOT NULL,
  agent_signal_id     VARCHAR(36) NOT NULL,
  agent_type          VARCHAR(50) NOT NULL,
  symbol              VARCHAR(20),
  predicted_direction VARCHAR(10),
  predicted_at        DATETIME,
  settlement_date     DATE,
  actual_return       FLOAT,
  is_correct          BOOLEAN,
  factor_snapshot     JSON,
  settled_at          DATETIME,
  UNIQUE KEY uk_agent_performance_signal (agent_signal_id)
);

CREATE TABLE IF NOT EXISTS agent_weight_configs (
  id           VARCHAR(36) PRIMARY KEY,
  agent_type   VARCHAR(50) NOT NULL UNIQUE,
  weight       FLOAT NOT NULL DEFAULT 0.25,
  accuracy_30d FLOAT,
  accuracy_60d FLOAT,
  is_locked    BOOLEAN DEFAULT FALSE,
  last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidate_pool (
  id          VARCHAR(36) PRIMARY KEY,
  symbol      VARCHAR(20) NOT NULL UNIQUE,
  symbol_name VARCHAR(100),
  added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  note        TEXT
);

CREATE TABLE IF NOT EXISTS portfolio_nav_history (
  id           VARCHAR(36) PRIMARY KEY,
  trade_date   DATE NOT NULL UNIQUE,
  nav          FLOAT NOT NULL,
  total_mv     FLOAT,
  daily_return FLOAT,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS graph_nodes (
  node_id           VARCHAR(36) PRIMARY KEY,
  approval_id       VARCHAR(36) NOT NULL,
  decision_run_id   VARCHAR(36),
  mode              VARCHAR(20),
  trade_date        DATE,
  symbols           JSON,
  market_regime     VARCHAR(20),
  effective_factors JSON,
  approved          BOOLEAN DEFAULT FALSE,
  outcome_return    FLOAT DEFAULT 0.0,
  outcome_sharpe    FLOAT DEFAULT 0.0,
  factor_snapshot   JSON,
  settled           BOOLEAN DEFAULT FALSE,
  created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
  settled_at        DATETIME
);
