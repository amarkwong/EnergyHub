import { useEffect, useMemo, useRef } from 'react'
import maplibregl, { type GeoJSONSource, type Map as MapLibreMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

type NmiLocation = {
  id: number
  nmi: string
  service_address?: string | null
  state?: string | null
  postcode?: string | null
  latitude?: number | null
  longitude?: number | null
  geocode_source?: string | null
  usage_kwh?: number | null
  latest_invoice_total?: number | null
  latest_invoice_number?: string | null
}

const SOURCE_ID = 'nmi-points'

export default function MapPage() {
  const mapContainerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<MapLibreMap | null>(null)

  const { data = [], isLoading } = useQuery({
    queryKey: ['nmi-locations'],
    queryFn: async () => {
      const response = await api.get('/api/account/nmi-locations')
      return response.data as NmiLocation[]
    },
  })

  const geoJson = useMemo(() => {
    const features = data
      .filter((row) => typeof row.longitude === 'number' && typeof row.latitude === 'number')
      .map((row) => ({
        type: 'Feature' as const,
        geometry: {
          type: 'Point' as const,
          coordinates: [row.longitude as number, row.latitude as number] as [number, number],
        },
        properties: {
          id: row.id,
          nmi: row.nmi,
          service_address: row.service_address ?? '',
          state: row.state ?? '',
          postcode: row.postcode ?? '',
          geocode_source: row.geocode_source ?? '',
          usage_kwh: row.usage_kwh ?? null,
          latest_invoice_total: row.latest_invoice_total ?? null,
          latest_invoice_number: row.latest_invoice_number ?? '',
        },
      }))
    return {
      type: 'FeatureCollection' as const,
      features,
    }
  }, [data])

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: [134.5, -25.8],
      zoom: 3.2,
      minZoom: 2.5,
      maxZoom: 15,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    map.on('load', () => {
      map.addSource(SOURCE_ID, {
        type: 'geojson',
        data: geoJson,
        cluster: true,
        clusterMaxZoom: 10,
        clusterRadius: 42,
      })

      map.addLayer({
        id: 'clusters',
        type: 'circle',
        source: SOURCE_ID,
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': ['step', ['get', 'point_count'], '#2563eb', 8, '#1d4ed8', 24, '#0f172a'],
          'circle-radius': ['step', ['get', 'point_count'], 16, 8, 20, 24, 26],
          'circle-opacity': 0.85,
        },
      })

      map.addLayer({
        id: 'cluster-count',
        type: 'symbol',
        source: SOURCE_ID,
        filter: ['has', 'point_count'],
        layout: {
          'text-field': ['get', 'point_count_abbreviated'],
          'text-size': 12,
        },
        paint: {
          'text-color': '#ffffff',
        },
      })

      map.addLayer({
        id: 'unclustered-point',
        type: 'circle',
        source: SOURCE_ID,
        filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-color': '#16a34a',
          'circle-radius': 7,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      })

      map.on('click', 'clusters', (e) => {
        const features = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })
        if (!features.length) return
        const clusterId = features[0].properties?.cluster_id
        const source = map.getSource(SOURCE_ID) as GeoJSONSource
        source
          .getClusterExpansionZoom(clusterId)
          .then((zoom) => {
            const coords = features[0].geometry.type === 'Point' ? features[0].geometry.coordinates : [134.5, -25.8]
            map.easeTo({ center: coords as [number, number], zoom })
          })
          .catch(() => undefined)
      })

      map.on('click', 'unclustered-point', (e) => {
        const feature = e.features?.[0]
        if (!feature || feature.geometry.type !== 'Point') return
        const props = feature.properties as Record<string, string | number | null>
        const usage = typeof props.usage_kwh === 'number' ? `${props.usage_kwh.toFixed(2)} kWh` : 'n/a'
        const bill = typeof props.latest_invoice_total === 'number' ? `$${props.latest_invoice_total.toFixed(2)}` : 'n/a'
        const invoiceNo = props.latest_invoice_number || 'n/a'
        const html = `
          <div style="font-size:12px; line-height:1.4;">
            <div style="font-weight:700; margin-bottom:4px;">NMI ${props.nmi}</div>
            <div>${props.service_address || 'Address unavailable'}</div>
            <div style="margin-top:6px;"><b>Usage:</b> ${usage}</div>
            <div><b>Latest Bill:</b> ${bill}</div>
            <div><b>Invoice:</b> ${invoiceNo}</div>
          </div>
        `
        new maplibregl.Popup({ closeButton: true, closeOnClick: true })
          .setLngLat(feature.geometry.coordinates as [number, number])
          .setHTML(html)
          .addTo(map)
      })

      map.on('mouseenter', 'clusters', () => {
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', 'clusters', () => {
        map.getCanvas().style.cursor = ''
      })
      map.on('mouseenter', 'unclustered-point', () => {
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', 'unclustered-point', () => {
        map.getCanvas().style.cursor = ''
      })
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [geoJson])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined
    if (!source) return
    source.setData(geoJson)
  }, [geoJson])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">NMI Map</h1>
        <p className="mt-1 text-sm text-slate-500">
          Interactive Australia map with clustered pins. Zoom in for state/city detail and click a pin for usage and bill.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="text-sm text-slate-600 mb-3">
          {isLoading ? 'Loading map data...' : `Mapped NMIs: ${geoJson.features.length}`}
        </div>
        <div ref={mapContainerRef} className="h-[600px] w-full rounded-lg border border-slate-200" />
      </div>
    </div>
  )
}
