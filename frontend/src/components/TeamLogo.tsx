// 팀 이름(한국어) → 로고 파일명 매핑
const TEAM_LOGO_MAP: Record<string, string> = {
  '전북': 'jeonbuk',
  '전북현대': 'jeonbuk',
  '울산': 'ulsan',
  '울산HD': 'ulsan',
  '포항': 'pohang',
  '포항스틸러스': 'pohang',
  '서울': 'seoul',
  'FC서울': 'seoul',
  '수원FC': 'suwonfc',
  '제주': 'jeju',
  '제주유나이티드': 'jeju',
  '인천': 'incheon',
  '인천유나이티드': 'incheon',
  '광주': 'gwangju',
  '광주FC': 'gwangju',
  '대구': 'daegu',
  '대구FC': 'daegu',
  '강원': 'gangwon',
  '강원FC': 'gangwon',
  '김천': 'gimcheon',
  '김천상무': 'gimcheon',
  '대전': 'daejeon',
  '대전시티즌': 'daejeon',
  '성남': 'seongnam',
  '성남FC': 'seongnam',
  '수원': 'suwon',
  '수원삼성': 'suwon',
  '전남': 'jeonnam',
  '전남드래곤즈': 'jeonnam',
  '부산': 'busan',
  '부산아이파크': 'busan',
  '안양': 'anyang',
  'FC안양': 'anyang',
}

// 팀 색상 (로고 없을 때 폴백)
const TEAM_COLORS: Record<string, string> = {
  '전북': '#F5C518',
  '울산': '#005BAC',
  '포항': '#C8102E',
  '서울': '#CC0000',
  '수원FC': '#003DA5',
  '제주': '#FF6B00',
  '인천': '#003DA5',
  '광주': '#FFD700',
  '대구': '#00A3E0',
  '강원': '#2E7D32',
  '김천': '#1565C0',
  '대전': '#6A0DAD',
  '성남': '#1A1A1A',
  '수원': '#004B87',
  '전남': '#0D47A1',
  '부산': '#8B0000',
  '안양': '#0057A8',
}

function getLogoKey(teamName: string): string | null {
  // 정확 매핑
  if (TEAM_LOGO_MAP[teamName]) return TEAM_LOGO_MAP[teamName]
  // 포함 매핑
  for (const [key, val] of Object.entries(TEAM_LOGO_MAP)) {
    if (teamName.includes(key) || key.includes(teamName)) return val
  }
  return null
}

function getTeamColor(teamName: string): string {
  for (const [key, color] of Object.entries(TEAM_COLORS)) {
    if (teamName.includes(key) || key.includes(teamName)) return color
  }
  return '#4B5563'
}

function getInitials(teamName: string): string {
  if (teamName.length <= 2) return teamName
  if (teamName.startsWith('FC') || teamName.startsWith('fc')) return 'FC'
  return teamName.slice(0, 2)
}

interface TeamLogoProps {
  team: string
  size?: number
  className?: string
}

export default function TeamLogo({ team, size = 24, className = '' }: TeamLogoProps) {
  const key = getLogoKey(team)

  if (key) {
    return (
      <img
        src={`/logos/${key}.png`}
        alt={team}
        width={size}
        height={size}
        className={`object-contain shrink-0 ${className}`}
        onError={(e) => {
          // 로고 로드 실패 시 폴백 배지로 교체
          const target = e.currentTarget as HTMLImageElement
          target.style.display = 'none'
          const parent = target.parentElement
          if (parent) {
            const badge = document.createElement('span')
            badge.style.cssText = `
              display:inline-flex;align-items:center;justify-content:center;
              width:${size}px;height:${size}px;border-radius:50%;
              background:${getTeamColor(team)};color:#fff;
              font-size:${Math.floor(size * 0.42)}px;font-weight:900;
              flex-shrink:0;
            `
            badge.textContent = getInitials(team)
            parent.insertBefore(badge, target)
          }
        }}
      />
    )
  }

  // 로고 없으면 색상 배지
  const color = getTeamColor(team)
  const fs = Math.floor(size * 0.42)
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full shrink-0 text-white font-black ${className}`}
      style={{ width: size, height: size, background: color, fontSize: fs }}
    >
      {getInitials(team)}
    </span>
  )
}
