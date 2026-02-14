import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { LATEST_INVOICE_FILE_KEY, LATEST_METER_FILE_KEY } from '../constants/storage'

type DiscrepancyStatus = 'match' | 'minor' | 'significant' | 'missing_invoiced' | 'missing_calculated'

type ReconciliationLineItem = {
  description: string
  charge_type: string
  invoiced_amount: number
  calculated_amount: number | null
  amount_difference: number
  percentage_difference: number | null
  status: DiscrepancyStatus
}

type ReconciliationSummary = {
  nmi: string
  invoice_number: string
  billing_period_start: string
  billing_period_end: string
  invoiced_total: number
  calculated_total: number
  total_difference: number
  total_percentage_difference: number
  line_items: ReconciliationLineItem[]
  overall_status: DiscrepancyStatus
  recommendations: string[]
}

const statusColors: Record<DiscrepancyStatus, string> = {
  match: 'bg-green-100 text-green-800',
  minor: 'bg-yellow-100 text-yellow-800',
  significant: 'bg-red-100 text-red-800',
  missing_invoiced: 'bg-orange-100 text-orange-800',
  missing_calculated: 'bg-blue-100 text-blue-800',
}

const statusLabels: Record<DiscrepancyStatus, string> = {
  match: 'Match',
  minor: 'Minor Discrepancy',
  significant: 'Significant Discrepancy',
  missing_invoiced: 'Missing on Invoice',
  missing_calculated: 'Missing in Calculation',
}

const money = (v: number | null | undefined) => `$${Number(v || 0).toFixed(2)}`

export default function Reconciliation() {
  const [invoiceFileId] = useState(() => window.localStorage.getItem(LATEST_INVOICE_FILE_KEY) || '')
  const [meterFileId] = useState(() => window.localStorage.getItem(LATEST_METER_FILE_KEY) || '')
  const [tariffCode, setTariffCode] = useState('')
  const [retailPlanName, setRetailPlanName] = useState('')
  const [lastRunKey, setLastRunKey] = useState('')

  const { data: assignments = [] } = useQuery({
    queryKey: ['account-assignments'],
    queryFn: async () => {
      const response = await api.get('/api/account/nmi-plan-assignments')
      return response.data as Array<{ network_tariff_code?: string | null; retailer_name?: string | null }>
    },
  })

  const { data: networkProviders = [] } = useQuery({
    queryKey: ['network-providers'],
    queryFn: async () => {
      const response = await api.get('/api/tariffs/network-providers')
      return response.data as Array<{ code: string; name: string }>
    },
  })

  const { data: retailers = [] } = useQuery({
    queryKey: ['retailers'],
    queryFn: async () => {
      const response = await api.get('/api/energy-plans/retailers')
      return response.data as Array<{ name: string; slug: string }>
    },
  })

  useEffect(() => {
    if (!tariffCode) {
      const suggestion = assignments.find((a) => !!a.network_tariff_code)?.network_tariff_code
      if (suggestion) setTariffCode(suggestion)
    }
    if (!retailPlanName) {
      const retailer = assignments.find((a) => !!a.retailer_name)?.retailer_name
      if (retailer) setRetailPlanName(retailer)
    }
  }, [assignments, tariffCode, retailPlanName])

  const { data: parsedInvoice } = useQuery({
    queryKey: ['invoice', invoiceFileId],
    queryFn: async () => {
      const response = await api.get(`/api/invoices/${invoiceFileId}`)
      return response.data as { invoice_number: string; nmi: string; billing_period_start: string; billing_period_end: string; total: number }
    },
    enabled: !!invoiceFileId,
  })

  const { data: intervals = [] } = useQuery({
    queryKey: ['meter-intervals-for-recon', meterFileId],
    queryFn: async () => {
      const response = await api.get(`/api/nem12/${meterFileId}/intervals`)
      return response.data as Array<{ nmi: string; value: number }>
    },
    enabled: !!meterFileId,
  })

  const usageSummary = useMemo(() => {
    const totalKwh = intervals.reduce((sum, item) => sum + Number(item.value || 0), 0)
    const nmiCount = new Set(intervals.map((i) => i.nmi)).size
    return { totalKwh, nmiCount, intervalCount: intervals.length }
  }, [intervals])

  const runReconciliation = useMutation({
    mutationFn: async () => {
      let resolvedTariffCode = tariffCode.trim()
      if (resolvedTariffCode) {
        const provider = networkProviders.find(
          (p) =>
            p.code.toLowerCase() === resolvedTariffCode.toLowerCase() ||
            p.name.toLowerCase() === resolvedTariffCode.toLowerCase()
        )
        if (provider) {
          const response = await api.get(`/api/tariffs/network/${provider.code}`)
          const tariffs = response.data as Array<{ tariff_code: string }>
          if (tariffs.length > 0) {
            resolvedTariffCode = tariffs[0].tariff_code
          }
        }
      }

      let resolvedPlanName = retailPlanName.trim()
      if (resolvedPlanName) {
        const retailerOnly = retailers.some((r) => r.name.toLowerCase() === resolvedPlanName.toLowerCase())
        if (retailerOnly) {
          resolvedPlanName = ''
        }
      }

      const response = await api.post('/api/reconciliation/run', {
        invoice_file_id: invoiceFileId,
        nem12_file_id: meterFileId,
        network_tariff_code: resolvedTariffCode || undefined,
        retail_plan_name: resolvedPlanName || undefined,
        tolerance_percent: 1.0,
      })
      return response.data as ReconciliationSummary
    },
  })

  useEffect(() => {
    const key = `${invoiceFileId}|${meterFileId}|${tariffCode}|${retailPlanName}`
    if (!invoiceFileId || !meterFileId) return
    if (runReconciliation.isPending) return
    if (lastRunKey === key) return
    setLastRunKey(key)
    runReconciliation.mutate()
  }, [invoiceFileId, meterFileId, tariffCode, retailPlanName, runReconciliation, lastRunKey])

  const result = runReconciliation.data
  const canRun = !!invoiceFileId && !!meterFileId

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Bill Check</h1>
        <p className="mt-1 text-sm text-slate-500">
          Reconcile your latest uploaded invoice against your latest uploaded usage data.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-3">
        <div className="text-sm text-slate-700">Invoice file: <span className="font-mono">{invoiceFileId || 'Not uploaded'}</span></div>
        <div className="text-sm text-slate-700">Meter file: <span className="font-mono">{meterFileId || 'Not uploaded'}</span></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input
            value={tariffCode}
            onChange={(e) => setTariffCode(e.target.value)}
            placeholder="Network tariff code (optional)"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            value={retailPlanName}
            onChange={(e) => setRetailPlanName(e.target.value)}
            placeholder="Retail plan/retailer name (optional)"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <button
          disabled={!canRun || runReconciliation.isPending}
          onClick={() => runReconciliation.mutate()}
          className={`px-4 py-2 rounded-md text-sm font-medium ${canRun ? 'bg-primary-600 text-white' : 'bg-slate-200 text-slate-500'}`}
        >
          {runReconciliation.isPending ? 'Running...' : 'Run Bill Check'}
        </button>
        {!canRun && (
          <p className="text-sm text-amber-700">
            Upload both a meter file and an invoice first. You can do this from the Upload Data page.
          </p>
        )}
      </div>

      {(parsedInvoice || intervals.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <h2 className="text-lg font-medium text-slate-900">Invoice Context</h2>
            {parsedInvoice ? (
              <div className="mt-2 text-sm text-slate-700 space-y-1">
                <p>Invoice: {parsedInvoice.invoice_number}</p>
                <p>NMI: {parsedInvoice.nmi}</p>
                <p>Period: {parsedInvoice.billing_period_start} to {parsedInvoice.billing_period_end}</p>
                <p>Total: {money(parsedInvoice.total)}</p>
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-500">No parsed invoice loaded.</p>
            )}
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <h2 className="text-lg font-medium text-slate-900">Usage Context</h2>
            <div className="mt-2 text-sm text-slate-700 space-y-1">
              <p>Intervals: {usageSummary.intervalCount}</p>
              <p>NMIs in data: {usageSummary.nmiCount}</p>
              <p>Total interval kWh: {usageSummary.totalKwh.toFixed(3)}</p>
            </div>
          </div>
        </div>
      )}

      {runReconciliation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          Failed to run reconciliation:{' '}
          {(() => {
            const e = runReconciliation.error as any
            return e?.response?.data?.detail || e?.message || 'Unknown error'
          })()}
        </div>
      )}

      {result && (
        <>
          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-medium text-slate-900">Invoice {result.invoice_number}</h2>
                  <p className="text-sm text-slate-500">
                    NMI: {result.nmi} | Period: {result.billing_period_start} - {result.billing_period_end}
                  </p>
                </div>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusColors[result.overall_status]}`}>
                  {statusLabels[result.overall_status]}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 divide-x divide-slate-200">
              <div className="px-6 py-4 text-center">
                <dt className="text-sm font-medium text-slate-500">Invoiced Total</dt>
                <dd className="mt-1 text-2xl font-semibold text-slate-900">{money(result.invoiced_total)}</dd>
              </div>
              <div className="px-6 py-4 text-center">
                <dt className="text-sm font-medium text-slate-500">Calculated Total</dt>
                <dd className="mt-1 text-2xl font-semibold text-slate-900">{money(result.calculated_total)}</dd>
              </div>
              <div className="px-6 py-4 text-center">
                <dt className="text-sm font-medium text-slate-500">Difference</dt>
                <dd className={`mt-1 text-2xl font-semibold ${result.total_difference > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {money(Math.abs(result.total_difference))}
                  {result.total_difference > 0 ? ' over' : ' under'}
                </dd>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200">
              <h3 className="text-lg font-medium text-slate-900">Line Item Breakdown</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Description</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Invoiced</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Calculated</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Difference</th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                  {result.line_items.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-slate-900">{item.description}</div>
                        <div className="text-sm text-slate-500">{item.charge_type}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-slate-900">{money(item.invoiced_amount)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-slate-900">{money(item.calculated_amount)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                        <span className={item.amount_difference !== 0 ? 'text-red-600' : 'text-slate-500'}>
                          {money(Math.abs(item.amount_difference))}
                          {item.percentage_difference !== null ? ` (${item.percentage_difference.toFixed(1)}%)` : ''}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[item.status]}`}>
                          {statusLabels[item.status]}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="text-blue-800 font-medium mb-2">Recommendations</h4>
            <ul className="list-disc list-inside text-sm text-blue-700 space-y-1">
              {result.recommendations.map((item, idx) => (
                <li key={idx}>{item}</li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  )
}
