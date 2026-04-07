import { useState } from 'react'
import type { Message, PlayerStat, MatchEvent } from '../types'

const EVENT_ICON: Record<string, string> = {
  goal: '⚽', own_goal: '⚽', yellow_card: '🟨', red_card: '🟥', yellow_red: '🟥',
}
const EVENT_LABEL: Record<string, string> = {
  goal: '골', own_goal: '자책골', yellow_card: '경고', red_card: '퇴장', yellow_red: '경고퇴장',
}

/* ── 타이핑 애니메이션 ─────────────────────── */
function TypingDots() {
  return (
    <div className="flex items-center gap-1.5 py-1.5">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="typing-dot w-2 h-2 rounded-full bg-slate-300 inline-block"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  )
}

/* ── 인라인 마크다운 (볼드) ─────────────────── */
function formatInline(s: string): React.ReactNode {
  const parts = s.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="text-slate-900 font-semibold">{part.slice(2, -2)}</strong>
    }
    return part
  })
}

/* ── 마크다운 테이블 ──────────────────────── */
function isTableRow(line: string) {
  const t = line.trim()
  return t.startsWith('|') && t.endsWith('|') && t.includes('|')
}
function isSeparatorRow(line: string) {
  return /^\|[\s\-:|]+\|$/.test(line.trim())
}
function parseCells(line: string) {
  return line.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
}

function MarkdownTable({ rows }: { rows: string[] }) {
  const header = parseCells(rows[0])
  const hasSep = rows.length > 1 && isSeparatorRow(rows[1])
  const bodyRows = (hasSep ? rows.slice(2) : rows.slice(1)).filter(r => !isSeparatorRow(r))

  return (
    <div className="my-4 overflow-x-auto rounded-xl border border-slate-200 shadow-sm">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            {header.map((h, i) => (
              <th key={i} className="px-4 py-3 text-left text-xs font-bold text-slate-500 uppercase tracking-wider whitespace-nowrap">
                {formatInline(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, ri) => {
            const cells = parseCells(row)
            return (
              <tr key={ri} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                {cells.map((cell, ci) => (
                  <td key={ci} className="px-4 py-2.5 text-slate-700 whitespace-nowrap tabular-nums">
                    {formatInline(cell)}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/* ── 마크다운 형식 답변 렌더러 ──────────────── */
export function FormattedContent({ text }: { text: string }) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let listItems: { text: string; indent: number }[] = []
  let tableRows: string[] = []
  let listKey = 0
  let tableKey = 0

  function flushList() {
    if (listItems.length === 0) return
    elements.push(
      <ul key={`list-${listKey++}`} className="my-3 space-y-1.5">
        {listItems.map((item, i) => (
          <li
            key={i}
            className="flex items-start gap-2.5"
            style={{ marginLeft: item.indent > 0 ? `${item.indent * 20}px` : undefined }}
          >
            <span className="mt-[7px] shrink-0 w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-slate-700 text-[15px] leading-relaxed">{formatInline(item.text)}</span>
          </li>
        ))}
      </ul>
    )
    listItems = []
  }

  function flushTable() {
    if (tableRows.length === 0) return
    elements.push(<MarkdownTable key={`tbl-${tableKey++}`} rows={tableRows} />)
    tableRows = []
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    if (isTableRow(trimmed)) {
      flushList()
      tableRows.push(trimmed)
      continue
    }
    if (tableRows.length > 0) flushTable()

    const numberedMatch = trimmed.match(/^(\d+)[.)]\s+(.+)/)
    if (numberedMatch) {
      flushList()
      listItems.push({ text: numberedMatch[2], indent: 0 })
      continue
    }

    const bulletMatch = trimmed.match(/^[-•*]\s+(.+)/)
    if (bulletMatch) {
      const indent = line.search(/\S/) >= 4 ? 1 : 0
      listItems.push({ text: bulletMatch[1], indent })
      continue
    }

    const h3Match = trimmed.match(/^###\s+(.+)/)
    if (h3Match) {
      flushList()
      elements.push(
        <p key={`h3-${i}`} className="text-sm font-bold text-emerald-600 mt-5 mb-2 tracking-wide uppercase">
          {formatInline(h3Match[1])}
        </p>
      )
      continue
    }

    if (trimmed === '') {
      flushList()
      continue
    }

    flushList()
    elements.push(
      <p key={`p-${i}`} className="text-[15px] text-slate-700 leading-[1.75] my-1">
        {formatInline(trimmed)}
      </p>
    )
  }
  flushList()
  flushTable()

  return <div className="space-y-0">{elements}</div>
}

/* ── 접기/펼치기 래퍼 ──────────────────────── */
function Collapsible({
  label,
  count,
  countUnit,
  accentColor,
  children,
}: {
  label: string
  count: number
  countUnit: string
  accentColor: 'emerald' | 'sky' | 'amber'
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(false)

  const colorMap = {
    emerald: {
      dot: 'bg-emerald-400',
      label: 'text-slate-700',
      badge: 'text-emerald-600 bg-emerald-50 border-emerald-200',
      bg: 'bg-white',
      border: 'border-slate-200',
      hoverBg: 'hover:bg-slate-50',
    },
    sky: {
      dot: 'bg-sky-400',
      label: 'text-slate-700',
      badge: 'text-sky-600 bg-sky-50 border-sky-200',
      bg: 'bg-white',
      border: 'border-slate-200',
      hoverBg: 'hover:bg-slate-50',
    },
    amber: {
      dot: 'bg-amber-400',
      label: 'text-slate-700',
      badge: 'text-amber-600 bg-amber-50 border-amber-200',
      bg: 'bg-white',
      border: 'border-slate-200',
      hoverBg: 'hover:bg-slate-50',
    },
  }
  const c = colorMap[accentColor]

  return (
    <div className={`w-full mt-3 rounded-xl border ${c.border} ${c.bg} overflow-hidden shadow-sm`}>
      <button
        onClick={() => setOpen(v => !v)}
        className={`w-full flex items-center gap-3 px-4 py-3 ${c.hoverBg} transition-colors`}
      >
        <span className={`w-2 h-2 rounded-full shrink-0 ${c.dot}`} />
        <span className={`text-sm font-semibold ${c.label}`}>{label}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${c.badge}`}>
          {count}{countUnit}
        </span>
        <svg
          width="12" height="12" viewBox="0 0 10 10" fill="none"
          className={`text-slate-400 ml-auto transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        >
          <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
      {open && (
        <div className="px-3 pb-3 border-t border-slate-100 fade-in">
          {children}
        </div>
      )}
    </div>
  )
}

/* ── 경기 이벤트 소스 카드 ─────────────────── */
function EventSourcesCard({ games }: { games: NonNullable<Message['eventSources']> }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)
  if (!games || games.length === 0) return null

  return (
    <Collapsible label="경기 이벤트" count={games.length} countUnit="경기" accentColor="amber">
      <div className="space-y-1.5 pt-2">
        {games.map((g, idx) => {
          const isOpen = expandedIdx === idx
          const goals   = (g.events ?? []).filter(e => e.type === 'goal' || e.type === 'own_goal')
          const yellows = (g.events ?? []).filter(e => e.type === 'yellow_card')
          const reds    = (g.events ?? []).filter(e => e.type === 'red_card' || e.type === 'yellow_red')

          return (
            <div key={idx} className="rounded-lg bg-slate-50 border border-slate-200 overflow-hidden">
              <button
                onClick={() => setExpandedIdx(isOpen ? null : idx)}
                className="w-full flex items-center gap-3 px-3.5 py-2.5 hover:bg-slate-100 transition-colors text-left"
              >
                <span className="text-slate-400 text-xs font-mono shrink-0">{g.date}</span>
                <div className="flex items-center gap-2 flex-1 justify-center min-w-0">
                  <span className="text-slate-700 text-sm font-semibold flex-1 text-right truncate">{g.home_team}</span>
                  <span className="bg-slate-800 text-white text-xs font-bold px-2.5 py-1 rounded-lg tracking-widest shrink-0 tabular-nums">
                    {g.home_score}:{g.away_score}
                  </span>
                  <span className="text-slate-700 text-sm font-semibold flex-1 text-left truncate">{g.away_team}</span>
                </div>
                <div className="flex items-center gap-1 shrink-0 text-xs">
                  {goals.length > 0   && <span className="text-slate-400">⚽{goals.length}</span>}
                  {yellows.length > 0 && <span>🟨{yellows.length}</span>}
                  {reds.length > 0    && <span>🟥{reds.length}</span>}
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className={`text-slate-400 ml-1 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
                    <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </div>
              </button>

              {isOpen && (g.events ?? []).length > 0 && (
                <div className="border-t border-slate-200 px-3.5 py-3 space-y-2">
                  {(g.events ?? []).map((e: MatchEvent, ei: number) => (
                    <div key={ei} className="flex items-center gap-2.5 text-sm">
                      <span className="text-slate-400 font-mono text-xs w-8 text-right shrink-0">{e.minute}'</span>
                      <span className="shrink-0 text-base leading-none">{EVENT_ICON[e.type] ?? '•'}</span>
                      <span className={`font-semibold shrink-0 ${
                        e.type === 'goal' ? 'text-slate-800' :
                        e.type === 'own_goal' ? 'text-slate-500' :
                        e.type === 'yellow_card' ? 'text-amber-500' : 'text-red-500'
                      }`}>
                        {e.player}
                      </span>
                      {e.type === 'own_goal' && <span className="text-slate-400 text-xs">(자책)</span>}
                      {e.assist && <span className="text-slate-400 text-xs">← {e.assist}</span>}
                      <span className="text-slate-400 text-xs ml-auto">{EVENT_LABEL[e.type]}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Collapsible>
  )
}

/* ── 참조 경기 소스 카드 ───────────────────── */
function SourcesCard({ sources }: { sources: Message['sources'] }) {
  if (!sources || sources.length === 0) return null

  return (
    <Collapsible label="참조 경기" count={sources.length} countUnit="건" accentColor="emerald">
      <div className="space-y-1.5 pt-2">
        {sources.map((s, i) => (
          <div key={i} className="px-3.5 py-2.5 rounded-lg bg-slate-50 border border-slate-200">
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-xs font-mono shrink-0">{s.date}</span>
              {s.round != null && (
                <span className="text-slate-400 text-xs shrink-0 bg-slate-200 px-1.5 py-0.5 rounded">R{s.round}</span>
              )}
              <div className="flex items-center gap-1.5 flex-1 justify-center min-w-0">
                <span className="text-slate-700 text-sm font-medium truncate">{s.home_team}</span>
                <span className="bg-slate-800 text-white text-xs font-bold px-2.5 py-0.5 rounded-lg tracking-widest shrink-0 tabular-nums">
                  {s.home_score}:{s.away_score}
                </span>
                <span className="text-slate-700 text-sm font-medium truncate">{s.away_team}</span>
              </div>
              {s.venue && (
                <span className="text-slate-400 text-xs shrink-0 truncate max-w-[90px]" title={s.venue}>{s.venue}</span>
              )}
            </div>
            {s.attendance != null && s.attendance > 0 && (
              <div className="mt-1.5 flex items-center gap-1.5">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-slate-400">
                  <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 7a4 4 0 100 8 4 4 0 000-8zM23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
                </svg>
                <span className="text-xs text-violet-500 font-semibold tabular-nums">
                  {s.attendance.toLocaleString()}명
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
    </Collapsible>
  )
}

/* ── 선수 기록 소스 카드 ───────────────────── */
const POS_STYLE: Record<string, string> = {
  FW: 'text-orange-500 bg-orange-50 border-orange-200',
  MF: 'text-sky-500 bg-sky-50 border-sky-200',
  DF: 'text-emerald-500 bg-emerald-50 border-emerald-200',
  GK: 'text-violet-500 bg-violet-50 border-violet-200',
}

function PlayerSourcesCard({ players }: { players: PlayerStat[] }) {
  if (!players || players.length === 0) return null

  return (
    <Collapsible label="선수 기록" count={players.length} countUnit="명" accentColor="sky">
      <div className="space-y-1.5 pt-2">
        {players.map((p, i) => (
          <div key={i} className="flex items-center gap-3 px-3.5 py-3 rounded-lg bg-slate-50 border border-slate-200">
            <span className="text-xs text-slate-400 font-mono w-5 text-center shrink-0 tabular-nums">{i + 1}</span>
            {p.position && (
              <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded border shrink-0 ${POS_STYLE[p.position] ?? 'text-slate-500 bg-slate-100 border-slate-200'}`}>
                {p.position}
              </span>
            )}
            <span className="text-slate-800 text-sm font-semibold flex-1 min-w-0 truncate">{p.player_name}</span>
            <span className="text-slate-400 text-xs shrink-0">{p.team}</span>
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-slate-800 text-sm font-bold tabular-nums">
                {p.goals}<span className="text-slate-400 text-xs font-normal ml-0.5">G</span>
              </span>
              <span className="text-slate-500 text-sm tabular-nums">
                {p.assists}<span className="text-slate-400 text-xs ml-0.5">A</span>
              </span>
            </div>
          </div>
        ))}
      </div>
    </Collapsible>
  )
}

/* ── 메인 채팅 메시지 ─────────────────────── */
export default function ChatMessage({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  const isEmpty = !msg.content && msg.isStreaming

  if (isUser) {
    return (
      <div className="flex justify-end items-end gap-2 py-2 msg-enter">
        <div className="max-w-[75%]">
          <div className="relative bg-gradient-to-br from-emerald-500 to-emerald-700 text-white px-5 py-3.5 rounded-2xl rounded-tr-sm text-[15px] leading-relaxed shadow-lg shadow-emerald-600/30 ring-1 ring-white/10">
            {/* 내부 하이라이트 */}
            <div className="absolute inset-0 rounded-2xl rounded-tr-sm bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />
            <span className="relative whitespace-pre-wrap">{msg.content}</span>
          </div>
        </div>
        {/* 유저 아바타 */}
        <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center shadow-sm mb-0.5">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
          </svg>
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3 py-3 msg-enter">
      {/* AI 아바타 */}
      <div className="shrink-0 mt-1">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-md shadow-emerald-500/25 text-[17px] leading-none">
          ⚽
        </div>
      </div>

      <div className="flex-1 min-w-0">
        {/* 발신자 이름 */}
        <p className="text-xs font-semibold text-slate-500 mb-2">Kick Data AI</p>

        {/* 컨텐츠 */}
        <div className="text-[15px] leading-relaxed text-slate-700">
          {isEmpty ? (
            <TypingDots />
          ) : (
            <>
              <FormattedContent text={msg.content} />
              {msg.isStreaming && (
                <span
                  className="inline-block w-[2px] h-[16px] bg-emerald-400 ml-0.5 align-middle rounded-full"
                  style={{ animation: 'blink 1s step-end infinite' }}
                />
              )}
            </>
          )}
        </div>

        {/* 소스 카드 */}
        {!msg.isStreaming && (
          <div className="mt-1">
            <EventSourcesCard games={msg.eventSources ?? []} />
            <SourcesCard sources={msg.sources} />
            <PlayerSourcesCard players={msg.playerSources ?? []} />
          </div>
        )}
      </div>
    </div>
  )
}
