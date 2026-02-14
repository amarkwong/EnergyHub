import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts'
import { api } from '../api/client'
import { LATEST_METER_FILE_KEY } from '../constants/storage'

type ViewMode = 'daily' | 'hourly'
type IntervalRow = {
  nmi: string
  date: string
  interval: number
  interval_length_minutes?: number
  value: number
  register_code?: string
  rate_type_description?: string
  quality_flag?: string
}

function intervalToHour(interval: number, intervalLengthMinutes: number) {
  const minutes = (interval - 1) * intervalLengthMinutes
  return Math.max(0, Math.min(23, Math.floor(minutes / 60)))
}

function isSolarExport(row: IntervalRow) {
  const rateType = (row.rate_type_description || '').toLowerCase()
  const register = (row.register_code || '').toLowerCase()
  return rateType.includes('solar') || /#b\d+$/.test(register)
}

export default function Consumption() {
  const [viewMode, setViewMode] = useState<ViewMode>('daily')
  const [selectedNmi, setSelectedNmi] = useState<string>('')
  const fileId = window.localStorage.getItem(LATEST_METER_FILE_KEY) || ''

  const { data: accountNmis = [] } = useQuery({
    queryKey: ['account-nmis'],
    queryFn: async () => {
      const response = await api.get('/api/account/nmis')
      return response.data as Array<{ id: number; nmi: string }>
    },
  })

  const { data: intervals = [], isLoading, isError, error } = useQuery({
    queryKey: ['meter-intervals', fileId, selectedNmi],
    queryFn: async () => {
      if (!fileId) return []
      const response = await api.get(`/api/nem12/${fileId}/intervals`, {
        params: selectedNmi ? { nmi: selectedNmi } : undefined,
      })
      return response.data as IntervalRow[]
    },
    enabled: !!fileId,
  })

  const availableNmis = useMemo(() => {
    const fromData = intervals.map((item) => item.nmi).filter(Boolean)
    const merged = [...accountNmis.map((n) => n.nmi), ...fromData]
    return Array.from(new Set(merged))
  }, [intervals, accountNmis])

  useEffect(() => {
    if (!selectedNmi && availableNmis.length > 0) {
      setSelectedNmi(availableNmis[0])
    }
  }, [availableNmis, selectedNmi])

  const filteredIntervals = useMemo(() => {
    if (!selectedNmi) return intervals
    return intervals.filter((item) => item.nmi === selectedNmi)
  }, [intervals, selectedNmi])

  const summary = useMemo(() => {
    let totalImport = 0
    let totalSolarExport = 0
    for (const row of filteredIntervals) {
      if (isSolarExport(row)) {
        totalSolarExport += row.value
        continue
      }
      totalImport += row.value
    }
    return {
      totalImport,
      totalSolarExport,
      netImport: totalImport - totalSolarExport,
    }
  }, [filteredIntervals])

  const dailyData = useMemo(() => {
    const byDate = new Map<string, { date: string; usageImport: number; solarExport: number; net: number }>()
    for (const row of filteredIntervals) {
      const current = byDate.get(row.date) ?? { date: row.date, usageImport: 0, solarExport: 0, net: 0 }
      if (isSolarExport(row)) {
        current.solarExport -= row.value
      } else {
        current.usageImport += row.value
      }
      current.net = current.usageImport + current.solarExport
      byDate.set(row.date, current)
    }
    return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
  }, [filteredIntervals])

  const hourlyData = useMemo(() => {
    const byHour = Array.from({ length: 24 }, (_, hour) => ({
      hour: `${String(hour).padStart(2, '0')}:00`,
      importTotal: 0,
      importCount: 0,
      solarTotal: 0,
      solarCount: 0,
    }))
    for (const row of filteredIntervals) {
      const intervalLength = row.interval_length_minutes ?? 30
      const hour = intervalToHour(row.interval, intervalLength)
      if (isSolarExport(row)) {
        byHour[hour].solarTotal += row.value
        byHour[hour].solarCount += 1
      } else {
        byHour[hour].importTotal += row.value
        byHour[hour].importCount += 1
      }
    }
    return byHour.map((item) => ({
      hour: item.hour,
      consumption: item.importCount > 0 ? item.importTotal / item.importCount : 0,
      solarExport: item.solarCount > 0 ? -(item.solarTotal / item.solarCount) : 0,
    }))
  }, [filteredIntervals])

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Energy Consumption</h1>
        <p className="mt-1 text-sm text-slate-500">
          Visualize your uploaded meter intervals by NMI and time period.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-4 flex flex-wrap items-center gap-3">
        <div className="text-sm text-slate-600">
          Latest file: <span className="font-mono text-slate-800">{fileId || 'Not uploaded yet'}</span>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-600" htmlFor="nmi-select">NMI</label>
          <select
            id="nmi-select"
            value={selectedNmi}
            onChange={(e) => setSelectedNmi(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          >
            {availableNmis.length === 0 && <option value="">No NMI</option>}
            {availableNmis.map((nmi) => (
              <option key={nmi} value={nmi}>{nmi}</option>
            ))}
          </select>
        </div>
      </div>

      {isLoading && (
        <div className="bg-white rounded-lg border border-slate-200 p-5 text-slate-600">Loading usage data...</div>
      )}

      {isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          Failed to load usage data: {(error as Error)?.message || 'Unknown error'}
        </div>
      )}

      {!isLoading && !isError && filteredIntervals.length === 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-700">
            No usage data found yet. Upload NEM12 or Retailer CSV in Meter Data first.
          </p>
        </div>
      )}

      {!isLoading && !isError && filteredIntervals.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
            <div className="bg-white rounded-lg border border-slate-200 p-5">
              <dt className="text-sm font-medium text-slate-500">Total Consumption</dt>
              <dd className="mt-1 text-3xl font-semibold text-slate-900">{summary.totalImport.toFixed(2)} kWh</dd>
              <p className="mt-1 text-sm text-slate-500">{dailyData.length} day(s)</p>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-5">
              <dt className="text-sm font-medium text-slate-500">Solar Export</dt>
              <dd className="mt-1 text-3xl font-semibold text-energy">{summary.totalSolarExport.toFixed(2)} kWh</dd>
              <p className="mt-1 text-sm text-slate-500">Rendered as negative usage in charts.</p>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-5">
              <dt className="text-sm font-medium text-slate-500">Net Import</dt>
              <dd className="mt-1 text-3xl font-semibold text-primary-600">{summary.netImport.toFixed(2)} kWh</dd>
              <p className="mt-1 text-sm text-slate-500">Import minus solar export.</p>
            </div>
          </div>

          <div className="flex space-x-4">
            <button
              onClick={() => setViewMode('daily')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'daily'
                  ? 'bg-primary-600 text-white'
                  : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
              }`}
            >
              Daily View
            </button>
            <button
              onClick={() => setViewMode('hourly')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                viewMode === 'hourly'
                  ? 'bg-primary-600 text-white'
                  : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
              }`}
            >
              Hourly View
            </button>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <h3 className="text-lg font-medium text-slate-900 mb-4">
              {viewMode === 'daily' ? 'Daily Consumption' : 'Hourly Consumption Profile'}
            </h3>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                {viewMode === 'daily' ? (
                  <BarChart data={dailyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis unit=" kWh" />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="usageImport" name="General Usage Import" fill="#0ea5e9" />
                    <Bar dataKey="solarExport" name="Solar Export" fill="#f59e0b" stackId="b" />
                  </BarChart>
                ) : (
                  <LineChart data={hourlyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="hour" />
                    <YAxis unit=" kWh" />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="stepAfter"
                      dataKey="consumption"
                      name="Average general usage"
                      stroke="#0ea5e9"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="stepAfter"
                      dataKey="solarExport"
                      name="Average solar export"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                )}
              </ResponsiveContainer>
            </div>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-blue-700">
              TOU (peak/off-peak/shoulder) is not inferred from this raw CSV format. TOU splits will be applied only when a TOU plan is explicitly identified from invoice + tariff mapping.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
