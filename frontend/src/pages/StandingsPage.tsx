import { useState, useEffect } from 'react'
import { fetchStandings, fetchTopScorers, fetchPlayers } from '../api'
import TeamLogo from '../components/TeamLogo'

const SEASONS = Array.from({ length: 2026 - 2013 + 1 }, (_, i) => 2026 - i)

interface StandingsRow {
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
  group?: 'A' | 'B' | null
}

interface StandingsData {
  season: number
  round_to: number | null
  max_round: number
  label: string
  has_final_round: boolean
  standings: StandingsRow[]
}

interface PlayerRow {
  player_name: string
  team: string
  goals: number
  assists: number
  appearances: number
  position?: string
}

function GdBadge({ gd }: { gd: number }) {
  const color = gd > 0 ? 'text-emerald-600 font-semibold' : gd < 0 ? 'text-red-500 font-semibold' : 'text-slate-400'
  return <span className={`tabular-nums ${color}`}>{gd > 0 ? `+${gd}` : gd}</span>
}

function PlayerRankTable({
  title,
  players,
  statKey,
  statLabel,
  loading,
  color,
}: {
  title: string
  players: PlayerRow[]
  statKey: 'goals' | 'assists'
  statLabel: string
  loading: boolean
  color: string
}) {
  return (
    <div className="bg-white/80 border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <span className="text-[13px] font-bold text-slate-800">{title}</span>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${color}`}>TOP 10</span>
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <div className="w-5 h-5 rounded-full border-2 border-slate-200 border-t-emerald-500 animate-spin" />
        </div>
      ) : players.length === 0 ? (
        <p className="text-center text-[12px] text-slate-400 py-6">데이터 없음</p>
      ) : (
        <div>
          {players.map((p, idx) => (
            <div
              key={`${p.player_name}-${p.team}`}
              className="flex items-center px-4 py-2.5 border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors"
            >
              {/* 순위 */}
              <span className={`text-[13px] font-black tabular-nums shrink-0 ${
                idx === 0 ? 'text-amber-500' : idx === 1 ? 'text-slate-400' : idx === 2 ? 'text-orange-400' : 'text-slate-300'
              }`} style={{ width: 24 }}>
                {idx + 1}
              </span>

              {/* 팀 로고 + 선수명 */}
              <div className="flex items-center gap-2 flex-1 min-w-0 pl-1">
                <TeamLogo team={p.team} size={20} className="shrink-0" />
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-slate-800 truncate">{p.player_name}</p>
                  <p className="text-[10px] text-slate-400 truncate">{p.team}</p>
                </div>
              </div>

              {/* 스탯 */}
              <div className="flex items-center gap-3 shrink-0">
                <div className="text-right">
                  <p className="text-[18px] font-black tabular-nums text-slate-800">{p[statKey]}</p>
                  <p className="text-[9px] text-slate-400 text-right">{statLabel}</p>
                </div>
                {statKey === 'goals' && (
                  <div className="text-right">
                    <p className="text-[12px] font-semibold tabular-nums text-slate-400">{p.assists}</p>
                    <p className="text-[9px] text-slate-300">도움</p>
                  </div>
                )}
                {statKey === 'assists' && (
                  <div className="text-right">
                    <p className="text-[12px] font-semibold tabular-nums text-slate-400">{p.goals}</p>
                    <p className="text-[9px] text-slate-300">득점</p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function StandingsPage() {
  const [season, setSeason] = useState(2025)
  const [data, setData] = useState<StandingsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [scorers, setScorers] = useState<PlayerRow[]>([])
  const [assisters, setAssisters] = useState<PlayerRow[]>([])
  const [scorersLoading, setScorersLoading] = useState(false)
  const [assistsLoading, setAssistsLoading] = useState(false)

  useEffect(() => {
    setData(null)
    setError(null)
    setLoading(true)
    fetchStandings(season)
      .then(setData)
      .catch((e: any) => setError(e?.message ?? '불러오기 실패'))
      .finally(() => setLoading(false))

    setScorers([])
    setAssisters([])
    setScorersLoading(true)
    setAssistsLoading(true)

    fetchTopScorers(season, 10)
      .then(d => setScorers(d.players ?? []))
      .catch(() => setScorers([]))
      .finally(() => setScorersLoading(false))

    fetchPlayers({ sort_by: 'assists', season, min_assists: 1 })
      .then(d => setAssisters((d.players ?? []).slice(0, 10)))
      .catch(() => setAssisters([]))
      .finally(() => setAssistsLoading(false))
  }, [season])

  const rows = data?.standings ?? []
  const totalTeams = rows.length
  const hasFinalRound = data?.has_final_round ?? false
  const AFC_ZONE = 3
  const RELEGATION_ZONE = totalTeams >= 10 ? totalTeams - 1 : null

  return (
    <div className="min-h-full bg-main flex flex-col items-center">

      <div className="w-full px-8 py-8 space-y-6" style={{ maxWidth: 1020 }}>

        {/* 연도 드롭박스 */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={season}
              onChange={e => setSeason(Number(e.target.value))}
              className="appearance-none bg-white border border-slate-200 text-slate-800 text-[13px] font-semibold pl-3 pr-7 py-2 rounded-lg cursor-pointer focus:outline-none focus:border-emerald-500/60 transition-colors"
            >
              {SEASONS.map(y => (
                <option key={y} value={y}>{y}시즌</option>
              ))}
            </select>
            <svg className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-slate-500" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </div>
          <span className="text-[11px] font-bold text-emerald-400/80 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md">
            K리그1 최종 순위
          </span>
        </div>

        {/* 로딩 */}
        {loading && (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 rounded-full border-2 border-slate-200 border-t-emerald-500 animate-spin" />
          </div>
        )}

        {/* 에러 */}
        {!loading && error && (
          <div className="text-center py-12 text-slate-500 text-[13px]">{error}</div>
        )}

        {/* 팀 순위 + 개인 순위 가로 배치 */}
        <div className="flex gap-4 items-start">

        {/* 왼쪽: 팀 순위표 */}
        <div className="shrink-0 space-y-4" style={{ width: 448 }}>
        {!loading && rows.length > 0 && (
          <div className="bg-white/80 border border-slate-200 rounded-xl overflow-hidden">
            {hasFinalRound && (
              <div className="flex items-center gap-2 px-4 py-1.5 bg-slate-50 border-b border-slate-200">
                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">파이널 A조</span>
                <div className="flex-1 h-px bg-slate-300" />
              </div>
            )}
            <div className="flex items-center px-4 py-2.5 border-b border-slate-200 bg-slate-50">
              <span className="text-[10px] font-bold text-slate-500 tabular-nums" style={{ width: 28 }}>순위</span>
              <span className="text-[10px] font-bold text-slate-500 pl-2" style={{ width: 160 }}>팀</span>
              <div className="flex items-center gap-0" style={{ width: 240 }}>
                {(['경기', '승', '무', '패', '득', '실', '득실', '승점'] as const).map(h => (
                  <span key={h} className={`text-[10px] font-bold text-center tabular-nums ${h === '승점' ? 'text-emerald-400/70' : 'text-slate-500'}`} style={{ width: 30 }}>
                    {h}
                  </span>
                ))}
              </div>
            </div>

            {rows.map((row, idx) => {
              const isAFC = row.rank <= AFC_ZONE
              const isRelegation = RELEGATION_ZONE !== null && row.rank >= RELEGATION_ZONE
              const isChampion = row.rank === 1
              const isGroupBoundary = hasFinalRound && row.group === 'B' && rows[idx - 1]?.group === 'A'

              return (
                <div key={row.team}>
                  {/* A조 / B조 구분선 */}
                  {isGroupBoundary && (
                    <div className="flex items-center gap-2 px-4 py-1.5 bg-slate-100 border-b border-slate-200">
                      <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">파이널 B조</span>
                      <div className="flex-1 h-px bg-slate-300" />
                    </div>
                  )}
                <div
                  className={`flex items-center px-4 py-2.5 border-b border-slate-100 last:border-0 transition-colors hover:bg-slate-50
                    ${isChampion ? 'bg-amber-50/60' : ''}
                    ${isAFC && !isChampion ? 'bg-emerald-50/40' : ''}
                    ${isRelegation ? 'bg-red-50/40' : ''}
                  `}
                >
                  <div style={{ width: 28 }} className="flex items-center justify-center shrink-0">
                    {isChampion ? (
                      <span className="text-[13px]">🏆</span>
                    ) : (
                      <span className={`text-[13px] font-black tabular-nums ${isAFC ? 'text-emerald-600' : isRelegation ? 'text-red-500' : 'text-slate-400'}`}>
                        {row.rank}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 min-w-0 pl-2" style={{ width: 160 }}>
                    <TeamLogo team={row.team} size={22} className="shrink-0" />
                    <span className={`text-[13px] font-bold truncate ${isChampion ? 'text-amber-700' : isAFC ? 'text-emerald-700' : isRelegation ? 'text-red-500' : 'text-slate-700'}`}>
                      {row.team}
                    </span>
                    {idx === AFC_ZONE - 1 && !isRelegation && (
                      <span className="text-[9px] text-emerald-500/60 font-bold shrink-0 hidden sm:block">AFC↑</span>
                    )}
                  </div>

                  <div className="flex items-center shrink-0" style={{ width: 240 }}>
                    <span className="text-[12px] text-slate-500 text-center tabular-nums" style={{ width: 30 }}>{row.games}</span>
                    <span className="text-[12px] text-emerald-700 text-center tabular-nums font-semibold" style={{ width: 30 }}>{row.win}</span>
                    <span className="text-[12px] text-slate-500 text-center tabular-nums" style={{ width: 30 }}>{row.draw}</span>
                    <span className="text-[12px] text-red-500 text-center tabular-nums" style={{ width: 30 }}>{row.lose}</span>
                    <span className="text-[12px] text-slate-600 text-center tabular-nums" style={{ width: 30 }}>{row.gf}</span>
                    <span className="text-[12px] text-slate-500 text-center tabular-nums" style={{ width: 30 }}>{row.ga}</span>
                    <div className="text-[12px] text-center" style={{ width: 30 }}><GdBadge gd={row.gd} /></div>
                    <span className={`text-[13px] font-black text-center tabular-nums ${isChampion ? 'text-amber-700' : 'text-slate-800'}`} style={{ width: 30 }}>{row.points}</span>
                  </div>
                </div>
                </div>
              )
            })}
          </div>
        )}

        {/* 범례 */}
        {!loading && rows.length > 0 && (
          <div className="flex flex-wrap items-center gap-3 px-1">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-sm bg-emerald-500/40" />
              <span className="text-[10px] text-slate-500">AFC 챔피언스리그 진출</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-sm bg-red-500/40" />
              <span className="text-[10px] text-slate-500">강등권</span>
            </div>
          </div>
        )}

        {!loading && rows.length > 0 && (
          <p className="text-center text-[10px] text-slate-400">
            승점 → 득점 → 득실차 순 정렬 · 공식 순위와 다를 수 있습니다
          </p>
        )}
        </div>{/* 왼쪽 끝 */}

        {/* 오른쪽: 개인 순위 */}
        <div className="flex flex-col gap-3 shrink-0">
          <div className="flex flex-row gap-3">
            <div style={{ width: 210 }}>
              <PlayerRankTable
                title="득점 순위"
                players={scorers}
                statKey="goals"
                statLabel="골"
                loading={scorersLoading}
                color="text-emerald-700 bg-emerald-500/10 border border-emerald-500/20"
              />
            </div>
            <div style={{ width: 210 }}>
              <PlayerRankTable
                title="도움 순위"
                players={assisters}
                statKey="assists"
                statLabel="도움"
                loading={assistsLoading}
                color="text-sky-700 bg-sky-500/10 border border-sky-500/20"
              />
            </div>
          </div>
          <p className="text-center text-[10px] text-slate-400">
            개인 기록은 참고용이며 공식 기록과 다를 수 있습니다
          </p>
        </div>

        </div>{/* 가로 배치 끝 */}

      </div>
    </div>
  )
}
