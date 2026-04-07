const SEASONS = Array.from({ length: 2026 - 2010 + 1 }, (_, i) => 2026 - i)

export interface SeasonRange {
  from: number
  to: number
}

interface Props {
  value: SeasonRange
  onChange: (range: SeasonRange) => void
  theme?: 'light' | 'dark'
}

const selectStyle = {
  background: '#fff',
  border: '1.5px solid #e2e8f0',
  borderRadius: '10px',
  color: '#1e293b',
  fontSize: '14px',
  fontWeight: '700',
  padding: '7px 36px 7px 14px',
  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
} as const

function SelectDropdown({
  value,
  onChange,
  options,
}: {
  value: number
  onChange: (y: number) => void
  options: number[]
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="appearance-none cursor-pointer focus:outline-none transition-all duration-150"
        style={selectStyle}
        onFocus={e => {
          e.currentTarget.style.borderColor = '#10b981'
          e.currentTarget.style.boxShadow = '0 0 0 3px rgba(16,185,129,0.12)'
        }}
        onBlur={e => {
          e.currentTarget.style.borderColor = '#e2e8f0'
          e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.06)'
        }}
      >
        {options.map(y => (
          <option key={y} value={y}>{y}</option>
        ))}
      </select>
      <svg
        className="pointer-events-none absolute top-1/2 -translate-y-1/2 text-slate-400"
        style={{ right: '12px' }}
        width="11" height="11" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </div>
  )
}

function Label({ text }: { text: string }) {
  return (
    <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 shrink-0">
      {text}
    </span>
  )
}

export default function SeasonSelector({ value, onChange }: Props) {
  const rangeMode = value.from !== value.to

  function handleFromChange(y: number) {
    if (rangeMode) {
      onChange({ from: y, to: Math.max(y, value.to) })
    } else {
      onChange({ from: y, to: y })
    }
  }

  function handleToChange(y: number) {
    onChange({ from: Math.min(value.from, y), to: y })
  }

  function enableSingle() {
    if (rangeMode) onChange({ from: value.from, to: value.from })
  }

  function enableRange() {
    if (!rangeMode) onChange({ from: value.from, to: value.from })
  }

  const tabBase = 'relative text-[12px] font-bold px-5 py-2 rounded-lg transition-all duration-200 shrink-0'
  const tabActive = {
    background: 'linear-gradient(135deg, #10b981, #059669)',
    color: '#fff',
    boxShadow: '0 2px 8px rgba(16,185,129,0.35)',
  }
  const tabInactive = { color: '#64748b' }

  return (
    <div className="flex items-center gap-4 flex-wrap">

      {/* 모드 탭 */}
      <div
        className="flex items-center rounded-xl p-1 shrink-0 gap-0.5"
        style={{ background: 'rgba(15,23,42,0.07)', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.08)' }}
      >
        <button onClick={enableSingle} className={tabBase} style={!rangeMode ? tabActive : tabInactive}>
          단일 시즌
        </button>
        <button onClick={enableRange} className={tabBase} style={rangeMode ? tabActive : tabInactive}>
          시즌 구간
        </button>
      </div>

      {/* 구분선 */}
      <span
        className="h-6 w-px shrink-0"
        style={{ background: 'linear-gradient(to bottom, transparent, #cbd5e1, transparent)' }}
      />

      {/* 단일 시즌 */}
      {!rangeMode ? (
        <div className="flex items-center gap-2.5">
          <Label text="시즌" />
          <SelectDropdown value={value.from} onChange={handleFromChange} options={SEASONS} />
        </div>
      ) : (
        /* 시즌 구간 */
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Label text="시작" />
            <SelectDropdown value={value.from} onChange={handleFromChange} options={SEASONS} />
          </div>

          <div className="flex items-end pb-1">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </div>

          <div className="flex items-center gap-2">
            <Label text="종료" />
            <SelectDropdown
              value={value.to}
              onChange={handleToChange}
              options={SEASONS.filter(y => y >= value.from)}
            />
          </div>

          {value.from !== value.to && (
            <div className="flex items-end pb-1">
              <span
                className="text-[11px] font-bold px-2.5 py-1 rounded-full"
                style={{
                  background: 'linear-gradient(135deg, rgba(16,185,129,0.12), rgba(5,150,105,0.08))',
                  color: '#059669',
                  border: '1px solid rgba(16,185,129,0.25)',
                }}
              >
                {value.to - value.from + 1}개 시즌
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
