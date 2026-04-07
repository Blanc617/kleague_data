import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchPlayerCareer, searchPlayersByName } from '../api'
import type { PlayerCareerData, PlayerCareerSeason, PlayerNameSuggestion } from '../types'
import { useFavorites } from '../hooks/useFavorites'

const POSITION_LABEL: Record<string, string> = {
  GK: 'GK',
  DF: 'DF',
  MF: 'MF',
  FW: 'FW',
}

const POSITION_COLOR: Record<string, { badge: string; accent: string }> = {
  GK: { badge: 'bg-amber-100 text-amber-700', accent: 'bg-amber-500' },
  DF: { badge: 'bg-sky-100 text-sky-700', accent: 'bg-sky-500' },
  MF: { badge: 'bg-emerald-100 text-emerald-700', accent: 'bg-emerald-500' },
  FW: { badge: 'bg-rose-100 text-rose-700', accent: 'bg-rose-500' },
}

export default function PlayerPage() {
  const { toggle, isFavorite } = useFavorites()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialName = searchParams.get('name') ?? ''

  const [query, setQuery] = useState(initialName)
  const [suggestions, setSuggestions] = useState<PlayerNameSuggestion[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [suggestLoading, setSuggestLoading] = useState(false)
  const suggestTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [data, setData] = useState<PlayerCareerData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const name = searchParams.get('name') ?? ''
    if (!name) return
    setQuery(name)
    loadCareer(name)
  }, [searchParams.get('name')])

  async function loadCareer(name: string) {
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const result = await fetchPlayerCareer(name)
      setData(result)
    } catch {
      setError(`'${name}' 선수 데이터를 찾을 수 없습니다.`)
    } finally {
      setLoading(false)
    }
  }

  function handleSubmit(name?: string) {
    const target = (name ?? query).trim()
    if (!target) return
    setShowSuggestions(false)
    setSearchParams({ name: target })
  }

  function handleInputChange(val: string) {
    setQuery(val)
    setShowSuggestions(true)
    if (suggestTimer.current) clearTimeout(suggestTimer.current)
    if (!val.trim()) { setSuggestions([]); return }
    suggestTimer.current = setTimeout(async () => {
      setSuggestLoading(true)
      try {
        const result = await searchPlayersByName(val.trim())
        setSuggestions(result.players ?? [])
      } catch {
        setSuggestions([])
      } finally {
        setSuggestLoading(false)
      }
    }, 300)
  }

  const pos = data?.profile?.position ?? ''
  const posColor = POSITION_COLOR[pos]

  return (
    <div className="min-h-full bg-main flex flex-col items-center px-6 py-10">
    <div className="w-full max-w-2xl">

      {/* 검색창 */}
      <div className="relative mb-8 px-0">
        <div className="relative">
          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
            </svg>
          </div>
          <input
            type="text"
            value={query}
            onChange={e => handleInputChange(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            onFocus={() => query && setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="선수 이름을 입력하세요"
            className="w-full bg-white border border-slate-200 rounded-xl pl-12 pr-20 py-4 text-[14px] text-slate-800 placeholder-slate-400 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 transition-all shadow-sm"
          />
          <button
            onClick={() => handleSubmit()}
            disabled={loading}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white font-semibold text-[13px] rounded-lg transition-colors"
          >
            검색
          </button>
        </div>
        {/* 자동완성 드롭다운 */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-xl shadow-lg z-10 overflow-hidden max-h-72 overflow-y-auto">
            {suggestLoading ? (
              <div className="px-4 py-3 text-[13px] text-slate-500">검색 중...</div>
            ) : (
              suggestions.slice(0, 8).map((s, i) => (
                <button
                  key={s.player_name}
                  onMouseDown={() => handleSubmit(s.player_name)}
                  className={`w-full flex items-center justify-between px-4 py-2.5 hover:bg-emerald-50 transition-colors text-left ${i > 0 ? 'border-t border-slate-50' : ''}`}
                >
                  <span className="text-[14px] text-slate-800 font-medium">{s.player_name}</span>
                  <span className="text-[12px] text-slate-400">{s.team} · {Math.min(...s.seasons)}~{Math.max(...s.seasons)}</span>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {/* 로딩 */}
      {loading && (
        <div className="flex justify-center py-20">
          <div className="w-7 h-7 border-2 border-emerald-200 border-t-emerald-500 rounded-full animate-spin" />
        </div>
      )}

      {/* 에러 */}
      {error && !loading && (
        <div className="bg-white border border-slate-100 rounded-2xl px-6 py-8 text-center shadow-sm">
          <div className="text-[32px] mb-3 opacity-60">😔</div>
          <p className="text-[14px] font-semibold text-slate-700">{error}</p>
          <p className="text-[12px] text-slate-400 mt-1">이름을 정확히 입력하거나 다른 이름으로 검색해 보세요.</p>
        </div>
      )}

      {/* 결과 */}
      {data && !loading && (
        <div className="space-y-4 fade-in">

          {/* ── 선수 프로필 카드 ── */}
          <div className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden">
            <div className="p-5">
              {/* 이름 + 포지션 */}
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2.5 mb-1">
                    <h2 className="text-[24px] font-black text-slate-900 leading-tight">{data.player_name}</h2>
                    <button
                      onClick={() => toggle('player', data.player_name)}
                      title={isFavorite('player', data.player_name) ? '즐겨찾기 해제' : '즐겨찾기 추가'}
                      className={`p-1.5 rounded-lg transition-colors ${
                        isFavorite('player', data.player_name)
                          ? 'text-amber-400 bg-amber-50'
                          : 'text-slate-300 hover:text-amber-300 hover:bg-amber-50'
                      }`}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24"
                        fill={isFavorite('player', data.player_name) ? 'currentColor' : 'none'}
                        stroke="currentColor" strokeWidth="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                      </svg>
                    </button>
                    {pos && posColor && (
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${posColor.badge}`}>
                        {POSITION_LABEL[pos] ?? pos}
                      </span>
                    )}
                    {data.profile?.is_foreign && (
                      <span className="text-[11px] font-bold px-2 py-0.5 rounded-md bg-purple-100 text-purple-700">외국인</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[13px] text-slate-500">
                    <span className="font-medium text-slate-600">{data.current_team}</span>
                    {data.profile?.jersey_number && (
                      <>
                        <span className="text-slate-300">|</span>
                        <span>No.{data.profile.jersey_number}</span>
                      </>
                    )}
                    {data.profile?.name_en && (
                      <>
                        <span className="text-slate-300">|</span>
                        <span className="text-slate-400">{data.profile.name_en}</span>
                      </>
                    )}
                  </div>
                </div>

                {/* 프로필 세부정보 */}
                {data.profile && (
                  <div className="text-right shrink-0 space-y-0.5">
                    {data.profile.birth_date && (
                      <p className="text-[12px] text-slate-400">
                        {data.profile.birth_date.replace(/-/g, '.')}
                        {data.profile.age ? <span className="text-slate-500 font-medium"> ({data.profile.age}세)</span> : ''}
                      </p>
                    )}
                    {data.profile.height_cm && (
                      <p className="text-[12px] text-slate-400">{data.profile.height_cm}cm</p>
                    )}
                  </div>
                )}
              </div>

              {/* 통산 기록 바 */}
              <div className="mt-4 pt-3 border-t border-slate-100">
                <p className="text-[11px] text-slate-400 font-medium mb-2.5">K리그 통산 기록</p>
                <div className="grid grid-cols-5 gap-2">
                  <StatItem
                    label="시즌"
                    value={data.totals.seasons}
                  />
                  <StatItem
                    label="출장"
                    value={data.totals.appearances}
                    highlight
                  />
                  <StatItem
                    label="득점"
                    value={data.totals.goals}
                    color="text-emerald-600"
                  />
                  <StatItem
                    label="도움"
                    value={data.totals.assists}
                    color="text-sky-600"
                  />
                  <StatItem
                    label="출전시간"
                    value={data.totals.total_minutes > 0 ? `${data.totals.total_minutes.toLocaleString()}분` : '-'}
                    small
                  />
                </div>
              </div>

              {/* 카드 */}
              {(data.totals.yellow_cards > 0 || data.totals.red_cards > 0) && (
                <div className="mt-3 pt-3 border-t border-slate-100 flex items-center gap-4">
                  {data.totals.yellow_cards > 0 && (
                    <div className="flex items-center gap-1.5">
                      <div className="w-3.5 h-4.5 rounded-sm bg-yellow-400" />
                      <span className="text-[13px] font-bold text-slate-600">{data.totals.yellow_cards}</span>
                    </div>
                  )}
                  {data.totals.red_cards > 0 && (
                    <div className="flex items-center gap-1.5">
                      <div className="w-3.5 h-4.5 rounded-sm bg-red-500" />
                      <span className="text-[13px] font-bold text-slate-600">{data.totals.red_cards}</span>
                    </div>
                  )}
                  {data.totals.appearances > 0 && data.totals.goals > 0 && (
                    <div className="ml-auto text-[12px] text-slate-400">
                      경기당 {(data.totals.goals / data.totals.appearances).toFixed(2)}골
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* ── 시즌별 기록 테이블 ── */}
          <div className="bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-sm">
            <div className="px-5 py-3.5 border-b border-slate-100">
              <h3 className="text-[13px] font-bold text-slate-700">시즌별 기록</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left pl-5 pr-2 py-2.5 text-[11px] text-slate-400 font-semibold">시즌</th>
                    <th className="text-left px-2 py-2.5 text-[11px] text-slate-400 font-semibold">팀</th>
                    <th className="text-center px-2 py-2.5 text-[11px] text-slate-400 font-semibold">출장</th>
                    <th className="text-center px-2 py-2.5 text-[11px] text-slate-400 font-semibold">득점</th>
                    <th className="text-center px-2 py-2.5 text-[11px] text-slate-400 font-semibold">도움</th>
                    <th className="text-center px-2 py-2.5">
                      <span className="inline-block w-2.5 h-3.5 rounded-[2px] bg-yellow-400 align-middle" />
                    </th>
                    <th className="text-center px-2 py-2.5">
                      <span className="inline-block w-2.5 h-3.5 rounded-[2px] bg-red-500 align-middle" />
                    </th>
                    <th className="text-center pl-2 pr-5 py-2.5 text-[11px] text-slate-400 font-semibold">출전(분)</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.career].reverse().map((s: PlayerCareerSeason, i: number) => (
                    <tr key={s.season} className={`border-b border-slate-50 ${i % 2 === 1 ? 'bg-slate-50/50' : ''}`}>
                      <td className="pl-5 pr-2 py-2.5 text-slate-800 font-bold">{s.season}</td>
                      <td className="px-2 py-2.5 text-slate-500 whitespace-nowrap">{s.team}</td>
                      <td className="px-2 py-2.5 text-center text-slate-600">
                        {s.appearances}
                        {s.starter_count > 0 && s.starter_count < s.appearances && (
                          <span className="text-slate-400 text-[11px] ml-0.5">({s.starter_count}선)</span>
                        )}
                      </td>
                      <td className="px-2 py-2.5 text-center">
                        {s.goals > 0 ? (
                          <span className="text-emerald-600 font-bold">{s.goals}</span>
                        ) : (
                          <span className="text-slate-300">-</span>
                        )}
                      </td>
                      <td className="px-2 py-2.5 text-center">
                        {s.assists > 0 ? (
                          <span className="text-sky-600 font-bold">{s.assists}</span>
                        ) : (
                          <span className="text-slate-300">-</span>
                        )}
                      </td>
                      <td className={`px-2 py-2.5 text-center ${s.yellow_cards > 0 ? 'text-yellow-600 font-medium' : 'text-slate-300'}`}>
                        {s.yellow_cards || '-'}
                      </td>
                      <td className={`px-2 py-2.5 text-center ${s.red_cards > 0 ? 'text-red-500 font-medium' : 'text-slate-300'}`}>
                        {s.red_cards || '-'}
                      </td>
                      <td className="pl-2 pr-5 py-2.5 text-center text-slate-400">
                        {s.total_minutes > 0 ? s.total_minutes.toLocaleString() : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-slate-200 bg-slate-50">
                    <td className="pl-5 pr-2 py-2.5 text-[12px] text-slate-500 font-bold">합계</td>
                    <td className="px-2 py-2.5 text-[12px] text-slate-400">{data.totals.seasons}시즌</td>
                    <td className="px-2 py-2.5 text-center text-slate-800 font-black">{data.totals.appearances}</td>
                    <td className="px-2 py-2.5 text-center text-emerald-600 font-black">{data.totals.goals || '-'}</td>
                    <td className="px-2 py-2.5 text-center text-sky-600 font-black">{data.totals.assists || '-'}</td>
                    <td className="px-2 py-2.5 text-center text-yellow-600 font-bold">{data.totals.yellow_cards || '-'}</td>
                    <td className="px-2 py-2.5 text-center text-red-500 font-bold">{data.totals.red_cards || '-'}</td>
                    <td className="pl-2 pr-5 py-2.5 text-center text-slate-600 font-bold">
                      {data.totals.total_minutes > 0 ? data.totals.total_minutes.toLocaleString() : '-'}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 빈 상태 */}
      {!data && !loading && !error && (
        <div className="text-center py-20">
          <div className="text-[36px] mb-3 opacity-50">⚽</div>
          <p className="text-[14px] font-medium text-slate-500">선수 이름을 검색하세요</p>
          <p className="text-[12px] text-slate-400 mt-1">2010~2026 K리그1 등록 선수</p>
        </div>
      )}
    </div>
    </div>
  )
}

/* ── 통산 기록 아이템 ── */
function StatItem({
  label, value, color, highlight, small,
}: {
  label: string
  value: string | number
  color?: string
  highlight?: boolean
  small?: boolean
}) {
  return (
    <div className="text-center">
      <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
      <p className={`${small ? 'text-[13px]' : 'text-[18px]'} font-black leading-tight ${color ?? (highlight ? 'text-slate-800' : 'text-slate-700')}`}>
        {value}
      </p>
    </div>
  )
}
