import { useState } from 'react'
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

// Sample data for demonstration
const dailyData = [
  { date: '2024-01-01', peak: 12.5, offPeak: 8.2, total: 20.7 },
  { date: '2024-01-02', peak: 14.1, offPeak: 7.8, total: 21.9 },
  { date: '2024-01-03', peak: 11.8, offPeak: 9.1, total: 20.9 },
  { date: '2024-01-04', peak: 15.2, offPeak: 8.5, total: 23.7 },
  { date: '2024-01-05', peak: 13.9, offPeak: 7.9, total: 21.8 },
  { date: '2024-01-06', peak: 8.5, offPeak: 10.2, total: 18.7 },
  { date: '2024-01-07', peak: 7.9, offPeak: 11.1, total: 19.0 },
]

const hourlyData = Array.from({ length: 24 }, (_, i) => ({
  hour: `${i.toString().padStart(2, '0')}:00`,
  consumption: Math.random() * 3 + (i >= 7 && i <= 22 ? 2 : 0.5),
}))

type ViewMode = 'daily' | 'hourly'

export default function Consumption() {
  const [viewMode, setViewMode] = useState<ViewMode>('daily')

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Energy Consumption</h1>
        <p className="mt-1 text-sm text-slate-500">
          Visualize your energy consumption patterns from NEM12 data.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <dt className="text-sm font-medium text-slate-500">Total Consumption</dt>
          <dd className="mt-1 text-3xl font-semibold text-slate-900">146.7 kWh</dd>
          <p className="mt-1 text-sm text-slate-500">Last 7 days</p>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <dt className="text-sm font-medium text-slate-500">Peak Usage</dt>
          <dd className="mt-1 text-3xl font-semibold text-energy">83.9 kWh</dd>
          <p className="mt-1 text-sm text-slate-500">57% of total</p>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <dt className="text-sm font-medium text-slate-500">Off-Peak Usage</dt>
          <dd className="mt-1 text-3xl font-semibold text-primary-600">62.8 kWh</dd>
          <p className="mt-1 text-sm text-slate-500">43% of total</p>
        </div>
      </div>

      {/* View mode selector */}
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

      {/* Charts */}
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
                <Bar dataKey="peak" name="Peak" fill="#f59e0b" stackId="a" />
                <Bar dataKey="offPeak" name="Off-Peak" fill="#22c55e" stackId="a" />
              </BarChart>
            ) : (
              <LineChart data={hourlyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" />
                <YAxis unit=" kWh" />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="consumption"
                  name="Consumption"
                  stroke="#16a34a"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>

      {/* Info message */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-700">
          This is sample data. Upload a NEM12 file to view your actual consumption.
        </p>
      </div>
    </div>
  )
}
