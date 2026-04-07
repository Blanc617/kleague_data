import { useState, useRef, useEffect, useCallback } from 'react'
import { streamQuery } from '../api'
import ChatMessage from '../components/ChatMessage'
import { type SeasonRange } from '../components/SeasonSelector'
import type { Message } from '../types'

const SEASONS = Array.from({ length: 2026 - 2010 + 1 }, (_, i) => 2026 - i)


export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [season, setSeason] = useState<SeasonRange>({ from: 2025, to: 2025 })
  const [rangeMode, setRangeMode] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const userScrolledUp = useRef(false)

  const seasonLabel = season.from === season.to ? `${season.from}` : `${season.from}~${season.to}`
  const hasMessages = messages.length > 0

  // 새 메시지 추가 시 (length 증가) → 항상 아래로
  useEffect(() => {
    userScrolledUp.current = false
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  // 스트리밍 토큰 업데이트 시 → 사용자가 위로 올리지 않았을 때만
  useEffect(() => {
    if (!userScrolledUp.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  const autoResizeTextarea = useCallback(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }, [])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    autoResizeTextarea()
  }, [autoResizeTextarea])

  const handleStop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const handleSend = useCallback(async (question?: string) => {
    const q = (question ?? input).trim()
    if (!q || loading) return
    setInput('')
    setLoading(true)
    if (inputRef.current) inputRef.current.style.height = 'auto'
    inputRef.current?.focus()

    const controller = new AbortController()
    abortRef.current = controller

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: q }
    const assistantId = (Date.now() + 1).toString()
    const assistantMsg: Message = { id: assistantId, role: 'assistant', content: '', isStreaming: true }
    setMessages(prev => [...prev, userMsg, assistantMsg])

    try {
      let full = ''
      for await (const event of streamQuery(q, season.from, season.from !== season.to ? season.to : undefined, controller.signal)) {
        if (event.type === 'token') {
          full += event.content
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: full } : m))
        } else if (event.type === 'sources') {
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, sources: event.content } : m))
        } else if (event.type === 'player_sources') {
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, playerSources: event.content } : m))
        } else if (event.type === 'event_sources') {
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, eventSources: event.content } : m))
        } else if (event.type === 'error') {
          setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: `오류: ${event.content}` } : m))
        }
      }
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: `오류: ${e?.message ?? '알 수 없는 오류'}` } : m))
      }
    } finally {
      abortRef.current = null
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, isStreaming: false } : m))
      setLoading(false)
    }
  }, [input, loading, season])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    function onScroll() {
      const distFromBottom = document.documentElement.scrollHeight - window.scrollY - window.innerHeight
      userScrolledUp.current = distFromBottom > 80
    }
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  function handleFromChange(y: number) {
    if (rangeMode) {
      setSeason(prev => ({ from: y, to: Math.max(y, prev.to) }))
    } else {
      setSeason({ from: y, to: y })
    }
    setMessages([])
  }

  function handleToChange(y: number) {
    setSeason(prev => ({ from: Math.min(prev.from, y), to: y }))
    setMessages([])
  }

  function toggleRangeMode() {
    setRangeMode(v => {
      if (v) setSeason(prev => ({ from: prev.from, to: prev.from }))
      return !v
    })
    setMessages([])
  }

  return (
    <div className="flex flex-col bg-white">

      {/* ── 상단 필터 바 ─────────────────────────── */}
      <div className="shrink-0 border-b border-slate-100 flex justify-center px-8" style={{ background: 'linear-gradient(to bottom, #f8fafc, #f1f5f9)', paddingTop: '24px', paddingBottom: '24px' }}>
        <div className="w-full max-w-3xl flex items-center gap-4 flex-wrap">

          {/* 모드 탭: 단일 시즌 / 시즌 구간 */}
          <div
            className="flex items-center rounded-xl p-1 shrink-0 gap-0.5"
            style={{ background: 'rgba(15,23,42,0.07)', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.08)' }}
          >
            <button
              onClick={() => { if (rangeMode) toggleRangeMode() }}
              className="relative text-[12px] font-bold px-5 py-2 rounded-lg transition-all duration-200 shrink-0"
              style={!rangeMode ? {
                background: 'linear-gradient(135deg, #10b981, #059669)',
                color: '#fff',
                boxShadow: '0 2px 8px rgba(16,185,129,0.35)',
              } : { color: '#64748b' }}
            >
              단일 시즌
            </button>
            <button
              onClick={() => { if (!rangeMode) toggleRangeMode() }}
              className="relative text-[12px] font-bold px-5 py-2 rounded-lg transition-all duration-200 shrink-0"
              style={rangeMode ? {
                background: 'linear-gradient(135deg, #10b981, #059669)',
                color: '#fff',
                boxShadow: '0 2px 8px rgba(16,185,129,0.35)',
              } : { color: '#64748b' }}
            >
              시즌 구간
            </button>
          </div>

          {/* 구분선 */}
          <span className="h-6 w-px shrink-0" style={{ background: 'linear-gradient(to bottom, transparent, #cbd5e1, transparent)' }} />

          {/* 단일 시즌: 연도 드롭다운 하나 */}
          {!rangeMode ? (
            <div className="flex items-center gap-2.5">
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 shrink-0">시즌</span>
              <div className="relative">
                <select
                  value={season.from}
                  onChange={e => handleFromChange(Number(e.target.value))}
                  className="appearance-none cursor-pointer focus:outline-none transition-all duration-150"
                  style={{
                    background: '#fff',
                    border: '1.5px solid #e2e8f0',
                    borderRadius: '10px',
                    color: '#1e293b',
                    fontSize: '14px',
                    fontWeight: '700',
                    padding: '7px 36px 7px 14px',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                  }}
                  onFocus={e => { e.currentTarget.style.borderColor = '#10b981'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(16,185,129,0.12)' }}
                  onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.06)' }}
                >
                  {SEASONS.map(y => <option key={y} value={y}>{y}시즌</option>)}
                </select>
                <svg className="pointer-events-none absolute top-1/2 -translate-y-1/2 text-slate-400" style={{ right: '12px' }} width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </div>
            </div>
          ) : (
            /* 시즌 구간: 시작 ~ 종료 */
            <div className="flex items-center gap-3 flex-wrap">
              {/* 시작 */}
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 shrink-0">시작</span>
                <div className="relative">
                  <select
                    value={season.from}
                    onChange={e => handleFromChange(Number(e.target.value))}
                    className="appearance-none cursor-pointer focus:outline-none transition-all duration-150"
                    style={{
                      background: '#fff',
                      border: '1.5px solid #e2e8f0',
                      borderRadius: '10px',
                      color: '#1e293b',
                      fontSize: '14px',
                      fontWeight: '700',
                      padding: '7px 36px 7px 14px',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                    }}
                    onFocus={e => { e.currentTarget.style.borderColor = '#10b981'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(16,185,129,0.12)' }}
                    onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.06)' }}
                  >
                    {SEASONS.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                  <svg className="pointer-events-none absolute top-1/2 -translate-y-1/2 text-slate-400" style={{ right: '12px' }} width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </div>
              </div>

              {/* 화살표 */}
              <div className="flex items-end pb-1">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </div>

              {/* 종료 */}
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 shrink-0">종료</span>
                <div className="relative">
                  <select
                    value={season.to}
                    onChange={e => handleToChange(Number(e.target.value))}
                    className="appearance-none cursor-pointer focus:outline-none transition-all duration-150"
                    style={{
                      background: '#fff',
                      border: '1.5px solid #e2e8f0',
                      borderRadius: '10px',
                      color: '#1e293b',
                      fontSize: '14px',
                      fontWeight: '700',
                      padding: '7px 36px 7px 14px',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                    }}
                    onFocus={e => { e.currentTarget.style.borderColor = '#10b981'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(16,185,129,0.12)' }}
                    onBlur={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.06)' }}
                  >
                    {SEASONS.filter(y => y >= season.from).map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                  <svg className="pointer-events-none absolute top-1/2 -translate-y-1/2 text-slate-400" style={{ right: '12px' }} width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </div>
              </div>

              {/* N개 시즌 뱃지 */}
              {season.from !== season.to && (
                <div className="flex items-end pb-1">
                  <span
                    className="text-[11px] font-bold px-2.5 py-1 rounded-full"
                    style={{
                      background: 'linear-gradient(135deg, rgba(16,185,129,0.12), rgba(5,150,105,0.08))',
                      color: '#059669',
                      border: '1px solid rgba(16,185,129,0.25)',
                    }}
                  >
                    {season.to - season.from + 1}개 시즌
                  </span>
                </div>
              )}
            </div>
          )}

          {/* 로딩 상태 */}
          {loading && (
            <div className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-full" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)' }}>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-semibold" style={{ color: '#059669' }}>응답 생성 중</span>
            </div>
          )}

          {/* 새 대화 버튼 (메시지 있을 때) */}
          {hasMessages && !loading && (
            <button
              onClick={() => setMessages([])}
              className="ml-auto flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
              새 대화
            </button>
          )}
        </div>
      </div>

      {/* ── 메시지 영역 ───────────────────────────── */}
      <div className="flex-1">
        {!hasMessages ? (
          <div className="flex flex-col items-center px-8 pt-12 fade-in">
            <div className="flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-xl shadow-emerald-500/25 mb-5">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="white" strokeWidth="1.5" />
                  <path d="M2 12H22M12 2Q6 6 6 12Q6 18 12 22M12 2Q18 6 18 12Q18 18 12 22" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-slate-800 mb-2">무엇이든 질문하세요</h2>
              <p className="text-slate-500 leading-relaxed">
                {seasonLabel}시즌 K리그1 경기 결과, 팀 전적, 선수 기록을<br />자연어로 검색합니다
              </p>
            </div>
          </div>
        ) : (
          <div className="flex justify-center px-8 py-10">
          <div className="w-full max-w-3xl space-y-1">
            {messages.map(msg => (
              <ChatMessage key={msg.id} msg={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
          </div>
        )}
      </div>

      {/* ── 입력 영역 ──────────────────────────────── */}
      <div className="shrink-0 border-t border-slate-100 flex justify-center px-8 pb-6 pt-4">
        <div className="w-full max-w-3xl">
          <div className="relative bg-white border border-slate-200 rounded-2xl shadow-lg shadow-slate-200/60 transition-all focus-within:border-emerald-300 focus-within:shadow-emerald-100/80 focus-within:shadow-xl">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder={`${seasonLabel}시즌 경기·선수·팀 전적을 질문하세요…`}
              rows={1}
              className="w-full bg-transparent px-5 pt-4 pb-3 text-[15px] text-slate-800 placeholder-slate-400 outline-none disabled:opacity-50 resize-none leading-relaxed"
              style={{ minHeight: '56px', maxHeight: '200px' }}
            />
            <div className="flex items-center justify-between px-4 pb-4 pt-1">
              <span className="text-xs text-slate-400 hidden sm:block select-none">
                Enter 전송 · Shift+Enter 줄바꿈
              </span>
              <div className="ml-auto flex items-center gap-2">
                {loading ? (
                  <button
                    onClick={handleStop}
                    className="flex items-center gap-2 text-sm font-medium text-red-500 hover:text-red-600 px-4 py-2 rounded-xl bg-red-50 hover:bg-red-100 border border-red-200 transition-all"
                  >
                    <svg width="9" height="9" viewBox="0 0 10 10" fill="currentColor"><rect width="10" height="10" rx="2" /></svg>
                    중단
                  </button>
                ) : (
                  <button
                    onClick={() => handleSend()}
                    disabled={!input.trim()}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-200 disabled:text-slate-400 transition-all active:scale-95 shadow-sm shadow-emerald-500/30"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                      <path d="M22 2L11 13" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                      <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    전송
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
