import { useState, useRef } from 'react'
import { fetchPlayerCompare, searchPlayersByName } from '../api'
import type { PlayerCompareData, PlayerCareerData, PlayerCareerSeason, PlayerNameSuggestion } from '../types'

const SEASONS = Array.from({ length: 2026 - 2010 + 1 }, (_, i) => 2026 - i)

// ─── 색상 설정 ────────────────────────────────────────────────────────────────
const C1 = { line: '#10b981', fill: '#d1fae5', text: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200', badge: 'bg-emerald-500', gradient: 'from-emerald-400 to-teal-500' }
const C2 = { line: '#f43f5e', fill: '#ffe4e6', text: 'text-rose-600', bg: 'bg-rose-50', border: 'border-rose-200', badge: 'bg-rose-500', gradient: 'from-rose-400 to-pink-500' }

const POSITION_BG: Record<string, string> = {
  GK: 'bg-amber-50 text-amber-700 border-amber-300',
  DF: 'bg-sky-50 text-sky-700 border-sky-300',
  MF: 'bg-emerald-50 text-emerald-700 border-emerald-300',
  FW: 'bg-rose-50 text-rose-700 border-rose-300',
}

// ─── 미러 바 차트 (통산 스탯 비교) ────────────────────────────────────────────
function MirrorBar({ label, v1, v2, unit = '' }: { label: string; v1: number; v2: number; unit?: string }) {
  const max = Math.max(v1, v2, 1)
  const pct1 = Math.round((v1 / max) * 100)
  const pct2 = Math.round((v2 / max) * 100)
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] gap-x-3 items-center py-2.5 border-b border-slate-100 last:border-0">
      {/* 선수 1 바 (오른쪽 정렬) */}
      <div className="flex items-center justify-end gap-2">
        <span className={`text-[14px] font-black ${C1.text}`}>{v1.toLocaleString()}{unit}</span>
        <div className="w-28 h-2 bg-slate-100 rounded-full overflow-hidden flex justify-end">
          <div className="h-full bg-emerald-400 rounded-full transition-all duration-700" style={{ width: `${pct1}%` }} />
        </div>
      </div>
      {/* 레이블 */}
      <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">{label}</span>
      {/* 선수 2 바 (왼쪽 정렬) */}
      <div className="flex items-center gap-2">
        <div className="w-28 h-2 bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full bg-rose-400 rounded-full transition-all duration-700" style={{ width: `${pct2}%` }} />
        </div>
        <span className={`text-[14px] font-black ${C2.text}`}>{v2.toLocaleString()}{unit}</span>
      </div>
    </div>
  )
}

// ─── SVG 꺾은선 그래프 ─────────────────────────────────────────────────────────
type StatKey = 'goals' | 'assists' | 'appearances' | 'total_minutes'

function LineChart({ p1, p2, statKey }: { p1: PlayerCareerData; p2: PlayerCareerData; statKey: StatKey }) {
  const W = 560; const H = 160; const PAD = { t: 16, r: 16, b: 32, l: 36 }
  const innerW = W - PAD.l - PAD.r
  const innerH = H - PAD.t - PAD.b

  // 공통 시즌 범위
  const allSeasons = Array.from(
    new Set([...p1.career.map(s => s.season), ...p2.career.map(s => s.season)])
  ).sort()

  if (allSeasons.length === 0) return null

  const getVal = (career: PlayerCareerSeason[], season: number): number | null => {
    const s = career.find(c => c.season === season)
    return s ? (s[statKey] ?? 0) : null
  }

  const allVals = allSeasons.flatMap(s => [
    getVal(p1.career, s) ?? 0,
    getVal(p2.career, s) ?? 0,
  ])
  const maxVal = Math.max(...allVals, 1)

  const xOf = (i: number) => PAD.l + (i / Math.max(allSeasons.length - 1, 1)) * innerW
  const yOf = (v: number) => PAD.t + innerH - (v / maxVal) * innerH

  const toPath = (career: PlayerCareerSeason[]) => {
    const pts = allSeasons
      .map((s, i) => ({ x: xOf(i), y: yOf(getVal(career, s) ?? 0), v: getVal(career, s) }))
      .filter(pt => pt.v !== null)
    if (pts.length === 0) return ''
    return pts.map((pt, i) => `${i === 0 ? 'M' : 'L'}${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(' ')
  }

  // y축 눈금 (0, max/2, max)
  const yTicks = [0, Math.round(maxVal / 2), maxVal]

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
      {/* 그리드 선 */}
      {yTicks.map(v => (
        <g key={v}>
          <line
            x1={PAD.l} y1={yOf(v)} x2={W - PAD.r} y2={yOf(v)}
            stroke="#e2e8f0" strokeWidth="1" strokeDasharray="4 3"
          />
          <text x={PAD.l - 4} y={yOf(v) + 4} textAnchor="end" fontSize="9" fill="#94a3b8">{v}</text>
        </g>
      ))}

      {/* x축 레이블 */}
      {allSeasons.map((s, i) => {
        // 시즌이 많으면 일부만 표시
        if (allSeasons.length > 10 && i % 2 !== 0) return null
        return (
          <text key={s} x={xOf(i)} y={H - 4} textAnchor="middle" fontSize="9" fill="#94a3b8">
            {String(s).slice(2)}
          </text>
        )
      })}

      {/* 선수 1 라인 */}
      <path d={toPath(p1.career)} fill="none" stroke={C1.line} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      {/* 선수 2 라인 */}
      <path d={toPath(p2.career)} fill="none" stroke={C2.line} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {/* 데이터 포인트 */}
      {allSeasons.map((s, i) => {
        const v1 = getVal(p1.career, s)
        const v2 = getVal(p2.career, s)
        return (
          <g key={s}>
            {v1 !== null && (
              <circle cx={xOf(i)} cy={yOf(v1)} r="3.5" fill={C1.line} stroke="white" strokeWidth="1.5" />
            )}
            {v2 !== null && (
              <circle cx={xOf(i)} cy={yOf(v2)} r="3.5" fill={C2.line} stroke="white" strokeWidth="1.5" />
            )}
          </g>
        )
      })}
    </svg>
  )
}

// ─── 선수 검색 인풋 ────────────────────────────────────────────────────────────
function PlayerSearchInput({
  value, onChange, onSelect, placeholder, color,
}: {
  value: string
  onChange: (v: string) => void
  onSelect: (name: string) => void
  placeholder: string
  color: typeof C1
}) {
  const [suggestions, setSuggestions] = useState<PlayerNameSuggestion[]>([])
  const [show, setShow] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function handleChange(v: string) {
    onChange(v)
    setShow(true)
    if (timer.current) clearTimeout(timer.current)
    if (!v.trim()) { setSuggestions([]); return }
    timer.current = setTimeout(async () => {
      try {
        const res = await searchPlayersByName(v.trim())
        setSuggestions(res.players ?? [])
      } catch {
        setSuggestions([])
      }
    }, 300)
  }

  return (
    <div className="relative flex-1">
      <input
        type="text"
        value={value}
        onChange={e => handleChange(e.target.value)}
        onFocus={() => value && setShow(true)}
        onBlur={() => setTimeout(() => setShow(false), 150)}
        placeholder={placeholder}
        className={`w-full bg-white border-2 ${color.border} rounded-xl px-4 py-3 text-[14px] text-slate-800 placeholder-slate-400 outline-none focus:ring-2 focus:ring-offset-0 transition-all shadow-sm`}
      />
      {show && suggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1.5 bg-white border border-slate-200 rounded-xl shadow-lg z-10 overflow-hidden">
          {suggestions.slice(0, 6).map((s, i) => (
            <button
              key={s.player_name}
              onMouseDown={() => { onSelect(s.player_name); setShow(false) }}
              className={`w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 transition-colors text-left ${i > 0 ? 'border-t border-slate-100' : ''}`}
            >
              <span className="text-[14px] text-slate-800 font-medium">{s.player_name}</span>
              <span className="text-[11px] text-slate-400">{s.team} · {Math.min(...s.seasons)}~{Math.max(...s.seasons)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── 선수 헤더 카드 ────────────────────────────────────────────────────────────
function PlayerHeader({ data, color }: { data: PlayerCareerData; color: typeof C1 }) {
  const pos = data.profile?.position ?? ''
  return (
    <div className={`bg-white border ${color.border} rounded-2xl overflow-hidden shadow-sm flex-1`}>
      <div className={`h-2 bg-gradient-to-r ${color.gradient}`} />
      <div className="px-5 py-4">
        <div className="flex items-center gap-3 mb-3">
          {data.profile?.jersey_number && (
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color.gradient} flex items-center justify-center shrink-0 shadow`}>
              <span className="text-white font-black text-[16px]">{data.profile.jersey_number}</span>
            </div>
          )}
          <div>
            <div className="text-[18px] font-black text-slate-900 leading-tight">{data.player_name}</div>
            <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
              <span className="text-[12px] text-slate-500">{data.current_team}</span>
              {pos && (
                <>
                  <span className="text-slate-300">·</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${POSITION_BG[pos] ?? 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                    {pos}
                  </span>
                </>
              )}
              {data.profile?.is_foreign && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full border bg-purple-50 text-purple-700 border-purple-300">외국인</span>
              )}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-100">
          {[
            { label: '시즌', value: `${data.totals.seasons}` },
            { label: '경기', value: `${data.totals.appearances}` },
            { label: '득점', value: `${data.totals.goals}` },
          ].map(item => (
            <div key={item.label} className="text-center">
              <div className={`text-[20px] font-black ${color.text}`}>{item.value}</div>
              <div className="text-[10px] text-slate-400 uppercase tracking-wider">{item.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── 메인 페이지 ───────────────────────────────────────────────────────────────
const CHART_TABS: { key: StatKey; label: string }[] = [
  { key: 'goals', label: '득점' },
  { key: 'assists', label: '도움' },
  { key: 'appearances', label: '출장' },
  { key: 'total_minutes', label: '출전시간' },
]

export default function PlayerComparePage() {
  const [name1, setName1] = useState('')
  const [name2, setName2] = useState('')
  const [seasonMode, setSeasonMode] = useState<'single' | 'range'>('single')
  const [seasonFrom, setSeasonFrom] = useState(2025)
  const [seasonTo, setSeasonTo] = useState(2025)
  const [data, setData] = useState<PlayerCompareData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chartStat, setChartStat] = useState<StatKey>('goals')

  const effectiveFrom = seasonMode === 'single' ? seasonFrom : seasonFrom
  const effectiveTo   = seasonMode === 'single' ? seasonFrom : seasonTo

  async function handleCompare() {
    if (!name1.trim() || !name2.trim()) return
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const result = await fetchPlayerCompare(name1.trim(), name2.trim(), effectiveFrom, effectiveTo)
      setData(result)
    } catch (e: any) {
      setError(e?.message ?? '비교 데이터를 불러올 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-full bg-main flex flex-col items-center px-6 py-10">
    <div className="w-full max-w-3xl">

      {/* 검색 카드 */}
      <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm mb-6 space-y-5">

        {/* 선수 입력 — 좌우 2열 */}
        <div className="grid grid-cols-[1fr_28px_1fr] items-start gap-1.5">
          {/* 선수 A */}
          <div>
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">선수 A</span>
            </div>
            <PlayerSearchInput
              value={name1}
              onChange={setName1}
              onSelect={setName1}
              placeholder="이름 검색"
              color={C1}
            />
          </div>

          {/* VS 구분선 */}
          <div className="flex flex-col items-center justify-center h-full pt-6 gap-1">
            <div className="flex-1 w-px bg-slate-100" />
            <span className="text-[10px] font-black text-slate-300 leading-none">VS</span>
            <div className="flex-1 w-px bg-slate-100" />
          </div>

          {/* 선수 B */}
          <div>
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0" />
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">선수 B</span>
            </div>
            <PlayerSearchInput
              value={name2}
              onChange={setName2}
              onSelect={setName2}
              placeholder="이름 검색"
              color={C2}
            />
          </div>
        </div>

        {/* 시즌 선택 */}
        <div className="pt-3 border-t border-slate-100">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5">시즌</p>

          {/* 라디오 버튼 */}
          <div className="flex gap-5 mb-3">
            {(['single', 'range'] as const).map(mode => (
              <label key={mode} className="flex items-center gap-2 cursor-pointer select-none" onClick={() => setSeasonMode(mode)}>
                <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                  seasonMode === mode ? 'border-slate-700' : 'border-slate-300'
                }`}>
                  {seasonMode === mode && <div className="w-2 h-2 rounded-full bg-slate-700" />}
                </div>
                <span className={`text-[13px] font-medium transition-colors ${
                  seasonMode === mode ? 'text-slate-800' : 'text-slate-400'
                }`}>
                  {mode === 'single' ? '특정 시즌' : '구간'}
                </span>
              </label>
            ))}
          </div>

          {/* 드롭다운 */}
          {seasonMode === 'single' ? (
            <div className="relative w-36">
              <select
                value={seasonFrom}
                onChange={e => setSeasonFrom(Number(e.target.value))}
                className="w-full appearance-none bg-slate-50 border border-slate-200 text-slate-800 text-[13px] font-semibold px-3 py-2 pr-7 rounded-lg cursor-pointer focus:outline-none focus:border-slate-400 transition-colors hover:border-slate-300"
              >
                {SEASONS.map(y => <option key={y} value={y}>{y}시즌</option>)}
              </select>
              <svg className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-slate-400" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <div className="relative">
                <select
                  value={seasonFrom}
                  onChange={e => {
                    const v = Number(e.target.value)
                    setSeasonFrom(v)
                    if (v > seasonTo) setSeasonTo(v)
                  }}
                  className="appearance-none bg-slate-50 border border-slate-200 text-slate-800 text-[13px] font-semibold px-3 py-2 pr-7 rounded-lg cursor-pointer focus:outline-none focus:border-slate-400 transition-colors hover:border-slate-300"
                >
                  {SEASONS.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
                <svg className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-slate-400" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
              </div>
              <span className="text-[12px] font-bold text-slate-300">~</span>
              <div className="relative">
                <select
                  value={seasonTo}
                  onChange={e => setSeasonTo(Number(e.target.value))}
                  className="appearance-none bg-slate-50 border border-slate-200 text-slate-800 text-[13px] font-semibold px-3 py-2 pr-7 rounded-lg cursor-pointer focus:outline-none focus:border-slate-400 transition-colors hover:border-slate-300"
                >
                  {SEASONS.filter(y => y >= seasonFrom).map(y => <option key={y} value={y}>{y}</option>)}
                </select>
                <svg className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-slate-400" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
              </div>
              {seasonFrom !== seasonTo && (
                <span className="text-[11px] text-slate-400">{seasonTo - seasonFrom + 1}개 시즌</span>
              )}
            </div>
          )}
        </div>

        <button
          onClick={handleCompare}
          disabled={loading || !name1.trim() || !name2.trim()}
          className="w-full py-3 bg-gradient-to-r from-slate-700 to-slate-900 hover:from-slate-600 hover:to-slate-800 disabled:opacity-40 text-white font-black text-[14px] rounded-xl transition-all shadow-sm hover:shadow-md"
        >
          {loading ? '분석 중...' : '비교하기'}
        </button>
      </div>

      {/* 로딩 */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-700 rounded-full animate-spin" />
          <p className="text-[13px] text-slate-400">커리어 데이터 및 AI 분석 중...</p>
        </div>
      )}

      {/* 에러 */}
      {error && !loading && (
        <div className="bg-white border border-red-100 rounded-2xl px-6 py-6 text-center shadow-sm">
          <p className="text-[14px] font-semibold text-red-500">{error}</p>
          <p className="text-[12px] text-slate-400 mt-1">이름을 다시 확인해 주세요.</p>
        </div>
      )}

      {/* 결과 */}
      {data && !loading && (
        <div className="space-y-4 fade-in">

          {/* 선수 헤더 카드 2개 */}
          <div className="flex gap-3">
            <PlayerHeader data={data.player1} color={C1} />
            <PlayerHeader data={data.player2} color={C2} />
          </div>

          {/* 통산 스탯 미러 바 차트 */}
          <div className="bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-sm">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-[14px] font-bold text-slate-800">통산 기록 비교</h3>
              <div className="flex items-center gap-4 text-[11px] font-semibold">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" />
                  <span className="text-slate-600">{data.player1.player_name}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-400 inline-block" />
                  <span className="text-slate-600">{data.player2.player_name}</span>
                </span>
              </div>
            </div>
            <div className="px-5 py-3">
              <MirrorBar label="득점" v1={data.player1.totals.goals} v2={data.player2.totals.goals} />
              <MirrorBar label="도움" v1={data.player1.totals.assists} v2={data.player2.totals.assists} />
              <MirrorBar label="출장" v1={data.player1.totals.appearances} v2={data.player2.totals.appearances} />
              <MirrorBar label="경고" v1={data.player1.totals.yellow_cards} v2={data.player2.totals.yellow_cards} />
              <MirrorBar
                label="출전(분)"
                v1={data.player1.totals.total_minutes}
                v2={data.player2.totals.total_minutes}
              />
            </div>
          </div>

          {/* 시즌별 트렌드 차트 */}
          <div className="bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-sm">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between flex-wrap gap-2">
              <h3 className="text-[14px] font-bold text-slate-800">시즌별 트렌드</h3>
              <div className="flex gap-1.5">
                {CHART_TABS.map(tab => (
                  <button
                    key={tab.key}
                    onClick={() => setChartStat(tab.key)}
                    className={`px-3 py-1.5 rounded-lg text-[11px] font-bold transition-colors ${
                      chartStat === tab.key
                        ? 'bg-slate-800 text-white'
                        : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="px-4 py-4">
              <LineChart p1={data.player1} p2={data.player2} statKey={chartStat} />
              <div className="flex items-center justify-center gap-5 mt-2">
                <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
                  <svg width="20" height="4" viewBox="0 0 20 4"><line x1="0" y1="2" x2="20" y2="2" stroke={C1.line} strokeWidth="2.5" strokeLinecap="round"/></svg>
                  {data.player1.player_name}
                </span>
                <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
                  <svg width="20" height="4" viewBox="0 0 20 4"><line x1="0" y1="2" x2="20" y2="2" stroke={C2.line} strokeWidth="2.5" strokeLinecap="round"/></svg>
                  {data.player2.player_name}
                </span>
              </div>
            </div>
          </div>

          {/* 시즌별 기록 테이블 (두 선수 나란히) */}
          <div className="bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-sm">
            <div className="px-5 py-4 border-b border-slate-100">
              <h3 className="text-[14px] font-bold text-slate-800">시즌별 기록</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-100">
                    <th className="text-left px-4 py-2.5 text-[10px] text-slate-400 uppercase tracking-wider">시즌</th>
                    <th className="text-center px-3 py-2.5 text-[10px] font-bold uppercase tracking-wider" style={{ color: C1.line }}>
                      {data.player1.player_name}
                    </th>
                    <th className="text-center px-3 py-2.5 text-[10px] font-bold uppercase tracking-wider" style={{ color: C2.line }}>
                      {data.player2.player_name}
                    </th>
                  </tr>
                  <tr className="bg-slate-50/50 border-b border-slate-100">
                    <th />
                    <th className="text-center px-3 py-1 text-[9px] text-slate-400 font-normal">출장·득점·도움</th>
                    <th className="text-center px-3 py-1 text-[9px] text-slate-400 font-normal">출장·득점·도움</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const allSeasons = Array.from(
                      new Set([
                        ...data.player1.career.map(s => s.season),
                        ...data.player2.career.map(s => s.season),
                      ])
                    ).sort((a, b) => b - a)

                    return allSeasons.map((season, i) => {
                      const s1 = data.player1.career.find(c => c.season === season)
                      const s2 = data.player2.career.find(c => c.season === season)
                      return (
                        <tr key={season} className={`border-b border-slate-50 hover:bg-slate-50/80 ${i % 2 !== 0 ? 'bg-slate-50/30' : ''}`}>
                          <td className="px-4 py-2.5 font-bold text-slate-700">{season}</td>
                          <td className="px-3 py-2.5 text-center">
                            {s1 ? (
                              <span className="text-slate-700">
                                <span className="text-slate-500">{s1.appearances}</span>
                                <span className="text-slate-300 mx-1">·</span>
                                <span className={`font-bold ${C1.text}`}>{s1.goals}G</span>
                                <span className="text-slate-300 mx-1">·</span>
                                <span className="text-sky-600 font-bold">{s1.assists}A</span>
                              </span>
                            ) : <span className="text-slate-200">—</span>}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            {s2 ? (
                              <span className="text-slate-700">
                                <span className="text-slate-500">{s2.appearances}</span>
                                <span className="text-slate-300 mx-1">·</span>
                                <span className={`font-bold ${C2.text}`}>{s2.goals}G</span>
                                <span className="text-slate-300 mx-1">·</span>
                                <span className="text-sky-600 font-bold">{s2.assists}A</span>
                              </span>
                            ) : <span className="text-slate-200">—</span>}
                          </td>
                        </tr>
                      )
                    })
                  })()}
                </tbody>
              </table>
            </div>
          </div>

          {/* AI 요약 */}
          {data.summary && (
            <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-sm">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/>
                    <path d="M2 12h20"/>
                  </svg>
                </div>
                <h3 className="text-[14px] font-bold text-slate-800">AI 해설 분석</h3>
              </div>
              <p className="text-[13px] text-slate-600 leading-relaxed whitespace-pre-wrap">{data.summary}</p>
            </div>
          )}

        </div>
      )}

      {/* 빈 상태 */}
      {!data && !loading && !error && (
        <div className="text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-white border border-slate-100 shadow-sm flex items-center justify-center mx-auto mb-4">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 00-3-3.87"/>
              <path d="M16 3.13a4 4 0 010 7.75"/>
            </svg>
          </div>
          <p className="text-[14px] font-semibold text-slate-500">두 선수를 입력하고 비교하세요</p>
          <p className="text-[12px] text-slate-400 mt-1">2010~2026 K리그1 등록 선수</p>
        </div>
      )}
    </div>
    </div>
  )
}
