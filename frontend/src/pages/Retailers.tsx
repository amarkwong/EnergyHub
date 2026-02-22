import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import EntityLogo from '../components/EntityLogo'

type Retailer = {
  slug: string
  name: string
  states?: string[]
}

type FeedInTariffEntry = {
  unit_price_cents_per_kwh: number
  name?: string | null
  tier_min_kwh?: number | null
  tier_max_kwh?: number | null
}

type TouRate = {
  name: string
  rate_cents_per_kwh?: number | null
  start_time?: string | null
  end_time?: string | null
  days?: number[] | null
}

type EnergyPlan = {
  idx: number
  retailer_slug: string
  retailer: string
  plan_name: string
  tariff_type: string
  customer_type?: string | null
  effective_from?: string | null
  daily_supply_charge_cents: number
  usage_rate_cents_per_kwh?: number | null
  tou_rates: TouRate[]
  feed_in_tariffs?: FeedInTariffEntry[]
  distributors?: string[]
  state?: string | null
  source_url?: string | null
}

type CatalogStatus = {
  generated_at_utc?: string | null
  retailer_count: number
  plan_count: number
}

type HourlyDataPoint = {
  hour: number
  hourLabel: string
  rate: number
  feedIn1?: number
  feedIn2?: number
}

const PERIOD_COLORS: Record<string, string> = {
  peak: '#ef4444',
  shoulder: '#f59e0b',
  off_peak: '#22c55e',
  anytime: '#6366f1',
}

const FEED_IN_COLORS = ['#f97316', '#fdba74'] // orange-500, orange-300

function formatTime(raw: string) {
  return raw.slice(0, 5)
}

/** Parse hour from time string, rounding up if minutes > 0 (handles CDR's ":59" end times). */
function toEndHour(raw: string): number {
  const parts = raw.split(':')
  const hour = Number.parseInt(parts[0], 10)
  const minutes = parts.length > 1 ? Number.parseInt(parts[1], 10) : 0
  return minutes > 0 ? hour + 1 : hour
}

function toStartHour(raw: string): number {
  return Number.parseInt(raw.split(':')[0], 10)
}

function isWithinPeriod(hour: number, start: number, end: number) {
  if (start === end) return true
  if (start < end) return hour >= start && hour < end
  return hour >= start || hour < end
}

/** Coerce Decimal string or number to a finite number, or null. */
function num(v: number | string | null | undefined): number | null {
  if (v == null) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function buildHourlyRateData(
  rates: TouRate[],
  flatRate: number | string | null,
  feedInTariffs?: FeedInTariffEntry[],
): HourlyDataPoint[] {
  const sorted = [...rates].sort((a, b) => a.name.localeCompare(b.name))
  const baseFlatRate = num(flatRate) ?? 0

  // Deduplicate feed-in tariffs: keep retailer FiT entries, skip legacy government schemes
  const feedIns = (feedInTariffs ?? [])
    .filter((f) => num(f.unit_price_cents_per_kwh) != null)
    .filter((f) => {
      const name = (f.name ?? '').toLowerCase()
      return !name.includes('solar bonus') && !name.includes('premium fit')
    })

  const output: HourlyDataPoint[] = []
  for (let hour = 0; hour < 24; hour += 1) {
    let rate = baseFlatRate
    for (const r of sorted) {
      if (!r.start_time || !r.end_time) continue
      const start = toStartHour(r.start_time)
      const end = toEndHour(r.end_time)
      const periodRate = num(r.rate_cents_per_kwh)
      if (isWithinPeriod(hour, start, end) && periodRate != null) {
        rate = periodRate
        break
      }
    }
    const point: HourlyDataPoint = { hour, hourLabel: `${String(hour).padStart(2, '0')}:00`, rate }
    if (feedIns.length >= 1) point.feedIn1 = num(feedIns[0].unit_price_cents_per_kwh) ?? undefined
    if (feedIns.length >= 2) point.feedIn2 = num(feedIns[1].unit_price_cents_per_kwh) ?? undefined
    output.push(point)
  }
  return output
}

function feedInLabel(entry: FeedInTariffEntry): string {
  const rate = num(entry.unit_price_cents_per_kwh)
  if (rate == null) return ''
  let label = `${rate.toFixed(1)}c/kWh`
  if (entry.tier_max_kwh != null) label += ` (first ${entry.tier_max_kwh}kWh)`
  else if (entry.tier_min_kwh != null) label += ` (after ${entry.tier_min_kwh}kWh)`
  return label
}

/** Derive a summary feed-in rate from the tariff list (first non-legacy entry). */
function primaryFeedInRate(tariffs?: FeedInTariffEntry[]): number | null {
  if (!tariffs) return null
  for (const f of tariffs) {
    const name = (f.name ?? '').toLowerCase()
    if (name.includes('solar bonus') || name.includes('premium fit')) continue
    const rate = num(f.unit_price_cents_per_kwh)
    if (rate != null) return rate
  }
  return null
}

export default function Retailers() {
  const [selectedRetailer, setSelectedRetailer] = useState<string | null>(null)
  const [selectedPlanIdx, setSelectedPlanIdx] = useState<number | null>(null)
  const [selectedState, setSelectedState] = useState<string | null>(null)

  const { data: catalogStatus } = useQuery({
    queryKey: ['catalog-status'],
    queryFn: async () => {
      const response = await api.get('/api/energy-plans/status')
      return response.data as CatalogStatus
    },
  })

  const { data: retailers = [], isLoading: retailersLoading } = useQuery({
    queryKey: ['retailers'],
    queryFn: async () => {
      const response = await api.get('/api/energy-plans/retailers')
      return response.data as Retailer[]
    },
  })

  const states = useMemo(() => {
    const all = new Set<string>()
    for (const r of retailers) {
      for (const s of r.states ?? []) all.add(s)
    }
    return [...all].sort()
  }, [retailers])

  const filteredRetailers = useMemo(() => {
    if (!selectedState) return retailers
    return retailers.filter((r) => r.states?.includes(selectedState))
  }, [retailers, selectedState])

  const activeRetailer = useMemo(() => {
    if (selectedRetailer) {
      const inFiltered = filteredRetailers.some((r) => r.slug === selectedRetailer)
      if (inFiltered) return selectedRetailer
    }
    return filteredRetailers[0]?.slug ?? null
  }, [selectedRetailer, filteredRetailers])

  const { data: plans = [], isLoading: plansLoading } = useQuery({
    queryKey: ['retailer-plans', activeRetailer],
    queryFn: async () => {
      const response = await api.get('/api/energy-plans/plans', {
        params: { retailer_slug: activeRetailer },
      })
      return response.data as EnergyPlan[]
    },
    enabled: !!activeRetailer,
  })

  const activePlanIdx = useMemo(() => selectedPlanIdx ?? plans[0]?.idx ?? null, [selectedPlanIdx, plans])

  // Deduplicate plans: one entry per (plan_name, tariff_type, first distributor)
  const uniquePlans = useMemo(() => {
    const seen = new Map<string, EnergyPlan>()
    for (const plan of plans) {
      const dist = plan.distributors?.[0] ?? ''
      const key = `${plan.plan_name}|${plan.tariff_type}|${dist}`
      if (!seen.has(key)) seen.set(key, plan)
    }
    return Array.from(seen.values())
  }, [plans])

  const activePlan = useMemo(() => plans.find((p) => p.idx === activePlanIdx) ?? null, [plans, activePlanIdx])

  const hourlyRateData = useMemo(() => {
    if (!activePlan) return []
    return buildHourlyRateData(
      activePlan.tou_rates ?? [],
      activePlan.usage_rate_cents_per_kwh ?? null,
      activePlan.feed_in_tariffs,
    )
  }, [activePlan])

  const activeFeedIns = useMemo(() => {
    return (activePlan?.feed_in_tariffs ?? [])
      .filter((f) => num(f.unit_price_cents_per_kwh) != null)
      .filter((f) => {
        const name = (f.name ?? '').toLowerCase()
        return !name.includes('solar bonus') && !name.includes('premium fit')
      })
  }, [activePlan])

  const lastUpdated = catalogStatus?.generated_at_utc
    ? new Date(catalogStatus.generated_at_utc).toLocaleDateString('en-AU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : null

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Retailers & Energy Plans</h1>
          <p className="mt-1 text-sm text-slate-500">
            Select a retailer to review plans and rates.
          </p>
        </div>
        {lastUpdated && (
          <span className="text-xs text-slate-400">
            Last updated: {lastUpdated}
          </span>
        )}
      </div>

      {states.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedState(null)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium ${
              selectedState === null ? 'bg-slate-800 text-white' : 'bg-white border border-slate-300 text-slate-700'
            }`}
          >
            All States
          </button>
          {states.map((state) => (
            <button
              key={state}
              onClick={() => setSelectedState(state)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium ${
                selectedState === state ? 'bg-slate-800 text-white' : 'bg-white border border-slate-300 text-slate-700'
              }`}
            >
              {state}
            </button>
          ))}
        </div>
      )}

      {retailersLoading ? (
        <div className="text-slate-500">Loading retailers...</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {filteredRetailers.map((retailer) => (
            <button
              key={retailer.slug}
              onClick={() => setSelectedRetailer(retailer.slug)}
              className={`h-24 rounded-2xl border px-3 ${
                activeRetailer === retailer.slug
                  ? 'border-primary-500 bg-primary-50 shadow-sm'
                  : 'border-slate-300 bg-white hover:border-slate-400'
              }`}
              aria-label={retailer.name}
              title={retailer.name}
            >
              <div className="flex h-full items-center justify-center">
                <EntityLogo name={retailer.name} type="retailer" className="h-12 w-auto max-w-full" />
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Energy Plan Cards */}
      <div>
        <h2 className="text-lg font-medium text-slate-900">Energy Plans</h2>
        {plansLoading ? (
          <p className="mt-3 text-slate-500">Loading plans...</p>
        ) : uniquePlans.length === 0 ? (
          <p className="mt-3 text-slate-500">No plans found.</p>
        ) : (
          <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
            {uniquePlans.map((plan) => {
              const touRates = plan.tou_rates.filter((r) => r.name !== 'anytime')
              const usageRate = num(plan.usage_rate_cents_per_kwh)
              const hasRates = plan.tou_rates.some((r) => num(r.rate_cents_per_kwh) != null) || usageRate != null
              const chartData = hasRates ? buildHourlyRateData(plan.tou_rates, plan.usage_rate_cents_per_kwh ?? null, plan.feed_in_tariffs) : null
              const isActive = activePlanIdx === plan.idx
              const hasFeedIn = chartData != null && chartData.some((d) => d.feedIn1 != null)
              const feedIn = primaryFeedInRate(plan.feed_in_tariffs)

              return (
                <button
                  key={plan.idx}
                  onClick={() => setSelectedPlanIdx(plan.idx)}
                  className={`w-full text-left rounded-lg border bg-white p-4 transition-shadow hover:shadow-md ${
                    isActive ? 'border-primary-500 ring-1 ring-primary-500' : 'border-slate-200'
                  }`}
                >
                  {/* Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-slate-900 truncate">{plan.plan_name}</div>
                      <div className="mt-0.5 text-xs text-slate-500">
                        {plan.tariff_type.toUpperCase()} | Effective {plan.effective_from}
                        {plan.distributors?.[0] ? ` | ${plan.distributors[0]}` : ''}
                      </div>
                    </div>
                    <span
                      className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
                        plan.tariff_type === 'tou'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-indigo-100 text-indigo-700'
                      }`}
                    >
                      {plan.tariff_type === 'tou' ? 'Time of Use' : 'Flat'}
                    </span>
                  </div>

                  {/* Key rates row */}
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                    <span className="text-slate-600">
                      Daily <span className="font-medium text-slate-900">{Number(plan.daily_supply_charge_cents).toFixed(2)}c</span>/day
                    </span>
                    {usageRate != null && (
                      <span className="text-slate-600">
                        Usage <span className="font-medium text-slate-900">{usageRate.toFixed(2)}c</span>/kWh
                      </span>
                    )}
                    {feedIn != null && (
                      <span className="text-slate-600">
                        Feed-in <span className="font-medium text-emerald-700">{feedIn.toFixed(1)}c</span>/kWh
                      </span>
                    )}
                  </div>

                  {/* TOU rate pills + mini chart */}
                  {touRates.length > 0 && (
                    <div className="mt-3 flex gap-3">
                      <div className="flex-1 flex flex-wrap gap-1.5">
                        {touRates.map((rate, i) => (
                          <span
                            key={`${rate.name}-${i}`}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-slate-50 border border-slate-150 text-slate-700"
                          >
                            <span
                              className="w-1.5 h-1.5 rounded-full"
                              style={{ backgroundColor: PERIOD_COLORS[rate.name] ?? '#94a3b8' }}
                            />
                            {rate.name.replace('_', '-')}{' '}
                            {num(rate.rate_cents_per_kwh) != null && (
                              <span className="font-medium">{num(rate.rate_cents_per_kwh)!.toFixed(2)}c</span>
                            )}
                            {rate.start_time && rate.end_time && (
                              <span className="text-slate-400">
                                {formatTime(rate.start_time)}{'\u2013'}{formatTime(rate.end_time)}
                              </span>
                            )}
                          </span>
                        ))}
                      </div>
                      {/* Mini chart thumbnail */}
                      {chartData && (
                        <div className="w-32 h-16 shrink-0">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 0, left: 0 }}>
                              <defs>
                                <linearGradient id={`grad-${plan.idx}`} x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="0%" stopColor="#16a34a" stopOpacity={0.3} />
                                  <stop offset="100%" stopColor="#16a34a" stopOpacity={0.05} />
                                </linearGradient>
                              </defs>
                              <Area
                                type="stepAfter"
                                dataKey="rate"
                                stroke="#16a34a"
                                strokeWidth={1.5}
                                fill={`url(#grad-${plan.idx})`}
                                isAnimationActive={false}
                              />
                              {hasFeedIn && (
                                <Area
                                  type="stepAfter"
                                  dataKey="feedIn1"
                                  stroke={FEED_IN_COLORS[0]}
                                  strokeWidth={1}
                                  strokeDasharray="3 2"
                                  fill="none"
                                  isAnimationActive={false}
                                />
                              )}
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      )}
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Full Hourly Rate Chart for selected plan */}
      {activePlan && (
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-lg font-medium text-slate-900">Hourly Rate View</h2>
          <p className="text-sm text-slate-500 mt-1">
            {activePlan.plan_name}
            {activePlan.distributors?.[0] ? ` | ${activePlan.distributors[0]}` : ''}
          </p>
          <div className="h-72 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={hourlyRateData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="hourLabel" tick={{ fontSize: 12 }} />
                <YAxis unit="c" tick={{ fontSize: 12 }} domain={[0, 'auto']} />
                <Tooltip
                  formatter={(value: number | string, name: string) => {
                    const n = Number(value)
                    if (!Number.isFinite(n)) return ['N/A', name]
                    return [`${n.toFixed(2)} c/kWh`, name]
                  }}
                  labelFormatter={(label) => `Hour ${label}`}
                />
                <Legend />
                <Line
                  type="stepAfter"
                  dataKey="rate"
                  name="Usage rate"
                  stroke="#16a34a"
                  strokeWidth={2.5}
                  dot={false}
                />
                {activeFeedIns.length >= 1 && (
                  <Line
                    type="stepAfter"
                    dataKey="feedIn1"
                    name={`Export ${feedInLabel(activeFeedIns[0])}`}
                    stroke={FEED_IN_COLORS[0]}
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    dot={false}
                  />
                )}
                {activeFeedIns.length >= 2 && (
                  <Line
                    type="stepAfter"
                    dataKey="feedIn2"
                    name={`Export ${feedInLabel(activeFeedIns[1])}`}
                    stroke={FEED_IN_COLORS[1]}
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    dot={false}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
