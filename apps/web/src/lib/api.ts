const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

export interface KnowledgeStats {
  document_count: number;
  chunk_count: number;
  open_conflict_count: number;
  avg_freshness_score: number;
  avg_trust_score: number;
  avg_conflict_risk: number;
  avg_hallucination_risk: number;
  coverage_pct: number;
}

export interface Document {
  id: string;
  source_type: string;
  source_url: string;
  title: string | null;
  ingested_at: string;
  chunk_count: number;
}

export interface SearchResult {
  chunk_id: string;
  text: string;
  score: number;
  freshness_score: number;
  trust_score: number;
  conflict_risk: number;
  document_id: string;
  document_title: string | null;
  source_type: string;
  source_url: string;
}

export interface ConflictTrendPoint {
  date: string;
  detected: number;
  closed: number;
}
export interface ConflictTrendResponse {
  days: number;
  data: ConflictTrendPoint[];
}

export interface QualityBySource {
  source_type: string;
  chunk_count: number;
  avg_freshness_score: number;
  avg_trust_score: number;
  avg_conflict_risk: number;
}
export interface QualityBySourceResponse {
  data: QualityBySource[];
}

export interface DistributionBucket {
  bucket: string;
  count: number;
}
export interface QualityDistributionResponse {
  freshness: DistributionBucket[];
  trust: DistributionBucket[];
  hallucination: DistributionBucket[];
}

export interface HallucinationRiskTrendPoint {
  date: string;
  avg_hallucination_risk: number;
  chunk_count: number;
}
export interface HallucinationRiskTrendResponse {
  days: number;
  data: HallucinationRiskTrendPoint[];
}

export interface StalenessByAgeBucket {
  age_bucket: string;
  chunk_count: number;
  avg_freshness_score: number;
}
export interface StalenessByAgeResponse {
  data: StalenessByAgeBucket[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
}
export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  confidence: number;
}
export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const api = {
  getStats: () => apiFetch<KnowledgeStats>("/api/v1/stats"),
  getDocuments: (skip = 0, limit = 50) =>
    apiFetch<Document[]>(`/api/v1/documents?skip=${skip}&limit=${limit}`),
  createDocument: (payload: { source_type: string; source_url: string; title?: string }) =>
    apiFetch<Document>("/api/v1/documents", { method: "POST", body: JSON.stringify(payload) }),
  search: (query: string, minFreshness = 0, maxConflictRisk = 1) =>
    apiFetch<SearchResult[]>("/api/v1/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: 8, min_freshness: minFreshness, max_conflict_risk: maxConflictRisk }),
    }),
  getHealth: () => apiFetch<{ status: string; checks: Record<string, string> }>("/health"),
  getConflictTrend: (days = 30) =>
    apiFetch<ConflictTrendResponse>(`/api/v1/stats/conflicts/trend?days=${days}`),
  getQualityBySource: () => apiFetch<QualityBySourceResponse>("/api/v1/stats/quality/by-source"),
  getQualityDistribution: () =>
    apiFetch<QualityDistributionResponse>("/api/v1/stats/quality/distribution"),
  getStalenessByAge: () => apiFetch<StalenessByAgeResponse>("/api/v1/stats/staleness/by-age"),
  getHallucinationRiskTrend: (days = 30) =>
    apiFetch<HallucinationRiskTrendResponse>(`/api/v1/stats/hallucination-risk/trend?days=${days}`),
  getGraph: () => apiFetch<GraphResponse>("/api/v1/graph"),
};
