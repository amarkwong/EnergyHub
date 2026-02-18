import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import EntityLogo from '../components/EntityLogo'

type NetworkProvider = {
  code: string
  name: string
  state: string
}

type TimePeriod = {
  name: string
  start_time?: string | null
  end_time?: string | null
  days?: number[]
  rate_cents_per_kwh?: number | string
  demand_rate_cents_per_kva?: number | string
  unit?: string
}

type NetworkTariff = {
  tariff_code: string
  tariff_name: string
  tariff_type: string
  effective_from: string
  daily_supply_charge_cents: number
  usage_rate_cents_per_kwh?: number | string
  demand_rate_cents_per_kw?: number | string
  time_periods?: TimePeriod[]
}

type TouDefinition = {
  id: number
  name: string
  effective_from: string
  timezone: string
  periods: Array<{
    id: number
    name: string
    start_time: string
    end_time: string
    days_of_week: number[]
    rate_cents_per_kwh?: number
  }>
}

type YearHistory = {
  year: number
  tariffs: NetworkTariff[]
}

export default function Tariffs() {
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)
  const [selectedState, setSelectedState] = useState<string | null>(null)
  const [selectedTariffKey, setSelectedTariffKey] = useState<string | null>(null)

  const { data: providers = [] } = useQuery({
    queryKey: ['network-providers'],
    queryFn: async () => {
      const response = await api.get('/api/tariffs/network-providers')
      return response.data as NetworkProvider[]
    },
  })

  const activeProvider = useMemo(() => selectedProvider || providers[0]?.code || null, [selectedProvider, providers])
  const states = [...new Set(providers.map((p) => p.state))]
  const filteredProviders = selectedState ? providers.filter((p) => p.state === selectedState) : providers

  const { data: tariffs = [], isLoading: tariffsLoading } = useQuery({
    queryKey: ['network-tariffs', activeProvider],
    queryFn: async () => {
      const response = await api.get(`/api/tariffs/network/${activeProvider}`)
      return response.data as NetworkTariff[]
    },
    enabled: !!activeProvider,
  })

  const { data: touDefinitions = [] } = useQuery({
    queryKey: ['network-tou', activeProvider],
    queryFn: async () => {
      const response = await api.get('/api/energy-plans/tou-definitions', {
        params: { scope_type: 'network', scope_key: activeProvider },
      })
      return response.data as TouDefinition[]
    },
    enabled: !!activeProvider,
  })

  const { data: history = [] } = useQuery({
    queryKey: ['network-history', activeProvider],
    queryFn: async () => {
      const response = await api.get(`/api/tariffs/network/${activeProvider}/history`)
      return response.data as YearHistory[]
    },
    enabled: !!activeProvider,
  })

  const activeTariff = useMemo(() => {
    if (!tariffs.length) return null
    if (!selectedTariffKey) return tariffs[0]
    return tariffs.find((t) => `${t.tariff_code}-${t.effective_from}` === selectedTariffKey) ?? tariffs[0]
  }, [tariffs, selectedTariffKey])

  const chartData = useMemo(() => {
    if (!activeTariff) return []
    const tariffPeriods = activeTariff.time_periods ?? []
    const hasWindows = tariffPeriods.some((p) => p.start_time && p.end_time)

    let effectivePeriods: TimePeriod[] = []
    if (hasWindows) {
      effectivePeriods = tariffPeriods
    } else {
      // When tariff record has rates but no windows, borrow windows from TOU definition.
      const def = touDefinitions.find(
        (d) =>
          d.name.toLowerCase().includes((activeTariff.tariff_code || '').toLowerCase()) &&
          d.effective_from === activeTariff.effective_from,
      ) ?? touDefinitions[0]
      if (def) {
        const rateByName = new Map<string, number>()
        for (const p of tariffPeriods) {
          const key = normalizePeriodName(p.name)
          const rate = toChartCents(p.rate_cents_per_kwh)
          if (rate !== null) rateByName.set(key, rate)
        }
        effectivePeriods = def.periods.map((p) => ({
          name: p.name,
          start_time: p.start_time,
          end_time: p.end_time,
          days: p.days_of_week,
          rate_cents_per_kwh: rateByName.get(normalizePeriodName(p.name)) ?? toChartCents(p.rate_cents_per_kwh) ?? undefined,
          unit: 'kWh',
        }))
      }
    }

    if (effectivePeriods.length > 0) {
      return buildHourlyRateData(
        effectivePeriods,
        toChartCents(activeTariff.usage_rate_cents_per_kwh),
      )
    }
    return Array.from({ length: 24 }, (_, hour) => {
      return {
        hourLabel: `${String(hour).padStart(2, '0')}:00`,
        rate: toChartCents(activeTariff.usage_rate_cents_per_kwh) ?? 0,
      }
    })
  }, [activeTariff, touDefinitions])

  const periodBands = useMemo(() => {
    if (!activeTariff) return []
    const periods = activeTariff.time_periods ?? []
    if (periods.some((p) => p.start_time && p.end_time)) return buildPeriodBands(periods)
    const def =
      touDefinitions.find(
        (d) =>
          d.name.toLowerCase().includes((activeTariff.tariff_code || '').toLowerCase()) &&
          d.effective_from === activeTariff.effective_from,
      ) ?? touDefinitions[0]
    if (!def) return []
    return buildPeriodBands(
      def.periods.map((p) => ({
        name: p.name,
        start_time: p.start_time,
        end_time: p.end_time,
        days: p.days_of_week,
        rate_cents_per_kwh: p.rate_cents_per_kwh,
      })),
    )
  }, [activeTariff, touDefinitions])

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Network</h1>
        <p className="mt-1 text-sm text-slate-500">
          Network provider tariffs, TOU structures, and historical tariff snapshots by year.
        </p>
      </div>

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

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {filteredProviders.map((provider) => (
          <button
            key={provider.code}
            onClick={() => setSelectedProvider(provider.code)}
            className={`rounded-md border h-28 ${
              activeProvider === provider.code ? 'border-primary-500 bg-primary-50' : 'border-slate-200 bg-white'
            }`}
            aria-label={provider.name}
            title={provider.name}
          >
            <div className="flex h-full items-center justify-center p-1">
              <EntityLogo name={provider.code} type="network" className="h-[82%] w-[82%] max-w-[92%]" />
            </div>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-lg font-medium text-slate-900">Tariffs</h2>
          {tariffsLoading ? (
            <p className="mt-3 text-slate-500">Loading tariffs...</p>
          ) : (
            <div className="mt-4 space-y-3">
              {tariffs.map((tariff) => {
                const tariffKey = `${tariff.tariff_code}-${tariff.effective_from}`
                const isActive = activeTariff && tariffKey === `${activeTariff.tariff_code}-${activeTariff.effective_from}`
                const periods = tariff.time_periods ?? []
                const hasRates = periods.some((p) => toChartCents(p.rate_cents_per_kwh) !== null) || toChartCents(tariff.usage_rate_cents_per_kwh) !== null
                const miniChartData = hasRates ? buildHourlyRateData(periods, toChartCents(tariff.usage_rate_cents_per_kwh)) : null

                return (
                  <button
                    key={tariffKey}
                    onClick={() => setSelectedTariffKey(tariffKey)}
                    className={`w-full text-left rounded-md border p-3 ${
                      isActive ? 'border-primary-500 bg-primary-50' : 'border-slate-200'
                    }`}
                  >
                    <div className="font-medium text-slate-900">{tariff.tariff_name}</div>
                    <div className="text-sm text-slate-600">
                      {tariff.tariff_code} | {tariff.tariff_type.toUpperCase()} | Effective {tariff.effective_from}
                    </div>
                    <div className="text-sm text-slate-600">
                      Daily {tariff.daily_supply_charge_cents}c/day
                      {tariff.usage_rate_cents_per_kwh ? ` | Usage ${tariff.usage_rate_cents_per_kwh}c/kWh` : ''}
                    </div>
                    {periods.length > 0 && (
                      <div className="mt-2 flex gap-3">
                        <div className="flex-1 flex flex-wrap gap-2">
                          {periods.map((period, idx) => (
                            <span key={idx} className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-700">
                              {period.name}: {period.rate_cents_per_kwh}c/kWh
                            </span>
                          ))}
                        </div>
                        {miniChartData && (
                          <div className="w-32 h-16 shrink-0">
                            <ResponsiveContainer width="100%" height="100%">
                              <AreaChart data={miniChartData} margin={{ top: 2, right: 2, bottom: 0, left: 0 }}>
                                <defs>
                                  <linearGradient id={`ngrad-${tariffKey}`} x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#16a34a" stopOpacity={0.3} />
                                    <stop offset="100%" stopColor="#16a34a" stopOpacity={0.05} />
                                  </linearGradient>
                                </defs>
                                <Area
                                  type="stepAfter"
                                  dataKey="rate"
                                  stroke="#16a34a"
                                  strokeWidth={1.5}
                                  fill={`url(#ngrad-${tariffKey})`}
                                  isAnimationActive={false}
                                />
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

        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-lg font-medium text-slate-900">TOU Section</h2>
          <div className="mt-4 space-y-3">
            {(() => {
              const seen = new Set<string>()
              return touDefinitions.filter((d) => {
                const key = `${d.name}|${d.effective_from}`
                if (seen.has(key)) return false
                seen.add(key)
                return true
              }).map((definition) => (
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
              ))
            })()}
            {touDefinitions.length === 0 && <p className="text-slate-500">No TOU definition found for this provider.</p>}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <h2 className="text-lg font-medium text-slate-900">Tariff Rate by Time</h2>
        <p className="text-sm text-slate-500 mt-1">
          Left Y: usage rate (c/kWh)
          {' | '}X axis: hour of day
          {activeTariff ? ` | ${activeTariff.tariff_code} (${activeTariff.effective_from})` : ''}
        </p>
        <div className="h-72 mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              {periodBands.map((band, idx) => (
                <ReferenceArea
                  key={`${band.name}-${idx}`}
                  x1={band.x1}
                  x2={band.x2}
                  fill={band.color}
                  fillOpacity={0.14}
                  strokeOpacity={0}
                />
              ))}
              <XAxis dataKey="hourLabel" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="usage" unit="c/kWh" tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number | string) => {
                  const num = typeof value === 'number' ? value : Number(value)
                  if (!Number.isFinite(num)) return ['N/A', 'Rate']
                  return [`${num.toFixed(3)}`, 'Rate']
                }}
                labelFormatter={(label) => `Hour ${label}`}
              />
              <Legend />
              <Line name="Usage rate (c/kWh)" yAxisId="usage" type="stepAfter" dataKey="rate" stroke="#16a34a" strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <h2 className="text-lg font-medium text-slate-900">Tariff History by Year</h2>
        <div className="mt-4 space-y-4">
          {history.map((bucket) => (
            <div key={bucket.year} className="rounded-md border border-slate-200 p-3">
              <div className="font-semibold text-slate-900">{bucket.year}</div>
              <div className="text-sm text-slate-600">Tariffs: {bucket.tariffs.length}</div>
            </div>
          ))}
          {history.length === 0 && <p className="text-slate-500">No tariff history found.</p>}
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

function buildHourlyRateData(
  periods: Array<{
    name: string
    start_time?: string | null
    end_time?: string | null
    rate_cents_per_kwh?: number | string
    demand_rate_cents_per_kva?: number | string
    unit?: string
  }>,
  flatRate: number | null,
) {
  const output = []
  for (let hour = 0; hour < 24; hour += 1) {
    let rate = flatRate ?? 0
    for (const period of periods) {
      if (!period.start_time || !period.end_time) continue
      const start = toHour(period.start_time)
      const end = toHour(period.end_time)
      const periodRate = toChartCents(period.rate_cents_per_kwh)
      if (isWithinPeriod(hour, start, end) && periodRate !== null) {
        rate = periodRate
        break
      }
    }
    output.push({
      hourLabel: `${String(hour).padStart(2, '0')}:00`,
      rate,
    })
  }
  return output
}

function toNum(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const n = Number(value)
    return Number.isFinite(n) ? n : null
  }
  return null
}

function toChartCents(value: unknown): number | null {
  const n = toNum(value)
  if (n === null) return null
  // Some sources provide dollars/kWh while UI and chart are in cents/kWh.
  return n > 0 && n < 2 ? n * 100 : n
}

function normalizePeriodName(name: string | undefined) {
  return (name || '').toLowerCase().replace(/[^a-z0-9]/g, '')
}

function buildPeriodBands(periods: TimePeriod[]) {
  const bands: Array<{ name: string; x1: string; x2: string; color: string }> = []
  for (const period of periods) {
    if (!period.start_time || !period.end_time) continue
    const start = toHour(period.start_time)
    const end = toHour(period.end_time)
    const name = (period.name || '').toLowerCase()
    const color =
      name === 'peak'
        ? '#f87171'
        : name === 'off_peak'
          ? '#60a5fa'
          : name === 'night'
            ? '#94a3b8'
            : name === 'shoulder'
              ? '#fbbf24'
              : '#86efac'

    if (start <= end) {
      bands.push({
        name,
        x1: `${String(start).padStart(2, '0')}:00`,
        x2: `${String(end).padStart(2, '0')}:00`,
        color,
      })
    } else {
      bands.push({
        name,
        x1: `${String(start).padStart(2, '0')}:00`,
        x2: '23:00',
        color,
      })
      bands.push({
        name,
        x1: '00:00',
        x2: `${String(end).padStart(2, '0')}:00`,
        color,
      })
    }
  }
  return bands
}
