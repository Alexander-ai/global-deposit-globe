import { useEffect, useState } from 'react'
import { COMMODITIES, type CommodityKey } from './commodities'

/** One mineral deposit, as written by scripts/prepare-data.py into public/deposits.json. */
export interface Deposit {
  name: string
  lat: number
  lng: number
  commodity: CommodityKey
  /** Development status — drives the density-tier toggle. 'deposit' = status unknown
   * (most global catalog sources don't record live operating status). */
  status: 'producer' | 'past' | 'deposit'
  /** Human label of the database this record came from (multi-source provenance). */
  source: string
  /** Country (as the source recorded it) — powers the country filter. */
  country?: string
  /** Geological deposit type (mining method/facility labels are split out of this). */
  depositType?: string
  /** How the site is worked — open-pit, underground, etc. (distinct from depositType). */
  miningTechnique?: string
  /** Other commodities recorded at the site (primary excluded). */
  also?: string[]
  /** Magnitude 1.2–3 (production size / tonnage derived) — drives dot size. */
  m?: number
  /** Number of distinct databases corroborating this site (present when ≥ 2). */
  corrob?: number
}

type LoadState =
  | { status: 'loading'; deposits: null; error: null }
  | { status: 'ready'; deposits: Deposit[]; error: null }
  | { status: 'error'; deposits: null; error: string }

/**
 * Loads the baked deposit data once. Filtering by commodity is layered on top in a
 * later phase — this hook only owns the fetch so the source of truth stays in one place.
 */
export function useDeposits(): LoadState {
  const [state, setState] = useState<LoadState>({
    status: 'loading',
    deposits: null,
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    fetch(`${import.meta.env.BASE_URL}deposits.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<Deposit[]>
      })
      .then((deposits) => {
        if (!cancelled) setState({ status: 'ready', deposits, error: null })
      })
      .catch((e: unknown) => {
        if (!cancelled)
          setState({ status: 'error', deposits: null, error: String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}

export type CommodityCounts = Record<CommodityKey, number>

/** Per-commodity deposit totals for the panel/legend. Computed once from the full set. */
export function countByCommodity(deposits: Deposit[] | null): CommodityCounts {
  const counts = Object.fromEntries(
    COMMODITIES.map((c) => [c.key, 0]),
  ) as CommodityCounts
  if (deposits) {
    for (const d of deposits) counts[d.commodity] = (counts[d.commodity] ?? 0) + 1
  }
  return counts
}

/**
 * The deposits whose commodity is currently switched on. When every commodity is
 * active we return the original array by reference, so the globe's merged geometry
 * isn't needlessly rebuilt in the all-on default state.
 */
export function filterByActive(
  deposits: Deposit[],
  active: ReadonlySet<CommodityKey>,
): Deposit[] {
  if (active.size >= COMMODITIES.length) return deposits
  return deposits.filter((d) => active.has(d.commodity))
}
