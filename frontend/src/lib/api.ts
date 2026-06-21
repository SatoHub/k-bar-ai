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

async function postJSON<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function putJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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
  netkeiba_id?: string | null;
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
  post_time: string | null;
  surface: string | null;
  distance_m: number | null;
  weather: string | null;
  track_condition: string | null;
  graded_race: string | null;
  head_count: number | null;
  stub_only: boolean;
  upset_score?: number | null;
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

// Calendar
export type CalendarDay = {
  date: string;
  race_count: number;
  has_entries: boolean;
};

export type CalendarResponse = {
  year_month: string;
  days: CalendarDay[];
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
  shap_data?: Record<string, number> | null;
};

// 荒れ度スコア (race-level upset score)
export type UpsetScore = {
  score: number;
  percentile: number;
  level: "low" | "mid" | "high";
  expected_upset_rate: number;
  hint: string;
};

// Race prediction response
export type RacePredictionResponse = {
  race_id: string;
  race_date: string | null;
  racecourse_name: string | null;
  race_name: string | null;
  model_version: string | null;
  upset?: UpsetScore | null;
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

// Odds
export type OddsEntry = {
  post_position: number;
  horse_name: string | null;
  win_odds: number | null;
  win_favorite: number | null;
  fetched_at: string;
};

export type OddsResponse = {
  race_id: string;
  entries: OddsEntry[];
  fetched_at: string | null;
};

export type OddsHistoryPoint = {
  post_position: number;
  horse_name: string | null;
  win_odds: number;
  fetched_at: string;
};

export type OddsHistoryResponse = {
  race_id: string;
  history: OddsHistoryPoint[];
};

// Horse detail
export type HorseRaceRecord = {
  race_id: string;
  race_date: string;
  racecourse_name: string | null;
  race_name: string | null;
  surface: string | null;
  distance_m: number | null;
  track_condition: string | null;
  finish_position: number | null;
  finish_note: string | null;
  total_time_tenths: number | null;
  win_odds: number | null;
  jockey_name: string | null;
};

export type HorseDetail = {
  id: string;
  name: string;
  sex: string | null;
  netkeiba_id: string | null;
  image_url: string | null;
  total_runs: number;
  wins: number;
  place_count: number;
  win_rate: number;
  place_rate: number;
  surface_stats: Record<string, { runs: number; wins: number; place: number }>;
  records: HorseRaceRecord[];
};

// Aptitude
export type AptitudeEntry = {
  horse_id: string;
  runs: number;
  wins: number;
  place_count: number;
  score: number; // 1-3
};

export type AptitudeResponse = {
  race_id: string;
  entries: AptitudeEntry[];
};

// Bet records
export type RaceResultEntry = {
  finish_position: number;
  horse_name: string;
};

export type BetEntryInfo = {
  post_position: number | null;
  bracket_number: number | null;
  horse_name: string;
};

export type BetRaceInfo = {
  race_number: number | null;
  racecourse_name: string | null;
  race_name: string | null;
  race_id_str: string | null;
  result_top3: RaceResultEntry[];
  entries: BetEntryInfo[];
};

export type BetRecord = {
  id: string;
  race_id: string | null;
  bet_date: string;
  bet_type: string;
  horse_names: string;
  amount_yen: number;
  odds_at_bet: number | null;
  actual_payout: number | null;
  is_hit: boolean | null;
  note: string | null;
  created_at: string;
  race_info: BetRaceInfo | null;
};

export type BetRecordCreate = {
  race_id?: string | null;
  bet_date: string;
  bet_type: string;
  horse_names: string;
  amount_yen: number;
  odds_at_bet?: number | null;
  note?: string | null;
};

export type BetRecordUpdate = {
  actual_payout?: number | null;
  is_hit?: boolean | null;
  note?: string | null;
};

export type BetListResponse = {
  items: BetRecord[];
  total: number;
  page: number;
  per_page: number;
};

export type BetSummary = {
  total_bets: number;
  total_amount: number;
  total_payout: number;
  recovery_rate: number;
  hit_count: number;
  hit_rate: number;
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
  year_month?: string;
  week?: string;
  racecourse?: string;
  page?: number;
  per_page?: number;
}): Promise<RaceListResponse> {
  const sp = new URLSearchParams();
  if (params?.date) sp.set("date", params.date);
  if (params?.year_month) sp.set("year_month", params.year_month);
  if (params?.week) sp.set("week", params.week);
  if (params?.racecourse) sp.set("racecourse", params.racecourse);
  if (params?.page) sp.set("page", String(params.page));
  if (params?.per_page) sp.set("per_page", String(params.per_page));
  const qs = sp.toString();
  return fetchJSON<RaceListResponse>(`/races${qs ? `?${qs}` : ""}`);
}

export function fetchCalendar(yearMonth: string): Promise<CalendarResponse> {
  return fetchJSON<CalendarResponse>(
    `/races/calendar?year_month=${yearMonth}`,
  );
}

export function fetchRaceDetail(raceId: string): Promise<RaceDetail> {
  return fetchJSON<RaceDetail>(`/races/${raceId}`);
}

// Past performances (馬柱)
export type PastRaceRecord = {
  race_id: string;
  race_date: string;
  racecourse_name: string | null;
  race_number: number | null;
  race_name: string | null;
  graded_race: string | null;
  surface: string | null;
  distance_m: number | null;
  track_condition: string | null;
  field_size: number | null;
  bracket_number: number | null;
  post_position: number | null;
  finish_position: number | null;
  finish_note: string | null;
  total_time_tenths: number | null;
  last_3f_time: number | null;
  margin: string | null;
  corner_passing: string | null;
  win_odds: number | null;
  win_favorite: number | null;
  weight_carried_kg: number | null;
  horse_weight_kg: number | null;
  horse_weight_diff: number | null;
  jockey_name: string | null;
};

export type HorsePastPerformances = {
  horse_id: string;
  post_position: number | null;
  records: PastRaceRecord[];
};

export type PastPerformancesResponse = {
  race_id: string;
  horses: HorsePastPerformances[];
};

export function fetchPastPerformances(
  raceId: string,
  limit = 5,
): Promise<PastPerformancesResponse> {
  return fetchJSON<PastPerformancesResponse>(
    `/races/${raceId}/past-performances?limit=${limit}`,
  );
}

// Pedigree (血統) — sourced from JRA-VAN NL_UM via FDW
export type HorsePedigree = {
  horse_id: string;
  post_position: number | null;
  sire: string | null;
  dam: string | null;
  broodmare_sire: string | null;
  paternal_grandsire: string | null;
};

export type RacePedigreeResponse = {
  race_id: string;
  horses: HorsePedigree[];
};

export function fetchPedigree(raceId: string): Promise<RacePedigreeResponse> {
  return fetchJSON<RacePedigreeResponse>(`/races/${raceId}/pedigree`);
}

// Confirmed (JV-Data) odds & payouts — self-contained tables synced from JRA-VAN
export type ConfirmedWinOdds = {
  umaban: number;
  win_odds: number | null;
  win_favorite: number | null;
};

export type ConfirmedPayouts = {
  runners: number | null;
  tan_umaban: string | null;
  tan_pay: number | null;
  tan_ninki: number | null;
  fuku_umaban: string | null;
  fuku_pay: number | null;
  fuku_ninki: number | null;
  umaren_kumi: string | null;
  umaren_pay: number | null;
  wide_kumi: string | null;
  wide_pay: number | null;
  umatan_kumi: string | null;
  umatan_pay: number | null;
  sanrenfuku_kumi: string | null;
  sanrenfuku_pay: number | null;
  sanrentan_kumi: string | null;
  sanrentan_pay: number | null;
};

export type ConfirmedDataResponse = {
  race_id: string;
  win_odds: ConfirmedWinOdds[];
  payouts: ConfirmedPayouts | null;
};

export function fetchConfirmedData(
  raceId: string,
): Promise<ConfirmedDataResponse> {
  return fetchJSON<ConfirmedDataResponse>(`/races/${raceId}/confirmed`);
}

// Track condition (含水率・クッション値) — JRA official, scraped on race days
export type TrackConditionDetailData = {
  cushion_value: number | null;
  turf_moisture_goal: number | null;
  turf_moisture_4c: number | null;
  dirt_moisture_goal: number | null;
  dirt_moisture_4c: number | null;
  scraped_at: string | null;
};

export type TrackConditionResponse = {
  race_id: string;
  racecourse_name: string | null;
  track_condition: string | null;
  detail: TrackConditionDetailData | null;
};

export function fetchTrackCondition(
  raceId: string,
): Promise<TrackConditionResponse> {
  return fetchJSON<TrackConditionResponse>(`/races/${raceId}/track-condition`);
}

export function fetchPredictions(
  raceId: string,
): Promise<RacePredictionResponse> {
  return fetchJSON<RacePredictionResponse>(`/predictions/${raceId}`);
}

// 予算指定の買い目自動提案
export type BetSuggestionItem = {
  bet_type: string;
  method: string;
  axis: number[] | null;
  horses: number[];
  points: number;
  dropped_points: number;
  stake_min: number;
  stake_max: number;
  cost: number;
  hit_rate: number;
  ev_ratio: number;
  payout_min: number;
  payout_max: number;
  gami_free: boolean;
  odds_estimated: boolean;
  rationale: string;
  recommended: boolean;
};

export type BetSuggestionResponse = {
  race_id: string;
  race_name: string | null;
  budget: number;
  upset_level: string;
  alloc_mode: string;
  odds_live: boolean;
  total_allocated: number;
  names: Record<string, string>;
  suggestions: BetSuggestionItem[];
  message?: string | null;
  coverage_note?: string | null;
  sleeper_posts?: number[];
};

export type HedgeRequest = {
  budget: number;
  honmei_ratio?: number;
  min_fav?: number;
};

export function fetchHedge(
  raceId: string,
  body: HedgeRequest,
): Promise<BetSuggestionResponse> {
  return postJSON<BetSuggestionResponse>(`/races/${raceId}/hedge`, body);
}

export type BetSuggestionRequest = {
  budget: number;
  alloc_mode?: string;
  bet_types?: string[] | null;
  type_budgets?: Record<string, number> | null;
};

export function fetchBetSuggestion(
  raceId: string,
  body: BetSuggestionRequest,
): Promise<BetSuggestionResponse> {
  return postJSON<BetSuggestionResponse>(`/races/${raceId}/bet-suggestion`, body);
}

// 巻き返し穴(sleeper)検出
export type SleeperEntry = {
  post_position: number | null;
  bracket_number: number | null;
  horse_name: string;
  win_favorite: number | null;
  is_sleeper: boolean;
  score: number;
  reason: string;
  surface_runs: number;
  surface_place_rate: number;
  has_win: boolean;
  graded_good: boolean;
  surface_mismatch: boolean;
};

export type SleeperResponse = {
  race_id: string;
  surface: string | null;
  analyzed: number;
  entries: SleeperEntry[];
  message?: string | null;
};

export function fetchSleepers(
  raceId: string,
  minFav = 5,
): Promise<SleeperResponse> {
  return fetchJSON<SleeperResponse>(`/races/${raceId}/sleepers?min_fav=${minFav}`);
}

export function fetchModels(): Promise<ModelVersionListResponse> {
  return fetchJSON<ModelVersionListResponse>("/models");
}

export function fetchModelMetrics(version: string): Promise<ModelMetrics> {
  return fetchJSON<ModelMetrics>(`/models/${version}/metrics`);
}

// Odds
export function fetchOdds(raceId: string): Promise<OddsResponse> {
  return fetchJSON<OddsResponse>(`/races/${raceId}/odds`);
}

export function refreshOdds(raceId: string): Promise<OddsResponse> {
  return postJSON<OddsResponse>(`/races/${raceId}/odds/refresh`);
}

export function fetchOddsHistory(raceId: string): Promise<OddsHistoryResponse> {
  return fetchJSON<OddsHistoryResponse>(`/races/${raceId}/odds/history`);
}

// Combo odds lookup
export type ComboOddsResponse = {
  race_id: string;
  bet_type: string;
  selections: number[];
  odds: number | null;
};

export function fetchComboOdds(
  raceId: string,
  betType: string,
  selections: number[],
): Promise<ComboOddsResponse> {
  return postJSON<ComboOddsResponse>(`/races/${raceId}/odds/combo`, {
    bet_type: betType,
    selections,
  });
}

// Full odds table for one bet type (all combinations)
export type OddsComboEntry = {
  combo: string; // netkeiba key, e.g. "01-02-03"
  odds: number | null;
  odds_low: number | null;
  odds_high: number | null;
  favorite: number | null;
};

export type OddsTableResponse = {
  race_id: string;
  bet_type: string;
  status: string | null;
  official_datetime: string | null;
  combos: OddsComboEntry[];
};

export function fetchOddsTable(
  raceId: string,
  betType: string,
): Promise<OddsTableResponse> {
  return fetchJSON<OddsTableResponse>(
    `/races/${raceId}/odds/table?bet_type=${encodeURIComponent(betType)}`,
  );
}

// Horse detail
export function fetchHorseDetail(horseId: string): Promise<HorseDetail> {
  return fetchJSON<HorseDetail>(`/horses/${horseId}`);
}

// Aptitude
export function fetchAptitude(raceId: string): Promise<AptitudeResponse> {
  return fetchJSON<AptitudeResponse>(`/races/${raceId}/aptitude`);
}

// Bets
export function createBet(data: BetRecordCreate): Promise<BetRecord> {
  return postJSON<BetRecord>("/bets", data);
}

export function fetchBets(params?: {
  page?: number;
  per_page?: number;
}): Promise<BetListResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.per_page) sp.set("per_page", String(params.per_page));
  const qs = sp.toString();
  return fetchJSON<BetListResponse>(`/bets${qs ? `?${qs}` : ""}`);
}

export function updateBet(
  betId: string,
  data: BetRecordUpdate,
): Promise<BetRecord> {
  return putJSON<BetRecord>(`/bets/${betId}`, data);
}

export async function deleteBet(betId: string): Promise<void> {
  const res = await fetch(`${BASE}/bets/${betId}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
}

export function fetchBetSummary(): Promise<BetSummary> {
  return fetchJSON<BetSummary>("/bets/summary");
}

export function settleBets(): Promise<{ settled: number }> {
  return postJSON<{ settled: number }>("/bets/settle");
}

// ---------------------------------------------------------------------------
// Results (AI prediction hit analysis)
// ---------------------------------------------------------------------------

export type ResultTop3Entry = {
  finish_position: number;
  horse_name: string;
  win_odds: number | null;
  win_favorite: number | null;
};

export type PredictedTop3Entry = {
  rank: number;
  horse_name: string;
};

export type AIHitResult = {
  predicted_top3: PredictedTop3Entry[];
  tansho_hit: boolean;
  fukusho_hit: boolean;
  umaren_hit: boolean;
  umatan_hit: boolean;
  wide_hit: boolean;
  sanrenpuku_hit: boolean;
  sanrentan_hit: boolean;
};

export type RaceResultWithAI = {
  race_id_str: string;
  race_date: string | null;
  racecourse_name: string | null;
  race_number: number | null;
  race_name: string | null;
  surface: string | null;
  distance_m: number | null;
  result_top3: ResultTop3Entry[];
  ai_prediction: AIHitResult | null;
};

export type RaceResultsResponse = {
  items: RaceResultWithAI[];
};

export type HitRateEntry = {
  hits: number;
  total: number;
  rate: number;
};

export type AiRoiEntry = {
  strategy: string;
  races: number;
  hits: number;
  hit_rate: number;
  invested: number;
  returned: number;
  roi: number;
};

export type ResultsSummary = {
  total_races: number;
  period: string;
  hit_rates: Record<string, HitRateEntry>;
  ai_roi: AiRoiEntry;
};

export type ResultsCalendarDay = {
  date: string;
  race_count: number;
};

export type ResultsCalendarResponse = {
  days: ResultsCalendarDay[];
};

export function fetchLatestResultDate(): Promise<{ latest_date: string | null }> {
  return fetchJSON<{ latest_date: string | null }>("/results/latest-date");
}

export function fetchResultsCalendar(
  yearMonth: string,
): Promise<ResultsCalendarResponse> {
  return fetchJSON<ResultsCalendarResponse>(
    `/results/calendar?year_month=${yearMonth}`,
  );
}

export function fetchResultsRacecourses(
  date: string,
): Promise<{ racecourses: string[] }> {
  return fetchJSON<{ racecourses: string[] }>(
    `/results/racecourses?date=${date}`,
  );
}

export function fetchResults(params: {
  date: string;
  racecourse?: string;
}): Promise<RaceResultsResponse> {
  const sp = new URLSearchParams();
  sp.set("date", params.date);
  if (params.racecourse) sp.set("racecourse", params.racecourse);
  return fetchJSON<RaceResultsResponse>(`/results?${sp.toString()}`);
}

export function fetchResultsSummary(
  yearMonth?: string,
  racecourse?: string,
): Promise<ResultsSummary> {
  const sp = new URLSearchParams();
  if (yearMonth) sp.set("year_month", yearMonth);
  if (racecourse) sp.set("racecourse", racecourse);
  const qs = sp.toString();
  return fetchJSON<ResultsSummary>(`/results/summary${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Scheduler
// ---------------------------------------------------------------------------

export type SchedulerJobInfo = {
  id: string;
  name: string;
  next_run: string | null;
  last_run: string | null;
  last_status: string | null;
  last_detail: string | null;
};

export type SchedulerStatus = {
  running: boolean;
  paused: boolean;
  timezone: string;
  jobs: SchedulerJobInfo[];
};

export type TriggerResponse = {
  success: boolean;
  message: string;
};

export function fetchSchedulerStatus(): Promise<SchedulerStatus> {
  return fetchJSON<SchedulerStatus>("/scheduler/status");
}

export function triggerSchedulerJob(jobId: string): Promise<TriggerResponse> {
  return postJSON<TriggerResponse>(`/scheduler/jobs/${jobId}/trigger`);
}

export function pauseScheduler(): Promise<TriggerResponse> {
  return postJSON<TriggerResponse>("/scheduler/pause");
}

export function resumeScheduler(): Promise<TriggerResponse> {
  return postJSON<TriggerResponse>("/scheduler/resume");
}

// ---------------------------------------------------------------------------
// Scraper
// ---------------------------------------------------------------------------

export type ScrapeResponse = {
  success: boolean;
  message: string;
};

export type ScrapeStatus = {
  date: string;
  running: boolean;
  last_status: string | null;
  last_entries: number | null;
  last_finished: string | null;
};

export function scrapeShutuba(date?: string): Promise<ScrapeResponse> {
  return postJSON<ScrapeResponse>("/scraper/shutuba", { date: date || null });
}

export function scrapeOdds(date?: string): Promise<ScrapeResponse> {
  return postJSON<ScrapeResponse>("/scraper/odds", { date: date || null });
}

export function scrapeResults(date?: string): Promise<ScrapeResponse> {
  return postJSON<ScrapeResponse>("/scraper/results", { date: date || null });
}

export function runPredict(date?: string): Promise<ScrapeResponse> {
  return postJSON<ScrapeResponse>("/scraper/predict", { date: date || null });
}

export function scrapeCalendar(): Promise<ScrapeResponse> {
  return postJSON<ScrapeResponse>("/scraper/calendar");
}

export function scrapeAll(date?: string): Promise<ScrapeResponse> {
  return postJSON<ScrapeResponse>("/scraper/all", { date: date || null });
}

export function fetchScrapeStatus(
  task: "shutuba" | "odds" | "results" | "predict" | "calendar" | "all",
  date?: string,
): Promise<ScrapeStatus> {
  const qs = date ? `?date=${date}` : "";
  return fetchJSON<ScrapeStatus>(`/scraper/${task}/status${qs}`);
}
