import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Globe, { type GlobeMethods } from 'react-globe.gl'
import * as THREE from 'three'
import { COMMODITY, type CommodityKey } from '../data/commodities'
import type { Deposit } from '../data/useDeposits'

/**
 * The hero object. A dark slate planet in deep space; the deposit points are the only
 * saturated color on screen. Isolated here so a later switch to deck.gl touches only
 * this file (per the architecture notes).
 *
 * Rendering: the deposits are ONE `THREE.Points` cloud — a single vertex per deposit,
 * drawn as a round shader sprite. That means the whole constellation is one draw call
 * with no per-point triangle meshes, so ~66k points build instantly and never need a
 * main-thread geometry rebuild. Filtering animates a per-vertex `aOn` attribute (the GPU
 * fades points in/out) instead of rebuilding the array — so toggling is jank-free.
 * Hover/click pick via a raycaster against the cloud (front hemisphere only).
 */

const ENV = {
  ocean: '#10182b',
  land: '#1b2540',
  landStroke: 'rgba(255,255,255,0.10)',
  atmosphere: '#4da6ff',
} as const

const POINT_ALT = 0.01 // height of points above the globe surface
const DRAG_SLOP_PX = 6 // pointer travel beyond this counts as a drag, not a click
const HIT_RADIUS_PX = 9 // max on-screen distance (px) between cursor and a pickable point

const POINT_VERT = /* glsl */ `
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aOn;            // 0..1 visibility (animated on filter)
  uniform float uPixelRatio;
  uniform float uSizeScale;
  varying vec3 vColor;
  varying float vOn;
  void main() {
    vColor = aColor;
    vOn = aOn;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    // Gently zoom-aware size: grows as the camera closes in (pow < 1 damps it) but is
    // clamped so dense clusters still resolve into separate dots instead of blobs.
    // 250.0 ≈ view depth of the front surface at the default altitude (globe radius 100).
    float zoomScale = pow(250.0 / max(-mv.z, 1.0), 0.35);
    gl_PointSize = clamp(aSize * uSizeScale * zoomScale, 2.2, 11.0)
                   * uPixelRatio * (0.4 + 0.6 * aOn);
    gl_Position = projectionMatrix * mv;
  }
`

const POINT_FRAG = /* glsl */ `
  precision mediump float;
  varying vec3 vColor;
  varying float vOn;
  void main() {
    if (vOn <= 0.01) discard;
    vec2 uv = gl_PointCoord - vec2(0.5);
    float r = length(uv) * 2.0;            // 0 at center -> 1 at sprite edge
    if (r > 1.0) discard;                  // round sprite
    // Mostly-solid body with a thin antialiased edge (the old full-radius fade left
    // most of the dot translucent, sinking dark hues into the slate).
    float alpha = 1.0 - smoothstep(0.72, 1.0, r);
    // Small center glint lifts low-luminance colors (zinc, nickel, other metals) off
    // the dark globe without repainting the palette.
    vec3 col = mix(vColor, vec3(1.0), 0.28 * (1.0 - smoothstep(0.0, 0.5, r)));
    gl_FragColor = vec4(col, alpha * vOn);
  }
`

interface Size {
  width: number
  height: number
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

interface HexBin {
  points: object[]
  sumWeight: number
  center: { lat: number; lng: number }
}

/** Most-common commodity colour among a bin's deposits. */
function dominantColor(points: Deposit[]): string {
  const tally: Partial<Record<CommodityKey, number>> = {}
  let best: CommodityKey = points[0].commodity
  let bestN = 0
  for (const p of points) {
    const n = (tally[p.commodity] = (tally[p.commodity] ?? 0) + 1)
    if (n > bestN) {
      bestN = n
      best = p.commodity
    }
  }
  return COMMODITY[best].color
}

function hexToRgba(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
}

interface Props {
  deposits: Deposit[]
  active: ReadonlySet<CommodityKey>
  onSelect: (deposit: Deposit | null) => void
  /** When this changes, the camera eases to the given deposit (search "fly-to"). */
  flyTo: { deposit: Deposit; nonce: number } | null
  /** 'points' = the constellation; 'density' = aggregated hexbins. */
  mode: 'points' | 'density'
  /** Clicking a country polygon hands its properties up to set the country filter. */
  onPickCountry: (props: Record<string, unknown> | null) => void
}

export default function DepositGlobe({
  deposits,
  active,
  onSelect,
  flyTo,
  mode,
  onPickCountry,
}: Props) {
  const globeRef = useRef<GlobeMethods | undefined>(undefined)
  const containerRef = useRef<HTMLDivElement>(null)
  const haloRef = useRef<HTMLDivElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const markRef = useRef<HTMLDivElement>(null) // search-result highlight
  const holdTimer = useRef<number | undefined>(undefined)
  const rafHover = useRef<number | undefined>(undefined)
  const markRaf = useRef<number | undefined>(undefined)
  const markTimer = useRef<number | undefined>(undefined)
  const downAt = useRef<{ x: number; y: number } | null>(null)

  // THREE objects owned imperatively (live in the globe scene, not React).
  const pointsRef = useRef<THREE.Points | null>(null)
  const starsRef = useRef<THREE.Points | null>(null)
  const onCurrent = useRef<Float32Array>(new Float32Array(0)) // animated visibility
  const onTarget = useRef<Float32Array>(new Float32Array(0))
  const visRaf = useRef<number | undefined>(undefined)
  const raycaster = useRef(new THREE.Raycaster())

  const depositsRef = useRef(deposits)
  depositsRef.current = deposits
  const activeRef = useRef(active)
  activeRef.current = active
  const modeRef = useRef(mode)
  modeRef.current = mode

  // Deposits feeding the hexbin layer (active-filtered) — only built in density mode.
  const hexData = useMemo(
    () => (mode === 'density' ? deposits.filter((d) => active.has(d.commodity)) : []),
    [mode, deposits, active],
  )

  const [size, setSize] = useState<Size>({ width: 0, height: 0 })
  const [countries, setCountries] = useState<object[]>([])
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const update = () => setSize({ width: el.clientWidth, height: el.clientHeight })
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    let cancelled = false
    fetch(`${import.meta.env.BASE_URL}ne_110m_admin_0_countries.geojson`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((g: { features: object[] }) => {
        if (!cancelled) setCountries(g.features)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const globeMaterial = useMemo(
    () =>
      new THREE.MeshPhongMaterial({
        color: ENV.ocean,
        shininess: 0,
        specular: new THREE.Color('#000000'),
      }),
    [],
  )

  const pointsMaterial = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uPixelRatio: { value: 1 },
          uSizeScale: { value: 2.8 }, // point size in CSS px (constant across zoom)
        },
        vertexShader: POINT_VERT,
        fragmentShader: POINT_FRAG,
        transparent: true,
        depthWrite: false,
      }),
    [],
  )

  // (Re)build the cloud geometry from the full deposit set. Visibility (filtering) is a
  // separate animated attribute, so this only runs when the underlying data changes.
  const buildCloud = useCallback(() => {
    const g = globeRef.current
    if (!g) return
    const ds = depositsRef.current
    const n = ds.length
    const positions = new Float32Array(n * 3)
    const colors = new Float32Array(n * 3)
    const sizes = new Float32Array(n)
    const on = new Float32Array(n)
    const tgt = new Float32Array(n)
    const c = new THREE.Color()
    const act = activeRef.current
    for (let i = 0; i < n; i++) {
      const d = ds[i]
      const p = g.getCoords(d.lat, d.lng, POINT_ALT)
      positions[i * 3] = p.x
      positions[i * 3 + 1] = p.y
      positions[i * 3 + 2] = p.z
      c.set(COMMODITY[d.commodity].color)
      colors[i * 3] = c.r
      colors[i * 3 + 1] = c.g
      colors[i * 3 + 2] = c.b
      // Magnitude (1.2–3, production-size/tonnage derived) scales the dot, normalized so
      // a mid-size deposit (~1.4) renders at the base size and majors read ~2x.
      sizes[i] = (d.m ?? 1.4) / 1.4
      const vis = act.has(d.commodity) ? 1 : 0
      on[i] = vis
      tgt[i] = vis
    }
    onCurrent.current = on
    onTarget.current = tgt

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geo.setAttribute('aColor', new THREE.BufferAttribute(colors, 3))
    geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1))
    geo.setAttribute('aOn', new THREE.BufferAttribute(on, 1))

    if (pointsRef.current) {
      pointsRef.current.geometry.dispose()
      pointsRef.current.geometry = geo
    } else {
      const pts = new THREE.Points(geo, pointsMaterial)
      pts.frustumCulled = false
      pointsRef.current = pts
      g.scene().add(pts)
    }
  }, [pointsMaterial])

  // Animate the visibility attribute toward the active set (GPU fade; instant if reduced).
  const applyFilter = useCallback(() => {
    const pts = pointsRef.current
    if (!pts) return
    const ds = depositsRef.current
    const act = activeRef.current
    const tgt = onTarget.current
    for (let i = 0; i < ds.length; i++) tgt[i] = act.has(ds[i].commodity) ? 1 : 0

    const attr = pts.geometry.getAttribute('aOn') as THREE.BufferAttribute
    const cur = onCurrent.current
    if (visRaf.current) cancelAnimationFrame(visRaf.current)

    if (prefersReducedMotion()) {
      cur.set(tgt)
      attr.needsUpdate = true
      return
    }
    const step = () => {
      let moving = false
      for (let i = 0; i < cur.length; i++) {
        const diff = tgt[i] - cur[i]
        if (Math.abs(diff) > 0.01) {
          cur[i] += diff * 0.18
          moving = true
        } else {
          cur[i] = tgt[i]
        }
      }
      attr.needsUpdate = true
      if (moving) visRaf.current = requestAnimationFrame(step)
    }
    step()
  }, [])

  const points = useMemo(() => deposits, [deposits]) // referenced for the build effect dep

  // Build/rebuild the cloud when data changes (after the globe is ready).
  useEffect(() => {
    if (ready) buildCloud()
  }, [ready, points, buildCloud])

  // Re-run the filter animation when the active set changes.
  useEffect(() => {
    if (ready) applyFilter()
  }, [ready, active, applyFilter])

  // Density mode hides the points cloud (the hexbins take over) and disables hover.
  useEffect(() => {
    if (pointsRef.current) pointsRef.current.visible = mode !== 'density'
    if (mode === 'density') hideHover()
  }, [mode, ready]) // eslint-disable-line react-hooks/exhaustive-deps

  // hexbin accessors (only consulted in density mode).
  // Near-flat tiles with a subtle, count-scaled lift — a density readout, not HUD bars.
  const hexAltitude = useCallback(
    (d: HexBin) => 0.004 + Math.min(0.05, Math.log10(d.points.length + 1) * 0.014),
    [],
  )
  const hexTopColor = useCallback(
    (d: HexBin) => hexToRgba(dominantColor(d.points as Deposit[]), 0.92),
    [],
  )
  const hexSideColor = useCallback(
    (d: HexBin) => hexToRgba(dominantColor(d.points as Deposit[]), 0.35),
    [],
  )
  const hexLabel = useCallback(
    (d: HexBin) =>
      `<div class="globe-tip"><span class="globe-tip__name">${d.points.length.toLocaleString(
        'en-US',
      )} deposits</span><span class="globe-tip__meta">in this cell</span></div>`,
    [],
  )

  // ---- picking -------------------------------------------------------------
  const pickIndex = useCallback((x: number, y: number): number => {
    if (modeRef.current === 'density') return -1
    const g = globeRef.current
    const pts = pointsRef.current
    const el = containerRef.current
    if (!g || !pts || !el) return -1
    const cam = g.camera() as THREE.Camera & { position: THREE.Vector3 }
    const ndc = new THREE.Vector2((x / el.clientWidth) * 2 - 1, -(y / el.clientHeight) * 2 + 1)
    raycaster.current.setFromCamera(ndc, cam)
    const camDist = cam.position.length()
    // Generous gather radius (∝ camera distance ⇒ ~constant on-screen) just to collect
    // CANDIDATES; the actual choice below is made in screen pixels.
    raycaster.current.params.Points!.threshold = camDist * 0.014
    const hits = raycaster.current.intersectObject(pts, false)
    const cur = onCurrent.current
    const ds = depositsRef.current
    // The raycaster sorts hits by distance ALONG the ray (camera proximity) — in dense
    // areas the first hit is often a neighbour, not the dot under the cursor. So project
    // each candidate to screen and pick the one nearest the pointer, within a px radius.
    let best = -1
    let bestPx = HIT_RADIUS_PX
    for (const h of hits) {
      const i = h.index ?? -1
      // front hemisphere only (not occluded by the globe) and currently visible
      if (i < 0 || h.distance >= camDist || cur[i] <= 0.5) continue
      const sc = g.getScreenCoords(ds[i].lat, ds[i].lng, POINT_ALT)
      const px = Math.hypot(sc.x - x, sc.y - y)
      if (px < bestPx) {
        bestPx = px
        best = i
      }
    }
    return best
  }, [])

  const hideHover = useCallback(() => {
    if (haloRef.current) haloRef.current.style.opacity = '0'
    if (tipRef.current) tipRef.current.style.opacity = '0'
    if (containerRef.current) containerRef.current.style.cursor = 'grab'
  }, [])

  const showHover = useCallback((dep: Deposit) => {
    const g = globeRef.current
    if (!g) return
    const sc = g.getScreenCoords(dep.lat, dep.lng, POINT_ALT)
    const lit = COMMODITY[dep.commodity].color
    const halo = haloRef.current
    if (halo) {
      halo.style.transform = `translate(${sc.x}px, ${sc.y}px)`
      halo.style.borderColor = lit
      halo.style.boxShadow = `0 0 12px 1px ${lit}`
      halo.style.opacity = '1'
    }
    const tip = tipRef.current
    if (tip) {
      tip.style.transform = `translate(${sc.x}px, ${sc.y}px)`
      ;(tip.firstChild as HTMLElement).textContent = dep.name
      ;(tip.lastChild as HTMLElement).textContent = COMMODITY[dep.commodity].label
      tip.style.opacity = '1'
    }
    if (containerRef.current) containerRef.current.style.cursor = 'pointer'
  }, [])

  const stopAutoRotate = useCallback(() => {
    if (holdTimer.current) window.clearTimeout(holdTimer.current)
    const g = globeRef.current
    if (g) g.controls().autoRotate = false
  }, [])

  // Pulse a temporary highlight on a deposit so it's findable in a crowded cluster: a
  // bouncing, flashing-yellow pin + expanding rings. Tracks the point each frame because
  // the camera is still easing into place. Starts after a short delay so the marker appears
  // as the deposit rotates to the front, not at a back-of-globe projection mid-pan.
  const flashDeposit = useCallback((dep: Deposit) => {
    const el = markRef.current
    if (!el) return
    if (markTimer.current) window.clearTimeout(markTimer.current)
    if (markRaf.current) cancelAnimationFrame(markRaf.current)
    el.classList.remove('is-on')
    markTimer.current = window.setTimeout(() => {
      const g = globeRef.current
      if (!g) return
      void el.offsetWidth // restart the CSS animations
      el.classList.add('is-on')
      let start = 0
      const DURATION = 2500
      const tick = (t: number) => {
        if (!start) start = t
        const sc = g.getScreenCoords(dep.lat, dep.lng, POINT_ALT)
        el.style.transform = `translate(${sc.x}px, ${sc.y}px)`
        if (t - start < DURATION) {
          markRaf.current = requestAnimationFrame(tick)
        } else {
          el.classList.remove('is-on')
          markRaf.current = undefined
        }
      }
      markRaf.current = requestAnimationFrame(tick)
    }, 450)
  }, [])

  // Search "fly-to": ease the camera to a chosen deposit, then flag it.
  useEffect(() => {
    if (!ready || !flyTo) return
    const g = globeRef.current
    if (!g) return
    stopAutoRotate()
    g.pointOfView(
      { lat: flyTo.deposit.lat, lng: flyTo.deposit.lng, altitude: 1.1 },
      1200,
    )
    flashDeposit(flyTo.deposit)
  }, [ready, flyTo, stopAutoRotate, flashDeposit])

  // Stop the highlight loop on unmount.
  useEffect(
    () => () => {
      if (markTimer.current) window.clearTimeout(markTimer.current)
      if (markRaf.current) cancelAnimationFrame(markRaf.current)
    },
    [],
  )

  // Imperative hover/click on the canvas (no React re-render on mouse move).
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onMove = (e: PointerEvent) => {
      if (rafHover.current) return
      rafHover.current = window.requestAnimationFrame(() => {
        rafHover.current = undefined
        const rect = el.getBoundingClientRect()
        const i = pickIndex(e.clientX - rect.left, e.clientY - rect.top)
        if (i >= 0) showHover(depositsRef.current[i])
        else hideHover()
      })
    }
    const onDown = (e: PointerEvent) => {
      downAt.current = { x: e.clientX, y: e.clientY }
    }
    const onUp = (e: PointerEvent) => {
      const start = downAt.current
      downAt.current = null
      if (start && Math.hypot(e.clientX - start.x, e.clientY - start.y) > DRAG_SLOP_PX)
        return
      const rect = el.getBoundingClientRect()
      const i = pickIndex(e.clientX - rect.left, e.clientY - rect.top)
      if (i >= 0) {
        stopAutoRotate()
        onSelect(depositsRef.current[i])
      } else {
        onSelect(null)
      }
    }
    const onLeave = () => hideHover()
    el.addEventListener('pointermove', onMove)
    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointerup', onUp)
    el.addEventListener('pointerleave', onLeave)
    return () => {
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointerup', onUp)
      el.removeEventListener('pointerleave', onLeave)
    }
  }, [pickIndex, showHover, hideHover, stopAutoRotate, onSelect])

  const onGlobeReady = () => {
    const g = globeRef.current
    if (!g) return
    g.pointOfView({ lat: 18, lng: -95, altitude: 2.5 })
    const controls = g.controls()
    controls.enableZoom = true
    controls.autoRotateSpeed = 0.45
    controls.addEventListener('start', stopAutoRotate)
    if (import.meta.env.DEV) (window as unknown as { __globe?: GlobeMethods }).__globe = g

    // Keep point sprites crisp at the device pixel ratio.
    pointsMaterial.uniforms.uPixelRatio.value = g.renderer().getPixelRatio()

    // A faint starfield gives the planet depth without competing with the data.
    if (!starsRef.current) starsRef.current = addStarfield(g)

    setReady(true)
    if (!prefersReducedMotion()) {
      holdTimer.current = window.setTimeout(() => {
        if (globeRef.current) globeRef.current.controls().autoRotate = true
      }, 2200)
    }
  }

  return (
    <div ref={containerRef} className={`globe-stage${ready ? ' is-ready' : ''}`}>
      {size.width > 0 && (
        <Globe
          ref={globeRef}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          globeMaterial={globeMaterial}
          showAtmosphere
          atmosphereColor={ENV.atmosphere}
          atmosphereAltitude={0.18}
          onGlobeReady={onGlobeReady}
          polygonsData={countries}
          polygonCapColor={() => ENV.land}
          polygonSideColor={() => 'rgba(0,0,0,0)'}
          polygonStrokeColor={() => ENV.landStroke}
          polygonAltitude={0.006}
          onPolygonClick={(polygon, event) => {
            // A click that lands on a deposit selects that deposit — it must NOT also filter
            // by country. Only blank land inside a country applies the country filter.
            const rect = containerRef.current?.getBoundingClientRect()
            const ev = event as MouseEvent | undefined
            if (rect && ev && pickIndex(ev.clientX - rect.left, ev.clientY - rect.top) >= 0) {
              return
            }
            onPickCountry(
              (polygon as { properties?: Record<string, unknown> })?.properties ?? null,
            )
          }}
          // Density mode: aggregate deposits into commodity-colored hexbins.
          hexBinPointsData={hexData}
          hexBinPointLat="lat"
          hexBinPointLng="lng"
          hexBinResolution={3}
          hexMargin={0.2}
          hexAltitude={hexAltitude}
          hexTopColor={hexTopColor}
          hexSideColor={hexSideColor}
          hexLabel={hexLabel}
          hexBinMerge
        />
      )}
      <div ref={haloRef} className="globe-halo" aria-hidden="true" />
      <div ref={tipRef} className="globe-tip globe-tip--floating" aria-hidden="true">
        <span className="globe-tip__name" />
        <span className="globe-tip__meta" />
      </div>
      <div ref={markRef} className="globe-search-mark" aria-hidden="true">
        <span className="globe-search-mark__ring" />
        <span className="globe-search-mark__pin" />
      </div>
    </div>
  )
}

function addStarfield(g: GlobeMethods): THREE.Points {
  const R = g.getGlobeRadius() * 6
  const n = 1400
  const pos = new Float32Array(n * 3)
  // Deterministic pseudo-random scatter on a far sphere (no Math.random dependency).
  for (let i = 0; i < n; i++) {
    const a = i * 2.399963 // golden-angle increment
    const yv = 1 - (i / (n - 1)) * 2
    const r = Math.sqrt(Math.max(0, 1 - yv * yv))
    pos[i * 3] = Math.cos(a) * r * R
    pos[i * 3 + 1] = yv * R
    pos[i * 3 + 2] = Math.sin(a) * r * R
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  const mat = new THREE.PointsMaterial({
    color: 0x9fb0d0,
    size: 1.4,
    sizeAttenuation: false,
    transparent: true,
    opacity: 0.5,
    depthWrite: false,
  })
  const stars = new THREE.Points(geo, mat)
  stars.frustumCulled = false
  g.scene().add(stars)
  return stars
}
