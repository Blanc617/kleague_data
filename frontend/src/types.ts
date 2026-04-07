export interface MatchEvent {
  minute: number
  type: 'goal' | 'yellow_card' | 'red_card' | 'yellow_red' | 'own_goal' | 'substitution'
  team: string
  player: string
  assist?: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceMatch[]
  playerSources?: PlayerStat[]
  eventSources?: { date: string; home_team: string; away_team: string; home_score: number; away_score: number; events: MatchEvent[] }[]
  isStreaming?: boolean
}

export interface SourceMatch {
  date: string
  round?: number
  home_team: string
  away_team: string
  home_score: number
  away_score: number
  venue?: string
  attendance?: number
}

export interface PlayerStat {
  player_name: string
  team: string
  position: string
  goals: number
  assists: number
  appearances: number
}

export interface TeamStats {
  team: string
  season: number
  season_to: number
  season_label: string
  total: { games: number; win: number; draw: number; lose: number; win_rate: number; gf: number; ga: number; gd: number; points: number }
  home: { games: number; win: number; draw: number; lose: number; gf: number; ga: number }
  away: { games: number; win: number; draw: number; lose: number; gf: number; ga: number }
  recent: { date: string; season?: number; home_team: string; away_team: string; home_score: number; away_score: number; result: 'W' | 'D' | 'L'; venue: string; stadium?: string }[]
  home_attendance?: {
    total: number
    avg: number
    max: number
    min: number
    games: number
    best_game: { date: string; opponent: string; attendance: number; score: string }
  } | null
}

export interface AttendanceTeamRow {
  rank: number
  team: string
  games: number
  total: number
  avg: number
  max: number
  min: number
  best_game: { date: string; opponent: string; attendance: number; score: string; venue: string }
}

export interface AttendanceTopGame {
  date: string
  round?: number
  home_team: string
  away_team: string
  attendance: number
  score: string
  venue: string
  season?: number
}

export interface AttendanceData {
  season: number
  season_to: number
  season_label: string
  summary: {
    total_games: number
    total_attendance: number
    avg_per_game: number
    max_game: AttendanceTopGame | null
  }
  by_team: AttendanceTeamRow[]
  top_games: AttendanceTopGame[]
  team_games?: { date: string; round?: number; opponent: string; attendance: number; score: string; venue: string; season?: number }[] | null
}

export interface StandingsRow {
  rank: number
  team: string
  games: number
  win: number
  draw: number
  lose: number
  gf: number
  ga: number
  gd: number
  points: number
}

export interface Standings {
  season: number
  round_to: number | null
  max_round: number
  label: string
  standings: StandingsRow[]
}

export interface PlayerMinutesGame {
  game_id: number
  round?: number
  date: string
  home_team: string
  away_team: string
  home_score: number | null
  away_score: number | null
  minutes: number
  starter: boolean
  subbed_off?: number | null
  subbed_on?: number | null
}

export interface PlayerMinutesData {
  season: number
  player_name: string
  team: string
  total_minutes: number
  appearances: number
  starter_count: number
  avg_minutes: number
  games: PlayerMinutesGame[]
}

export interface TeamMinutesData {
  season: number
  team: string
  players: {
    player_name: string
    total_minutes: number
    appearances: number
    starter_count: number
    avg_minutes: number
  }[]
}

export interface PlayerSearchResult {
  season: number
  count: number
  players: {
    player_name: string
    player_name_en: string
    team: string
    position: string
    appearances: number
    goals: number
    assists: number
    yellow_cards: number
    red_cards: number
    minutes_played: number
  }[]
}

export interface PlayerCareerSeason {
  season: number
  team: string
  appearances: number
  goals: number
  assists: number
  own_goals: number
  yellow_cards: number
  red_cards: number
  total_minutes: number
  starter_count: number
}

export interface PlayerProfile {
  name_en: string
  name_ko: string
  team: string
  position: string
  birth_date?: string
  age?: number
  height_cm?: number
  nationality?: string
  jersey_number?: string
  is_foreign?: boolean
}

export interface PlayerCareerData {
  player_name: string
  current_team: string
  profile: PlayerProfile | null
  career: PlayerCareerSeason[]
  totals: {
    seasons: number
    appearances: number
    goals: number
    assists: number
    yellow_cards: number
    red_cards: number
    total_minutes: number
  }
}

export interface PlayerNameSuggestion {
  player_name: string
  team: string
  seasons: number[]
}

export interface PlayerCompareData {
  player1: PlayerCareerData
  player2: PlayerCareerData
  summary: string
}
