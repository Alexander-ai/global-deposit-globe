import { useState } from 'react'
import { COMMODITY } from '../data/commodities'
import type { Deposit } from '../data/useDeposits'
import './SearchBox.css'

interface Props {
  query: string
  onQuery: (q: string) => void
  /** Top matches for the current query (already filtered by active commodities). */
  results: Deposit[]
  total: number
  onPick: (deposit: Deposit) => void
}

/**
 * Find a deposit by name and fly to it. The dropdown shows the top matches; picking one
 * eases the camera there and opens its card.
 */
export default function SearchBox({ query, onQuery, results, total, onPick }: Props) {
  const [focused, setFocused] = useState(false)
  const open = focused && query.trim().length > 0

  return (
    <div className="search">
      <input
        type="search"
        className="search__input mono"
        placeholder="Search deposits…"
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setTimeout(() => setFocused(false), 120)}
        aria-label="Search deposits by name"
        autoComplete="off"
      />
      {open && (
        <ul className="search__results" role="listbox">
          {results.length === 0 ? (
            <li className="search__empty">No matches.</li>
          ) : (
            <>
              {results.map((d, i) => (
                <li key={`${d.name}-${d.lat}-${d.lng}-${i}`}>
                  <button
                    type="button"
                    className="search__hit"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => onPick(d)}
                  >
                    <span
                      className="search__swatch"
                      style={{ background: COMMODITY[d.commodity].color }}
                      aria-hidden="true"
                    />
                    <span className="search__name">{d.name}</span>
                    <span className="search__coord mono">
                      {d.lat.toFixed(2)}, {d.lng.toFixed(2)}
                    </span>
                  </button>
                </li>
              ))}
              {total > results.length && (
                <li className="search__more mono">
                  +{(total - results.length).toLocaleString('en-US')} more — refine your
                  search
                </li>
              )}
            </>
          )}
        </ul>
      )}
    </div>
  )
}
