import {
  lazy,
  Suspense,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from 'react'
import CommodityPanel from './components/CommodityPanel'
import DepositCard from './components/DepositCard'
import SearchBox from './components/SearchBox'
import AboutPanel from './components/AboutPanel'
import DepositList from './components/DepositList'
import { COMMODITIES, type CommodityKey } from './data/commodities'
import { countByCommodity, useDeposits, type Deposit } from './data/useDeposits'
import './styles/app.css'

// Code-split the 3D layer (three.js + globe.gl) so it doesn't block first paint.
const DepositGlobe = lazy(() => import('./components/DepositGlobe'))

const ALL_KEYS: ReadonlySet<CommodityKey> = new Set(COMMODITIES.map((c) => c.key))
const VALID_KEYS = new Set<string>(COMMODITIES.map((c) => c.key))
const SEARCH_LIMIT = 8

const normCountry = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')

// Natural Earth polygon name (normalized) -> the spelling our data uses (normalized).
const NE_ALIAS: Record<string, string> = {
  unitedstatesofamerica: 'unitedstates',
  demrepcongo: 'congokinshasa',
  democraticrepublicofthecongo: 'congokinshasa',
  republicofthecongo: 'congobrazzaville',
  unitedrepublicoftanzania: 'tanzania',
  czechia: 'czechrepublic',
  northmacedonia: 'macedonia',
  republicofserbia: 'serbia',
  cotedivoire: 'cotedivoire',
}

/** Read the active-commodity filter out of the URL hash (#c=gold,copper). */
function readHashFilter(): ReadonlySet<CommodityKey> | null {
  if (typeof location === 'undefined') return null
  const m = /[#&]c=([^&]*)/.exec(location.hash)
  if (!m) return null
  const keys = decodeURIComponent(m[1])
    .split(',')
    .filter((k) => VALID_KEYS.has(k)) as CommodityKey[]
  return new Set(keys) // empty set is meaningful ("none")
}

export default function App() {
  const { status, deposits } = useDeposits()
  const [active, setActive] = useState<ReadonlySet<CommodityKey>>(
    () => readHashFilter() ?? ALL_KEYS,
  )
  const [selected, setSelected] = useState<Deposit | null>(null)
  const [query, setQuery] = useState('')
  const [view, setView] = useState<'globe' | 'list'>('globe')
  const [flyTo, setFlyTo] = useState<{ deposit: Deposit; nonce: number } | null>(null)
  const [aboutOpen, setAboutOpen] = useState(false)
  // Default to 'current' (producing mines + catalogued deposits). This excludes the ~55k
  // MRDS historical past-producers — a US-collection-bias lump that otherwise swamps the
  // map — so the opening view reads as a balanced global picture (53% US vs 81%) while
  // keeping every major world deposit. 'All' restores the full historical set.
  const [tier, setTier] = useState<'all' | 'current'>('current')
  const [mode, setMode] = useState<'points' | 'density'>('points')
  const [country, setCountry] = useState<string | null>(null) // country filter (#7)

  const deferredQuery = useDeferredValue(query)

  const currentCount = useMemo(
    () => (deposits ? deposits.filter((d) => d.status !== 'past').length : 0),
    [deposits],
  )

  // Tier (history) + country filter applied together; everything downstream derives from this.
  const tierDeposits = useMemo(() => {
    if (!deposits) return null
    let d = tier === 'all' ? deposits : deposits.filter((x) => x.status !== 'past')
    if (country) {
      const cn = normCountry(country)
      d = d.filter((x) => x.country != null && normCountry(x.country) === cn)
    }
    return d
  }, [deposits, tier, country])

  const counts = useMemo(() => countByCommodity(tierDeposits), [tierDeposits])
  const present = useMemo(
    () => COMMODITIES.filter((c) => counts[c.key] > 0),
    [counts],
  )
  const hasVisible = present.some((c) => active.has(c.key))

  // Deposits matching the tier/country + active filter + the (deferred) search query
  // (search matches deposit name OR country, so typing "Zambia" surfaces its deposits).
  const matches = useMemo(() => {
    if (!tierDeposits) return []
    const q = deferredQuery.trim().toLowerCase()
    return tierDeposits.filter(
      (d) =>
        active.has(d.commodity) &&
        (!q ||
          d.name.toLowerCase().includes(q) ||
          (d.country?.toLowerCase().includes(q) ?? false)),
    )
  }, [tierDeposits, active, deferredQuery])

  // Resolve a clicked country polygon (Natural Earth names) to a country in our data.
  const countryIndex = useMemo(() => {
    const m = new Map<string, string>()
    if (deposits)
      for (const d of deposits)
        if (d.country) {
          const n = normCountry(d.country)
          if (!m.has(n)) m.set(n, d.country)
        }
    return m
  }, [deposits])

  const pickCountry = (props: Record<string, unknown> | null) => {
    if (!props) return
    for (const field of ['NAME_LONG', 'ADMIN', 'NAME', 'SOVEREIGNT', 'GEOUNIT']) {
      const v = props[field]
      if (typeof v === 'string') {
        const n = NE_ALIAS[normCountry(v)] ?? normCountry(v)
        const canon = countryIndex.get(n)
        if (canon) {
          setCountry((cur) => (cur === canon ? null : canon))
          return
        }
      }
    }
  }

  const chooseTier = (t: 'all' | 'current') => {
    if (t === 'current' && selected && selected.status === 'past') setSelected(null)
    setTier(t)
  }

  const chooseMode = (m: 'points' | 'density') => {
    if (m === 'density') setSelected(null) // individual points are hidden in density mode
    setMode(m)
  }

  const searchResults = useMemo(() => matches.slice(0, SEARCH_LIMIT), [matches])

  // Keep the active filter shareable via the URL hash.
  useEffect(() => {
    const isAll = active.size === COMMODITIES.length
    const next = isAll ? '' : `#c=${[...active].join(',')}`
    if ((location.hash || '') !== next) {
      history.replaceState(null, '', next || `${location.pathname}${location.search}`)
    }
  }, [active])

  const reconcileSelection = (next: ReadonlySet<CommodityKey>) => {
    if (selected && !next.has(selected.commodity)) setSelected(null)
  }

  const toggle = (key: CommodityKey) =>
    setActive((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      reconcileSelection(next)
      return next
    })

  const solo = (key: CommodityKey) =>
    setActive((prev) => {
      const next: ReadonlySet<CommodityKey> =
        prev.size === 1 && prev.has(key) ? ALL_KEYS : new Set([key])
      reconcileSelection(next)
      return next
    })

  const setAll = () => setActive(ALL_KEYS)
  const setNone = () => {
    setSelected(null)
    setActive(new Set())
  }

  // Pick a deposit from search/list: open its card and fly the camera to it.
  const focusDeposit = (d: Deposit) => {
    setSelected(d)
    setView('globe')
    setFlyTo((prev) => ({ deposit: d, nonce: (prev?.nonce ?? 0) + 1 }))
  }

  return (
    <div className="app">
      {status === 'ready' && tierDeposits && (
        <Suspense fallback={null}>
          <DepositGlobe
            deposits={tierDeposits}
            active={active}
            onSelect={setSelected}
            flyTo={flyTo}
            mode={mode}
            onPickCountry={pickCountry}
          />
        </Suspense>
      )}

      <div className="rail">
        <header className="topbar">
          <h1 className="topbar__title">
            <span className="topbar__mark" aria-hidden="true" />
            Global mineral deposits
          </h1>
          <p className="topbar__dek">
            A constellation of the world&rsquo;s producing mines and known deposits, by
            commodity.
          </p>
        </header>

        {status === 'ready' && (
          <div className="toolbar">
            <SearchBox
              query={query}
              onQuery={setQuery}
              results={searchResults}
              total={matches.length}
              onPick={focusDeposit}
            />
            <div className="toolbar__row">
              <div className="tier" role="group" aria-label="Coverage tier">
                <button
                  type="button"
                  className={`tier__btn${tier === 'current' ? ' is-on' : ''}`}
                  aria-pressed={tier === 'current'}
                  onClick={() => chooseTier('current')}
                  title="Producing mines + catalogued deposits (excludes historical past-producers)"
                >
                  Active <span className="tier__n mono">{currentCount.toLocaleString('en-US')}</span>
                </button>
                <button
                  type="button"
                  className={`tier__btn${tier === 'all' ? ' is-on' : ''}`}
                  aria-pressed={tier === 'all'}
                  onClick={() => chooseTier('all')}
                  title="Everything, including ~55k historical (mostly US) past-producers"
                >
                  All <span className="tier__n mono">{(deposits?.length ?? 0).toLocaleString('en-US')}</span>
                </button>
              </div>
              <div className="tier" role="group" aria-label="Render mode">
                <button
                  type="button"
                  className={`tier__btn${mode === 'points' ? ' is-on' : ''}`}
                  aria-pressed={mode === 'points'}
                  onClick={() => chooseMode('points')}
                >
                  Points
                </button>
                <button
                  type="button"
                  className={`tier__btn${mode === 'density' ? ' is-on' : ''}`}
                  aria-pressed={mode === 'density'}
                  onClick={() => chooseMode('density')}
                >
                  Density
                </button>
              </div>
              <button
                type="button"
                className="toolbar__view"
                onClick={() => setView('list')}
              >
                View as list
              </button>
            </div>
            {country && (
              <button
                type="button"
                className="country-chip"
                onClick={() => setCountry(null)}
                title="Clear country filter"
              >
                <span className="country-chip__label">{country}</span>
                <span aria-hidden="true">×</span>
              </button>
            )}
          </div>
        )}

        {status === 'ready' && (
          <CommodityPanel
            commodities={present}
            counts={counts}
            active={active}
            onToggle={toggle}
            onSolo={solo}
            onAll={setAll}
            onNone={setNone}
          />
        )}
      </div>

      {status === 'loading' && (
        <p className="stage-note" role="status">
          Plotting deposits&hellip;
        </p>
      )}
      {status === 'error' && (
        <p className="stage-note" role="alert">
          Couldn&rsquo;t load the deposit data. Try a refresh.
        </p>
      )}
      {status === 'ready' && !hasVisible && (
        <p className="stage-note" role="status">
          No deposits match the current filters.
        </p>
      )}

      {selected && (
        <DepositCard
          deposit={selected}
          onClose={() => setSelected(null)}
          onCountry={(c) => setCountry(c)}
        />
      )}

      {view === 'list' && status === 'ready' && (
        <DepositList
          deposits={matches}
          query={query}
          onQuery={setQuery}
          onPick={focusDeposit}
          onClose={() => setView('globe')}
        />
      )}

      <footer className="attribution mono">
        <button
          type="button"
          className="attribution__about"
          onClick={() => setAboutOpen(true)}
        >
          About the data
        </button>
        <span className="attribution__text">
          Compiled from USGS, Geoscience Australia, NRCan, BC &amp; SK · 12 open
          databases, de-duplicated · locations historical &amp; approximate
        </span>
      </footer>

      {aboutOpen && <AboutPanel onClose={() => setAboutOpen(false)} />}
    </div>
  )
}
