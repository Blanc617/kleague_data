import type { TeamStats } from '../types'

const RESULT_CFG = {
  W: { dot: 'bg-emerald-500', badge: 'text-emerald-700 bg-emerald-50 border border-emerald-100' },
  D: { dot: 'bg-amber-400',   badge: 'text-amber-700 bg-amber-50 border border-amber-100' },
  L: { dot: 'bg-red-400',     badge: 'text-red-700 bg-red-50 border border-red-100' },
}

function ProgressBar({ rate, color = 'bg-emerald-500' }: { rate: number; color?: string }) {
  return (
    <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
      <div
        className={`h-full rounded-full progress-bar ${color}`}
        style={{ '--target-width': `${Math.min(100, Math.max(0, rate))}%` } as React.CSSProperties}
      />
    </div>
  )
}

function StatGroup({ label, win, draw, lose, gf, ga }: {
  label: string; win: number; draw: number; lose: number; gf?: number; ga?: number
}) {
  const games = win + draw + lose
  const rate = games > 0 ? Math.round((win / games) * 100) : 0
  return (
    <div className="text-center">
      <p className="text-[10px] font-semibold text-slate-400 mb-2">{label}</p>
      <div className="flex items-baseline justify-center gap-1 mb-1.5">
        <span className="text-[16px] font-bold text-emerald-600 tabular-nums">{win}</span>
        <span className="text-[10px] text-slate-400">승</span>
        <span className="text-[16px] font-bold text-slate-400 tabular-nums ml-1">{draw}</span>
        <span className="text-[10px] text-slate-400">무</span>
        <span className="text-[16px] font-bold text-slate-500 tabular-nums ml-1">{lose}</span>
        <span className="text-[10px] text-slate-400">패</span>
      </div>
      <ProgressBar rate={rate} />
      <div className="flex justify-center items-center gap-2 mt-1">
        <span className="text-[11px] font-semibold text-emerald-600">{rate}%</span>
        {gf !== undefined && ga !== undefined && (
          <span className="text-[10px] text-slate-400">{gf}득 {ga}실</span>
        )}
      </div>
    </div>
  )
}

export default function StatsCard({ stats }: { stats: TeamStats }) {
  const { total } = stats
  const gdColor = total.gd > 0 ? 'text-emerald-600' : total.gd < 0 ? 'text-red-500' : 'text-slate-400'
  const gdText  = total.gd > 0 ? `+${total.gd}` : String(total.gd)

  return (
    <div>
      {/* 팀 헤더 */}
      <div className="px-4 py-4 border-b border-slate-100">
        <div className="flex items-start justify-between mb-3">
          <div>
            <p className="text-[10px] font-semibold text-emerald-600 uppercase tracking-widest mb-1">
              K LEAGUE 1 · {stats.season_label}
            </p>
            <h3 className="text-[20px] font-bold text-slate-900 leading-none">{stats.team}</h3>
          </div>
          <div className="text-right">
            <p className="text-[28px] font-bold text-emerald-600 leading-none tabular-nums">{total.win_rate}%</p>
            <p className="text-[10px] text-slate-400 mt-0.5">승률</p>
          </div>
        </div>
        <ProgressBar rate={total.win_rate} />
      </div>

      {/* 핵심 지표 */}
      <div className="grid grid-cols-4 divide-x divide-slate-100 border-b border-slate-100">
        {[
          { label: '승점', value: total.points, sub: `${total.games}경기`, color: 'text-slate-900' },
          { label: '득점', value: total.gf, sub: `경기당 ${total.games > 0 ? (total.gf / total.games).toFixed(1) : 0}`, color: 'text-emerald-600' },
          { label: '실점', value: total.ga, sub: `경기당 ${total.games > 0 ? (total.ga / total.games).toFixed(1) : 0}`, color: 'text-red-500' },
          { label: '득실차', value: gdText, sub: `${total.gf}득 ${total.ga}실`, color: gdColor },
        ].map(item => (
          <div key={item.label} className="px-3 py-3 text-center">
            <p className="text-[10px] text-slate-400 mb-1">{item.label}</p>
            <p className={`text-[19px] font-bold tabular-nums leading-none ${item.color}`}>{item.value}</p>
            <p className="text-[9px] text-slate-400 mt-0.5">{item.sub}</p>
          </div>
        ))}
      </div>

      {/* 홈/원정 분석 */}
      <div className="px-4 py-4 grid grid-cols-3 gap-4 border-b border-slate-100">
        <StatGroup label="전체" win={total.win} draw={total.draw} lose={total.lose} />
        <StatGroup label="홈" win={stats.home.win} draw={stats.home.draw} lose={stats.home.lose} gf={stats.home.gf} ga={stats.home.ga} />
        <StatGroup label="원정" win={stats.away.win} draw={stats.away.draw} lose={stats.away.lose} gf={stats.away.gf} ga={stats.away.ga} />
      </div>

      {/* 홈 관중 */}
      {stats.home_attendance && (
        <div className="px-4 py-4 border-b border-slate-100">
          <p className="text-[10px] font-semibold text-slate-400 mb-2.5">홈 관중</p>
          <div className="grid grid-cols-3 gap-3 mb-2.5">
            {[
              { label: '평균', value: stats.home_attendance.avg.toLocaleString(), unit: '명/경기', color: 'text-violet-600' },
              { label: '최다', value: stats.home_attendance.max.toLocaleString(), unit: '명', color: 'text-violet-600' },
              { label: '총 관중', value: `${(stats.home_attendance.total / 10000).toFixed(1)}만`, unit: `${stats.home_attendance.games}경기`, color: 'text-violet-600' },
            ].map(item => (
              <div key={item.label} className="bg-violet-50 rounded-lg px-3 py-2.5 text-center">
                <p className="text-[9px] text-slate-400 mb-1">{item.label}</p>
                <p className={`text-[16px] font-bold tabular-nums ${item.color}`}>{item.value}</p>
                <p className="text-[9px] text-slate-400 mt-0.5">{item.unit}</p>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 bg-violet-50 rounded-lg px-3 py-2">
            <span className="text-[9px] font-semibold text-violet-500 shrink-0">최다 관중</span>
            <span className="text-[11px] text-slate-600 flex-1 min-w-0 truncate">
              {stats.home_attendance.best_game.date} vs {stats.home_attendance.best_game.opponent}
              <span className="text-slate-400 ml-1">({stats.home_attendance.best_game.score})</span>
            </span>
            <span className="text-[12px] font-bold text-violet-600 shrink-0">
              {stats.home_attendance.best_game.attendance.toLocaleString()}명
            </span>
          </div>
        </div>
      )}

      {/* 최근 경기 */}
      {stats.recent?.length > 0 && (
        <div className="px-4 py-4">
          <p className="text-[10px] font-semibold text-slate-400 mb-2.5">최근 {stats.recent.length}경기</p>
          {/* 결과 폼 바 */}
          <div className="flex gap-1 mb-3">
            {stats.recent.map((r, i) => (
              <div
                key={i}
                title={`${r.date} ${r.home_team} ${r.home_score}-${r.away_score} ${r.away_team}`}
                className={`flex-1 h-1.5 rounded-full ${RESULT_CFG[r.result].dot}`}
              />
            ))}
          </div>
          <div className="space-y-0.5">
            {stats.recent.map((r, i) => (
              <div
                key={i}
                className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-50 transition-colors"
              >
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md shrink-0 ${RESULT_CFG[r.result].badge}`}>
                  {r.result}
                </span>
                <span className={`text-[10px] font-semibold shrink-0 w-8 ${r.venue === '홈' ? 'text-emerald-500' : 'text-slate-400'}`}>
                  {r.venue}
                </span>
                <div className="flex-1 min-w-0 flex items-center gap-1.5">
                  {stats.season !== stats.season_to && r.season && (
                    <span className="text-[9px] font-semibold px-1 py-0.5 rounded bg-slate-100 text-slate-500 shrink-0">{r.season}</span>
                  )}
                  <span className="text-[10px] text-slate-400 font-mono shrink-0">{r.date}</span>
                  <span className="text-[11px] text-slate-700 truncate">
                    {r.home_team} <span className="text-slate-400 font-semibold">{r.home_score}:{r.away_score}</span> {r.away_team}
                  </span>
                </div>
                {r.stadium && (
                  <span className="text-[9px] text-slate-400 shrink-0 truncate max-w-[80px]">{r.stadium}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
