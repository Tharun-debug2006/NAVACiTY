import { useRef } from 'react'

/**
 * The Metro / Bus segmented control.
 *
 * It behaves like a radio group: the arrow keys move between the options and
 * `aria-pressed` states which one is active.  The metro uses the indigo
 * family, the bus the amber family, so the mode is recognisable without
 * reading the label.
 */
const MODE_LABEL = { metro: 'Metro', bus: 'Bus' }
const MODES = ['metro', 'bus']

export default function ModeSwitch({ value, onChange, disabled = false, id = 'mode-switch' }) {
  const refs = useRef({})

  const handleKeyDown = (event) => {
    const index = MODES.indexOf(value)
    let next = null
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      next = MODES[(index + 1) % MODES.length]
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      next = MODES[(index - 1 + MODES.length) % MODES.length]
    }
    if (next) {
      event.preventDefault()
      onChange(next)
      refs.current[next]?.focus()
    }
  }

  return (
    <div
      role="group"
      aria-label="Transport mode"
      id={id}
      className="inline-flex rounded-control border border-slate-300 bg-white p-1"
      onKeyDown={handleKeyDown}
    >
      {MODES.map((mode) => {
        const active = value === mode
        return (
          <button
            key={mode}
            ref={(node) => {
              refs.current[mode] = node
            }}
            type="button"
            aria-pressed={active}
            disabled={disabled}
            onClick={() => onChange(mode)}
            className={`min-h-[40px] flex-1 rounded-control px-4 text-sm font-semibold transition ${
              active
                ? mode === 'metro'
                  ? 'bg-metro-700 text-white'
                  : 'bg-bus-600 text-white'
                : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            {MODE_LABEL[mode]}
          </button>
        )
      })}
    </div>
  )
}
