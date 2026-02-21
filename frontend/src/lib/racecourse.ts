/**
 * Decode racecourse info from netkeiba-style race_id.
 * race_id format: YYYYCCRRDDNN
 *   YYYY = year, CC = racecourse code, RR = round, DD = day, NN = race number
 */

const RACECOURSE_MAP: Record<string, string> = {
  "01": "札幌",
  "02": "函館",
  "03": "福島",
  "04": "新潟",
  "05": "東京",
  "06": "中山",
  "07": "中京",
  "08": "京都",
  "09": "阪神",
  "10": "小倉",
  // Also handle single-digit codes from older data
  "1": "札幌",
  "2": "函館",
  "3": "福島",
  "4": "新潟",
  "5": "東京",
  "6": "中山",
  "7": "中京",
  "8": "京都",
  "9": "阪神",
};

export function decodeRacecourse(raceId: string): string | null {
  if (!raceId || raceId.length < 6) return null;
  const code = raceId.substring(4, 6);
  return RACECOURSE_MAP[code] ?? RACECOURSE_MAP[code.replace(/^0/, "")] ?? null;
}

export function decodeRaceName(
  raceId: string,
  raceNumber: number | null,
): string {
  const course = decodeRacecourse(raceId);
  const num = raceNumber ?? parseInt(raceId.substring(10, 12), 10);
  if (course && num) return `${course}${num}R`;
  if (num) return `第${num}R`;
  return raceId;
}
