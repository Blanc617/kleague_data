import { useState, useRef, useCallback } from 'react'
import { streamQuery } from '../api'
import { FormattedContent } from '../components/ChatMessage'

const K1_TEAMS = [
  '전북', '울산', '포항', '서울', '수원FC', '제주', '인천',
  '광주', '대구', '강원', '김천', '대전', '성남', '수원', '전남', '부산',
]

const SEASONS = Array.from({ length: 2026 - 2010 + 1 }, (_, i) => 2026 - i)

function Chevron() {
  return (
    <svg
      className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400"
      width="13" height="13" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  )
}

export default function BriefingPage() {
  const [teamA, setTeamA] = useState('전북')
  const [teamB, setTeamB] = useState('울산')
  const [season, setSeason] = useState(2025)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const sameTeam = teamA === teamB

  const handleSwap = useCallback(() => {
    setTeamA(teamB)
    setTeamB(teamA)
    setResult('')
  }, [teamA, teamB])

  const handleStop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const handleGenerate = useCallback(async () => {
    if (sameTeam || loading) return

    const question = `${teamA} vs ${teamB} ${season}시즌 경기 전 브리핑 시트`

    setResult('')
    setLoading(true)
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      let full = ''
      for await (const event of streamQuery(question, season, undefined, controller.signal)) {
        if (event.type === 'token') {
          full += event.content
          setResult(full)
        }
      }
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        setResult(`오류: ${e?.message ?? '알 수 없는 오류'}`)
      }
    } finally {
      abortRef.current = null
      setLoading(false)
      setStreaming(false)
    }
  }, [teamA, teamB, season, sameTeam, loading])

  const selectClass =
    'w-full appearance-none bg-white border border-slate-200 text-slate-800 ' +
    'text-[15px] font-bold px-4 py-3 pr-10 rounded-xl cursor-pointer ' +
    'hover:border-violet-400 focus:outline-none focus:border-violet-500 transition-all'

  return (
    <div className="min-h-full bg-main flex justify-center px-8 py-10">

      <div className="w-full max-w-2xl">

        {/* ── 팀 선택 패널 ── */}
        <div className="bg-white/80 border border-slate-200 rounded-2xl p-7 mb-6">

          {/* 시즌 선택 */}
          <div className="flex items-center justify-between mb-5">
            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">시즌</p>
            <div className="relative">
              <select
                value={season}
                onChange={e => { setSeason(Number(e.target.value)); setResult('') }}
                className="appearance-none bg-white border border-slate-200 text-slate-800 text-[13px] font-bold px-3 py-2 pr-8 rounded-xl cursor-pointer hover:border-violet-400 focus:outline-none focus:border-violet-500 transition-all"
              >
                {SEASONS.map(y => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              <Chevron />
            </div>
          </div>

          {/* 팀 선택 행 */}
          <div className="flex items-center gap-3">

            {/* 팀 A */}
            <div className="flex-1">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 px-1">홈팀</p>
              <div className="relative">
                <select
                  value={teamA}
                  onChange={e => { setTeamA(e.target.value); setResult('') }}
                  className={selectClass}
                >
                  {K1_TEAMS.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <Chevron />
              </div>
            </div>

            {/* vs + swap */}
            <div className="flex flex-col items-center gap-1.5 pt-5 shrink-0">
              <span className="text-[13px] font-black text-slate-500">vs</span>
              <button
                onClick={handleSwap}
                title="팀 순서 바꾸기"
                className="w-7 h-7 flex items-center justify-center rounded-lg bg-slate-100 border border-slate-300 text-slate-500 hover:text-slate-700 hover:border-slate-400 transition-all active:scale-90"
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4" />
                </svg>
              </button>
            </div>

            {/* 팀 B */}
            <div className="flex-1">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 px-1">원정팀</p>
              <div className="relative">
                <select
                  value={teamB}
                  onChange={e => { setTeamB(e.target.value); setResult('') }}
                  className={`${selectClass} ${sameTeam ? 'border-red-400' : ''}`}
                >
                  {K1_TEAMS.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <Chevron />
              </div>
            </div>
          </div>

          {sameTeam && (
            <p className="text-[11px] text-red-400 mt-2 px-1">같은 팀은 선택할 수 없습니다.</p>
          )}

          {/* 생성 버튼 */}
          <button
            onClick={loading ? handleStop : handleGenerate}
            disabled={sameTeam}
            className={`w-full mt-5 py-3 rounded-xl font-bold text-[14px] transition-all active:scale-[0.98] flex items-center justify-center gap-2
              ${loading
                ? 'bg-red-600 hover:bg-red-500 text-white'
                : sameTeam
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-500/20'
              }`}
          >
            {loading ? (
              <>
                <svg width="14" height="14" viewBox="0 0 10 10" fill="white"><rect width="10" height="10" rx="2" /></svg>
                생성 중단
              </>
            ) : (
              <>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
                {teamA} vs {teamB} 브리핑 생성
              </>
            )}
          </button>
        </div>

        {/* ── 결과 영역 ── */}
        {(result || streaming) && (
          <div className="bg-white/80 border border-slate-200 rounded-2xl p-7 fade-in">

            {/* 결과 헤더 */}
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-violet-400" />
                <span className="text-[12px] font-bold text-slate-700">
                  {teamA} vs {teamB} — {season}시즌
                </span>
              </div>
              {streaming && (
                <div className="flex items-center gap-1.5 text-[11px] text-violet-500">
                  <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                  생성 중...
                </div>
              )}
              {!streaming && result && (
                <button
                  onClick={() => navigator.clipboard?.writeText(result)}
                  className="text-[11px] text-slate-500 hover:text-slate-700 flex items-center gap-1 px-2.5 py-1.5 rounded-lg hover:bg-slate-100 transition-all"
                  title="결과 복사"
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                  </svg>
                  복사
                </button>
              )}
            </div>

            {/* 마크다운 렌더링 */}
            <div className="text-slate-700 text-[14px] leading-relaxed">
              <FormattedContent text={result} />
              {streaming && (
                <span
                  className="inline-block w-[2px] h-[15px] bg-violet-400 ml-1 align-middle rounded-full"
                  style={{ animation: 'blink 1s step-end infinite' }}
                />
              )}
            </div>
          </div>
        )}

        {/* ── 빈 상태 안내 ── */}
        {!result && !streaming && (
          <div className="flex flex-col items-center justify-center py-16 text-center fade-in">
            <div className="w-16 h-16 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mb-4">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
            </div>
            <p className="text-[15px] font-bold text-slate-700 mb-1">두 팀을 선택하고 브리핑을 생성하세요</p>
            <p className="text-[12px] text-slate-500 leading-relaxed max-w-xs">
              순위·폼·홈원정 성적·주요 득점자·선제골 승률·맞대결 전적을<br />한 페이지로 정리합니다
            </p>
          </div>
        )}

      </div>
    </div>
  )
}
