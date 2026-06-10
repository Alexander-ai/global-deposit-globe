import { useEffect, useRef } from 'react'
import { COMMODITY } from '../data/commodities'
import type { Deposit } from '../data/useDeposits'
import './DepositCard.css'

interface Props {
  deposit: Deposit
  onClose: () => void
  /** Filter the whole globe to this country (clicked from the card). */
  onCountry: (country: string) => void
}

const coord = (n: number) => n.toFixed(4)

const STATUS_LABEL: Record<Deposit['status'], string> = {
  producer: 'Producing',
  past: 'Past producer',
  deposit: 'Known deposit',
}

/** Magnitude (1.2–3) -> a plain-English scale label. */
const scaleLabel = (m?: number) =>
  m == null ? null : m >= 2.4 ? 'Major' : m >= 1.7 ? 'Medium' : 'Minor'

/**
 * Detail card shown on point-click. Same translucent surface as the panel, docked
 * bottom-right. Numbers are mono — the instrument feel. Dismiss with the × or Escape.
 */
export default function DepositCard({ deposit, onClose, onCountry }: Props) {
  const cardRef = useRef<HTMLDivElement>(null)
  const commodity = COMMODITY[deposit.commodity]

  // Escape dismisses; move focus into the card when it opens so keyboard users land here.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    cardRef.current?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      ref={cardRef}
      className="card"
      role="dialog"
      aria-label={`Deposit: ${deposit.name}`}
      tabIndex={-1}
    >
      <button
        type="button"
        className="card__close"
        aria-label="Close"
        onClick={onClose}
      >
        &times;
      </button>

      <h2 className="card__name">{deposit.name}</h2>

      <dl className="card__rows">
        <div className="card__row">
          <dt>Commodity</dt>
          <dd className="card__commodity">
            <span
              className="card__swatch"
              style={{ background: commodity.color }}
              aria-hidden="true"
            />
            {commodity.label}
          </dd>
        </div>
        {deposit.also && deposit.also.length > 0 && (
          <div className="card__row">
            <dt>Also present</dt>
            <dd>{deposit.also.join(', ')}</dd>
          </div>
        )}
        <div className="card__row">
          <dt>Deposit type</dt>
          <dd className="mono">{deposit.depositType ?? 'Not recorded'}</dd>
        </div>
        {deposit.miningTechnique && (
          <div className="card__row">
            <dt>Mining technique</dt>
            <dd className="mono">{deposit.miningTechnique}</dd>
          </div>
        )}
        <div className="card__row">
          <dt>Status</dt>
          <dd>{STATUS_LABEL[deposit.status]}</dd>
        </div>
        {scaleLabel(deposit.m) && (
          <div className="card__row">
            <dt>Scale</dt>
            <dd>{scaleLabel(deposit.m)}</dd>
          </div>
        )}
        {deposit.country && (
          <div className="card__row">
            <dt>Country</dt>
            <dd>
              <button
                type="button"
                className="card__country"
                onClick={() => onCountry(deposit.country!)}
                title={`Show only ${deposit.country}`}
              >
                {deposit.country}
              </button>
            </dd>
          </div>
        )}
        <div className="card__row">
          <dt>Coordinates</dt>
          <dd className="mono">
            {coord(deposit.lat)}, {coord(deposit.lng)}
          </dd>
        </div>
        <div className="card__row">
          <dt>Source</dt>
          <dd className="card__source">
            {deposit.source}
            {deposit.corrob && deposit.corrob > 1 && (
              <span className="card__corrob"> · in {deposit.corrob} databases</span>
            )}
          </dd>
        </div>
      </dl>

      {deposit.porterUrl && (
        <a
          className="card__porter"
          href={deposit.porterUrl}
          target="_blank"
          rel="noreferrer"
        >
          Full description on PorterGeo
          <span aria-hidden="true"> ↗</span>
        </a>
      )}
    </div>
  )
}
