const BASE = (import.meta.env.VITE_API_BASE_URL ?? '') + '/api'

export async function* streamQuery(
  question: string,
  seasonFrom = 2025,
  seasonTo?: number,
  signal?: AbortSignal,
): AsyncGenerator<
  | { type: 'token'; content: string }
  | { type: 'sources'; content: any[] }
  | { type: 'player_sources'; content: any[] }
  | { type: 'event_sources'; content: any[] }
  | { type: 'error'; content: string }
> {
  const body: Record<string, unknown> = { question, season: seasonFrom }
  if (seasonTo !== undefined && seasonTo !== seasonFrom) {
    body.season_to = seasonTo
  }

  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok) throw new Error(`HTTP ${res.status}`)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (data === '[DONE]') return
        try {
          yield JSON.parse(data)
        } catch {}
      }
    }
  } finally {
    reader.cancel()
  }
}

export async function fetchStandings(season: number, roundTo?: number) {
  const qs = new URLSearchParams({ season: String(season) })
  if (roundTo !== undefined) qs.set('round_to', String(roundTo))
  const res = await fetch(`${BASE}/standings?${qs}`)
  if (!res.ok) throw new Error(`${season}시즌 순위 데이터 없음`)
  return res.json()
}

export async function fetchStatsTeams(seasonFrom: number, seasonTo?: number): Promise<string[]> {
  const qs = new URLSearchParams({ season: String(seasonFrom) })
  if (seasonTo !== undefined && seasonTo !== seasonFrom) qs.set('season_to', String(seasonTo))
  const res = await fetch(`${BASE}/stats/teams?${qs}`)
  if (!res.ok) throw new Error('팀 목록 없음')
  const data = await res.json()
  return data.teams as string[]
}

export async function fetchStats(team: string, seasonFrom: number, seasonTo?: number) {
  const qs = new URLSearchParams({ season: String(seasonFrom) })
  if (seasonTo !== undefined && seasonTo !== seasonFrom) qs.set('season_to', String(seasonTo))
  const res = await fetch(`${BASE}/stats/${encodeURIComponent(team)}?${qs}`)
  if (!res.ok) throw new Error(`팀 '${team}' 데이터 없음`)
  return res.json()
}

export async function fetchTopScorers(seasonFrom: number, limit = 10, seasonTo?: number) {
  const qs = new URLSearchParams({ season: String(seasonFrom), limit: String(limit) })
  if (seasonTo !== undefined && seasonTo !== seasonFrom) qs.set('season_to', String(seasonTo))
  const res = await fetch(`${BASE}/players/top?${qs}`)
  if (!res.ok) throw new Error('선수 데이터 없음')
  return res.json()
}

export async function fetchAttendance(seasonFrom: number, seasonTo?: number, team?: string) {
  const qs = new URLSearchParams({ season: String(seasonFrom) })
  if (seasonTo !== undefined && seasonTo !== seasonFrom) qs.set('season_to', String(seasonTo))
  if (team) qs.set('team', team)
  const res = await fetch(`${BASE}/attendance?${qs}`)
  if (!res.ok) throw new Error('관중 데이터 없음')
  return res.json()
}

export async function fetchPlayerMinutes(player: string, season: number, team?: string) {
  const qs = new URLSearchParams({ season: String(season) })
  if (team) qs.set('team', team)
  const res = await fetch(`${BASE}/player-minutes/${encodeURIComponent(player)}?${qs}`)
  if (!res.ok) throw new Error(`'${player}' 선수 출전시간 데이터 없음`)
  return res.json()
}

export async function fetchTeamMinutes(team: string, season: number) {
  const qs = new URLSearchParams({ season: String(season) })
  const res = await fetch(`${BASE}/team-minutes/${encodeURIComponent(team)}?${qs}`)
  if (!res.ok) throw new Error(`'${team}' 팀 출전시간 데이터 없음`)
  return res.json()
}

export async function fetchSchedule(params: {
  season: number
  season_to?: number
  team?: string
  page?: number
  per_page?: number
}) {
  const qs = new URLSearchParams({ season: String(params.season) })
  if (params.season_to && params.season_to !== params.season) qs.set('season_to', String(params.season_to))
  if (params.team) qs.set('team', params.team)
  if (params.page) qs.set('page', String(params.page))
  if (params.per_page) qs.set('per_page', String(params.per_page))
  const res = await fetch(`${BASE}/schedule?${qs}`)
  if (!res.ok) throw new Error('경기 일정 데이터 없음')
  return res.json()
}

export async function fetchMatchDetail(season: number, gameId: number) {
  const res = await fetch(`${BASE}/schedule/${season}/${gameId}`)
  if (!res.ok) throw new Error('경기 상세 데이터 없음')
  return res.json()
}

export async function fetchScheduleTeams(season: number, season_to?: number) {
  const qs = new URLSearchParams({ season: String(season) })
  if (season_to && season_to !== season) qs.set('season_to', String(season_to))
  const res = await fetch(`${BASE}/schedule/teams?${qs}`)
  if (!res.ok) throw new Error('팀 목록 없음')
  return res.json()
}

export async function fetchPlayerCareer(playerName: string, seasonFrom = 2010, seasonTo = 2026) {
  const qs = new URLSearchParams({ season_from: String(seasonFrom), season_to: String(seasonTo) })
  const res = await fetch(`${BASE}/players/${encodeURIComponent(playerName)}/career?${qs}`)
  if (!res.ok) throw new Error(`'${playerName}' 선수 커리어 데이터 없음`)
  return res.json()
}

export async function searchPlayersByName(name: string) {
  const qs = new URLSearchParams({ name })
  const res = await fetch(`${BASE}/players/search?${qs}`)
  if (!res.ok) throw new Error('선수 검색 실패')
  return res.json()
}

export async function fetchPlayerCompare(player1: string, player2: string, seasonFrom = 2010, seasonTo = 2026) {
  const qs = new URLSearchParams({
    player1,
    player2,
    season_from: String(seasonFrom),
    season_to: String(seasonTo),
  })
  const res = await fetch(`${BASE}/players/compare?${qs}`)
  if (!res.ok) throw new Error('선수 비교 데이터 없음')
  return res.json()
}

export async function fetchTeamForm(team: string, season: number, limit = 20) {
  const qs = new URLSearchParams({ season: String(season), limit: String(limit) })
  const res = await fetch(`${BASE}/stats/${encodeURIComponent(team)}/form?${qs}`)
  if (!res.ok) throw new Error(`'${team}' 폼 데이터 없음`)
  return res.json()
}

export async function fetchGoalDistribution(team: string, season: number) {
  const qs = new URLSearchParams({ season: String(season) })
  const res = await fetch(`${BASE}/stats/${encodeURIComponent(team)}/goal-distribution?${qs}`)
  if (!res.ok) throw new Error(`'${team}' 득점 분포 데이터 없음`)
  return res.json()
}

export async function fetchStandingsTimeline(season: number) {
  const qs = new URLSearchParams({ season: String(season) })
  const res = await fetch(`${BASE}/standings/timeline?${qs}`)
  if (!res.ok) throw new Error(`${season}시즌 타임라인 데이터 없음`)
  return res.json()
}

export async function fetchPlayers(params: {
  team?: string
  position?: string
  min_goals?: number
  min_assists?: number
  sort_by?: string
  season?: number
  season_to?: number
}) {
  const qs = new URLSearchParams()
  if (params.team) qs.set('team', params.team)
  if (params.position) qs.set('position', params.position)
  if (params.min_goals) qs.set('min_goals', String(params.min_goals))
  if (params.min_assists) qs.set('min_assists', String(params.min_assists))
  if (params.sort_by) qs.set('sort_by', params.sort_by)
  if (params.season) qs.set('season', String(params.season))
  if (params.season_to && params.season_to !== params.season) qs.set('season_to', String(params.season_to))

  const res = await fetch(`${BASE}/players?${qs}`)
  if (!res.ok) throw new Error('선수 데이터 없음')
  return res.json()
}
