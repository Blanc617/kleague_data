import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchStats, fetchTopScorers, fetchStandings, fetchAttendance, fetchPlayerMinutes, fetchTeamMinutes, fetchStatsTeams } from '../api'
import { useFavorites } from '../hooks/useFavorites'
import StatsCard from '../components/StatsCard'
import TeamLogo from '../components/TeamLogo'
import SeasonSelector, { type SeasonRange } from '../components/SeasonSelector'
import type { TeamStats, PlayerSearchResult, Standings, AttendanceData, PlayerMinutesData, TeamMinutesData } from '../types'

const TEAM_STYLE_MAP: Record<string, { accent: string; hover: string }> = {
  '전북':   { accent: 'border-yellow-400 bg-yellow-50 text-yellow-800', hover: 'hover:border-yellow-400 hover:bg-yellow-50/70' },
  '울산':   { accent: 'border-sky-400 bg-sky-50 text-sky-800',          hover: 'hover:border-sky-400 hover:bg-sky-50/70' },
  '서울':   { accent: 'border-red-400 bg-red-50 text-red-800',          hover: 'hover:border-red-400 hover:bg-red-50/70' },
  '포항':   { accent: 'border-red-500 bg-red-50 text-red-900',          hover: 'hover:border-red-500 hover:bg-red-50/70' },
  '인천':   { accent: 'border-blue-400 bg-blue-50 text-blue-800',       hover: 'hover:border-blue-400 hover:bg-blue-50/70' },
  '대전':   { accent: 'border-purple-400 bg-purple-50 text-purple-800', hover: 'hover:border-purple-400 hover:bg-purple-50/70' },
  '광주':   { accent: 'border-amber-400 bg-amber-50 text-amber-800',    hover: 'hover:border-amber-400 hover:bg-amber-50/70' },
  '강원':   { accent: 'border-orange-400 bg-orange-50 text-orange-800', hover: 'hover:border-orange-400 hover:bg-orange-50/70' },
  '제주':   { accent: 'border-emerald-400 bg-emerald-50 text-emerald-800', hover: 'hover:border-emerald-400 hover:bg-emerald-50/70' },
  '대구':   { accent: 'border-indigo-400 bg-indigo-50 text-indigo-800', hover: 'hover:border-indigo-400 hover:bg-indigo-50/70' },
  '수원삼성': { accent: 'border-blue-600 bg-blue-50 text-blue-900',     hover: 'hover:border-blue-600 hover:bg-blue-50/70' },
  '수원FC': { accent: 'border-blue-400 bg-blue-50 text-blue-800',       hover: 'hover:border-blue-400 hover:bg-blue-50/70' },
  '수원':   { accent: 'border-blue-500 bg-blue-50 text-blue-900',       hover: 'hover:border-blue-500 hover:bg-blue-50/70' },
  '성남':   { accent: 'border-gray-600 bg-gray-50 text-gray-800',       hover: 'hover:border-gray-600 hover:bg-gray-50/70' },
  '전남':   { accent: 'border-green-500 bg-green-50 text-green-800',    hover: 'hover:border-green-500 hover:bg-green-50/70' },
  '경남':   { accent: 'border-teal-500 bg-teal-50 text-teal-800',       hover: 'hover:border-teal-500 hover:bg-teal-50/70' },
  '부산':   { accent: 'border-rose-500 bg-rose-50 text-rose-800',       hover: 'hover:border-rose-500 hover:bg-rose-50/70' },
  '김천':   { accent: 'border-cyan-500 bg-cyan-50 text-cyan-800',       hover: 'hover:border-cyan-500 hover:bg-cyan-50/70' },
  '안산':   { accent: 'border-lime-500 bg-lime-50 text-lime-800',       hover: 'hover:border-lime-500 hover:bg-lime-50/70' },
  '청주':   { accent: 'border-violet-500 bg-violet-50 text-violet-800', hover: 'hover:border-violet-500 hover:bg-violet-50/70' },
  '서울이랜드': { accent: 'border-pink-500 bg-pink-50 text-pink-800',   hover: 'hover:border-pink-500 hover:bg-pink-50/70' },
  '천안':   { accent: 'border-fuchsia-500 bg-fuchsia-50 text-fuchsia-800', hover: 'hover:border-fuchsia-500 hover:bg-fuchsia-50/70' },
  '아산':   { accent: 'border-stone-500 bg-stone-50 text-stone-800',    hover: 'hover:border-stone-500 hover:bg-stone-50/70' },
  '안양':   { accent: 'border-yellow-500 bg-yellow-50 text-yellow-900', hover: 'hover:border-yellow-500 hover:bg-yellow-50/70' },
  '부천':   { accent: 'border-orange-500 bg-orange-50 text-orange-900', hover: 'hover:border-orange-500 hover:bg-orange-50/70' },
  '김포':   { accent: 'border-sky-500 bg-sky-50 text-sky-900',          hover: 'hover:border-sky-500 hover:bg-sky-50/70' },
}
const DEFAULT_STYLE = { accent: 'border-slate-400 bg-slate-50 text-slate-800', hover: 'hover:border-slate-400 hover:bg-slate-50/70' }

function getTeamStyle(teamName: string) {
  const key = Object.keys(TEAM_STYLE_MAP).find(k => teamName.includes(k))
  return key ? TEAM_STYLE_MAP[key] : DEFAULT_STYLE
}

/* ── 공통 섹션 카드 헤더 ── */
function SectionHeader({ title, sub, action }: { title: string; sub?: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-6 py-5">
      <div className="flex items-center gap-2">
        <span className="text-[14px] font-semibold text-slate-800">{title}</span>
        {sub && <span className="text-[11px] text-slate-400">{sub}</span>}
      </div>
      {action}
    </div>
  )
}

/* ── 펼침 버튼 ── */
function ExpandBtn({ open, onClick, loading }: { open: boolean; onClick: () => void; loading: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="flex items-center gap-1.5 text-[12px] font-medium text-slate-500 hover:text-slate-800 transition-colors disabled:opacity-40"
    >
      {loading ? (
        <span className="w-3.5 h-3.5 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
      ) : (
        <>
          {open ? '접기' : '보기'}
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
            style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }}>
            <path d="M6 9l6 6 6-6" />
          </svg>
        </>
      )}
    </button>
  )
}

export default function StatsPage() {
  const navigate = useNavigate()
  const { toggle, isFavorite } = useFavorites()
  const autoSelectRef = useRef(new URLSearchParams(window.location.search).get('team'))
  const [season, setSeason] = useState<SeasonRange>({ from: 2025, to: 2025 })
  const [teams, setTeams] = useState<string[]>([])
  const [teamsLoading, setTeamsLoading] = useState(false)
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null)
  const [stats, setStats] = useState<TeamStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [topScorers, setTopScorers] = useState<PlayerSearchResult | null>(null)
  const [scorersLoading, setScorersLoading] = useState(false)
  const [standings, setStandings] = useState<Standings | null>(null)
  const [standingsLoading, setStandingsLoading] = useState(false)
  const [standingsRound, setStandingsRound] = useState<number | null>(null)
  const [attendance, setAttendance] = useState<AttendanceData | null>(null)
  const [attendanceLoading, setAttendanceLoading] = useState(false)
  const [minutesQuery, setMinutesQuery] = useState('')
  const [minutesData, setMinutesData] = useState<PlayerMinutesData | TeamMinutesData | null>(null)
  const [minutesLoading, setMinutesLoading] = useState(false)
  const [minutesError, setMinutesError] = useState<string | null>(null)

  const seasonLabel = season.from === season.to ? `${season.from}` : `${season.from}~${season.to}`
  const isRange = season.from !== season.to

  useEffect(() => {
    setTeamsLoading(true)
    fetchStatsTeams(season.from, isRange ? season.to : undefined)
      .then(t => {
        setTeams(t)
        const pending = autoSelectRef.current
        if (pending && t.includes(pending)) {
          autoSelectRef.current = null
          handleTeamClick(pending)
        }
      })
      .catch(() => setTeams([]))
      .finally(() => setTeamsLoading(false))
  }, [season.from, season.to])

  async function handleTeamClick(team: string) {
    if (selectedTeam === team && stats) {
      setSelectedTeam(null)
      setStats(null)
      return
    }
    setSelectedTeam(team)
    setStatsLoading(true)
    setStats(null)
    try {
      const data = await fetchStats(team, season.from, isRange ? season.to : undefined)
      setStats(data)
    } catch {
      alert(`${team} ${seasonLabel}시즌 데이터를 불러오지 못했습니다.`)
      setSelectedTeam(null)
    } finally {
      setStatsLoading(false)
    }
  }

  async function handleTopScorers() {
    if (topScorers) { setTopScorers(null); return }
    setScorersLoading(true)
    try {
      const data = await fetchTopScorers(season.from, 15, isRange ? season.to : undefined)
      setTopScorers(data)
    } catch {
      alert('득점 데이터를 불러오지 못했습니다.')
    } finally {
      setScorersLoading(false)
    }
  }

  async function handleMinutesSearch() {
    const q = minutesQuery.trim()
    if (!q) return
    setMinutesLoading(true)
    setMinutesError(null)
    setMinutesData(null)
    try {
      const teamNames = ['전북', '울산', '서울', 'FC서울', '수원', '포항', '인천', '대전', '광주', '강원', '제주', '대구', '김천', '충남']
      const isTeamSearch = teamNames.some(t => q.includes(t))
      if (isTeamSearch) {
        const data = await fetchTeamMinutes(q, season.from)
        setMinutesData(data)
      } else {
        const data = await fetchPlayerMinutes(q, season.from)
        setMinutesData(data)
      }
    } catch (e: any) {
      setMinutesError(e.message || '데이터를 불러오지 못했습니다.')
    } finally {
      setMinutesLoading(false)
    }
  }

  function handleSeasonChange(range: SeasonRange) {
    setSeason(range)
    setStats(null)
    setSelectedTeam(null)
    setTopScorers(null)
    setStandings(null)
    setStandingsRound(null)
    setAttendance(null)
    setMinutesData(null)
    setMinutesError(null)
  }

  async function handleAttendance() {
    if (attendance) { setAttendance(null); return }
    setAttendanceLoading(true)
    try {
      const data = await fetchAttendance(season.from, isRange ? season.to : undefined)
      setAttendance(data)
    } catch {
      alert('관중 데이터를 불러오지 못했습니다.')
    } finally {
      setAttendanceLoading(false)
    }
  }

  async function handleStandings(round?: number) {
    const r = round ?? standingsRound ?? undefined
    setStandingsLoading(true)
    try {
      const data = await fetchStandings(season.from, r)
      setStandings(data)
      setStandingsRound(r ?? null)
    } catch {
      alert('순위 데이터를 불러오지 못했습니다.')
    } finally {
      setStandingsLoading(false)
    }
  }

  return (
    <div className="min-h-full bg-[#f3f4f6]">

      {/* 상단 헤더 */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-4xl mx-auto px-6 py-6 flex flex-col gap-4">
          <div>
            <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-widest mb-0.5">K LEAGUE 1</p>
            <h1 className="text-[17px] font-bold text-slate-900">시즌 통계</h1>
          </div>
          <SeasonSelector value={season} onChange={handleSeasonChange} theme="light" />
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-5">

        {/* ── 팀 선택 ── */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <SectionHeader
            title="팀 선택"
            sub={teamsLoading ? '불러오는 중...' : `${teams.length}개 팀`}
          />
          <div className="border-t border-slate-100 px-4 py-3">
            {teamsLoading ? (
              <div className="flex flex-wrap gap-1.5">
                {Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} className="h-8 w-16 rounded-lg bg-slate-100 animate-pulse" />
                ))}
              </div>
            ) : teams.length === 0 ? (
              <p className="text-[13px] text-slate-400 py-2">{seasonLabel}시즌 팀 데이터가 없습니다.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {teams.map(name => {
                  const style = getTeamStyle(name)
                  const isSelected = selectedTeam === name
                  return (
                    <button
                      key={name}
                      onClick={() => handleTeamClick(name)}
                      disabled={statsLoading && selectedTeam !== name}
                      className={`relative flex items-center gap-1.5 h-8 px-3 rounded-lg border text-[13px] font-medium transition-all disabled:opacity-40 ${
                        isSelected ? style.accent + ' border-2' : `bg-white border-slate-200 text-slate-600 ${style.hover}`
                      }`}
                    >
                      {statsLoading && isSelected ? (
                        <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <span
                          role="button"
                          onClick={e => { e.stopPropagation(); toggle('team', name) }}
                          className={`transition-colors ${isFavorite('team', name) ? 'text-amber-400' : 'text-slate-300 hover:text-amber-300'}`}
                        >
                          <svg width="10" height="10" viewBox="0 0 24 24"
                            fill={isFavorite('team', name) ? 'currentColor' : 'none'}
                            stroke="currentColor" strokeWidth="2">
                            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                          </svg>
                        </span>
                      )}
                      <TeamLogo team={name} size={18} />
                      {name}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* ── 팀 통계 결과 ── */}
        {(statsLoading || stats) && (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden fade-in">
            {statsLoading ? (
              <div className="px-6 py-6 space-y-3">
                <div className="h-4 w-1/3 rounded bg-slate-100 animate-pulse" />
                <div className="h-4 w-1/2 rounded bg-slate-100 animate-pulse" />
                <div className="h-24 w-full rounded-lg bg-slate-100 animate-pulse" />
              </div>
            ) : stats && (
              <StatsCard stats={stats} />
            )}
          </div>
        )}

        {/* ── 리그 순위 ── */}
        {!isRange && (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden fade-in">
            <div className="flex items-center justify-between px-6 py-5">
              <div className="flex items-center gap-2">
                <span className="text-[14px] font-semibold text-slate-800">리그 순위</span>
                {standingsRound && (
                  <span className="text-[11px] text-slate-400">{standingsRound}라운드까지</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {standings && (
                  <button
                    onClick={() => { setStandings(null); setStandingsRound(null) }}
                    className="text-[11px] text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    초기화
                  </button>
                )}
                <div className="flex items-center gap-1.5">
                  <select
                    value={standingsRound ?? ''}
                    onChange={e => setStandingsRound(e.target.value === '' ? null : Number(e.target.value))}
                    className="text-[12px] text-slate-600 border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-slate-400 cursor-pointer"
                  >
                    <option value="">전체 라운드</option>
                    {Array.from({ length: standings?.max_round ?? 38 }, (_, i) => i + 1).map(r => (
                      <option key={r} value={r}>{r}라운드까지</option>
                    ))}
                  </select>
                  <button
                    onClick={() => handleStandings(standingsRound ?? undefined)}
                    disabled={standingsLoading}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[12px] font-semibold bg-slate-900 hover:bg-slate-700 text-white transition-all disabled:opacity-50"
                  >
                    {standingsLoading
                      ? <span className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                      : '조회'
                    }
                  </button>
                </div>
              </div>
            </div>

            {standings && !standingsLoading && (
              <div className="border-t border-slate-100 fade-in">
                {/* 범례 */}
                <div className="flex items-center gap-4 px-4 py-2.5 bg-slate-50 border-b border-slate-100">
                  <span className="text-[10px] font-medium text-slate-400">{season.from}시즌</span>
                  <span className="ml-auto flex items-center gap-1 text-[10px] text-amber-600">
                    <span className="w-2.5 h-2.5 rounded-sm bg-amber-400 inline-block" />1위
                  </span>
                  <span className="flex items-center gap-1 text-[10px] text-sky-600">
                    <span className="w-2.5 h-2.5 rounded-sm bg-sky-400 inline-block" />AFC
                  </span>
                  <span className="flex items-center gap-1 text-[10px] text-red-500">
                    <span className="w-2.5 h-2.5 rounded-sm bg-red-400 inline-block" />강등권
                  </span>
                </div>
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-b border-slate-100">
                      <th className="w-9 py-2.5 text-center text-[10px] font-semibold text-slate-400">#</th>
                      <th className="py-2.5 pl-1 text-left text-[10px] font-semibold text-slate-400">팀</th>
                      <th className="w-9 py-2.5 text-center text-[10px] font-semibold text-slate-400">경기</th>
                      <th className="w-9 py-2.5 text-center text-[10px] font-semibold text-emerald-600">승</th>
                      <th className="w-9 py-2.5 text-center text-[10px] font-semibold text-slate-400">무</th>
                      <th className="w-9 py-2.5 text-center text-[10px] font-semibold text-red-400">패</th>
                      <th className="w-11 py-2.5 text-center text-[10px] font-semibold text-slate-400">득점</th>
                      <th className="w-11 py-2.5 text-center text-[10px] font-semibold text-slate-400">실점</th>
                      <th className="w-11 py-2.5 text-center text-[10px] font-semibold text-slate-400">득실</th>
                      <th className="w-12 py-2.5 text-center text-[10px] font-semibold text-slate-900 pr-4">승점</th>
                    </tr>
                  </thead>
                  <tbody>
                    {standings.standings.map((row, i) => {
                      const n = standings.standings.length
                      const isTop1    = i === 0
                      const isTop3    = i > 0 && i < 3
                      const isBottom2 = i >= n - 2
                      const barColor  = isTop1 ? 'bg-amber-400' : isTop3 ? 'bg-sky-400' : isBottom2 ? 'bg-red-400' : 'bg-transparent'
                      const rowBg     = isTop1 ? 'bg-amber-50/40' : isBottom2 ? 'bg-red-50/30' : ''
                      const gdText    = row.gd > 0 ? `+${row.gd}` : String(row.gd)
                      const gdColor   = row.gd > 0 ? 'text-emerald-600 font-semibold' : row.gd < 0 ? 'text-red-500 font-semibold' : 'text-slate-400'
                      return (
                        <tr key={row.team} className={`${rowBg} border-b border-slate-50 hover:bg-slate-50/70 transition-colors`}>
                          <td className="py-2.5 text-center">
                            <div className="flex items-center justify-center gap-1">
                              <div className={`w-[3px] h-4 rounded-full ${barColor}`} />
                              <span className={`tabular-nums text-[13px] font-semibold ${isTop1 ? 'text-amber-600' : isTop3 ? 'text-sky-600' : isBottom2 ? 'text-red-500' : 'text-slate-500'}`}>
                                {row.rank}
                              </span>
                            </div>
                          </td>
                          <td className="py-2.5 pl-1 pr-3">
                            <span className="font-semibold text-slate-800">{row.team}</span>
                          </td>
                          <td className="py-2.5 text-center text-slate-500 tabular-nums">{row.games}</td>
                          <td className="py-2.5 text-center text-emerald-600 font-semibold tabular-nums">{row.win}</td>
                          <td className="py-2.5 text-center text-slate-400 tabular-nums">{row.draw}</td>
                          <td className="py-2.5 text-center text-red-400 tabular-nums">{row.lose}</td>
                          <td className="py-2.5 text-center text-slate-700 tabular-nums">{row.gf}</td>
                          <td className="py-2.5 text-center text-slate-500 tabular-nums">{row.ga}</td>
                          <td className={`py-2.5 text-center tabular-nums ${gdColor}`}>{gdText}</td>
                          <td className="py-2.5 pr-4 text-center">
                            <span className={`inline-block min-w-[1.8rem] text-center text-[14px] font-bold tabular-nums ${isTop1 ? 'text-amber-600' : 'text-slate-900'}`}>
                              {row.points}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── 관중현황 ── */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden fade-in">
          <SectionHeader
            title="관중현황"
            sub={attendance ? attendance.season_label : undefined}
            action={
              <ExpandBtn
                open={!!attendance}
                onClick={handleAttendance}
                loading={attendanceLoading}
              />
            }
          />

          {attendance && (
            <div className="border-t border-slate-100 fade-in">
              {/* 요약 지표 */}
              <div className="grid grid-cols-3 divide-x divide-slate-100 border-b border-slate-100">
                <div className="px-4 py-3.5 text-center">
                  <p className="text-[10px] text-slate-400 mb-1">총 관중</p>
                  <p className="text-[20px] font-bold text-slate-900 tabular-nums leading-none">
                    {(attendance.summary.total_attendance / 10000).toFixed(0)}<span className="text-[13px] font-normal text-slate-500 ml-0.5">만</span>
                  </p>
                  <p className="text-[10px] text-slate-400 mt-0.5">{attendance.summary.total_attendance.toLocaleString()}명</p>
                </div>
                <div className="px-4 py-3.5 text-center">
                  <p className="text-[10px] text-slate-400 mb-1">경기당 평균</p>
                  <p className="text-[20px] font-bold text-violet-600 tabular-nums leading-none">
                    {attendance.summary.avg_per_game.toLocaleString()}
                  </p>
                  <p className="text-[10px] text-slate-400 mt-0.5">명</p>
                </div>
                <div className="px-4 py-3.5 text-center">
                  <p className="text-[10px] text-slate-400 mb-1">집계 경기</p>
                  <p className="text-[20px] font-bold text-slate-900 tabular-nums leading-none">
                    {attendance.summary.total_games}
                  </p>
                  <p className="text-[10px] text-slate-400 mt-0.5">경기</p>
                </div>
              </div>

              {/* 최다 관중 경기 */}
              {attendance.summary.max_game && (
                <div className="px-4 py-2.5 bg-violet-50 border-b border-slate-100 flex items-center gap-2">
                  <span className="text-[10px] font-semibold text-violet-500 shrink-0">최다 관중</span>
                  <span className="text-[12px] text-slate-700 font-medium">
                    {attendance.summary.max_game.home_team} vs {attendance.summary.max_game.away_team}
                  </span>
                  <span className="text-[12px] font-bold text-violet-600 ml-auto">
                    {attendance.summary.max_game.attendance.toLocaleString()}명
                  </span>
                  <span className="text-[10px] text-slate-400">{attendance.summary.max_game.date}</span>
                </div>
              )}

              {/* 홈팀별 관중 순위 */}
              <div className="border-b border-slate-100">
                <div className="px-4 py-2.5 bg-slate-50">
                  <span className="text-[11px] font-semibold text-slate-600">홈팀별 평균 관중</span>
                </div>
                <table className="w-full text-[13px]" style={{ tableLayout: 'fixed' }}>
                  <colgroup>
                    <col style={{ width: '2.2rem' }} />
                    <col style={{ width: '5rem' }} />
                    <col style={{ width: '2.8rem' }} />
                    <col />
                    <col style={{ width: '5rem' }} />
                  </colgroup>
                  <thead>
                    <tr className="border-b border-slate-100">
                      <th className="py-2 text-center text-[10px] font-semibold text-slate-400">#</th>
                      <th className="py-2 pl-2 text-left text-[10px] font-semibold text-slate-400">팀</th>
                      <th className="py-2 text-center text-[10px] font-semibold text-slate-400">경기</th>
                      <th className="py-2 px-3 text-left text-[10px] font-semibold text-violet-600">평균 관중</th>
                      <th className="py-2 text-center text-[10px] font-semibold text-slate-400 pr-4">최다</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attendance.by_team.map((row, i) => {
                      const maxAvg = attendance.by_team[0]?.avg ?? 1
                      const barW = Math.round((row.avg / maxAvg) * 100)
                      return (
                        <tr key={row.team} className="border-b border-slate-50 hover:bg-slate-50/70 transition-colors">
                          <td className="py-2.5 text-center">
                            <span className={`tabular-nums font-semibold ${i === 0 ? 'text-violet-600' : i < 3 ? 'text-violet-500' : 'text-slate-400'}`}>
                              {row.rank}
                            </span>
                          </td>
                          <td className="py-2.5 pl-2">
                            <span className="font-semibold text-slate-700 truncate block">{row.team}</span>
                          </td>
                          <td className="py-2.5 text-center text-slate-400 tabular-nums">{row.games}</td>
                          <td className="py-2.5 px-3">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                                <div className="h-full bg-violet-400 rounded-full" style={{ width: `${barW}%` }} />
                              </div>
                              <span className="text-[12px] font-bold text-violet-600 tabular-nums shrink-0 min-w-[3.5rem] text-right">
                                {row.avg.toLocaleString()}
                              </span>
                            </div>
                          </td>
                          <td className="py-2.5 text-center text-slate-400 tabular-nums text-[12px] pr-4">
                            {row.max.toLocaleString()}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* TOP 10 경기 */}
              <div>
                <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-100">
                  <span className="text-[11px] font-semibold text-slate-600">최다 관중 TOP 10</span>
                </div>
                <div className="divide-y divide-slate-50">
                  {attendance.top_games.map((g, i) => {
                    const [homeScore, awayScore] = (g.score ?? '').split('-').map(s => s.trim())
                    return (
                      <div key={i} className="flex items-center px-4 py-2.5 hover:bg-slate-50/70 transition-colors">
                        <span className={`text-[13px] font-bold w-7 text-center shrink-0 tabular-nums ${
                          i === 0 ? 'text-amber-500' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-600/80' : 'text-slate-300'
                        }`}>
                          {i + 1}
                        </span>
                        <span className="text-[11px] text-slate-400 shrink-0 w-[70px] tabular-nums">{g.date?.slice(5) ?? ''}</span>
                        <span className="text-[10px] text-slate-300 shrink-0 w-[28px]">{g.round ? `${g.round}R` : ''}</span>

                        <div className="flex items-center gap-1.5 justify-end flex-1 min-w-0">
                          <span className="text-[13px] font-semibold text-slate-800 truncate text-right">{g.home_team}</span>
                          <TeamLogo team={g.home_team} size={22} />
                        </div>

                        <div className="mx-2.5 shrink-0">
                          <span className="inline-flex items-center justify-center font-bold text-[13px] w-[64px] py-1 rounded-lg bg-slate-900 text-white tracking-wide">
                            {homeScore} : {awayScore}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5 flex-1 min-w-0">
                          <TeamLogo team={g.away_team} size={22} />
                          <span className="text-[13px] font-semibold text-slate-800 truncate">{g.away_team}</span>
                        </div>

                        <span className="text-[11px] text-slate-400 shrink-0 ml-3 truncate max-w-[110px] hidden sm:block">
                          {g.venue ?? ''}{g.season && isRange ? ` · ${g.season}` : ''}
                        </span>

                        <span className="text-[14px] font-bold text-violet-600 tabular-nums shrink-0 ml-3 min-w-[60px] text-right">
                          {g.attendance.toLocaleString()}
                          <span className="text-[10px] text-slate-400 font-normal ml-0.5">명</span>
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── 선수 출전시간 ── */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden fade-in">
          <SectionHeader title="선수 출전시간" />
          <div className="border-t border-slate-100 px-4 py-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={minutesQuery}
                onChange={e => setMinutesQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleMinutesSearch()}
                placeholder="선수명 또는 팀명 (예: 조진혁, 전북)"
                className="flex-1 bg-slate-50 border border-slate-200 text-slate-800 text-[13px] px-3.5 py-2 rounded-lg placeholder-slate-400 focus:outline-none focus:border-slate-400 transition-all"
              />
              <button
                onClick={handleMinutesSearch}
                disabled={minutesLoading || !minutesQuery.trim()}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-semibold bg-slate-900 hover:bg-slate-700 text-white transition-all disabled:opacity-40 shrink-0"
              >
                {minutesLoading
                  ? <span className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  : '조회'}
              </button>
              {minutesData && (
                <button
                  onClick={() => { setMinutesData(null); setMinutesError(null) }}
                  className="text-[12px] text-slate-400 hover:text-slate-600 transition-colors px-1.5"
                >
                  초기화
                </button>
              )}
            </div>

            {minutesError && (
              <p className="mt-2.5 text-[12px] text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                {minutesError}
              </p>
            )}
          </div>

          {minutesData && !minutesLoading && (
            <div className="border-t border-slate-100 fade-in">
              {'games' in minutesData ? (
                <>
                  {/* 선수 개인 헤더 */}
                  <div className="px-4 py-3 bg-teal-50 border-b border-teal-100 flex items-center justify-between">
                    <div>
                      <button
                        onClick={() => navigate(`/player?name=${encodeURIComponent((minutesData as PlayerMinutesData).player_name)}`)}
                        className="text-[15px] font-bold text-slate-900 hover:text-teal-600 transition-colors"
                      >
                        {(minutesData as PlayerMinutesData).player_name}
                      </button>
                      <p className="text-[11px] text-slate-500 mt-0.5">{(minutesData as PlayerMinutesData).team} · {minutesData.season}시즌</p>
                    </div>
                    <div className="flex gap-4 text-right">
                      {[
                        { label: '총 출전', value: `${(minutesData as PlayerMinutesData).total_minutes}분` },
                        { label: '출전 경기', value: `${(minutesData as PlayerMinutesData).appearances}경기` },
                        { label: '선발', value: `${(minutesData as PlayerMinutesData).starter_count}회` },
                        { label: '경기 평균', value: `${(minutesData as PlayerMinutesData).avg_minutes}분` },
                      ].map(item => (
                        <div key={item.label}>
                          <p className="text-[9px] text-slate-400">{item.label}</p>
                          <p className="text-[14px] font-bold text-teal-600">{item.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50">
                        <th className="w-9 py-2 text-center text-[10px] font-semibold text-slate-400">R</th>
                        <th className="py-2 pl-2 text-left text-[10px] font-semibold text-slate-400">날짜</th>
                        <th className="py-2 text-left text-[10px] font-semibold text-slate-400">홈팀</th>
                        <th className="py-2 text-left text-[10px] font-semibold text-slate-400">원정팀</th>
                        <th className="w-12 py-2 text-center text-[10px] font-semibold text-slate-400">스코어</th>
                        <th className="w-14 py-2 text-center text-[10px] font-semibold text-teal-600">출전</th>
                        <th className="py-2 pr-3 text-center text-[10px] font-semibold text-slate-400">비고</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(minutesData as PlayerMinutesData).games.map((g, i) => {
                        const note = g.subbed_off != null ? `${g.subbed_off}분 아웃`
                          : g.subbed_on != null ? `${g.subbed_on}분 인`
                          : g.starter ? '선발' : '-'
                        const minuteColor = g.minutes >= 90 ? 'text-teal-600 font-bold'
                          : g.minutes >= 60 ? 'text-teal-500 font-semibold'
                          : 'text-slate-500'
                        return (
                          <tr key={i} className="border-b border-slate-50 hover:bg-slate-50/70 transition-colors">
                            <td className="py-2 text-center text-slate-400 tabular-nums">{g.round ?? '-'}</td>
                            <td className="py-2 pl-2 text-slate-400 tabular-nums">{g.date}</td>
                            <td className="py-2 text-slate-700">{g.home_team}</td>
                            <td className="py-2 text-slate-700">{g.away_team}</td>
                            <td className="py-2 text-center text-slate-400 tabular-nums">{g.home_score ?? '?'}-{g.away_score ?? '?'}</td>
                            <td className={`py-2 text-center tabular-nums ${minuteColor}`}>{g.minutes}분</td>
                            <td className="py-2 pr-3 text-center text-[11px] text-slate-400">{note}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </>
              ) : (
                <>
                  {/* 팀 전체 헤더 */}
                  <div className="px-4 py-3 bg-teal-50 border-b border-teal-100">
                    <p className="text-[15px] font-bold text-slate-900">{(minutesData as TeamMinutesData).team}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5">{minutesData.season}시즌 출전시간</p>
                  </div>
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50">
                        <th className="w-9 py-2.5 text-center text-[10px] font-semibold text-slate-400">#</th>
                        <th className="py-2.5 pl-2 text-left text-[10px] font-semibold text-slate-400">선수명</th>
                        <th className="w-11 py-2.5 text-center text-[10px] font-semibold text-slate-400">경기</th>
                        <th className="w-11 py-2.5 text-center text-[10px] font-semibold text-slate-400">선발</th>
                        <th className="w-18 py-2.5 text-center text-[10px] font-semibold text-teal-600">총 출전</th>
                        <th className="w-14 py-2.5 text-center text-[10px] font-semibold text-slate-400 pr-3">평균</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(minutesData as TeamMinutesData).players.map((p, i) => (
                        <tr key={i} className="border-b border-slate-50 hover:bg-slate-50/70 transition-colors">
                          <td className="py-2.5 text-center text-slate-400 tabular-nums text-[12px]">{i + 1}</td>
                          <td className="py-2.5 pl-2 font-medium text-slate-700">
                            <button
                              onClick={() => navigate(`/player?name=${encodeURIComponent(p.player_name)}`)}
                              className="hover:text-teal-600 transition-colors text-left"
                            >
                              {p.player_name}
                            </button>
                          </td>
                          <td className="py-2.5 text-center text-slate-400 tabular-nums">{p.appearances}</td>
                          <td className="py-2.5 text-center text-slate-400 tabular-nums">{p.starter_count}</td>
                          <td className="py-2.5 text-center font-bold text-teal-600 tabular-nums">{p.total_minutes}분</td>
                          <td className="py-2.5 pr-3 text-center text-slate-400 tabular-nums text-[12px]">{p.avg_minutes}분</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          )}
        </div>

        {/* ── 득점 순위 ── */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden fade-in">
          <SectionHeader
            title="득점 순위"
            sub={topScorers ? `TOP 15 · ${seasonLabel}시즌` : undefined}
            action={
              <ExpandBtn
                open={!!topScorers}
                onClick={handleTopScorers}
                loading={scorersLoading}
              />
            }
          />

          {topScorers && (
            <div className="border-t border-slate-100 fade-in">
              <div className="divide-y divide-slate-50">
                {topScorers.players.map((p, i) => {
                  const maxGoals = topScorers.players[0]?.goals ?? 1
                  const barW = Math.round((p.goals / maxGoals) * 100)
                  return (
                    <div key={i} className="flex items-center px-4 py-2.5 hover:bg-slate-50/70 transition-colors gap-3">
                      <span className={`text-[13px] font-bold w-6 text-center shrink-0 tabular-nums ${
                        i === 0 ? 'text-amber-500' : i === 1 ? 'text-slate-400' : i === 2 ? 'text-amber-600/80' : 'text-slate-300'
                      }`}>
                        {i + 1}
                      </span>
                      <button
                        onClick={() => navigate(`/player?name=${encodeURIComponent(p.player_name)}`)}
                        className="text-[13px] font-semibold text-slate-800 min-w-0 text-left hover:text-emerald-600 transition-colors w-24 shrink-0"
                      >
                        {p.player_name}
                      </button>
                      <span className="text-[11px] text-slate-400 shrink-0 w-16 truncate">{p.team}</span>
                      <div className="flex-1 flex items-center gap-2 min-w-0">
                        <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                          <div className="h-full bg-emerald-400 rounded-full" style={{ width: `${barW}%` }} />
                        </div>
                        <span className="text-[15px] font-bold text-slate-900 tabular-nums shrink-0 w-8 text-right">
                          {p.goals}
                        </span>
                        <span className="text-[10px] text-slate-400 shrink-0">G</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
