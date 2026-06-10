import { useMemo, useRef, useState } from 'react'
import { COMMODITY } from '../data/commodities'
import type { Deposit } from '../data/useDeposits'
import './DepositList.css'

type SortKey = 'name' | 'commodity' | 'lat' | 'lng'

interface Props {
  /** Deposits already filtered by active commodities + search query. */
  deposits: Deposit[]
  query: string
  onQuery: (q: string) => void
  onPick: (deposit: Deposit) => void
  onClose: () => void
}

const ROW_H = 40
const OVERSCAN = 6

/**
 * A keyboard- and screen-reader-accessible view of the same data: a sortable, searchable
 * table. Hand-virtualized (fixed row height, render only the visible slice) so it stays
 * smooth across tens of thousands of rows without a windowing dependency.
 */
export default function DepositList({
  deposits,
  query,
  onQuery,
  onPick,
  onClose,
}: Props) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({
    key: 'name',
    dir: 1,
  })
  const [scrollTop, setScrollTop] = useState(0)
  const bodyRef = useRef<HTMLDivElement>(null)
  const [bodyH, setBodyH] = useState(480)

  const sorted = useMemo(() => {
    const arr = deposits.slice()
    const { key, dir } = sort
    arr.sort((a, b) => {
      let r: number
      if (key === 'lat' || key === 'lng') r = a[key] - b[key]
      else if (key === 'commodity')
        r = COMMODITY[a.commodity].label.localeCompare(COMMODITY[b.commodity].label)
      else r = a.name.localeCompare(b.name)
      return r * dir
    })
    return arr
  }, [deposits, sort])

  const total = sorted.length
  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - OVERSCAN)
  const end = Math.min(total, Math.ceil((scrollTop + bodyH) / ROW_H) + OVERSCAN)
  const slice = sorted.slice(start, end)

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: 1 }))

  const sortIndicator = (key: SortKey) =>
    sort.key === key ? (sort.dir === 1 ? ' ↑' : ' ↓') : ''

  const measure = (el: HTMLDivElement | null) => {
    bodyRef.current = el
    if (el) setBodyH(el.clientHeight)
  }

  return (
    <section className="dataview" aria-label="Deposit list">
      <header className="dataview__head">
        <button type="button" className="dataview__back" onClick={onClose}>
          ← Globe
        </button>
        <input
          type="search"
          className="dataview__search mono"
          placeholder="Filter by name…"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          aria-label="Filter deposits by name"
          autoComplete="off"
        />
        <span className="dataview__count mono">
          {total.toLocaleString('en-US')} deposits
        </span>
      </header>

      <div className="dataview__cols" role="row">
        <button className="dataview__col dataview__col--name" onClick={() => toggleSort('name')}>
          Name{sortIndicator('name')}
        </button>
        <button
          className="dataview__col dataview__col--commodity"
          onClick={() => toggleSort('commodity')}
        >
          Commodity{sortIndicator('commodity')}
        </button>
        <button className="dataview__col dataview__col--lat" onClick={() => toggleSort('lat')}>
          Lat{sortIndicator('lat')}
        </button>
        <button className="dataview__col dataview__col--lng" onClick={() => toggleSort('lng')}>
          Lng{sortIndicator('lng')}
        </button>
      </div>

      <div
        className="dataview__body"
        ref={measure}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      >
        {total === 0 ? (
          <p className="dataview__empty">No deposits match the current filters.</p>
        ) : (
          <div className="dataview__spacer" style={{ height: total * ROW_H }}>
            {slice.map((d, i) => {
              const idx = start + i
              const c = COMMODITY[d.commodity]
              return (
                <button
                  key={`${d.source}-${d.name}-${d.lat}-${d.lng}`}
                  type="button"
                  className="dataview__row"
                  style={{ top: idx * ROW_H }}
                  onClick={() => onPick(d)}
                >
                  <span className="dataview__cell dataview__col--name">{d.name}</span>
                  <span className="dataview__cell dataview__col--commodity">
                    <span
                      className="dataview__swatch"
                      style={{ background: c.color }}
                      aria-hidden="true"
                    />
                    {c.label}
                  </span>
                  <span className="dataview__cell dataview__col--lat mono">
                    {d.lat.toFixed(4)}
                  </span>
                  <span className="dataview__cell dataview__col--lng mono">
                    {d.lng.toFixed(4)}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}
