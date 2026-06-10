/**
 * Single source of truth: commodity key → color → label.
 * Both the points layer and the control panel/legend read from here.
 * Colors are mirrored from the design system; never hardcode a commodity color twice.
 *
 * Keys match the `commodity` bucket written by scripts/prepare-data.py.
 */

export type CommodityKey =
  | 'gold'
  | 'copper'
  | 'lithium'
  | 'cobalt'
  | 'nickel'
  | 'ree'
  | 'zinc'
  | 'uranium'
  | 'silver'
  | 'iron'
  | 'bauxite'
  | 'platinum'
  | 'manganese'
  | 'other_metals'
  | 'other'

export type CommodityGroup = 'precious' | 'base' | 'critical' | 'other'

export interface Commodity {
  key: CommodityKey
  label: string
  color: string
  group: CommodityGroup
}

/** Legend section labels + order. */
export const GROUPS: { key: CommodityGroup; label: string }[] = [
  { key: 'precious', label: 'Precious' },
  { key: 'base', label: 'Base & ferrous' },
  { key: 'critical', label: 'Battery & critical' },
  { key: 'other', label: 'Other' },
]

/**
 * Grouped for the legend (precious / base & ferrous / battery & critical / other). Colors
 * are material-derived; the two close pairs (bauxite↔copper, platinum↔silver) are nudged
 * apart for readability and colour-vision safety.
 */
export const COMMODITIES: Commodity[] = [
  { key: 'gold', label: 'Gold', color: '#f2c14e', group: 'precious' },
  { key: 'silver', label: 'Silver', color: '#d6dce6', group: 'precious' },
  { key: 'platinum', label: 'Platinum (PGE)', color: '#7fbccd', group: 'precious' }, // platinum sheen (cooler, away from silver)
  { key: 'copper', label: 'Copper', color: '#c66b3d', group: 'base' }, // oxidized penny
  { key: 'iron', label: 'Iron', color: '#b03a30', group: 'base' }, // hematite red
  { key: 'zinc', label: 'Zinc', color: '#7a8aa0', group: 'base' },
  { key: 'nickel', label: 'Nickel', color: '#9fb4a7', group: 'base' },
  { key: 'manganese', label: 'Manganese', color: '#7b5cb0', group: 'base' }, // manganese-violet
  { key: 'bauxite', label: 'Bauxite', color: '#e0bd86', group: 'base' }, // bauxite buff (lighter, away from copper)
  { key: 'lithium', label: 'Lithium', color: '#4fd1c5', group: 'critical' }, // battery teal
  { key: 'cobalt', label: 'Cobalt', color: '#2d6be0', group: 'critical' }, // cobalt blue
  { key: 'ree', label: 'Rare earths', color: '#b86bd6', group: 'critical' }, // exotic magenta
  { key: 'uranium', label: 'Uranium', color: '#8fe34d', group: 'critical' }, // radioactive green
  { key: 'other_metals', label: 'Other metals', color: '#8a7f6e', group: 'other' }, // bronze (tin, chrome, W…)
  { key: 'other', label: 'Other', color: '#5a6478', group: 'other' },
]

/** Lookup by key, e.g. COMMODITY.gold.color */
export const COMMODITY: Record<CommodityKey, Commodity> = Object.fromEntries(
  COMMODITIES.map((c) => [c.key, c]),
) as Record<CommodityKey, Commodity>

/** Fallback color for any unexpected/missing key — the neutral "other" tone. */
export const FALLBACK_COLOR = COMMODITY.other.color

export function commodityColor(key: string): string {
  return COMMODITY[key as CommodityKey]?.color ?? FALLBACK_COLOR
}
