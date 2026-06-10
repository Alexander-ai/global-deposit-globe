import { useEffect, useRef } from 'react'
import './AboutPanel.css'

interface Props {
  onClose: () => void
}

/**
 * Honesty, expanded. The footer carries the one-line data-vintage note; this panel
 * explains the MRDS caveats and exactly what filter is applied, because being straight
 * about the source is part of the craft here.
 */
export default function AboutPanel({ onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    ref.current?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="about-scrim" onClick={onClose}>
      <div
        ref={ref}
        className="about"
        role="dialog"
        aria-label="About the data"
        aria-modal="true"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          className="about__close"
          aria-label="Close"
          onClick={onClose}
        >
          &times;
        </button>

        <h2 className="about__title">About the data</h2>

        <div className="about__body">
          <p>
            Deposits are <strong>compiled from twelve open databases</strong> and merged into
            one uniform set, de-duplicated across sources. Each point&rsquo;s detail card names
            the database it came from.
          </p>
          <p className="about__warn">
            The default <strong>Active</strong> view (producing mines + catalogued deposits) is
            roughly globally balanced (~36% US, every continent represented). Switching to{' '}
            <strong>All</strong> adds ~55k
            <strong> historical past-producers</strong> that are overwhelmingly US: USGS
            catalogued US sites exhaustively (the ~305k-record MRDS, frozen since
            <strong> 2011</strong>) while comparable open catalogs don&rsquo;t exist for most
            countries — so &ldquo;All&rdquo; over-represents the US by <em>count</em>, a
            data-availability artifact, not a reflection of where deposits are. Locations are
            historical and approximate.
          </p>
          <p>Sources (all public-domain or open-licensed, so this app can redistribute them):</p>
          <ul className="about__sources">
            <li>
              <a href="https://mrdata.usgs.gov/mrds/" target="_blank" rel="noreferrer">USGS MRDS</a>
              {' '}— global, US-heavy, frozen 2011 (public domain)
            </li>
            <li>
              <a href="https://mrdata.usgs.gov/mineral-operations/" target="_blank" rel="noreferrer">USGS Mineral Operations outside the US</a>
              {' '}— non-US mines &amp; plants (public domain)
            </li>
            <li>
              USGS world deposit catalogs:{' '}
              <a href="https://mrdata.usgs.gov/porcu/" target="_blank" rel="noreferrer">porphyry copper</a>,{' '}
              <a href="https://mrdata.usgs.gov/ree/" target="_blank" rel="noreferrer">rare earths</a>,{' '}
              <a href="https://mrdata.usgs.gov/sedznpb/" target="_blank" rel="noreferrer">sediment Zn-Pb</a>,{' '}
              <a href="https://mrdata.usgs.gov/vms/" target="_blank" rel="noreferrer">VMS</a> (public domain)
            </li>
            <li>
              <a href="https://mrdata.usgs.gov/pp1802/" target="_blank" rel="noreferrer">USGS Global Critical Minerals</a>
              {' '}— 22 commodities across 150 countries (public domain)
            </li>
            <li>
              <a href="https://services.ga.gov.au/" target="_blank" rel="noreferrer">Geoscience Australia</a>
              {' '}— Australian operating mines (CC-BY 4.0)
            </li>
            <li>
              <a href="https://services2.arcgis.com/rtefou6JFIxFvYTf/arcgis/rest/services/AFR_Mineral_Facilities_shp/FeatureServer" target="_blank" rel="noreferrer">USGS Mineral Industries of Africa</a>
              {' '}— 58 African countries (public domain)
            </li>
            <li>
              Canada:{' '}
              <a href="https://natural-resources.canada.ca/maps-tools-publications/maps/principal-mineral-areas-canada" target="_blank" rel="noreferrer">NRCan 900A</a>,{' '}
              <a href="https://catalogue.data.gov.bc.ca/dataset/minfile-mineral-occurrence-database" target="_blank" rel="noreferrer">BC MINFILE</a>,{' '}
              <a href="https://gis.saskatchewan.ca/" target="_blank" rel="noreferrer">Saskatchewan SMDI</a>
              {' '}(Open Government Licence)
            </li>
          </ul>
          <p>How it&rsquo;s built:</p>
          <ul>
            <li>
              Colored by <strong>primary commodity</strong>, normalized into 14 buckets — the
              critical minerals, major base/precious metals, and the bulk/strategic commodities
              that define non-US mining (iron, bauxite, platinum-group, manganese, plus an
              &ldquo;other metals&rdquo; catch-all). Pure energy/aggregate sites (coal, cement,
              sand &amp; gravel) are excluded.
            </li>
            <li>
              De-duplicated by proximity + name: nearby fuzzy matches merge within ~1.5 km,
              and a <strong>distinctively-named site merges its variants within 100 km</strong>
              &mdash; while a common label (&ldquo;Gold King&rdquo; names dozens of separate
              mines) stays split. The detail card notes when a site appears in several databases.
            </li>
            <li>
              <strong>Dot size reflects recorded scale</strong> — production size or ore
              tonnage where the source provides it; the card labels it Major / Medium / Minor.
            </li>
            <li>
              Each site is <strong>Producing</strong>, a <strong>Past producer</strong>, or a{' '}
              <strong>Known deposit</strong> (catalog sources rarely record live status). The{' '}
              <strong>Active / All</strong> toggle switches between the balanced default and the
              full historical set.
            </li>
            <li>
              Major deposits link out to{' '}
              <a href="https://portergeo.com.au/database/" target="_blank" rel="noreferrer">
                PorterGeo&rsquo;s
              </a>{' '}
              in-depth geological description, matched by location and commodity where we have
              coordinates, otherwise by name &mdash; conservatively, so a link never points at a
              same-named site elsewhere.
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
