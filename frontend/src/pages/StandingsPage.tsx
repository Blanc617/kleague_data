import { useState, useEffect } from 'react'
import { fetchStandings } from '../api'
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
}

interface StandingsData {
  season: number
  round_to: number | null
  max_round: number
  label: string
  standings: StandingsRow[]
}

function GdBadge({ gd }: { gd: number }) {
  const color = gd > 0 ? 'text-emerald-600 font-semibold' : gd < 0 ? 'text-red-500 font-semibold' : 'text-slate-400'
  return <span className={`tabular-nums ${color}`}>{gd > 0 ? `+${gd}` : gd}</span>
}

export default function StandingsPage() {
  const [season, setSeason] = useState(2025)
  const [data, setData] = useState<StandingsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setData(null)
    setError(null)
    setLoading(true)
    fetchStandings(season)
      .then(setData)
      .catch((e: any) => setError(e?.message ?? '불러오기 실패'))
      .finally(() => setLoading(false))
  }, [season])

  const rows = data?.standings ?? []
  const totalTeams = rows.length

  // 시즌별 승격/강등 구간 (K리그1 기준)
  // 상위 2~3팀: AFC, 하위 2팀: 강등
  const AFC_ZONE = 3
  const RELEGATION_ZONE = totalTeams >= 10 ? totalTeams - 1 : null // 최하위 2팀

  return (
    <div className="min-h-full bg-main flex flex-col items-center">

      <div className="w-full px-8 py-8 space-y-6" style={{ maxWidth: 580 }}>

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

        {/* 순위표 */}
        {!loading && rows.length > 0 && (
          <div className="bg-white/80 border border-slate-200 rounded-xl overflow-hidden">

            {/* 테이블 헤더 */}
            <div className="flex items-center px-4 py-2.5 border-b border-slate-200 bg-slate-50">
              <span className="text-[10px] font-bold text-slate-500 tabular-nums" style={{ width: 28 }}>순위</span>
              <span className="text-[10px] font-bold text-slate-500 flex-1 pl-2">팀</span>
              <div className="flex items-center gap-0" style={{ width: 240 }}>
                {(['경기', '승', '무', '패', '득', '실', '득실', '승점'] as const).map(h => (
                  <span key={h} className={`text-[10px] font-bold text-center tabular-nums ${h === '승점' ? 'text-emerald-400/70' : 'text-slate-500'}`} style={{ width: 30 }}>
                    {h}
                  </span>
                ))}
              </div>
            </div>

            {/* 팀 행 */}
            {rows.map((row, idx) => {
              const isAFC = row.rank <= AFC_ZONE
              const isRelegation = RELEGATION_ZONE !== null && row.rank >= RELEGATION_ZONE
              const isChampion = row.rank === 1

              return (
                <div
                  key={row.team}
                  className={`flex items-center px-4 py-2.5 border-b border-slate-100 last:border-0 transition-colors hover:bg-slate-50
                    ${isChampion ? 'bg-amber-50/60' : ''}
                    ${isAFC && !isChampion ? 'bg-emerald-50/40' : ''}
                    ${isRelegation ? 'bg-red-50/40' : ''}
                  `}
                >
                  {/* 순위 */}
                  <div style={{ width: 28 }} className="flex items-center justify-center shrink-0">
                    {isChampion ? (
                      <span className="text-[13px]">🏆</span>
                    ) : (
                      <span className={`text-[13px] font-black tabular-nums ${isAFC ? 'text-emerald-600' : isRelegation ? 'text-red-500' : 'text-slate-400'}`}>
                        {row.rank}
                      </span>
                    )}
                  </div>

                  {/* 팀명 + 로고 */}
                  <div className="flex items-center gap-2 flex-1 min-w-0 pl-2">
                    <TeamLogo team={row.team} size={22} className="shrink-0" />
                    <span className={`text-[13px] font-bold truncate ${isChampion ? 'text-amber-700' : isAFC ? 'text-emerald-700' : isRelegation ? 'text-red-500' : 'text-slate-700'}`}>
                      {row.team}
                    </span>
                    {idx === AFC_ZONE - 1 && !isRelegation && (
                      <span className="text-[9px] text-emerald-500/60 font-bold shrink-0 hidden sm:block">AFC↑</span>
                    )}
                  </div>

                  {/* 통계 */}
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
          <p className="text-center text-[10px] text-slate-400 pb-4">
            승점 → 득점 → 득실차 순 정렬 · 공식 순위와 다를 수 있습니다
          </p>
        )}
      </div>
    </div>
  )
}
