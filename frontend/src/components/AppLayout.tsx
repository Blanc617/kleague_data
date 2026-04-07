import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { KickDataLogo } from './KickDataLogo'

const NAV_ITEMS = [
  {
    path: '/',
    label: '홈',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
        <polyline points="9 22 9 12 15 12 15 22" />
      </svg>
    ),
  },
  {
    path: '/chat',
    label: 'AI 채팅',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
      </svg>
    ),
  },
  {
    path: '/stats',
    label: '시즌 통계',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 20V10M12 20V4M6 20v-6" />
      </svg>
    ),
  },
  {
    path: '/schedule',
    label: '경기 일정',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    ),
  },
  {
    path: '/standings',
    label: '순위표',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
      </svg>
    ),
  },
  {
    path: '/player',
    label: '선수 프로필',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
  {
    path: '/analytics',
    label: '데이터 분석',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 2a10 10 0 0110 10" />
        <path d="M12 12L8 8" />
        <circle cx="12" cy="12" r="2" />
      </svg>
    ),
  },
  {
    path: '/compare',
    label: '선수 비교',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 00-3-3.87" />
        <path d="M16 3.13a4 4 0 010 7.75" />
      </svg>
    ),
  },
]

export default function AppLayout() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div className="flex flex-col min-h-screen">

      {/* ── 헤더 (브랜드 바) ─────────────────────── */}
      <header className="shrink-0 bg-slate-100 border-b border-slate-200 z-30 flex justify-center">
        <div className="w-full max-w-3xl flex items-center gap-5 px-8" style={{ paddingTop: '18px', paddingBottom: '18px' }}>
          <button onClick={() => navigate('/')} className="group">
            <KickDataLogo size={40} textSize={16} subSize={11} />
          </button>

          <div className="ml-auto flex items-center gap-2 bg-white border border-slate-200 rounded-full px-3.5 py-1.5">
            <span className="live-dot w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
            <span className="text-[11px] text-slate-500 font-semibold">2010 – 2026 K리그1</span>
          </div>
        </div>
      </header>

      {/* ── 네비게이션 바 (다크) ──────────────────── */}
      <nav className="shrink-0 z-20 shadow-lg" style={{ backgroundColor: '#2d3f55' }}>
        <div
          className="flex items-center justify-center gap-5 px-6 overflow-x-auto"
          style={{ scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}
        >
          {NAV_ITEMS.map(item => {
            const active = location.pathname === item.path
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                style={{ paddingTop: '14px', paddingBottom: '14px' }}
                className={`relative shrink-0 flex items-center gap-2 px-5 text-[13px] font-semibold transition-colors whitespace-nowrap ${
                  active
                    ? 'text-emerald-400'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {item.icon}
                {item.label}
                {active && (
                  <span className="absolute bottom-0 left-3 right-3 h-[3px] bg-emerald-400 rounded-t-full" />
                )}
              </button>
            )
          })}
        </div>
      </nav>

      {/* ── 페이지 콘텐츠 + 푸터 ──────────────────── */}
      <main className="flex-1">
        <Outlet />

        {/* ── 공통 푸터 ──────────────────────────── */}
        <footer className="flex flex-col mt-20" style={{ backgroundColor: '#2d3f55' }}>

        {/* 메인 푸터 영역 */}
        <div className="flex justify-center">
          <div className="w-full max-w-xl px-8 pt-16 pb-12">
            <div className="grid grid-cols-4 gap-8">

              {/* 브랜드 컬럼 */}
              <div className="col-span-2">
                <div className="flex items-center gap-3 mb-4">
                  <KickDataLogo size={36} textSize={14} subSize={11} dark />
                </div>
                <p className="text-[13px] text-slate-200 leading-relaxed mb-5">
                  K리그1 2010–2026 경기 데이터를 기반으로<br />
                  AI가 실시간 해설과 분석을 지원합니다.
                </p>
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg inline-flex w-fit" style={{ backgroundColor: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)' }}>
                  <span className="live-dot w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                  <span className="text-[11px] font-medium text-emerald-300">2010 – 2026 K리그1</span>
                </div>
              </div>

              {/* 메뉴 컬럼 */}
              <div>
                <p className="text-[11px] font-bold text-slate-300 uppercase tracking-widest mb-4">메뉴</p>
                <ul className="space-y-2.5">
                  {[
                    { path: '/chat',      label: 'AI 채팅' },
                    { path: '/stats',     label: '시즌 통계' },
                    { path: '/schedule',  label: '경기 일정' },
                    { path: '/standings', label: '순위표' },
                    { path: '/player',    label: '선수 프로필' },
                    { path: '/compare',   label: '선수 비교' },
                    { path: '/analytics', label: '데이터 분석' },
                  ].map(item => (
                    <li key={item.path}>
                      <button
                        onClick={() => navigate(item.path)}
                        className="text-[13px] text-slate-200 hover:text-white transition-colors duration-150"
                      >
                        {item.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>

              {/* 데이터 출처 컬럼 */}
              <div>
                <p className="text-[11px] font-bold text-slate-300 uppercase tracking-widest mb-4">데이터 출처</p>
                <ul className="space-y-2.5">
                  {[
                    'K리그 공식',
                    'FotMob',
                    'Wikipedia',
                    'Transfermarkt',
                    'Naver Sports',
                  ].map(src => (
                    <li key={src} className="flex items-center gap-2">
                      <span className="w-1 h-1 rounded-full bg-slate-400 shrink-0" />
                      <span className="text-[13px] text-slate-200">{src}</span>
                    </li>
                  ))}
                </ul>
              </div>

            </div>
          </div>
        </div>

        {/* 하단 카피라이트 바 */}
        <div className="flex justify-center" style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          <div className="w-full max-w-xl px-8 py-4 flex items-center justify-between">
            <p className="text-[11px] text-slate-300">
              본 서비스의 데이터는 참고용이며 공식 기록과 차이가 있을 수 있습니다.
            </p>
            <p className="text-[11px] text-slate-300">
              © {new Date().getFullYear()} KickData. All rights reserved.
            </p>
          </div>
        </div>

        </footer>
      </main>
    </div>
  )
}
