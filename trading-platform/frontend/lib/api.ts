export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store",
    ...init
  });
  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export type ServiceStatus = {
  status: "ok" | "error";
  detail?: string | null;
};

export type HealthzResponse = {
  overall: "ok" | "degraded";
  services: Record<string, ServiceStatus>;
};

export type Strategy = {
  name: string;
  strategy_type: string;
  asset_class: string;
  status: string;
  allocated_capital: number;
  current_weight: number;
  consecutive_losses: number;
};

export type Position = {
  symbol: string;
  quantity: number;
  avg_price: number;
  unrealized_pnl: number;
};

export type Pnl = {
  daily: number;
  total_realized: number;
  unrealized: number;
};

export type RiskSnapshot = {
  halted: boolean;
  halted_reason: string | null;
  daily_realized_pnl: number;
  gross_exposure: number;
  fo_margin_utilisation: number;
  capital: number;
};

export type LearningRun = {
  model_name: string;
  old_sharpe: number;
  new_sharpe: number;
  accepted: string;
  reason: string;
  created_at: string;
};

export async function getHealthz(): Promise<HealthzResponse> {
  return fetchJson<HealthzResponse>("/healthz");
}

export async function getStrategies(): Promise<Strategy[]> {
  return fetchJson<Strategy[]>("/api/strategies/");
}

export async function getPositions(): Promise<Position[]> {
  return fetchJson<Position[]>("/api/positions/");
}

export async function getPnl(): Promise<Pnl> {
  return fetchJson<Pnl>("/api/pnl/");
}

export async function getRisk(): Promise<RiskSnapshot> {
  return fetchJson<RiskSnapshot>("/api/risk/");
}

export async function getLearningRuns(): Promise<LearningRun[]> {
  return fetchJson<LearningRun[]>("/api/learning/runs");
}

// --- Intelligence & Commodities Types ---

export type RegimeState = {
  regime: string;
  probability: number;
  volatility_regime: string;
  india_vix: number;
  vix: number;
  detected_at: string;
};

export type CorrelationPair = {
  asset_a: string;
  asset_b: string;
  pearson: number;
  spearman: number;
  window_days: number;
  computed_at: string;
};

export type AgentOutput = {
  agent_name: string;
  action: "buy" | "sell" | "hold";
  confidence: number;
  risk: number;
  affected_assets: string[];
  rationale: string;
  metadata: Record<string, unknown>;
  ts: string;
};

export type OrchestratorResult = {
  final_action: "buy" | "sell" | "hold";
  ensemble_confidence: number;
  ensemble_risk: number;
  agent_outputs: AgentOutput[];
  rationale: string;
  affected_assets: string[];
};

export type GoldSilverSnapshot = {
  gold_mcx_per10g: number;
  gold_comex_usd_oz: number;
  silver_mcx_per_kg: number;
  silver_comex_usd_oz: number;
  usd_inr: number;
  gold_mcx_fair_value: number;
  gold_premium_pct: number;
  dxy: number;
  us_real_yield_10y: number;
  central_bank_buying: boolean;
  geopolitical_risk_score: number;
  inflation_hedge_score: number;
  ai_sentiment: "bullish" | "bearish" | "neutral";
  ai_confidence: number;
  updated_at: string;
};

export type MCXContract = {
  symbol: string;
  price: number;
  change_pct: number;
  open_interest: number;
  oi_change_pct: number;
  volume: number;
  expiry: string;
};

export async function getRegime(): Promise<RegimeState> {
  return fetchJson<RegimeState>("/api/intelligence/regime");
}

export async function getCrossMarket(): Promise<CorrelationPair[]> {
  return fetchJson<CorrelationPair[]>("/api/intelligence/cross-market");
}

export async function getAgents(): Promise<{ name: string; type: string }[]> {
  return fetchJson<{ name: string; type: string }[]>("/api/intelligence/agents");
}

export async function runAnalysis(context: Record<string, unknown> = {}): Promise<OrchestratorResult> {
  return fetchJson<OrchestratorResult>("/api/intelligence/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(context),
  });
}

export async function getGoldSilver(): Promise<GoldSilverSnapshot> {
  return fetchJson<GoldSilverSnapshot>("/api/commodities/gold-silver");
}

export async function getMCX(): Promise<MCXContract[]> {
  return fetchJson<MCXContract[]>("/api/commodities/mcx");
}

