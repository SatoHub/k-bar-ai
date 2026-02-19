// ---------------------------------------------------------------------------
// K-Bar AI — API Client
// ---------------------------------------------------------------------------

const BASE = "/api/v1";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Types — mirrors backend Pydantic schemas
// ---------------------------------------------------------------------------

// Health
export type HealthStatus = {
  status: string;
  database: string;
};

// Data status
export type DataStatus = {
  total_races: number;
  total_entries: number;
  total_horses: number;
  total_jockeys: number;
  total_trainers: number;
  date_min: string | null;
  date_max: string | null;
  racecourses: string[];
};

// Horse / Jockey / Trainer (embedded in entries)
export type HorseBase = {
  id: string;
  name: string;
  sex: string | null;
};

export type JockeyBase = {
  id: string;
  name: string;
};

export type TrainerBase = {
  id: string;
  name: string;
};

// Race entry (embedded in RaceDetail)
export type RaceEntry = {
  id: string;
  bracket_number: number | null;
  post_position: number | null;
  horse_age: number | null;
  weight_carried_kg: number | null;
  finish_position: number | null;
  finish_note: string | null;
  total_time_tenths: number | null;
  margin: string | null;
  corner_pos_1: string | null;
  corner_pos_2: string | null;
  corner_pos_3: string | null;
  corner_pos_4: string | null;
  last_3f_time: number | null;
  win_odds: number | null;
  win_favorite: number | null;
  horse_weight_kg: number | null;
  horse_weight_diff: number | null;
  owner: string | null;
  prize_money_10k_yen: number | null;
  horse: HorseBase;
  jockey: JockeyBase | null;
  trainer: TrainerBase | null;
};

// Race list item
export type RaceListItem = {
  id: string;
  race_id: string;
  race_date: string;
  racecourse_name: string | null;
  race_number: number | null;
  race_name: string | null;
  surface: string | null;
  distance_m: number | null;
  weather: string | null;
  track_condition: string | null;
  graded_race: string | null;
};

// Race detail (extends list item)
export type RaceDetail = RaceListItem & {
  racecourse_code: string | null;
  direction: string | null;
  race_symbols: Record<string, boolean> | null;
  entries: RaceEntry[];
};

// Race list response (paginated)
export type RaceListResponse = {
  items: RaceListItem[];
  total: number;
  page: number;
  per_page: number;
};

// Prediction entry
export type PredictionEntry = {
  id: string;
  horse_id: string;
  horse_name: string | null;
  predicted_position: number | null;
  predicted_score: number | null;
  confidence: string | null;
  explanation: string | null;
  actual_finish: number | null;
};

// Race prediction response
export type RacePredictionResponse = {
  race_id: string;
  race_date: string | null;
  racecourse_name: string | null;
  race_name: string | null;
  model_version: string | null;
  predictions: PredictionEntry[];
};

// Model version
export type ModelVersion = {
  id: string;
  version: string;
  description: string | null;
  accuracy: number | null;
  created_at: string;
};

export type ModelVersionListResponse = {
  items: ModelVersion[];
};

// Model metrics
export type ModelMetrics = {
  version: string;
  accuracy: number | null;
  f1: number | null;
  roc_auc: number | null;
  train_rows: number | null;
  test_rows: number | null;
  best_iteration: number | null;
  cutoff_year: number | null;
  unique_races: number | null;
  win_hit_rate: number | null;
  place_hit_rate: number | null;
};

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export function fetchHealth(): Promise<HealthStatus> {
  return fetchJSON<HealthStatus>("/health");
}

export function fetchDataStatus(): Promise<DataStatus> {
  return fetchJSON<DataStatus>("/data/status");
}

export function fetchRaces(params?: {
  date?: string;
  racecourse?: string;
  page?: number;
  per_page?: number;
}): Promise<RaceListResponse> {
  const sp = new URLSearchParams();
  if (params?.date) sp.set("date", params.date);
  if (params?.racecourse) sp.set("racecourse", params.racecourse);
  if (params?.page) sp.set("page", String(params.page));
  if (params?.per_page) sp.set("per_page", String(params.per_page));
  const qs = sp.toString();
  return fetchJSON<RaceListResponse>(`/races${qs ? `?${qs}` : ""}`);
}

export function fetchRaceDetail(raceId: string): Promise<RaceDetail> {
  return fetchJSON<RaceDetail>(`/races/${raceId}`);
}

export function fetchPredictions(
  raceId: string,
): Promise<RacePredictionResponse> {
  return fetchJSON<RacePredictionResponse>(`/predictions/${raceId}`);
}

export function fetchModels(): Promise<ModelVersionListResponse> {
  return fetchJSON<ModelVersionListResponse>("/models");
}

export function fetchModelMetrics(version: string): Promise<ModelMetrics> {
  return fetchJSON<ModelMetrics>(`/models/${version}/metrics`);
}
