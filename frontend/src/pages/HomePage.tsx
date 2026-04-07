import { useNavigate } from 'react-router-dom'
import { useFavorites } from '../hooks/useFavorites'

const MENU = [
  {
    path: '/chat',
    label: 'AI 채팅',
    desc: '자연어로 경기·선수·팀 전적 질문',
    color: 'emerald',
    border: 'hover:border-emerald-300',
    shadow: 'hover:shadow-emerald-500/10',
    iconColor: '#10b981',
    bgColor: 'rgba(16,185,129,0.08)',
    activeBg: 'rgba(16,185,129,0.14)',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
      </svg>
    ),
  },
  {
    path: '/stats',
    label: '시즌 통계',
    desc: '팀 성적·득점 순위 연도별 확인',
    color: 'sky',
    border: 'hover:border-sky-300',
    shadow: 'hover:shadow-sky-500/10',
    iconColor: '#0ea5e9',
    bgColor: 'rgba(14,165,233,0.08)',
    activeBg: 'rgba(14,165,233,0.14)',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 20V10M12 20V4M6 20v-6" />
      </svg>
    ),
  },
  {
    path: '/schedule',
    label: '경기 일정',
    desc: '2010~2026 시즌별 경기 결과 조회',
    color: 'orange',
    border: 'hover:border-orange-300',
    shadow: 'hover:shadow-orange-500/10',
    iconColor: '#f97316',
    bgColor: 'rgba(249,115,22,0.08)',
    activeBg: 'rgba(249,115,22,0.14)',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    ),
  },
  {
    path: '/standings',
    label: '역대 순위표',
    desc: '2013~2026 시즌별 최종 순위 조회',
    color: 'amber',
    border: 'hover:border-amber-300',
    shadow: 'hover:shadow-amber-500/10',
    iconColor: '#f59e0b',
    bgColor: 'rgba(245,158,11,0.08)',
    activeBg: 'rgba(245,158,11,0.14)',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
      </svg>
    ),
  },
  {
    path: '/player',
    label: '선수 프로필',
    desc: '커리어 기록·출장·득점·도움 조회',
    color: 'rose',
    border: 'hover:border-rose-300',
    shadow: 'hover:shadow-rose-500/10',
    iconColor: '#f43f5e',
    bgColor: 'rgba(244,63,94,0.08)',
    activeBg: 'rgba(244,63,94,0.14)',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
  {
    path: '/analytics',
    label: '데이터 분석',
    desc: '팀 폼 히트맵·득점 패턴·순위 흐름',
    color: 'teal',
    border: 'hover:border-teal-300',
    shadow: 'hover:shadow-teal-500/10',
    iconColor: '#14b8a6',
    bgColor: 'rgba(20,184,166,0.08)',
    activeBg: 'rgba(20,184,166,0.14)',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
  },
  {
    path: '/compare',
    label: '선수 비교',
    desc: '두 선수 커리어 나란히 비교·AI 분석',
    color: 'indigo',
    border: 'hover:border-indigo-300',
    shadow: 'hover:shadow-indigo-500/10',
    iconColor: '#6366f1',
    bgColor: 'rgba(99,102,241,0.08)',
    activeBg: 'rgba(99,102,241,0.14)',
    icon: (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 00-3-3.87" />
        <path d="M16 3.13a4 4 0 010 7.75" />
      </svg>
    ),
  },
]

export default function HomePage() {
  const navigate = useNavigate()
  const { favorites, toggle } = useFavorites()

  return (
    <div className="h-full bg-main flex flex-col items-center justify-start px-6 pt-8 pb-5 overflow-hidden">
      <div className="fade-in w-full max-w-2xl flex flex-col gap-4">

        {/* 인트로 */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1">K League 1 · 2010 – 2026</p>
            <h2 className="text-[17px] font-black text-slate-800 leading-snug">
              무엇을 확인할까요?
            </h2>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-slate-200 shadow-sm">
            <span className="live-dot w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
            <span className="text-[11px] font-semibold text-slate-500">데이터 준비됨</span>
          </div>
        </div>

        {/* 즐겨찾기 */}
        {favorites.length > 0 && (
          <div className="bg-white/70 border border-slate-200 rounded-xl px-4 py-3">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 flex items-center gap-1.5">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" stroke="none" className="text-amber-400">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
              즐겨찾기
            </p>
            <div className="flex flex-wrap gap-1.5">
              {favorites
                .slice()
                .sort((a, b) => b.addedAt - a.addedAt)
                .map(f => (
                  <div
                    key={`${f.type}-${f.name}`}
                    className="flex items-center gap-0 bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm hover:shadow transition-shadow"
                  >
                    <button
                      onClick={() =>
                        f.type === 'team'
                          ? navigate(`/stats?team=${encodeURIComponent(f.name)}`)
                          : navigate(`/player?name=${encodeURIComponent(f.name)}`)
                      }
                      className="flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-slate-50 transition-colors"
                    >
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                        f.type === 'team' ? 'bg-emerald-100 text-emerald-700' : 'bg-sky-100 text-sky-700'
                      }`}>
                        {f.type === 'team' ? '팀' : '선수'}
                      </span>
                      <span className="text-[12px] font-semibold text-slate-700">{f.name}</span>
                    </button>
                    <button
                      onClick={() => toggle(f.type, f.name)}
                      className="px-2 py-1.5 text-slate-200 hover:text-rose-400 transition-colors border-l border-slate-100"
                      title="즐겨찾기 삭제"
                    >
                      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                        <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* 2×4 메뉴 그리드 */}
        <div className="grid grid-cols-2 gap-2">
          {MENU.map(item => (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`group flex items-center gap-3 bg-white/80 border border-slate-200 ${item.border} hover:bg-white rounded-xl px-4 py-3 transition-all duration-150 ${item.shadow} hover:shadow-md text-left`}
            >
              <div
                className="w-9 h-9 shrink-0 rounded-lg flex items-center justify-center transition-colors duration-150"
                style={{
                  color: item.iconColor,
                  background: item.bgColor,
                  border: `1px solid ${item.iconColor}22`,
                }}
              >
                {item.icon}
              </div>
              <div className="min-w-0">
                <p className="text-[13px] font-bold text-slate-800 leading-tight truncate"
                  style={{ transition: 'color .15s' }}
                  onMouseEnter={e => (e.currentTarget.style.color = item.iconColor)}
                  onMouseLeave={e => (e.currentTarget.style.color = '')}
                >
                  {item.label}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5 leading-tight truncate">{item.desc}</p>
              </div>
            </button>
          ))}
        </div>

      </div>
    </div>
  )
}
