import { useState, useEffect } from 'react'
import { fetchStatsTeams, fetchTeamForm, fetchGoalDistribution, fetchStandingsTimeline } from '../api'

type Tab = 'form' | 'goals' | 'timeline'

interface FormGame {
  date: string; round: number | null; is_home: boolean
  opponent: string; opponent_rank: number | null
  gf: number; ga: number; result: 'W' | 'D' | 'L'
}
interface FormData {
  team: string; season: number; total: number
  summary: { W: number; D: number; L: number }
  games: FormGame[]
}
interface GoalInterval {
  label: string; scored: number; conceded: number
  scored_home: number; scored_away: number
}
interface GoalData {
  team: string; season: number
  total_scored: number; total_conceded: number
  intervals: GoalInterval[]
}
interface TimelineTeam { team: string; ranks: number[] }
interface TimelineData {
  season: number; max_round: number; rounds: number[]
  num_teams: number; teams: TimelineTeam[]
}

const FORM_SEASONS     = [2013,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025,2026]
const GOAL_SEASONS     = [2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025,2026]
const TIMELINE_SEASONS = [2013,2015,2016,2017,2018,2019,2020,2021,2024,2025,2026]

const SEASON_NOTES: Record<number, string> = {
  2013: '74경기만 존재 (부분 데이터)',
  2026: '시즌 진행중',
}

const TEAM_COLORS = [
  '#10b981','#3b82f6','#f59e0b','#ef4444','#8b5cf6',
  '#f97316','#06b6d4','#ec4899','#84cc16','#64748b','#a855f7','#fb923c',
]

function seasonsFor(tab: Tab) {
  if (tab === 'form') return FORM_SEASONS
  if (tab === 'goals') return GOAL_SEASONS
  return TIMELINE_SEASONS
}

export default function AnalyticsPage() {
  const [tab, setTab]             = useState<Tab>('form')
  const [season, setSeason]       = useState(2025)
  const [team, setTeam]           = useState('')
  const [teams, setTeams]         = useState<string[]>([])
  const [formData, setFormData]   = useState<FormData | null>(null)
  const [goalData, setGoalData]   = useState<GoalData | null>(null)
  const [timelineData, setTimelineData] = useState<TimelineData | null>(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')
  const [highlight, setHighlight] = useState('')

  useEffect(() => {
    const available = seasonsFor(tab)
    if (!available.includes(season)) {
      const closest = available.reduce((a, b) =>
        Math.abs(b - season) < Math.abs(a - season) ? b : a)
      setSeason(closest)
    }
  }, [tab])

  useEffect(() => {
    fetchStatsTeams(season)
      .then(t => { setTeams(t); if (t.length > 0) setTeam(p => t.includes(p) ? p : t[0]) })
      .catch(() => {})
  }, [season])

  useEffect(() => {
    if (tab === 'timeline') {
      setTimelineData(null)
      run(async () => { const d = await fetchStandingsTimeline(season); setTimelineData(d); setHighlight('') })
    }
  }, [tab, season])

  useEffect(() => {
    if (!team) return
    if (tab === 'form') {
      setFormData(null)
      run(async () => { setFormData(await fetchTeamForm(team, season)) })
    }
    if (tab === 'goals') {
      setGoalData(null)
      run(async () => { setGoalData(await fetchGoalDistribution(team, season)) })
    }
  }, [tab, team, season])

  async function run(fn: () => Promise<void>) {
    setLoading(true); setError('')
    try { await fn() } catch (e: any) { setError(e.message) } finally { setLoading(false) }
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: 'form',     label: '팀 폼' },
    { key: 'goals',    label: '득점 패턴' },
    { key: 'timeline', label: '순위 흐름' },
  ]

  const note = SEASON_NOTES[season]

  return (
    <div className="min-h-full bg-[#f3f4f6]">

      {/* 상단 헤더 */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-4xl mx-auto px-6 py-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-widest mb-0.5">K LEAGUE 1</p>
            <h1 className="text-[17px] font-bold text-slate-900">데이터 분석</h1>
          </div>
          <div className="flex items-center gap-2">
            {note && (
              <span className="text-[10px] text-amber-600 bg-amber-50 border border-amber-100 px-2.5 py-1 rounded-full shrink-0">
                {note}
              </span>
            )}
            <select
              value={season}
              onChange={e => setSeason(Number(e.target.value))}
              className="text-[12px] text-slate-600 border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-slate-400 cursor-pointer"
            >
              {seasonsFor(tab).map(s => <option key={s} value={s}>{s}시즌</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-5">

        {/* 분석 유형 + 팀 선택 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-6 py-5">
            <div className="flex items-center gap-2">
              <span className="text-[14px] font-semibold text-slate-800">분석 유형</span>
            </div>
            {tab !== 'timeline' && (
              <select
                value={team}
                onChange={e => setTeam(e.target.value)}
                className="text-[12px] text-slate-600 border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-slate-400 cursor-pointer"
              >
                {teams.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            )}
          </div>
          <div className="border-t border-slate-100 px-4 py-3">
            <div className="flex flex-wrap gap-1.5">
              {TABS.map(t => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`h-8 px-3 rounded-lg border text-[13px] font-medium transition-all ${
                    tab === t.key
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-700 border-2'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 로딩 */}
        {loading && (
          <div className="bg-white rounded-xl shadow-sm p-10 flex items-center justify-center">
            <span className="w-6 h-6 border-2 border-slate-200 border-t-emerald-500 rounded-full animate-spin" />
          </div>
        )}

        {/* 에러 */}
        {!loading && error && (
          <div className="bg-white rounded-xl shadow-sm px-6 py-10 text-center">
            <p className="text-[13px] text-slate-400">{error}</p>
          </div>
        )}

        {/* 콘텐츠 */}
        {!loading && !error && (
          <>
            {tab === 'form'     && formData     && <FormHeatmap data={formData} />}
            {tab === 'goals'    && goalData      && <GoalChart data={goalData} />}
            {tab === 'timeline' && timelineData  && (
              <TimelineChart data={timelineData} highlight={highlight} onHighlight={setHighlight} />
            )}
            {!loading && !error && (
              (tab !== 'timeline' && !formData && !goalData) ||
              (tab === 'timeline' && !timelineData)
            ) && (
              <div className="bg-white rounded-xl shadow-sm px-6 py-14 text-center">
                <p className="text-[13px] text-slate-400">불러오는 중...</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/* ───────────────────────────────────────────
   팀 폼 히트맵
─────────────────────────────────────────── */
function FormHeatmap({ data }: { data: FormData }) {

  const { games, summary, team, season } = data
  const winRate = Math.round((summary.W / data.total) * 100)
  const totalGf = games.reduce((s, g) => s + g.gf, 0)
  const totalGa = games.reduce((s, g) => s + g.ga, 0)
  const gd = totalGf - totalGa

  const RESULT_STYLE: Record<string, { label: string; badge: string; score: string; row: string }> = {
    W: { label: '승', badge: 'bg-emerald-50 text-emerald-700 border border-emerald-200', score: 'text-emerald-700', row: 'hover:bg-emerald-50/40' },
    D: { label: '무', badge: 'bg-slate-100 text-slate-500 border border-slate-200',     score: 'text-slate-600',   row: 'hover:bg-slate-50/60' },
    L: { label: '패', badge: 'bg-red-50 text-red-600 border border-red-200',            score: 'text-red-600',     row: 'hover:bg-red-50/30' },
  }

  const homeGames = games.filter(g => g.is_home)
  const awayGames = games.filter(g => !g.is_home)

  return (
    <div className="space-y-5">
      {/* 폼 요약 카드 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-5">
          <div className="flex items-center gap-2">
            <span className="text-[14px] font-semibold text-slate-800">폼 요약</span>
            <span className="text-[11px] text-slate-400">{team} · {season}시즌</span>
          </div>
        </div>

        {/* 핵심 지표 그리드 */}
        <div className="border-t border-slate-100">
          <div className="grid grid-cols-4 divide-x divide-slate-100">
            <div className="px-4 py-3.5 text-center">
              <p className="text-[10px] text-slate-400 mb-1">경기</p>
              <p className="text-[20px] font-bold text-slate-900 tabular-nums leading-none">{data.total}</p>
            </div>
            <div className="px-4 py-3.5 text-center">
              <p className="text-[10px] text-slate-400 mb-1">승률</p>
              <p className="text-[20px] font-bold text-emerald-600 tabular-nums leading-none">
                {winRate}<span className="text-[13px] font-normal text-slate-400">%</span>
              </p>
            </div>
            <div className="px-4 py-3.5 text-center">
              <p className="text-[10px] text-slate-400 mb-1">득실</p>
              <p className="text-[20px] font-bold tabular-nums leading-none">
                <span className="text-slate-700">{totalGf}</span>
                <span className="text-slate-300 mx-0.5">:</span>
                <span className="text-slate-500">{totalGa}</span>
              </p>
            </div>
            <div className="px-4 py-3.5 text-center">
              <p className="text-[10px] text-slate-400 mb-1">득실차</p>
              <p className={`text-[20px] font-bold tabular-nums leading-none ${gd > 0 ? 'text-emerald-600' : gd < 0 ? 'text-red-500' : 'text-slate-400'}`}>
                {gd > 0 ? `+${gd}` : String(gd)}
              </p>
            </div>
          </div>
        </div>

        {/* 승/무/패 바 */}
        <div className="border-t border-slate-100 px-6 py-4">
          <div className="flex items-center gap-4 mb-2.5">
            <span className="flex items-center gap-1.5 text-[12px]">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" />
              <span className="font-semibold text-emerald-700">{summary.W}</span>
              <span className="text-slate-400">승</span>
            </span>
            <span className="flex items-center gap-1.5 text-[12px]">
              <span className="w-2.5 h-2.5 rounded-sm bg-amber-400 inline-block" />
              <span className="font-semibold text-amber-700">{summary.D}</span>
              <span className="text-slate-400">무</span>
            </span>
            <span className="flex items-center gap-1.5 text-[12px]">
              <span className="w-2.5 h-2.5 rounded-sm bg-rose-500 inline-block" />
              <span className="font-semibold text-rose-700">{summary.L}</span>
              <span className="text-slate-400">패</span>
            </span>
          </div>
          <div className="flex rounded-full h-2 overflow-hidden">
            <div className="bg-emerald-500 transition-all" style={{ width: `${(summary.W / data.total) * 100}%` }} />
            <div className="bg-amber-400 transition-all" style={{ width: `${(summary.D / data.total) * 100}%` }} />
            <div className="bg-rose-500 transition-all" style={{ width: `${(summary.L / data.total) * 100}%` }} />
          </div>
        </div>

        {/* 홈/원정 비교 */}
        <div className="border-t border-slate-100 divide-y divide-slate-50">
          {[
            { label: '홈', gs: homeGames },
            { label: '원정', gs: awayGames },
          ].map(({ label, gs }) => {
            const w = gs.filter(g => g.result === 'W').length
            const d = gs.filter(g => g.result === 'D').length
            const l = gs.filter(g => g.result === 'L').length
            const total = gs.length
            const rate = total > 0 ? Math.round((w / total) * 100) : 0
            return (
              <div key={label} className="px-6 py-3 flex items-center gap-4">
                <span className="text-[12px] font-medium text-slate-500 w-10 shrink-0">{label}</span>
                <div className="flex items-baseline gap-1 w-28 shrink-0">
                  <span className="text-[13px] font-bold text-emerald-600">{w}</span>
                  <span className="text-[10px] text-slate-400">승</span>
                  <span className="text-[13px] font-bold text-slate-400 ml-1">{d}</span>
                  <span className="text-[10px] text-slate-400">무</span>
                  <span className="text-[13px] font-bold text-slate-500 ml-1">{l}</span>
                  <span className="text-[10px] text-slate-400">패</span>
                </div>
                <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${rate}%` }} />
                </div>
                <span className="text-[12px] font-semibold text-emerald-600 w-10 text-right tabular-nums">{rate}%</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* 경기 결과 목록 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <span className="text-[14px] font-semibold text-slate-800">경기 결과</span>
            <span className="text-[11px] text-slate-400">{games.length}경기 · 최신순</span>
          </div>
        </div>

        {/* 헤더 */}
        <div className="flex items-center px-5 py-2 bg-slate-50 border-b border-slate-100">
          <span className="text-[10px] font-bold text-slate-400 w-8">결과</span>
          <span className="text-[10px] font-bold text-slate-400 flex-1">상대팀</span>
          <span className="text-[10px] font-bold text-slate-400 w-14 text-center">스코어</span>
          <span className="text-[10px] font-bold text-slate-400 w-10 text-center">홈/원정</span>
          <span className="text-[10px] font-bold text-slate-400 w-16 text-right">날짜</span>
        </div>

        <div className="divide-y divide-slate-50">
          {games.map((g, i) => {
            const s = RESULT_STYLE[g.result]
            return (
              <div key={i} className={`flex items-center px-5 py-2.5 transition-colors ${s.row}`}>
                {/* 결과 배지 */}
                <div className="w-8 shrink-0">
                  <span className={`inline-flex items-center justify-center w-6 h-6 rounded text-[11px] font-bold ${s.badge}`}>
                    {s.label}
                  </span>
                </div>

                {/* 상대팀 */}
                <div className="flex-1 min-w-0 flex items-center gap-1.5">
                  <span className="text-[13px] font-semibold text-slate-800 truncate">{g.opponent}</span>
                  {g.opponent_rank != null && (
                    <span className="text-[10px] text-slate-400 shrink-0">{g.opponent_rank}위</span>
                  )}
                  {g.round && (
                    <span className="text-[10px] text-slate-300 shrink-0">R{g.round}</span>
                  )}
                </div>

                {/* 스코어 */}
                <div className="w-14 text-center shrink-0">
                  <span className={`text-[14px] font-black tabular-nums ${s.score}`}>
                    {g.gf}
                  </span>
                  <span className="text-[12px] text-slate-300 mx-0.5">-</span>
                  <span className="text-[14px] font-black tabular-nums text-slate-500">
                    {g.ga}
                  </span>
                </div>

                {/* 홈/원정 */}
                <div className="w-10 text-center shrink-0">
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    g.is_home
                      ? 'bg-slate-100 text-slate-600'
                      : 'bg-white border border-slate-200 text-slate-400'
                  }`}>
                    {g.is_home ? '홈' : '원정'}
                  </span>
                </div>

                {/* 날짜 */}
                <div className="w-16 text-right shrink-0">
                  <span className="text-[10px] text-slate-400 tabular-nums">{g.date}</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

/* ───────────────────────────────────────────
   득점 패턴 차트
─────────────────────────────────────────── */
function GoalChart({ data }: { data: GoalData }) {
  const [showConceded, setShowConceded] = useState(false)
  const { intervals, total_scored, team, season } = data

  const maxVal = Math.max(...intervals.map(iv =>
    showConceded ? Math.max(iv.scored, iv.conceded) : iv.scored
  ), 1)

  const peak = intervals.reduce((a, b) => b.scored > a.scored ? b : a, intervals[0])
  const firstHalf  = intervals.slice(0, 3).reduce((s, i) => s + i.scored, 0)
  const secondHalf = intervals.slice(3).reduce((s, i) => s + i.scored, 0)
  const tendency   = secondHalf > firstHalf ? '후반 강세' : firstHalf > secondHalf ? '전반 강세' : '균형'

  const W = 560, H = 180
  const padL = 20, padT = 20, padB = 28
  const chartH = H - padT - padB
  const groupW = (W - padL) / intervals.length
  const barW = showConceded ? 16 : 24

  return (
    <div className="space-y-5">
      {/* 요약 카드 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <span className="text-[16px] font-bold text-slate-800">득점 패턴</span>
            <span className="w-px h-4 bg-slate-300" />
            <span className="text-[13px] font-bold text-blue-600">{team}</span>
            <span className="text-[13px] font-normal text-slate-400">{season}시즌</span>
          </div>
          <button
            onClick={() => setShowConceded(!showConceded)}
            className={`text-[11px] px-2.5 py-1.5 rounded-lg border font-medium transition-all ${
              showConceded
                ? 'bg-rose-50 border-rose-200 text-rose-600'
                : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300'
            }`}
          >
            {showConceded ? '득점만' : '실점 비교'}
          </button>
        </div>

        <div className="border-t border-slate-100">
          <div className="grid grid-cols-3 divide-x divide-slate-100">
            <div className="px-4 py-3.5 text-center">
              <p className="text-[10px] text-slate-400 mb-1">총 득점</p>
              <p className="text-[20px] font-bold text-slate-900 tabular-nums leading-none">{total_scored}</p>
            </div>
            <div className="px-4 py-3.5 text-center">
              <p className="text-[10px] text-slate-400 mb-1">최다 구간</p>
              <p className="text-[20px] font-bold text-emerald-600 tabular-nums leading-none">
                {peak.label}<span className="text-[13px] font-normal text-slate-400">분</span>
              </p>
            </div>
            <div className="px-4 py-3.5 text-center">
              <p className="text-[10px] text-slate-400 mb-1">경향</p>
              <p className="text-[20px] font-bold text-slate-900 leading-none">{tendency}</p>
            </div>
          </div>
        </div>

        {/* 차트 */}
        <div className="border-t border-slate-100 px-6 py-4 overflow-x-auto">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 340, maxHeight: 200 }}>
            {[0.5, 1].map(p => {
              const y = padT + chartH * (1 - p)
              return (
                <g key={p}>
                  <line x1={padL} y1={y} x2={W} y2={y} stroke="#f1f5f9" strokeWidth="1" />
                  <text x={padL - 4} y={y + 3.5} fontSize="8" textAnchor="end" fill="#cbd5e1">
                    {Math.round(maxVal * p)}
                  </text>
                </g>
              )
            })}
            <line x1={padL} y1={padT + chartH} x2={W} y2={padT + chartH} stroke="#e2e8f0" strokeWidth="1" />

            {intervals.map((iv, i) => {
              const cx   = padL + i * groupW + groupW / 2
              const sH   = (iv.scored / maxVal) * chartH
              const cH   = (iv.conceded / maxVal) * chartH
              const sx   = showConceded ? cx - barW - 2 : cx - barW / 2
              const isPeak = iv.label === peak.label

              return (
                <g key={iv.label}>
                  {i === 3 && (
                    <line x1={cx - groupW / 2} y1={padT} x2={cx - groupW / 2} y2={padT + chartH}
                      stroke="#e2e8f0" strokeWidth="1" strokeDasharray="3,3" />
                  )}
                  <rect
                    x={sx} y={padT + chartH - sH}
                    width={barW} height={Math.max(sH, 2)}
                    fill={isPeak ? '#059669' : '#10b981'}
                    rx="3" opacity={isPeak ? 1 : 0.75}
                  />
                  {iv.scored > 0 && (
                    <text x={sx + barW / 2} y={padT + chartH - sH - 4}
                      fontSize="9" textAnchor="middle"
                      fill={isPeak ? '#059669' : '#94a3b8'}
                      fontWeight={isPeak ? '700' : '400'}>
                      {iv.scored}
                    </text>
                  )}
                  {showConceded && (
                    <>
                      <rect
                        x={cx + 2} y={padT + chartH - cH}
                        width={barW} height={Math.max(cH, 2)}
                        fill="#ef4444" rx="3" opacity="0.65"
                      />
                      {iv.conceded > 0 && (
                        <text x={cx + 2 + barW / 2} y={padT + chartH - cH - 4}
                          fontSize="9" textAnchor="middle" fill="#9ca3af">
                          {iv.conceded}
                        </text>
                      )}
                    </>
                  )}
                  <text x={cx} y={H - 4} fontSize="9" textAnchor="middle" fill="#94a3b8">
                    {iv.label}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        <div className="px-6 pb-4 flex items-center gap-5 text-[11px] text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-4 border-t border-dashed border-slate-300" />
            전반 / 후반 구분
          </span>
          {showConceded && (
            <>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" />득점
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-red-400 inline-block" />실점
              </span>
            </>
          )}
        </div>
      </div>

      {/* 시간대별 상세 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-5">
          <span className="text-[14px] font-semibold text-slate-800">시간대별 상세</span>
        </div>
        <div className="border-t border-slate-100 divide-y divide-slate-50">
          {intervals.map((iv, i) => {
            const isPeak = iv.label === peak.label
            const rate = total_scored > 0 ? Math.round((iv.scored / total_scored) * 100) : 0
            const halfLabel = i < 3 ? '전반' : i === 3 ? '후반' : ''
            return (
              <div key={iv.label} className="flex items-center px-6 py-2.5 gap-4 hover:bg-slate-50/70 transition-colors">
                <div className="flex items-center gap-2 w-24 shrink-0">
                  {halfLabel && (
                    <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                      halfLabel === '전반' ? 'bg-slate-100 text-slate-500' : 'bg-emerald-50 text-emerald-600'
                    }`}>{halfLabel}</span>
                  )}
                  <span className={`text-[12px] font-semibold ${isPeak ? 'text-emerald-700' : 'text-slate-600'}`}>
                    {iv.label}분
                  </span>
                  {isPeak && (
                    <span className="text-[9px] font-semibold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">PEAK</span>
                  )}
                </div>
                <div className="flex-1 flex items-center gap-2">
                  <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${isPeak ? 'bg-emerald-600' : 'bg-emerald-400'}`}
                      style={{ width: `${rate}%` }}
                    />
                  </div>
                  <span className={`text-[13px] font-bold tabular-nums w-6 text-right ${isPeak ? 'text-emerald-600' : 'text-slate-700'}`}>
                    {iv.scored}
                  </span>
                  <span className="text-[10px] text-slate-400">G</span>
                </div>
                {showConceded && (
                  <span className="text-[12px] text-slate-400 tabular-nums w-12 text-right shrink-0">
                    실 {iv.conceded}
                  </span>
                )}
                <span className="text-[10px] text-slate-300 w-8 text-right shrink-0">{rate}%</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

/* ───────────────────────────────────────────
   순위 흐름 타임라인
─────────────────────────────────────────── */
function TimelineChart({ data, highlight, onHighlight }: {
  data: TimelineData; highlight: string; onHighlight: (t: string) => void
}) {
  const { teams, rounds, num_teams, season } = data

  const W = 660, H = 300
  const padL = 26, padR = 56, padT = 12, padB = 24
  const chartW = W - padL - padR
  const chartH = H - padT - padB

  const xOf = (r: number) =>
    rounds.length < 2 ? padL + chartW / 2
    : padL + ((r - 1) / (rounds.length - 1)) * chartW

  const yOf = (rank: number) =>
    num_teams < 2 ? padT + chartH / 2
    : padT + ((rank - 1) / (num_teams - 1)) * chartH

  const colorOf = (team: string) =>
    TEAM_COLORS[teams.findIndex(d => d.team === team) % TEAM_COLORS.length]

  const xLabels = rounds.filter((_, i) =>
    i === 0 || i === rounds.length - 1 || i % Math.max(1, Math.floor(rounds.length / 6)) === 0
  )

  return (
    <div className="space-y-5">
      {/* 팀 선택 카드 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-5">
          <span className="text-[14px] font-semibold text-slate-800">팀 선택</span>
          {highlight && (
            <button
              onClick={() => onHighlight('')}
              className="text-[11px] text-slate-400 hover:text-slate-700 transition-colors"
            >
              전체 보기
            </button>
          )}
        </div>
        <div className="border-t border-slate-100 px-4 py-3">
          <div className="flex flex-wrap gap-1.5">
            {teams.map(d => {
              const color = colorOf(d.team)
              const isHL = highlight === d.team
              const lastRank = d.ranks[d.ranks.length - 1]
              return (
                <button
                  key={d.team}
                  onClick={() => onHighlight(isHL ? '' : d.team)}
                  className={`flex items-center gap-1.5 h-8 px-3 rounded-lg border text-[13px] font-medium transition-all ${
                    isHL ? 'border-2' : 'border-slate-200 text-slate-600 bg-white hover:border-slate-300'
                  }`}
                  style={isHL ? {
                    borderColor: color,
                    backgroundColor: color + '12',
                    color: color,
                  } : {}}
                >
                  {d.team}
                  <span className={`text-[10px] font-normal ${isHL ? '' : 'text-slate-300'}`}>{lastRank}위</span>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* 차트 카드 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-5">
          <div className="flex items-center gap-2">
            <span className="text-[14px] font-semibold text-slate-800">{season}시즌 순위 흐름</span>
            <span className="text-[11px] text-slate-400">{rounds.length}라운드 · {num_teams}팀</span>
          </div>
        </div>
        <div className="border-t border-slate-100 px-6 py-4 overflow-x-auto">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 420, maxHeight: 340 }}>
            {Array.from({ length: num_teams }, (_, i) => i + 1).map(rank => {
              const y = yOf(rank)
              const isAFC = rank === 3
              const isRel = rank === num_teams - 1
              return (
                <g key={rank}>
                  <line
                    x1={padL} y1={y} x2={W - padR} y2={y}
                    stroke={isAFC ? '#dbeafe' : isRel ? '#ffe4e6' : '#f8fafc'}
                    strokeWidth={isAFC || isRel ? 1.5 : 1}
                    strokeDasharray={isAFC || isRel ? '4,3' : ''}
                  />
                  {(rank === 1 || rank === num_teams || isAFC || isRel) && (
                    <text x={padL - 4} y={y + 3.5} fontSize="8" textAnchor="end" fill="#cbd5e1">
                      {rank}
                    </text>
                  )}
                </g>
              )
            })}

            {xLabels.map(r => (
              <text key={r} x={xOf(r)} y={H - 3} fontSize="8" textAnchor="middle" fill="#cbd5e1">
                {r}R
              </text>
            ))}

            {teams.map(d => {
              const color = colorOf(d.team)
              const isHL = highlight === d.team
              const hasHL = !!highlight
              const opacity = hasHL ? (isHL ? 1 : 0.06) : 0.5
              const pts = d.ranks.map((rank, i) => `${xOf(rounds[i])},${yOf(rank)}`).join(' ')
              const lastRank = d.ranks[d.ranks.length - 1]
              const lx = xOf(rounds[rounds.length - 1])
              const ly = yOf(lastRank)

              return (
                <g key={d.team} style={{ opacity }}>
                  <polyline
                    points={pts} fill="none"
                    stroke={color} strokeWidth={isHL ? 2.5 : 1.5}
                    strokeLinejoin="round" strokeLinecap="round"
                  />
                  {isHL && d.ranks.map((rank, i) => (
                    <circle key={i}
                      cx={xOf(rounds[i])} cy={yOf(rank)}
                      r={2.5} fill={color} />
                  ))}
                  <text
                    x={lx + 6} y={ly + 4}
                    fontSize={isHL ? '10' : '8'}
                    fill={color}
                    fontWeight={isHL ? '700' : '400'}
                  >
                    {isHL ? `${d.team} ${lastRank}위` : `${lastRank}`}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        <div className="px-6 pb-4 flex gap-5 text-[11px] text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-5 border-t border-dashed border-sky-300" />
            AFC 챔피언스리그권
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-5 border-t border-dashed border-rose-300" />
            강등권 ({num_teams - 1}위~)
          </span>
        </div>
      </div>

      {/* 최종 순위 표 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-5">
          <span className="text-[14px] font-semibold text-slate-800">최종 순위</span>
        </div>
        <div className="border-t border-slate-100 divide-y divide-slate-50">
          {[...teams]
            .sort((a, b) => a.ranks[a.ranks.length - 1] - b.ranks[b.ranks.length - 1])
            .map(d => {
              const color = colorOf(d.team)
              const finalRank = d.ranks[d.ranks.length - 1]
              const peakRank  = Math.min(...d.ranks)
              const isHL = highlight === d.team
              return (
                <div
                  key={d.team}
                  onClick={() => onHighlight(isHL ? '' : d.team)}
                  className={`flex items-center px-6 py-2.5 gap-3 cursor-pointer transition-colors ${
                    isHL ? 'bg-slate-50' : 'hover:bg-slate-50/70'
                  }`}
                >
                  <span className="text-[13px] font-bold tabular-nums w-6 text-center"
                    style={{ color: isHL ? color : '#94a3b8' }}>
                    {finalRank}
                  </span>
                  <div
                    className="w-1 h-5 rounded-full shrink-0"
                    style={{ backgroundColor: color, opacity: isHL ? 1 : 0.4 }}
                  />
                  <span className={`text-[13px] font-semibold flex-1 ${isHL ? 'text-slate-900' : 'text-slate-600'}`}>
                    {d.team}
                  </span>
                  <span className="text-[11px] text-slate-400">
                    최고 <span className="font-semibold text-slate-600">{peakRank}위</span>
                  </span>
                  <div className="flex gap-0.5 w-20">
                    {d.ranks.filter((_, i) => i % Math.max(1, Math.floor(d.ranks.length / 8)) === 0).map((r, i) => (
                      <div
                        key={i}
                        className="flex-1 rounded-sm"
                        style={{
                          height: 16,
                          backgroundColor: color,
                          opacity: isHL ? (1 - (r - 1) / (num_teams - 1)) * 0.8 + 0.2 : 0.2,
                          marginTop: `${((r - 1) / (num_teams - 1)) * 6}px`,
                        }}
                      />
                    ))}
                  </div>
                </div>
              )
            })}
        </div>
      </div>
    </div>
  )
}
