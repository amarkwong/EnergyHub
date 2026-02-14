import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import EntityLogo from '../components/EntityLogo'

type Retailer = {
  id: number
  name: string
  slug: string
  source_url?: string | null
}

type EnergyPlan = {
  id: number
  retailer: string
  retailer_slug: string
  plan_name: string
  network_provider?: string | null
  tariff_type: string
  effective_from: string
  daily_supply_charge_cents: number
  usage_rate_cents_per_kwh?: number | null
}

type TouPeriod = {
  id: number
  name: string
  start_time: string
  end_time: string
  days_of_week: number[]
  rate_cents_per_kwh?: number | null
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

  const activePlan = useMemo(() => plans.find((p) => p.id === activePlanId) ?? null, [plans, activePlanId])
  const activeDefinition = useMemo(
    () => touDefinitions.find((d) => d.plan_id === activePlanId) ?? touDefinitions[0],
    [touDefinitions, activePlanId]
  )
  const hourlyRateData = useMemo(() => {
    const usageRate = activePlan?.usage_rate_cents_per_kwh ?? null
    return buildHourlyRateData(activeDefinition?.periods ?? [], usageRate)
  }, [activeDefinition, activePlan])

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
            Select a retailer to review current plans, TOU definitions, and yearly plan history.
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-lg font-medium text-slate-900">Plans</h2>
          {plansLoading ? (
            <p className="mt-3 text-slate-500">Loading plans...</p>
          ) : (
            <div className="mt-4 space-y-3">
              {plans.map((plan) => (
                <button
                  key={plan.id}
                  onClick={() => setSelectedPlanId(plan.id)}
                  className={`w-full text-left rounded-md border p-3 ${
                    activePlanId === plan.id ? 'border-primary-500 bg-primary-50' : 'border-slate-200'
                  }`}
                >
                  <div className="font-medium text-slate-900">{plan.plan_name}</div>
                  <div className="text-sm text-slate-600">
                    {plan.tariff_type.toUpperCase()} | Effective {plan.effective_from}
                  </div>
                  <div className="text-sm text-slate-600">
                    Daily {plan.daily_supply_charge_cents}c/day
                    {plan.usage_rate_cents_per_kwh ? ` | Usage ${plan.usage_rate_cents_per_kwh}c/kWh` : ''}
                  </div>
                </button>
              ))}
              {plans.length === 0 && <p className="text-slate-500">No plans found.</p>}
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-lg font-medium text-slate-900">TOU Definitions</h2>
          <div className="mt-4 space-y-3">
            {touDefinitions.map((definition) => (
              <div key={definition.id} className="rounded-md border border-slate-200 p-3">
                <div className="font-medium text-slate-900">{definition.name}</div>
                <div className="text-sm text-slate-600">
                  TZ {definition.timezone} | Effective {definition.effective_from}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {definition.periods.map((period) => (
                    <span key={period.id} className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-700">
                      {period.name}: {period.start_time}-{period.end_time}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {touDefinitions.length === 0 && <p className="text-slate-500">No TOU definitions found.</p>}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <h2 className="text-lg font-medium text-slate-900">Hourly Rate View</h2>
        <p className="text-sm text-slate-500 mt-1">
          Selected plan: {activePlan?.plan_name || 'N/A'} {activeDefinition ? `| TZ ${activeDefinition.timezone}` : ''}
        </p>
        <div className="h-72 mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={hourlyRateData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="hourLabel" tick={{ fontSize: 12 }} />
              <YAxis unit="c/kWh" tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number | string) => {
                  const num = typeof value === 'number' ? value : Number(value)
                  if (!Number.isFinite(num)) return ['N/A', 'Rate']
                  return [`${num.toFixed(2)} c/kWh`, 'Rate']
                }}
                labelFormatter={(label) => `Hour ${label}`}
              />
              <Line type="monotone" dataKey="rate" stroke="#16a34a" strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

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

function toHour(raw: string) {
  const [hour] = raw.split(':')
  return Number.parseInt(hour, 10)
}

function isWithinPeriod(hour: number, start: number, end: number) {
  if (start === end) return true
  if (start < end) return hour >= start && hour < end
  return hour >= start || hour < end
}

function buildHourlyRateData(periods: TouPeriod[], flatRate: number | null) {
  const sorted = [...periods].sort((a, b) => a.name.localeCompare(b.name))
  const output = []
  for (let hour = 0; hour < 24; hour += 1) {
    let rate = flatRate ?? 0
    for (const period of sorted) {
      const start = toHour(period.start_time)
      const end = toHour(period.end_time)
      if (isWithinPeriod(hour, start, end) && typeof period.rate_cents_per_kwh === 'number') {
        rate = period.rate_cents_per_kwh
        break
      }
    }
    output.push({
      hour,
      hourLabel: `${String(hour).padStart(2, '0')}:00`,
      rate,
    })
  }
  return output
}
