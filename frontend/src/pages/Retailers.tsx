import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import EntityLogo from '../components/EntityLogo'

type Retailer = {
  id: number
  name: string
  slug: string
  source_url?: string | null
}

type FeedInTariffEntry = {
  unit_price_cents_per_kwh: number
  name?: string | null
  tier_min_kwh?: number | null
  tier_max_kwh?: number | null
}

type EnergyPlan = {
  id: number
  retailer: string
  retailer_slug: string
  plan_name: string
  network_provider?: string | null
  tariff_type: string
  effective_from: string
  daily_supply_charge_cents: number | string
  usage_rate_cents_per_kwh?: number | string | null
  feed_in_tariff_cents_per_kwh?: number | string | null
  feed_in_tariffs?: FeedInTariffEntry[]
}

type TouPeriod = {
  id: number
  name: string
  start_time: string
  end_time: string
  days_of_week: number[]
  rate_cents_per_kwh?: number | string | null
}

type TouDefinition = {
  id: number
  plan_id?: number | null
  name: string
  timezone: string
  effective_from: string
  periods: TouPeriod[]
}

type YearHistory = {
  year: number
  plans: EnergyPlan[]
  tou_definitions: TouDefinition[]
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
  periods: TouPeriod[],
  flatRate: number | string | null,
  feedInTariffs?: FeedInTariffEntry[],
): HourlyDataPoint[] {
  const sorted = [...periods].sort((a, b) => a.name.localeCompare(b.name))
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
    for (const period of sorted) {
      const start = toStartHour(period.start_time)
      const end = toEndHour(period.end_time)
      const periodRate = num(period.rate_cents_per_kwh)
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

export default function Retailers() {
  const queryClient = useQueryClient()
  const [selectedRetailer, setSelectedRetailer] = useState<string | null>(null)
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null)

  const refreshMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/api/energy-plans/refresh')
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['retailers'] })
      queryClient.invalidateQueries({ queryKey: ['retailer-plans'] })
      queryClient.invalidateQueries({ queryKey: ['retailer-tou'] })
      queryClient.invalidateQueries({ queryKey: ['retailer-history'] })
    },
  })

  const { data: retailers = [], isLoading: retailersLoading } = useQuery({
    queryKey: ['retailers'],
    queryFn: async () => {
      const response = await api.get('/api/energy-plans/retailers')
      return response.data as Retailer[]
    },
  })

  const activeRetailer = useMemo(() => {
    if (selectedRetailer) return selectedRetailer
    return retailers[0]?.slug ?? null
  }, [selectedRetailer, retailers])

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

  const activePlanId = useMemo(() => selectedPlanId ?? plans[0]?.id ?? null, [selectedPlanId, plans])

  const { data: touDefinitions = [] } = useQuery({
    queryKey: ['retailer-tou', activeRetailer],
    queryFn: async () => {
      const response = await api.get('/api/energy-plans/tou-definitions', {
        params: { scope_type: 'retailer', scope_key: activeRetailer },
      })
      return response.data as TouDefinition[]
    },
    enabled: !!activeRetailer,
  })

  const touByPlanId = useMemo(() => {
    const map = new Map<number, TouDefinition>()
    for (const def of touDefinitions) {
      if (def.plan_id != null) map.set(def.plan_id, def)
    }
    return map
  }, [touDefinitions])

  // Deduplicate plans: one entry per (plan_name, tariff_type)
  const uniquePlans = useMemo(() => {
    const seen = new Map<string, EnergyPlan>()
    for (const plan of plans) {
      const key = `${plan.plan_name}|${plan.tariff_type}`
      if (!seen.has(key)) seen.set(key, plan)
    }
    return Array.from(seen.values())
  }, [plans])

  const activePlan = useMemo(() => plans.find((p) => p.id === activePlanId) ?? null, [plans, activePlanId])
  const activeDefinition = useMemo(
    () => touDefinitions.find((d) => d.plan_id === activePlanId) ?? touDefinitions[0],
    [touDefinitions, activePlanId]
  )
  const hourlyRateData = useMemo(() => {
    return buildHourlyRateData(
      activeDefinition?.periods ?? [],
      activePlan?.usage_rate_cents_per_kwh ?? null,
      activePlan?.feed_in_tariffs,
    )
  }, [activeDefinition, activePlan])

  const activeFeedIns = useMemo(() => {
    return (activePlan?.feed_in_tariffs ?? [])
      .filter((f) => num(f.unit_price_cents_per_kwh) != null)
      .filter((f) => {
        const name = (f.name ?? '').toLowerCase()
        return !name.includes('solar bonus') && !name.includes('premium fit')
      })
  }, [activePlan])

  const { data: history = [] } = useQuery({
    queryKey: ['retailer-history', activeRetailer],
    queryFn: async () => {
      const response = await api.get('/api/energy-plans/history', {
        params: { retailer_slug: activeRetailer },
      })
      return response.data as YearHistory[]
    },
    enabled: !!activeRetailer,
  })

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Retailers & Energy Plans</h1>
          <p className="mt-1 text-sm text-slate-500">
            Select a retailer to review plans, rates, and yearly history.
          </p>
        </div>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="px-4 py-2 rounded-md bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-60"
        >
          {refreshMutation.isPending ? 'Syncing...' : 'Sync Plans'}
        </button>
      </div>

      {retailersLoading ? (
        <div className="text-slate-500">Loading retailers...</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {retailers.map((retailer) => (
            <button
              key={retailer.id}
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
              const def = touByPlanId.get(plan.id)
              const periods = def?.periods ?? []
              const touPeriods = periods.filter((p) => p.name !== 'anytime')
              const usageRate = num(plan.usage_rate_cents_per_kwh)
              const hasRates = periods.some((p) => num(p.rate_cents_per_kwh) != null) || usageRate != null
              const chartData = hasRates ? buildHourlyRateData(periods, plan.usage_rate_cents_per_kwh ?? null, plan.feed_in_tariffs) : null
              const isActive = activePlanId === plan.id
              const hasFeedIn = chartData != null && chartData.some((d) => d.feedIn1 != null)

              return (
                <button
                  key={plan.id}
                  onClick={() => setSelectedPlanId(plan.id)}
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
                        {plan.network_provider ? ` | ${plan.network_provider}` : ''}
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
                    {num(plan.feed_in_tariff_cents_per_kwh) != null && (
                      <span className="text-slate-600">
                        Feed-in <span className="font-medium text-emerald-700">{num(plan.feed_in_tariff_cents_per_kwh)!.toFixed(1)}c</span>/kWh
                      </span>
                    )}
                  </div>

                  {/* TOU period pills + mini chart */}
                  {touPeriods.length > 0 && (
                    <div className="mt-3 flex gap-3">
                      <div className="flex-1 flex flex-wrap gap-1.5">
                        {touPeriods.map((period) => (
                          <span
                            key={period.id}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-slate-50 border border-slate-150 text-slate-700"
                          >
                            <span
                              className="w-1.5 h-1.5 rounded-full"
                              style={{ backgroundColor: PERIOD_COLORS[period.name] ?? '#94a3b8' }}
                            />
                            {period.name.replace('_', '-')}{' '}
                            {num(period.rate_cents_per_kwh) != null && (
                              <span className="font-medium">{num(period.rate_cents_per_kwh)!.toFixed(2)}c</span>
                            )}
                            <span className="text-slate-400">
                              {formatTime(period.start_time)}{'\u2013'}{formatTime(period.end_time)}
                            </span>
                          </span>
                        ))}
                      </div>
                      {/* Mini chart thumbnail */}
                      {chartData && (
                        <div className="w-32 h-16 shrink-0">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 0, left: 0 }}>
                              <defs>
                                <linearGradient id={`grad-${plan.id}`} x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="0%" stopColor="#16a34a" stopOpacity={0.3} />
                                  <stop offset="100%" stopColor="#16a34a" stopOpacity={0.05} />
                                </linearGradient>
                              </defs>
                              <Area
                                type="stepAfter"
                                dataKey="rate"
                                stroke="#16a34a"
                                strokeWidth={1.5}
                                fill={`url(#grad-${plan.id})`}
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
            {activePlan.plan_name} {activeDefinition ? `| ${activeDefinition.timezone}` : ''}
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

      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <h2 className="text-lg font-medium text-slate-900">History by Year</h2>
        <div className="mt-4 space-y-4">
          {history.map((bucket) => (
            <div key={bucket.year} className="rounded-md border border-slate-200 p-3">
              <div className="font-semibold text-slate-900">{bucket.year}</div>
              <div className="text-sm text-slate-600">
                Plans: {bucket.plans.length} | TOU definitions: {bucket.tou_definitions.length}
              </div>
            </div>
          ))}
          {history.length === 0 && <p className="text-slate-500">No history found.</p>}
        </div>
      </div>
    </div>
  )
}
