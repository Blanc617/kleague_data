interface Props {
  size?: number
  className?: string
}

/** 킥 동작 실루엣 + 데이터 바 로고마크 */
export function KickDataMark({ size = 40, className = '' }: Props) {
  const inner = Math.round(size * 0.56)
  return (
    <div
      className={`bg-gradient-to-br from-emerald-400 to-emerald-600 rounded-xl flex items-center justify-center shrink-0 shadow-md shadow-emerald-500/25 ${className}`}
      style={{ width: size, height: size }}
    >
      <svg width={inner} height={inner} viewBox="0 0 24 24" fill="none">
        {/* ── 데이터 바 (왼쪽, 오름차순) ── */}
        <rect x="1"   y="19"   width="2.5" height="4.5"  rx="1.2" fill="white" opacity="0.55" />
        <rect x="4.5" y="15.5" width="2.5" height="8"    rx="1.2" fill="white" opacity="0.72" />
        <rect x="8"   y="11.5" width="2.5" height="12"   rx="1.2" fill="white" opacity="0.90" />

        {/* ── 킥 실루엣 (오른쪽) ── */}
        {/* 머리 */}
        <circle cx="19" cy="3.5" r="2.1" fill="white" />
        {/* 상체 */}
        <line x1="19" y1="5.6" x2="18" y2="9.8"
          stroke="white" strokeWidth="1.9" strokeLinecap="round" />
        {/* 지지 다리: 엉덩이 → 무릎 → 발 */}
        <path d="M18 9.8 L16.5 15.5 L14.5 21.5"
          stroke="white" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
        {/* 킥 다리: 허벅지(뒤) → 무릎 → 종아리(앞으로 뻗음) */}
        <path d="M18 9.8 L13.5 13 L22.5 10.5"
          stroke="white" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  )
}

/** 텍스트 포함 풀 로고 */
export function KickDataLogo({
  size = 40,
  textSize = 16,
  subSize = 11,
  dark = false,
  className = '',
}: {
  size?: number
  textSize?: number
  subSize?: number
  dark?: boolean
  className?: string
}) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <KickDataMark size={size} />
      <div className="text-left">
        <p
          className="font-black leading-none tracking-tight"
          style={{ fontSize: textSize, color: dark ? '#fff' : '#1e293b' }}
        >
          Kick<span style={{ color: '#10b981' }}>Data</span>
        </p>
        <p
          className="mt-0.5 font-medium"
          style={{ fontSize: subSize, color: dark ? '#94a3b8' : '#94a3b8' }}
        >
          K League 1 Analytics
        </p>
      </div>
    </div>
  )
}
