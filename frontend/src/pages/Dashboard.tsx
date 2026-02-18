import { useEffect, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import maplibregl, { type Map as MapLibreMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useAppMode } from '../context/AppModeContext'
import { api } from '../api/client'

type NmiLocation = {
  id: number
  nmi: string
  service_address?: string | null
  state?: string | null
  postcode?: string | null
  latitude?: number | null
  longitude?: number | null
  usage_kwh?: number | null
  latest_invoice_total?: number | null
  latest_invoice_number?: string | null
}

type NmiPlanAssignment = {
  id: number
  nmi: string
  effective_from: string
  effective_to?: string | null
  retailer_name?: string | null
  network_tariff_code?: string | null
}

type BillingGap = {
  gap_start: string
  gap_end: string
}

type InvoiceSummaryItem = {
  invoice_number?: string | null
  billing_period_start: string
  billing_period_end: string
  total: number
}

type DashboardSummary = {
  invoice_total: number
  billing_period_start?: string | null
  billing_period_end?: string | null
  billing_gaps: BillingGap[]
  usage_kwh: number
  controlled_load_kwh: number
  solar_export_kwh: number
  invoices: InvoiceSummaryItem[]
}

function NmiMapCompact({ locations }: { locations: NmiLocation[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<MapLibreMap | null>(null)

  const points = useMemo(
    () => locations.filter((l) => typeof l.latitude === 'number' && typeof l.longitude === 'number'),
    [locations],
  )

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const center: [number, number] =
      points.length > 0 ? [points[0].longitude!, points[0].latitude!] : [134.5, -25.8]
    const zoom = points.length > 0 ? 12 : 3.2

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center,
      zoom,
      minZoom: 2.5,
      maxZoom: 15,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    map.on('load', () => {
      for (const loc of points) {
        const usage =
          typeof loc.usage_kwh === 'number' ? `${loc.usage_kwh.toFixed(2)} kWh` : 'n/a'
        const bill =
          typeof loc.latest_invoice_total === 'number'
            ? `$${loc.latest_invoice_total.toFixed(2)}`
            : 'n/a'
        const html = `
          <div style="font-size:12px; line-height:1.4;">
            <div style="font-weight:700; margin-bottom:4px;">NMI ${loc.nmi}</div>
            <div>${loc.service_address || 'Address unavailable'}</div>
            <div style="margin-top:6px;"><b>Usage:</b> ${usage}</div>
            <div><b>Latest Bill:</b> ${bill}</div>
          </div>
        `
        new maplibregl.Marker({ color: '#16a34a' })
          .setLngLat([loc.longitude!, loc.latitude!])
          .setPopup(new maplibregl.Popup({ closeButton: true }).setHTML(html))
          .addTo(map)
      }
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [points])

  if (points.length === 0) {
    return (
      <div className="h-[300px] rounded-lg border border-slate-200 bg-slate-50 flex items-center justify-center text-sm text-slate-500">
        No geocoded NMI locations to display.
      </div>
    )
  }

  return <div ref={containerRef} className="h-[300px] w-full rounded-lg border border-slate-200" />
}

export default function Dashboard() {
  const { mode } = useAppMode()

  const {
    data: locations = [],
    isLoading: locationsLoading,
  } = useQuery({
    queryKey: ['nmi-locations'],
    queryFn: async () => {
      const res = await api.get('/api/account/nmi-locations')
      return res.data as NmiLocation[]
    },
  })

  const {
    data: assignments = [],
    isLoading: assignmentsLoading,
  } = useQuery({
    queryKey: ['nmi-plan-assignments'],
    queryFn: async () => {
      const res = await api.get('/api/account/nmi-plan-assignments')
      return res.data as NmiPlanAssignment[]
    },
  })

  const {
    data: summary,
    isLoading: summaryLoading,
  } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: async () => {
      const res = await api.get('/api/account/dashboard-summary')
      return res.data as DashboardSummary
    },
  })

  const isLoading = locationsLoading || assignmentsLoading || summaryLoading

  // Use the first NMI for the residential single-NMI view
  const primary = locations[0] ?? null
  const primaryAssignment = assignments.find((a) => a.nmi === primary?.nmi) ?? null

  // Business quick actions (kept as-is per plan)
  const businessQuickActions = [
    { name: 'Ingest Meter Data', description: 'Upload portfolio interval files', href: '/upload', icon: '🏢' },
    { name: 'Run Invoice Audit', description: 'Validate supplier invoices at scale', href: '/reconciliation', icon: '🧾' },
    { name: 'Review Network Charges', description: 'Inspect demand and TOU structures', href: '/network', icon: '⚡' },
    { name: 'Compare Retail Contracts', description: 'Track retailer plan history', href: '/retailers', icon: '📑' },
  ]

  const businessStats = [
    { name: 'Sites Tracked', value: '24', change: '+2', changeType: 'increase' },
    { name: 'Billed vs Expected', value: '$8,420', change: '-3.1%', changeType: 'decrease' },
    { name: 'Invoices Audited', value: '67', change: '+8', changeType: 'increase' },
    { name: 'Risk Alerts', value: '3', change: '+1', changeType: 'neutral' },
  ]

  if (mode === 'business') {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Business Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">
            Portfolio-level oversight for tariff governance, invoice assurance, and risk controls.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {businessStats.map((stat) => (
            <div key={stat.name} className="bg-white overflow-hidden rounded-lg border border-slate-200 px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-slate-500 truncate">{stat.name}</dt>
              <dd className="mt-1 flex items-baseline justify-between md:block lg:flex">
                <div className="text-2xl font-semibold text-slate-900">{stat.value}</div>
                <div
                  className={`inline-flex items-baseline px-2.5 py-0.5 rounded-full text-sm font-medium ${
                    stat.changeType === 'increase'
                      ? 'bg-green-100 text-green-800'
                      : stat.changeType === 'decrease'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-slate-100 text-slate-800'
                  }`}
                >
                  {stat.change}
                </div>
              </dd>
            </div>
          ))}
        </div>
        <div>
          <h2 className="text-lg font-medium text-slate-900 mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {businessQuickActions.map((action) => (
              <Link
                key={action.name}
                to={action.href}
                className="relative group bg-white p-6 rounded-lg border border-slate-200 hover:border-primary-300 hover:shadow-md transition-all"
              >
                <div className="text-3xl mb-3">{action.icon}</div>
                <h3 className="text-base font-medium text-slate-900 group-hover:text-primary-600">{action.name}</h3>
                <p className="mt-1 text-sm text-slate-500">{action.description}</p>
              </Link>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // ─── Residential Dashboard ────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-500">Loading dashboard...</div>
      </div>
    )
  }

  if (locations.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">Residential Dashboard</h1>
        <div className="bg-white rounded-lg border border-slate-200 p-8 text-center">
          <p className="text-slate-500 mb-4">No NMI data found. Upload your meter data or an invoice to get started.</p>
          <Link
            to="/upload"
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
          >
            Upload Data
          </Link>
        </div>
      </div>
    )
  }

  const invoiceTotal =
    summary && summary.invoice_total > 0 ? `$${summary.invoice_total.toFixed(2)}` : '--'
  const usageKwh =
    summary && summary.usage_kwh > 0 ? `${summary.usage_kwh.toFixed(2)} kWh` : '--'
  const billingPeriod =
    summary?.billing_period_start && summary?.billing_period_end
      ? `${summary.billing_period_start} to ${summary.billing_period_end}`
      : '--'
  const billingGaps = summary?.billing_gaps ?? []
  const hasSolar = summary ? summary.solar_export_kwh > 0 : false
  const retailerInfo = primaryAssignment?.retailer_name ?? '--'
  const tariffCode = primaryAssignment?.network_tariff_code ?? null

  const residentialQuickActions = [
    { name: 'Meter Data', description: 'Upload household consumption data', href: '/upload?stage=meter' },
    { name: 'Invoice Upload', description: 'Parse your bill and extract charges', href: '/upload?stage=invoice' },
    { name: 'Run Bill Check', description: 'Compare charged vs expected costs', href: '/reconciliation' },
    { name: 'Plan Emulator', description: 'Emulate costs on other plans', href: '/emulator' },
    { name: 'Best Plan Summary', description: 'Get recommendation from your usage', href: '/summary' },
    { name: 'Network Tariffs', description: 'Browse network tariffs and TOU', href: '/network' },
  ]

  return (
    <div className="space-y-6">
      {/* Header: NMI, address, retailer/plan */}
      <div className="bg-white rounded-lg border border-slate-200 px-6 py-4">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 className="text-xl font-bold text-slate-900">NMI {primary.nmi}</h1>
          <span className="text-sm text-slate-500">{primary.service_address ?? 'Address unavailable'}</span>
          {primaryAssignment?.retailer_name && (
            <span className="text-sm text-primary-600 font-medium">{primaryAssignment.retailer_name}</span>
          )}
        </div>
      </div>

      {/* Stat cards row */}
      <div className={`grid grid-cols-1 gap-4 sm:grid-cols-2 ${hasSolar ? 'lg:grid-cols-5' : 'lg:grid-cols-4'}`}>
        <div className="bg-white rounded-lg border border-slate-200 px-5 py-4">
          <div className="text-sm font-medium text-slate-500">Invoice Total</div>
          <div className="mt-1 text-2xl font-semibold text-slate-900">{invoiceTotal}</div>
          {summary && summary.invoices.length > 1 && (
            <div className="mt-1 text-xs text-slate-400">{summary.invoices.length} invoices</div>
          )}
        </div>
        <div className="bg-white rounded-lg border border-slate-200 px-5 py-4">
          <div className="text-sm font-medium text-slate-500">Total Usage</div>
          <div className="mt-1 text-2xl font-semibold text-slate-900">{usageKwh}</div>
          {summary && summary.controlled_load_kwh > 0 && (
            <div className="mt-1 text-xs text-slate-400">
              incl. {summary.controlled_load_kwh.toFixed(2)} kWh controlled load
            </div>
          )}
        </div>
        <div className="bg-white rounded-lg border border-slate-200 px-5 py-4">
          <div className="text-sm font-medium text-slate-500">Billing Period</div>
          <div className="mt-1 text-lg font-semibold text-slate-900">{billingPeriod}</div>
          {billingGaps.length > 0 && (
            <div className="mt-1 space-y-0.5">
              {billingGaps.map((gap, i) => (
                <div key={i} className="text-xs font-medium text-amber-600">
                  Gap: {gap.gap_start} to {gap.gap_end}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="bg-white rounded-lg border border-slate-200 px-5 py-4">
          <div className="text-sm font-medium text-slate-500">Retailer / Tariff</div>
          <div className="mt-1 text-lg font-semibold text-slate-900">
            {retailerInfo}
            {tariffCode && <span className="ml-2 text-sm font-normal text-slate-400">{tariffCode}</span>}
          </div>
        </div>
        {hasSolar && (
          <div className="bg-white rounded-lg border border-slate-200 px-5 py-4">
            <div className="text-sm font-medium text-slate-500">Solar Export</div>
            <div className="mt-1 text-2xl font-semibold text-green-600">
              {summary!.solar_export_kwh.toFixed(2)} kWh
            </div>
          </div>
        )}
      </div>

      {/* Two-column: Invoice summary + Map */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Invoice & Meter Summary */}
        <div className="bg-white rounded-lg border border-slate-200 p-6">
          <h2 className="text-lg font-medium text-slate-900 mb-4">Invoice & Meter Summary</h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Billing Period</dt>
              <dd className="font-medium text-slate-900">{billingPeriod}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Total Charges</dt>
              <dd className="font-medium text-slate-900">{invoiceTotal}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Usage (excl. solar)</dt>
              <dd className="font-medium text-slate-900">{usageKwh}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Retailer</dt>
              <dd className="font-medium text-slate-900">{retailerInfo}</dd>
            </div>
          </dl>

          {summary && summary.invoices.length > 0 && (
            <div className="mt-5 border-t border-slate-100 pt-4">
              <h3 className="text-sm font-medium text-slate-700 mb-2">Invoices ({summary.invoices.length})</h3>
              <div className="space-y-2">
                {summary.invoices.map((inv, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="text-slate-500">
                      {inv.invoice_number ?? `Invoice ${i + 1}`}
                      <span className="ml-1 text-slate-400">
                        ({inv.billing_period_start} to {inv.billing_period_end})
                      </span>
                    </span>
                    <span className="font-medium text-slate-900">${inv.total.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* NMI Map (compact) */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h2 className="text-lg font-medium text-slate-900 mb-3">NMI Location</h2>
          <NmiMapCompact locations={locations} />
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-medium text-slate-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {residentialQuickActions.map((action) => (
            <Link
              key={action.name}
              to={action.href}
              className="relative group bg-white p-5 rounded-lg border border-slate-200 hover:border-primary-300 hover:shadow-md transition-all"
            >
              <h3 className="text-base font-medium text-slate-900 group-hover:text-primary-600">{action.name}</h3>
              <p className="mt-1 text-sm text-slate-500">{action.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
