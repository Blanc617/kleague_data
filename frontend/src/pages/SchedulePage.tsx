import { useState, useEffect, useCallback } from 'react'
import { fetchSchedule, fetchMatchDetail } from '../api'
import TeamLogo from '../components/TeamLogo'

const SEASONS = Array.from({ length: 2026 - 2010 + 1 }, (_, i) => 2026 - i)
const PER_PAGE = 30

interface GoalEvent {
  minute: number
  type: string
  player: string
  team: string
  assist?: string
}

interface TeamStats {
  possession: number
  attempts: number
  onTarget: number
  corners: number
  fouls: number
  yellowCards: number
  redCards: number
  offsides: number
  freeKicks?: number
}

interface MatchStats {
  home: TeamStats
  away: TeamStats
}

interface GameRow {
  season: number
  game_id: number
  date: string | null
  home_team: string
  away_team: string
  home_score: number | null
  away_score: number | null
  finished: boolean
  goals: GoalEvent[]
  round?: number | null
  venue?: string
  stats?: MatchStats | null
}

interface ScheduleData {
  season: number
  season_to: number
  season_label: string
  total: number
  page: number
  total_pages: number
  per_page: number
  all_teams: string[]
  games: GameRow[]
}

interface MatchEvent {
  minute: number
  type: string
  player: string
  team: string
  assist?: string
}

interface MatchDetail {
  events: MatchEvent[]
  stats: MatchStats | null
}

const EVENT_ICON: Record<string, string> = {
  goal: '⚽', own_goal: '⚽', yellow_card: '🟨', red_card: '🟥', yellow_red: '🟧',
}

function StatBar({ label, home, away, isPercent = false }: {
  label: string; home: number; away: number; isPercent?: boolean
}) {
  const total = home + away || 1
  const homePct = isPercent ? home : Math.round((home / total) * 100)
  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-[11px] font-semibold">
        <span className="text-slate-700 tabular-nums">{isPercent ? `${home}%` : home}</span>
        <span className="text-slate-500 text-[10px]">{label}</span>
        <span className="text-slate-700 tabular-nums">{isPercent ? `${away}%` : away}</span>
      </div>
      <div className="flex h-1.5 rounded-full overflow-hidden bg-slate-200">
        <div className="bg-emerald-500/70 rounded-full transition-all" style={{ width: `${homePct}%` }} />
        <div className="flex-1 bg-sky-500/70 rounded-full transition-all" />
      </div>
    </div>
  )
}

function formatDate(date: string | null, season: number): string {
  if (!date) return `${season}시즌`
  const parts = date.split('-')
  if (parts.length === 3) {
    const [, m, d] = parts
    return `${m}/${d}`
  }
  return date
}

function ScoreBadge({ home, away, homeTeam, selectedTeam, finished }: {
  home: number | null; away: number | null; homeTeam: string; awayTeam?: string; selectedTeam: string; finished: boolean
}) {
  const isPlayed = finished && home !== null && away !== null
  const isDraw = isPlayed && home === away
  const isWin = isPlayed && selectedTeam
    ? (homeTeam.includes(selectedTeam) ? home! > away! : away! > home!)
    : null

  const resultLabel = isPlayed && selectedTeam
    ? isDraw ? '무' : isWin ? '승' : '패'
    : null

  const resultColor = isDraw
    ? 'text-gray-400'
    : isWin
      ? 'text-emerald-500'
      : 'text-red-400'

  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className={`inline-flex items-center justify-center font-black text-[14px] w-[72px] py-1.5 rounded-lg tracking-wide ${isPlayed ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-400'}`}>
        {isPlayed ? `${home} : ${away}` : 'vs'}
      </span>
      {resultLabel && (
        <span className={`text-[10px] font-bold ${resultColor}`}>{resultLabel}</span>
      )}
    </div>
  )
}

// 이벤트 한 줄 (홈 or 원정)
function EventRow({ ev, side }: { ev: MatchEvent; side: 'home' | 'away' }) {
  const isGoal = ev.type === 'goal' || ev.type === 'own_goal'
  const isYellow = ev.type === 'yellow_card'
  const isRed = ev.type === 'red_card' || ev.type === 'yellow_red'
  const isOwn = ev.type === 'own_goal'

  const playerColor = isGoal
    ? (isOwn ? 'text-slate-400' : 'text-slate-800')
    : isYellow
      ? 'text-amber-600'
      : isRed
        ? 'text-red-600'
        : 'text-slate-600'

  const icon = EVENT_ICON[ev.type] ?? '•'
  const minute = `${ev.minute}'`

  if (side === 'home') {
    // 홈: 이벤트 정보 왼쪽 정렬, 분 오른쪽
    return (
      <div className="flex items-center gap-1 min-w-0 justify-end">
        {ev.assist && (
          <span className="text-slate-500 text-[10px] truncate hidden sm:block">
            ← {ev.assist}
          </span>
        )}
        <span className={`font-semibold text-[12px] truncate ${playerColor}`}>
          {ev.player}
          {isOwn && <span className="text-slate-500 text-[10px] ml-0.5">(자책)</span>}
        </span>
        <span className="text-[12px] shrink-0">{icon}</span>
        <span className="text-slate-500 text-[11px] shrink-0 tabular-nums">{minute}</span>
      </div>
    )
  } else {
    // 원정: 분 왼쪽, 이벤트 오른쪽 정렬
    return (
      <div className="flex items-center gap-1 min-w-0">
        <span className="text-slate-500 text-[11px] shrink-0 tabular-nums">{minute}</span>
        <span className="text-[12px] shrink-0">{icon}</span>
        <span className={`font-semibold text-[12px] truncate ${playerColor}`}>
          {ev.player}
          {isOwn && <span className="text-slate-500 text-[10px] ml-0.5">(자책)</span>}
        </span>
        {ev.assist && (
          <span className="text-slate-500 text-[10px] truncate hidden sm:block">
            → {ev.assist}
          </span>
        )}
      </div>
    )
  }
}

export default function SchedulePage() {
  const [season, setSeason] = useState(2025)
  const [teamFilter, setTeamFilter] = useState('')
  const [data, setData] = useState<ScheduleData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [expandedGame, setExpandedGame] = useState<string | null>(null)
  const [detailCache, setDetailCache] = useState<Record<string, MatchDetail>>({})
  const [loadingKey, setLoadingKey] = useState<string | null>(null)

  useEffect(() => {
    setTeamFilter('')
    setPage(1)
  }, [season])

  const load = useCallback(async (pg: number) => {
    setLoading(true)
    setError(null)
    try {
      const d = await fetchSchedule({
        season,
        team: teamFilter || undefined,
        page: pg,
        per_page: PER_PAGE,
      })
      setData(d)
    } catch (e: any) {
      setError(e?.message ?? '불러오기 실패')
    } finally {
      setLoading(false)
    }
  }, [season, teamFilter])

  useEffect(() => { load(page) }, [load, page])
  useEffect(() => { setPage(1) }, [teamFilter])

  async function toggleExpand(g: GameRow) {
    const key = `${g.season}_${g.game_id}`
    if (expandedGame === key) { setExpandedGame(null); return }
    setExpandedGame(key)
    if (!detailCache[key]) {
      setLoadingKey(key)
      try {
        const detail = await fetchMatchDetail(g.season, g.game_id)
        setDetailCache(prev => ({
          ...prev,
          [key]: { events: detail.events ?? [], stats: detail.stats ?? null },
        }))
      } catch {
        setDetailCache(prev => ({ ...prev, [key]: { events: g.goals, stats: null } }))
      } finally {
        setLoadingKey(null)
      }
    }
  }

  const seasonLabel = data?.season_label ?? String(season)

  return (
    <div className="min-h-full bg-main flex flex-col items-center">

      <div className="w-full px-8 py-8 space-y-6" style={{ maxWidth: 740 }}>

        {/* 필터 바 */}
        <div className="flex gap-2">
          <div className="relative" style={{ minWidth: 120 }}>
            <select
              value={season}
              onChange={e => setSeason(Number(e.target.value))}
              className="w-full appearance-none bg-white border border-slate-200 text-slate-800 text-[13px] font-semibold pl-3 pr-8 py-2 rounded-lg cursor-pointer focus:outline-none focus:border-emerald-500/60 transition-colors"
            >
              {SEASONS.map(y => (
                <option key={y} value={y}>{y}시즌</option>
              ))}
            </select>
            <svg className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </div>

          <div className="relative" style={{ minWidth: 100 }}>
            <select
              value={teamFilter}
              onChange={e => setTeamFilter(e.target.value)}
              className="w-full appearance-none bg-white border border-slate-200 text-slate-800 text-[13px] font-semibold pl-3 pr-8 py-2 rounded-lg cursor-pointer focus:outline-none focus:border-emerald-500 transition-colors"
            >
              <option value="">전체 팀</option>
              {(data?.all_teams ?? []).map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <svg className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </div>

          {teamFilter && (
            <button
              onClick={() => setTeamFilter('')}
              className="px-3 py-2 text-[12px] text-slate-500 hover:text-slate-700 bg-white border border-slate-200 rounded-lg transition-colors"
            >
              초기화
            </button>
          )}
        </div>

        {/* 시즌 배지 */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold text-orange-400 bg-orange-500/10 border border-orange-500/20 px-2 py-0.5 rounded-md">
            K리그1 {seasonLabel}
          </span>
          {teamFilter && (
            <span className="text-[11px] font-bold text-sky-400 bg-sky-500/10 border border-sky-500/20 px-2 py-0.5 rounded-md">
              {teamFilter}
            </span>
          )}
        </div>

        {loading && (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 rounded-full border-2 border-slate-200 border-t-emerald-500 animate-spin" />
          </div>
        )}

        {!loading && error && (
          <div className="text-center py-12 text-slate-500 text-[13px]">{error}</div>
        )}

        {!loading && data && data.games.length === 0 && (
          <div className="text-center py-12 text-slate-500 text-[13px]">
            {teamFilter ? `${teamFilter} 경기가 없습니다.` : '경기 데이터가 없습니다.'}
          </div>
        )}

        {!loading && data && data.games.length > 0 && (
          <div className="space-y-1.5">
            {data.games.map(g => {
              const key = `${g.season}_${g.game_id}`
              const isExpanded = expandedGame === key
              const isLoadingThis = loadingKey === key
              const cached = detailCache[key]
              const events = cached?.events
              const matchStats = cached?.stats ?? g.stats ?? null

              // 이벤트를 홈/원정으로 분리
              const homeEvents: MatchEvent[] = []
              const awayEvents: MatchEvent[] = []
              if (events) {
                for (const ev of events) {
                  const isHome = ev.team === g.home_team ||
                    ev.team.includes(g.home_team) ||
                    g.home_team.includes(ev.team)
                  if (isHome) homeEvents.push(ev)
                  else awayEvents.push(ev)
                }
              }

              // 분 기준 정렬된 전체 이벤트 (좌우 동시 표시용)
              const allMinutes = Array.from(
                new Set([...homeEvents, ...awayEvents].map(e => e.minute))
              ).sort((a, b) => a - b)

              return (
                <div
                  key={key}
                  className="bg-white/80 border border-slate-200 rounded-xl overflow-hidden"
                >
                  {/* 경기 행 */}
                  <button
                    onClick={() => toggleExpand(g)}
                    className="w-full flex items-center px-5 py-3.5 text-left hover:bg-slate-50 transition-colors"
                  >
                    {/* 날짜 — 왼쪽 고정 */}
                    <span className="shrink-0 text-[12px] text-slate-500 font-medium tabular-nums" style={{ width: 44 }}>
                      {g.date ? formatDate(g.date, g.season) : `${g.season}`}
                    </span>

                    {/* 라운드 — 고정 너비 */}
                    <div className="shrink-0 flex items-center justify-center ml-3" style={{ width: 36 }}>
                      {g.round != null && (
                        <span className="text-[10px] text-slate-400 font-medium">{g.round}R</span>
                      )}
                    </div>

                    {/* 경기 정보 — 중앙 고정 블록 */}
                    <div className="flex-1 flex items-center justify-center">
                      {/* 홈팀: 이름 + 로고 — 고정 너비, 오른쪽 정렬 */}
                      <div className={`flex items-center justify-end gap-2.5 shrink-0 ${teamFilter && g.home_team.includes(teamFilter) ? 'text-emerald-600' : 'text-slate-800'}`} style={{ width: 140 }}>
                        <span className="text-[14px] font-bold truncate">{g.home_team}</span>
                        <TeamLogo team={g.home_team} size={26} className="shrink-0" />
                      </div>

                      {/* 스코어 */}
                      <div className="shrink-0" style={{ margin: '0 32px' }}>
                        <ScoreBadge
                          home={g.home_score}
                          away={g.away_score}
                          homeTeam={g.home_team}
                          selectedTeam={teamFilter}
                          finished={g.finished}
                        />
                      </div>

                      {/* 원정팀: 로고 + 이름 — 고정 너비, 왼쪽 정렬 */}
                      <div className={`flex items-center gap-2.5 shrink-0 ${teamFilter && g.away_team.includes(teamFilter) ? 'text-emerald-600' : 'text-slate-800'}`} style={{ width: 140 }}>
                        <TeamLogo team={g.away_team} size={26} className="shrink-0" />
                        <span className="text-[14px] font-bold truncate">{g.away_team}</span>
                      </div>
                    </div>

                    {/* 경기장 — 고정 너비, 왼쪽 정렬 */}
                    <div className="shrink-0 flex items-center justify-start" style={{ width: 140 }}>
                      {g.venue && (
                        <span className="text-[11px] text-slate-500 truncate hidden sm:block">
                          {g.venue}
                        </span>
                      )}
                    </div>

                    {/* 화살표 */}
                    <div className="w-5 flex justify-center shrink-0 ml-1">
                      {isLoadingThis ? (
                        <span className="w-3.5 h-3.5 rounded-full border border-slate-300 border-t-emerald-500 animate-spin block" />
                      ) : (
                        <svg
                          className={`text-slate-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                          width="13" height="13" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                        >
                          <path d="M6 9l6 6 6-6" />
                        </svg>
                      )}
                    </div>
                  </button>

                  {/* 이벤트 드롭다운 */}
                  {isExpanded && (
                    <div className="border-t border-slate-200 bg-slate-50">
                      {isLoadingThis || !events ? (
                        <div className="flex justify-center py-5">
                          <div className="w-4 h-4 rounded-full border border-slate-200 border-t-emerald-500 animate-spin" />
                        </div>
                      ) : (
                        <div className="flex justify-center" style={{ padding: '12px 0 28px' }}>
                          <div style={{ width: 560 }}>
                            <div className="border-t border-slate-200 mb-3" />

                            {/* 이벤트 목록 */}
                            {events.length === 0 ? (
                              <p className="text-center text-[12px] text-slate-500 py-2">이벤트 데이터가 없습니다.</p>
                            ) : (
                              <div className="space-y-1.5 mb-4">
                                {allMinutes.map(min => {
                                  const homeEvs = homeEvents.filter(e => e.minute === min)
                                  const awayEvs = awayEvents.filter(e => e.minute === min)
                                  const maxRows = Math.max(homeEvs.length, awayEvs.length)

                                  return Array.from({ length: maxRows }).map((_, ri) => (
                                    <div key={`${min}-${ri}`} className="flex items-center">
                                      {/* 홈 이벤트 */}
                                      <div className="flex justify-end" style={{ width: 160 }}>
                                        {homeEvs[ri] ? <EventRow ev={homeEvs[ri]} side="home" /> : null}
                                      </div>

                                      {/* 중앙 구분 */}
                                      <div className="flex justify-center" style={{ width: 100 }}>
                                        <div className="w-px h-4 bg-slate-300" />
                                      </div>

                                      {/* 원정 이벤트 */}
                                      <div style={{ width: 160 }}>
                                        {awayEvs[ri] ? <EventRow ev={awayEvs[ri]} side="away" /> : null}
                                      </div>
                                    </div>
                                  ))
                                })}
                              </div>
                            )}

                            {/* 경기 통계 바 */}
                            {matchStats && (
                              <div className="space-y-2 px-2">
                                <div className="border-t border-slate-200 mb-3" />
                                <div className="flex items-center justify-between text-[10px] font-bold text-slate-500 mb-1">
                                  <span className="text-emerald-500">{g.home_team}</span>
                                  <span>통계</span>
                                  <span className="text-sky-500">{g.away_team}</span>
                                </div>
                                <StatBar label="점유율" home={matchStats.home.possession} away={matchStats.away.possession} isPercent />
                                <StatBar label="슈팅" home={matchStats.home.attempts} away={matchStats.away.attempts} />
                                <StatBar label="유효슈팅" home={matchStats.home.onTarget} away={matchStats.away.onTarget} />
                                <StatBar label="코너킥" home={matchStats.home.corners} away={matchStats.away.corners} />
                                <StatBar label="파울" home={matchStats.home.fouls} away={matchStats.away.fouls} />
                                <StatBar label="경고" home={matchStats.home.yellowCards} away={matchStats.away.yellowCards} />
                                {(matchStats.home.offsides + matchStats.away.offsides) > 0 && (
                                  <StatBar label="오프사이드" home={matchStats.home.offsides} away={matchStats.away.offsides} />
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* 페이지네이션 */}
        {!loading && data && data.total_pages > 1 && (
          <div className="flex items-center justify-center gap-2 py-4">
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:text-slate-700 hover:border-slate-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 18l-6-6 6-6" />
              </svg>
            </button>

            {Array.from({ length: Math.min(7, data.total_pages) }, (_, i) => {
              let p: number
              const mid = Math.min(Math.max(page, 4), data.total_pages - 3)
              if (data.total_pages <= 7) {
                p = i + 1
              } else if (i === 0) {
                p = 1
              } else if (i === 6) {
                p = data.total_pages
              } else if (i === 1 && page > 4) {
                return <span key="l" className="text-slate-400 text-[12px]">…</span>
              } else if (i === 5 && page < data.total_pages - 3) {
                return <span key="r" className="text-slate-400 text-[12px]">…</span>
              } else {
                p = mid - 2 + i
              }
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-8 h-8 flex items-center justify-center rounded-lg text-[12px] font-semibold transition-colors ${
                    p === page
                      ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-600'
                      : 'border border-slate-200 text-slate-500 hover:text-slate-700 hover:border-slate-400'
                  }`}
                >
                  {p}
                </button>
              )
            })}

            <button
              disabled={page >= data.total_pages}
              onClick={() => setPage(p => p + 1)}
              className="w-8 h-8 flex items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:text-slate-700 hover:border-slate-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>
          </div>
        )}

        {!loading && data && data.games.length > 0 && (
          <p className="text-center text-[10px] text-slate-400 pb-6">
            {season <= 2021 ? '※ 2021년 이전 데이터는 날짜 및 이벤트가 제공되지 않을 수 있습니다.' : ''}
          </p>
        )}
      </div>
    </div>
  )
}
