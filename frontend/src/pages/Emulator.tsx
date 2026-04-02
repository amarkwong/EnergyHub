import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import { api } from '../api/client'
import EntityLogo from '../components/EntityLogo'

type Nmi = { id: number; nmi: string; label?: string | null }

type Retailer = { id: number; name: string; slug: string }

type DashboardSummary = {
  invoice_total: number
  billing_period_start?: string | null
  billing_period_end?: string | null
}

type PeriodUsage = {
  period_name: string
  kwh: number
  rate_cents_per_kwh: number
  cost_dollars: number
}

type PlanCost = {
  retailer: string
  retailer_slug: string
  plan_name: string
  tariff_type: string
  distributor: string | null
  state: string | null
  supply_charge_dollars: number
  usage_charge_dollars: number
  feed_in_credit_dollars: number
  subtotal_dollars: number
  gst_dollars: number
  total_dollars: number
  period_breakdown: PeriodUsage[]
  feed_in_rate_cents: number | null
  feed_in_kwh: number
  delta_vs_current_dollars: number | null
  delta_vs_current_percent: number | null
  rank: number
}

type UsageInsights = {
  peak_usage_pct: number
  offpeak_usage_pct: number
  top_usage_hours: number[]
  tou_likely_beneficial: boolean
}

type EmulatorResponse = {
  nmi: string
  billing_start: string
  billing_end: string
  billing_days: number
  total_import_kwh: number
  total_export_kwh: number
  interval_count: number
  invoiced_total: number | null
  plans: PlanCost[]
  cheapest_plan_name: string
  cheapest_total: number
  potential_annual_saving: number | null
  usage_insights: UsageInsights | null
}

type SortField = 'total' | 'usage' | 'supply' | 'delta'

const PERIOD_COLORS: Record<string, string> = {
  peak: '#ef4444',
  shoulder: '#f59e0b',
  off_peak: '#22c55e',
  usage: '#6366f1',
}

function toHour(raw: string) {
  return Number.parseInt(raw.split(':')[0], 10)
}

function isWithinPeriod(hour: number, start: number, end: number) {
  if (start === end) return true
  if (start < end) return hour >= start && hour < end
  return hour >= start || hour < end
}

function toEndHour(raw: string): number {
  const parts = raw.split(':')
  const hour = Number.parseInt(parts[0], 10)
  const minutes = parts.length > 1 ? Number.parseInt(parts[1], 10) : 0
  return minutes > 0 ? hour + 1 : hour
}

function buildHourlyRateData(
  periods: Array<{ name: string; start_time?: string; end_time?: string; rate_cents_per_kwh?: number }>,
  flatRate: number | null,
) {
  const output = []
  for (let hour = 0; hour < 24; hour += 1) {
    let rate = flatRate ?? 0
    for (const period of periods) {
      if (!period.start_time || !period.end_time) continue
      const start = toHour(period.start_time)
      const end = toEndHour(period.end_time)
      if (isWithinPeriod(hour, start, end) && period.rate_cents_per_kwh != null) {
        rate = period.rate_cents_per_kwh
        break
      }
    }
    output.push({ hourLabel: `${String(hour).padStart(2, '0')}:00`, rate })
  }
  return output
}

function dollars(v: number) {
  return `$${v.toFixed(2)}`
}

function deltaLabel(v: number | null) {
  if (v == null) return '--'
  if (v === 0) return '--'
  const sign = v > 0 ? '+' : ''
  return `${sign}$${v.toFixed(2)}`
}

export default function Emulator() {
  const [selectedNmi, setSelectedNmi] = useState<string>('')
  const [billingStart, setBillingStart] = useState('')
  const [billingEnd, setBillingEnd] = useState('')
  const [retailerFilter, setRetailerFilter] = useState<string[]>([])
  const [expandedRow, setExpandedRow] = useState<number | null>(null)
  const [sortField, setSortField] = useState<SortField>('total')
  const [planSearch, setPlanSearch] = useState('')

  // Fetch NMIs
  const { data: nmis = [] } = useQuery({
    queryKey: ['account-nmis'],
    queryFn: async () => {
      const res = await api.get('/api/account/nmis')
      return res.data as Nmi[]
    },
  })

  // Fetch retailers for filter
  const { data: retailers = [] } = useQuery({
    queryKey: ['retailers'],
    queryFn: async () => {
      const res = await api.get('/api/energy-plans/retailers')
      return res.data as Retailer[]
    },
  })

  // Fetch dashboard summary for billing period prefill
  const { data: summary } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: async () => {
      const res = await api.get('/api/account/dashboard-summary')
      return res.data as DashboardSummary
    },
  })

  // Set default NMI on mount
  useEffect(() => {
    if (nmis.length > 0 && !selectedNmi) {
      setSelectedNmi(nmis[0].nmi)
    }
  }, [nmis]) // eslint-disable-line react-hooks/exhaustive-deps

  // Prefill billing dates from dashboard summary
  useEffect(() => {
    if (summary?.billing_period_start && !billingStart) {
      setBillingStart(summary.billing_period_start)
    }
    if (summary?.billing_period_end && !billingEnd) {
      setBillingEnd(summary.billing_period_end)
    }
  }, [summary]) // eslint-disable-line react-hooks/exhaustive-deps

  // Emulation mutation
  const mutation = useMutation({
    mutationFn: async () => {
      const res = await api.post('/api/emulator/compare', {
        nmi: selectedNmi,
        billing_start: billingStart,
        billing_end: billingEnd,
        retailer_filter: retailerFilter.length > 0 ? retailerFilter : null,
      })
      return res.data as EmulatorResponse
    },
  })

  const result = mutation.data

  // Sort and filter plans
  const sortedPlans = useMemo(() => {
    if (!result) return []
    let plans = [...result.plans]

    // Fuzzy search: all query words must appear in retailer or plan name
    if (planSearch.trim()) {
      const words = planSearch.trim().toLowerCase().split(/\s+/)
      plans = plans.filter((p) => {
        const haystack = `${p.retailer} ${p.plan_name}`.toLowerCase()
        return words.every((w) => haystack.includes(w))
      })
    }

    switch (sortField) {
      case 'total':
        plans.sort((a, b) => a.total_dollars - b.total_dollars)
        break
      case 'usage':
        plans.sort((a, b) => a.usage_charge_dollars - b.usage_charge_dollars)
        break
      case 'supply':
        plans.sort((a, b) => a.supply_charge_dollars - b.supply_charge_dollars)
        break
      case 'delta':
        plans.sort((a, b) => (a.delta_vs_current_dollars ?? 999) - (b.delta_vs_current_dollars ?? 999))
        break
    }
    return plans
  }, [result, sortField, planSearch])

  const canRun = selectedNmi && billingStart && billingEnd

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Plan Emulator</h1>
        <p className="mt-1 text-sm text-slate-500">
          Compare {retailers.length > 0 ? '200+' : ''} retail plans against your actual meter data.
        </p>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* NMI */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">NMI</label>
            <select
              value={selectedNmi}
              onChange={(e) => setSelectedNmi(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Select NMI</option>
              {nmis.map((n) => (
                <option key={n.nmi} value={n.nmi}>
                  {n.nmi} {n.label ? `(${n.label})` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Billing Start */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Start Date</label>
            <input
              type="date"
              value={billingStart}
              onChange={(e) => setBillingStart(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          {/* Billing End */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">End Date</label>
            <input
              type="date"
              value={billingEnd}
              onChange={(e) => setBillingEnd(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* Retailer Filter */}
        {retailers.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Filter Retailers</label>
            <div className="flex flex-wrap gap-1.5">
              {retailers.map((r) => {
                const active = retailerFilter.includes(r.slug)
                return (
                  <button
                    key={r.slug}
                    onClick={() =>
                      setRetailerFilter((prev) =>
                        active ? prev.filter((s) => s !== r.slug) : [...prev, r.slug],
                      )
                    }
                    className={`text-xs px-2 py-1 rounded-md border ${
                      active
                        ? 'bg-primary-100 border-primary-400 text-primary-700'
                        : 'bg-white border-slate-300 text-slate-600'
                    }`}
                  >
                    {r.name}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={() => mutation.mutate()}
            disabled={!canRun || mutation.isPending}
            className="px-5 py-2.5 rounded-md bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {mutation.isPending ? 'Running...' : 'Run Emulation'}
          </button>
          {mutation.isError && (
            <span className="text-sm text-red-600">
              {(mutation.error as any)?.response?.data?.detail || 'Emulation failed'}
            </span>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      {result && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="text-sm text-slate-500">Cheapest Plan</div>
            <div className="mt-1 font-semibold text-slate-900 truncate">{result.cheapest_plan_name}</div>
            <div className="mt-1 text-2xl font-bold text-emerald-600">{dollars(result.cheapest_total)}</div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="text-sm text-slate-500">Your Invoiced Cost</div>
            {result.invoiced_total != null ? (
              <div className="mt-1 text-2xl font-bold text-slate-700">{dollars(result.invoiced_total)}</div>
            ) : (
              <div className="mt-1 text-sm text-slate-400">No invoices found for this period</div>
            )}
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="text-sm text-slate-500">Potential Annual Saving</div>
            {result.potential_annual_saving != null ? (
              <div className="mt-1 text-2xl font-bold text-emerald-600">
                {dollars(result.potential_annual_saving)}/yr
              </div>
            ) : (
              <div className="mt-1 text-sm text-slate-400">Upload invoices to compare</div>
            )}
            <div className="mt-1 text-xs text-slate-500">
              {result.interval_count} intervals | {result.billing_days} days | {result.total_import_kwh.toFixed(1)} kWh import
              {result.total_export_kwh > 0 ? ` | ${result.total_export_kwh.toFixed(1)} kWh export` : ''}
            </div>
          </div>
        </div>
      )}

      {/* Usage Insights */}
      {result?.usage_insights && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="text-sm font-medium text-slate-700 mb-3">Consumption Insights</div>
          <div className="flex flex-wrap gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400 shrink-0" />
              <span className="text-slate-600">Peak usage (weekday 7–22h):</span>
              <span className="font-semibold text-slate-900">{result.usage_insights.peak_usage_pct}%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shrink-0" />
              <span className="text-slate-600">Off-peak:</span>
              <span className="font-semibold text-slate-900">{result.usage_insights.offpeak_usage_pct}%</span>
            </div>
            {result.usage_insights.top_usage_hours.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-slate-600">Busiest hours:</span>
                <span className="font-semibold text-slate-900">
                  {result.usage_insights.top_usage_hours.map((h) => `${String(h).padStart(2, '0')}:00`).join(', ')}
                </span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  result.usage_insights.tou_likely_beneficial
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-slate-100 text-slate-600'
                }`}
              >
                {result.usage_insights.tou_likely_beneficial
                  ? 'TOU plans likely beneficial'
                  : 'Flat-rate plans likely better'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Results Table */}
      {result && (
        <div className="bg-white rounded-lg border border-slate-200">
          {/* Sort + Search controls */}
          <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-slate-100">
            <span className="text-sm text-slate-500">Sort by:</span>
            {([
              ['total', 'Total'],
              ['delta', 'Savings'],
              ['usage', 'Usage'],
              ['supply', 'Supply'],
            ] as [SortField, string][]).map(([field, label]) => (
              <button
                key={field}
                onClick={() => setSortField(field)}
                className={`text-xs px-2.5 py-1 rounded-md ${
                  sortField === field
                    ? 'bg-slate-800 text-white'
                    : 'bg-white border border-slate-300 text-slate-600'
                }`}
              >
                {label}
              </button>
            ))}
            <div className="ml-auto flex items-center gap-2">
              <input
                type="text"
                value={planSearch}
                onChange={(e) => setPlanSearch(e.target.value)}
                placeholder="Search plans..."
                className="text-sm rounded-md border border-slate-300 px-3 py-1 w-48 focus:outline-none focus:ring-1 focus:ring-primary-400"
              />
              <span className="text-sm text-slate-500 whitespace-nowrap">
                {sortedPlans.length}{planSearch ? ` / ${result.plans.length}` : ''} plans
              </span>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm table-fixed">
              <colgroup>
                <col className="w-10" />
                <col className="w-10" />
                <col className="w-28" />
                <col />
                <col className="w-14" />
                <col className="w-[88px]" />
                <col className="w-[88px]" />
                <col className="w-[88px]" />
                <col className="w-[96px]" />
                <col className="w-[96px]" />
              </colgroup>
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                  <th className="px-3 py-2">#</th>
                  <th className="px-1 py-2"></th>
                  <th className="px-2 py-2">Retailer</th>
                  <th className="px-2 py-2">Plan</th>
                  <th className="px-2 py-2">Type</th>
                  <th className="px-2 py-2 text-right">Supply</th>
                  <th className="px-2 py-2 text-right">Usage</th>
                  <th className="px-2 py-2 text-right">Feed-in</th>
                  <th className="px-2 py-2 text-right">Total</th>
                  <th className="px-2 py-2 text-right">vs Invoiced</th>
                </tr>
              </thead>
              <tbody>
                {sortedPlans.map((plan, idx) => {
                  const isExpanded = expandedRow === idx
                  const touRateData =
                    plan.tariff_type === 'tou' && plan.period_breakdown.length > 1
                      ? buildHourlyRateData(
                          plan.period_breakdown.map((pb) => ({
                            name: pb.period_name,
                            rate_cents_per_kwh: pb.rate_cents_per_kwh,
                          })),
                          plan.period_breakdown[0]?.rate_cents_per_kwh ?? null,
                        )
                      : null

                  return (
                    <tr
                      key={`${plan.retailer_slug}-${plan.plan_name}-${idx}`}
                      className="group"
                    >
                      <td colSpan={10} className="p-0">
                        {/* Main row */}
                        <div
                          role="button"
                          tabIndex={0}
                          onClick={() => setExpandedRow(isExpanded ? null : idx)}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setExpandedRow(isExpanded ? null : idx) }}
                          className={`w-full cursor-pointer border-b transition-colors ${
                            'border-slate-50 hover:bg-slate-50'
                          }`}
                        >
                          <div className="flex items-center">
                            <span className="px-3 py-2.5 w-10 text-xs text-slate-400 shrink-0 text-center">{plan.rank}</span>
                            <span className="px-1 py-2.5 w-10 shrink-0">
                              <EntityLogo name={plan.retailer} type="retailer" className="h-6 w-6" />
                            </span>
                            <span className="px-2 py-2.5 w-28 truncate text-slate-700 shrink-0">{plan.retailer}</span>
                            <span className="px-2 py-2.5 flex-1 min-w-0 truncate font-medium text-slate-900">
                              {plan.plan_name}
                              {plan.distributor && (
                                <span className="ml-1 text-xs font-normal text-slate-400">
                                  ({plan.distributor})
                                </span>
                              )}
                            </span>
                            <span className="px-2 py-2.5 w-14 shrink-0 text-center">
                              <span
                                className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                                  plan.tariff_type === 'tou'
                                    ? 'bg-amber-100 text-amber-700'
                                    : 'bg-indigo-100 text-indigo-700'
                                }`}
                              >
                                {plan.tariff_type === 'tou' ? 'TOU' : 'Flat'}
                              </span>
                            </span>
                            <span className="px-2 py-2.5 w-[88px] text-right text-slate-600 shrink-0 tabular-nums">
                              {dollars(plan.supply_charge_dollars)}
                            </span>
                            <span className="px-2 py-2.5 w-[88px] text-right text-slate-600 shrink-0 tabular-nums">
                              {dollars(plan.usage_charge_dollars)}
                            </span>
                            <span className="px-2 py-2.5 w-[88px] text-right text-emerald-600 shrink-0 tabular-nums">
                              {plan.feed_in_credit_dollars > 0
                                ? `-${dollars(plan.feed_in_credit_dollars)}`
                                : '--'}
                            </span>
                            <span className="px-2 py-2.5 w-[96px] text-right font-semibold text-slate-900 shrink-0 tabular-nums">
                              {dollars(plan.total_dollars)}
                            </span>
                            <span
                              className={`px-2 py-2.5 w-[96px] text-right font-medium shrink-0 tabular-nums ${
                                plan.delta_vs_current_dollars != null && plan.delta_vs_current_dollars < 0
                                  ? 'text-emerald-600'
                                  : plan.delta_vs_current_dollars != null && plan.delta_vs_current_dollars > 0
                                    ? 'text-red-500'
                                    : 'text-slate-400'
                              }`}
                            >
                              {deltaLabel(plan.delta_vs_current_dollars)}
                            </span>
                          </div>
                        </div>

                        {/* Expanded breakdown */}
                        {isExpanded && (
                          <div className="px-4 py-3 bg-slate-50 border-b border-slate-100">
                            <div className="flex gap-6">
                              <div className="flex-1 space-y-1.5">
                                <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                                  Period Breakdown
                                </div>
                                {plan.period_breakdown.map((pb, pIdx) => (
                                  <div
                                    key={pIdx}
                                    className="flex items-center gap-3 text-sm"
                                  >
                                    <span
                                      className="w-2 h-2 rounded-full shrink-0"
                                      style={{
                                        backgroundColor:
                                          PERIOD_COLORS[pb.period_name] ?? '#94a3b8',
                                      }}
                                    />
                                    <span className="w-20 text-slate-600 capitalize">
                                      {pb.period_name.replace('_', ' ')}
                                    </span>
                                    <span className="w-24 text-slate-700 tabular-nums">
                                      {pb.kwh.toFixed(1)} kWh
                                    </span>
                                    <span className="w-20 text-slate-500 tabular-nums">
                                      @ {pb.rate_cents_per_kwh.toFixed(2)}c
                                    </span>
                                    <span className="font-medium text-slate-900 tabular-nums">
                                      {dollars(pb.cost_dollars)}
                                    </span>
                                  </div>
                                ))}
                                <div className="border-t border-slate-200 pt-1.5 mt-1.5 flex gap-4 text-xs text-slate-500">
                                  <span>Supply: {dollars(plan.supply_charge_dollars)}</span>
                                  {plan.feed_in_credit_dollars > 0 && (
                                    <span>
                                      Feed-in: -{dollars(plan.feed_in_credit_dollars)}
                                      {plan.feed_in_rate_cents != null && (
                                        <> ({plan.feed_in_rate_cents.toFixed(1)}c/kWh)</>
                                      )}
                                    </span>
                                  )}
                                  <span>GST: {dollars(plan.gst_dollars)}</span>
                                </div>
                              </div>

                              {/* Mini TOU chart */}
                              {touRateData && (
                                <div className="w-48 shrink-0">
                                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                                    Rate by Hour
                                  </div>
                                  <div className="h-20">
                                    <ResponsiveContainer width="100%" height="100%">
                                      <AreaChart
                                        data={touRateData}
                                        margin={{ top: 2, right: 2, bottom: 0, left: 0 }}
                                      >
                                        <defs>
                                          <linearGradient
                                            id={`emu-grad-${idx}`}
                                            x1="0"
                                            y1="0"
                                            x2="0"
                                            y2="1"
                                          >
                                            <stop offset="0%" stopColor="#16a34a" stopOpacity={0.3} />
                                            <stop
                                              offset="100%"
                                              stopColor="#16a34a"
                                              stopOpacity={0.05}
                                            />
                                          </linearGradient>
                                        </defs>
                                        <Area
                                          type="stepAfter"
                                          dataKey="rate"
                                          stroke="#16a34a"
                                          strokeWidth={1.5}
                                          fill={`url(#emu-grad-${idx})`}
                                          isAnimationActive={false}
                                        />
                                      </AreaChart>
                                    </ResponsiveContainer>
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
