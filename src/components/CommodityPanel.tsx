import { Fragment } from 'react'
import { GROUPS, type Commodity, type CommodityKey } from '../data/commodities'
import type { CommodityCounts } from '../data/useDeposits'
import './CommodityPanel.css'

const GROUP_LABEL = Object.fromEntries(GROUPS.map((g) => [g.key, g.label]))

interface Props {
  /** Only commodities present in the data — this panel doubles as the legend. */
  commodities: Commodity[]
  counts: CommodityCounts
  active: ReadonlySet<CommodityKey>
  onToggle: (key: CommodityKey) => void
  onSolo: (key: CommodityKey) => void
  onAll: () => void
  onNone: () => void
}

const fmt = (n: number) => n.toLocaleString('en-US')

/**
 * The docked control panel — and the legend. One toggle per commodity: color swatch,
 * label, and a live mono count. Active rows are full-opacity; inactive rows dim and
 * their swatch goes hollow. The whole row is the toggle; a hover-revealed "Only" solos it.
 */
export default function CommodityPanel({
  commodities,
  counts,
  active,
  onToggle,
  onSolo,
  onAll,
  onNone,
}: Props) {
  return (
    <aside className="panel" aria-label="Filter deposits by commodity">
      <div className="panel__head">
        <h2 className="panel__header">Commodities</h2>
        <div className="panel__bulk">
          <button type="button" className="panel__bulk-btn" onClick={onAll}>
            All
          </button>
          <span aria-hidden="true">·</span>
          <button type="button" className="panel__bulk-btn" onClick={onNone}>
            None
          </button>
        </div>
      </div>
      <ul className="panel__list">
        {commodities.map((c, i) => {
          const on = active.has(c.key)
          const showHeader = i === 0 || commodities[i - 1].group !== c.group
          return (
            <Fragment key={c.key}>
              {showHeader && (
                <li className="panel__group" aria-hidden="true">
                  {GROUP_LABEL[c.group]}
                </li>
              )}
              <li className="row-wrap">
              <button
                type="button"
                className="row"
                aria-pressed={on}
                onClick={() => onToggle(c.key)}
              >
                <span
                  className={`row__swatch${on ? '' : ' is-hollow'}`}
                  style={
                    on
                      ? { background: c.color }
                      : { boxShadow: `inset 0 0 0 2px ${c.color}` }
                  }
                  aria-hidden="true"
                />
                <span className="row__label">{c.label}</span>
                <span className="row__count mono">{fmt(counts[c.key])}</span>
              </button>
                <button
                  type="button"
                  className="row__solo"
                  aria-label={`Show only ${c.label}`}
                  onClick={() => onSolo(c.key)}
                >
                  Only
                </button>
              </li>
            </Fragment>
          )
        })}
      </ul>
    </aside>
  )
}
