import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

interface NetworkProvider {
  code: string
  name: string
  state: string
}

// Sample providers data (would come from API)
const providers: NetworkProvider[] = [
  { code: 'ausgrid', name: 'Ausgrid', state: 'NSW' },
  { code: 'endeavour_energy', name: 'Endeavour Energy', state: 'NSW' },
  { code: 'essential_energy', name: 'Essential Energy', state: 'NSW' },
  { code: 'energex', name: 'Energex', state: 'QLD' },
  { code: 'ergon_energy', name: 'Ergon Energy', state: 'QLD' },
  { code: 'ausnet_services', name: 'AusNet Services', state: 'VIC' },
  { code: 'citipower', name: 'CitiPower', state: 'VIC' },
  { code: 'jemena', name: 'Jemena', state: 'VIC' },
  { code: 'powercor', name: 'Powercor', state: 'VIC' },
  { code: 'united_energy', name: 'United Energy', state: 'VIC' },
  { code: 'evoenergy', name: 'Evoenergy', state: 'ACT' },
  { code: 'tasnetworks', name: 'TasNetworks', state: 'TAS' },
]

const stateColors: Record<string, string> = {
  NSW: 'bg-blue-100 text-blue-800',
  QLD: 'bg-purple-100 text-purple-800',
  VIC: 'bg-green-100 text-green-800',
  ACT: 'bg-orange-100 text-orange-800',
  TAS: 'bg-teal-100 text-teal-800',
}

export default function Tariffs() {
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)
  const [selectedState, setSelectedState] = useState<string | null>(null)

  const states = [...new Set(providers.map((p) => p.state))]

  const filteredProviders = selectedState
    ? providers.filter((p) => p.state === selectedState)
    : providers

  const { data: tariffs, isLoading } = useQuery({
    queryKey: ['tariffs', selectedProvider],
    queryFn: async () => {
      if (!selectedProvider) return null
      const response = await api.get(`/api/tariffs/network/${selectedProvider}`)
      return response.data
    },
    enabled: !!selectedProvider,
  })

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Network Tariffs</h1>
        <p className="mt-1 text-sm text-slate-500">
          Browse tariff data from Australian electricity network distributors.
        </p>
      </div>

      {/* State filter */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedState(null)}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
            selectedState === null
              ? 'bg-slate-800 text-white'
              : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
          }`}
        >
          All States
        </button>
        {states.map((state) => (
          <button
            key={state}
            onClick={() => setSelectedState(state)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              selectedState === state
                ? 'bg-slate-800 text-white'
                : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
            }`}
          >
            {state}
          </button>
        ))}
      </div>

      {/* Provider grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredProviders.map((provider) => (
          <button
            key={provider.code}
            onClick={() => setSelectedProvider(provider.code)}
            className={`p-4 text-left rounded-lg border transition-all ${
              selectedProvider === provider.code
                ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-500'
                : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium text-slate-900">{provider.name}</span>
              <span
                className={`px-2 py-0.5 text-xs font-medium rounded ${
                  stateColors[provider.state]
                }`}
              >
                {provider.state}
              </span>
            </div>
          </button>
        ))}
      </div>

      {/* Tariff details */}
      {selectedProvider && (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
            <h3 className="text-lg font-medium text-slate-900">
              {providers.find((p) => p.code === selectedProvider)?.name} Tariffs
            </h3>
          </div>

          {isLoading ? (
            <div className="p-6 text-center text-slate-500">Loading tariffs...</div>
          ) : tariffs ? (
            <div className="divide-y divide-slate-200">
              {tariffs.map((tariff: any) => (
                <div key={tariff.tariff_code} className="p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium text-slate-900">{tariff.tariff_name}</h4>
                      <p className="text-sm text-slate-500">Code: {tariff.tariff_code}</p>
                    </div>
                    <span className="px-2 py-1 text-xs font-medium rounded bg-slate-100 text-slate-700">
                      {tariff.tariff_type.toUpperCase()}
                    </span>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <dt className="text-slate-500">Daily Supply Charge</dt>
                      <dd className="font-medium text-slate-900">
                        {tariff.daily_supply_charge_cents}c/day
                      </dd>
                    </div>
                    {tariff.usage_rate_cents_per_kwh && (
                      <div>
                        <dt className="text-slate-500">Usage Rate</dt>
                        <dd className="font-medium text-slate-900">
                          {tariff.usage_rate_cents_per_kwh}c/kWh
                        </dd>
                      </div>
                    )}
                  </div>

                  {tariff.time_periods && tariff.time_periods.length > 0 && (
                    <div className="mt-4">
                      <dt className="text-sm text-slate-500 mb-2">Time of Use Periods</dt>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                        {tariff.time_periods.map((period: any, idx: number) => (
                          <div
                            key={idx}
                            className="p-2 rounded bg-slate-50 text-sm"
                          >
                            <span className="font-medium capitalize">{period.name}</span>
                            <span className="text-slate-500 ml-2">
                              {period.rate_cents_per_kwh}c/kWh
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-slate-500">
              Select a provider to view tariffs
            </div>
          )}
        </div>
      )}
    </div>
  )
}
