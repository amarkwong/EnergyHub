import { useState } from 'react'

type DiscrepancyStatus = 'match' | 'minor' | 'significant'

interface LineItem {
  description: string
  chargeType: string
  invoicedAmount: number
  calculatedAmount: number
  difference: number
  percentageDiff: number
  status: DiscrepancyStatus
}

// Sample reconciliation data
const sampleReconciliation = {
  invoiceNumber: 'INV-2024-001234',
  nmi: '12345678901',
  billingPeriod: '01/12/2023 - 31/12/2023',
  invoicedTotal: 333.85,
  calculatedTotal: 328.50,
  totalDifference: 5.35,
  overallStatus: 'minor' as DiscrepancyStatus,
  lineItems: [
    {
      description: 'Peak Energy Usage',
      chargeType: 'usage',
      invoicedAmount: 157.50,
      calculatedAmount: 155.75,
      difference: 1.75,
      percentageDiff: 1.1,
      status: 'minor' as DiscrepancyStatus,
    },
    {
      description: 'Off-Peak Energy Usage',
      chargeType: 'usage',
      invoicedAmount: 50.40,
      calculatedAmount: 50.40,
      difference: 0,
      percentageDiff: 0,
      status: 'match' as DiscrepancyStatus,
    },
    {
      description: 'Daily Supply Charge',
      chargeType: 'supply',
      invoicedAmount: 37.20,
      calculatedAmount: 37.20,
      difference: 0,
      percentageDiff: 0,
      status: 'match' as DiscrepancyStatus,
    },
    {
      description: 'Network Charges',
      chargeType: 'network',
      invoicedAmount: 58.40,
      calculatedAmount: 54.80,
      difference: 3.60,
      percentageDiff: 6.2,
      status: 'significant' as DiscrepancyStatus,
    },
  ] as LineItem[],
}

const statusColors = {
  match: 'bg-green-100 text-green-800',
  minor: 'bg-yellow-100 text-yellow-800',
  significant: 'bg-red-100 text-red-800',
}

const statusLabels = {
  match: 'Match',
  minor: 'Minor Discrepancy',
  significant: 'Significant Discrepancy',
}

export default function Reconciliation() {
  const [selectedItem, setSelectedItem] = useState<LineItem | null>(null)

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Invoice Reconciliation</h1>
        <p className="mt-1 text-sm text-slate-500">
          Compare invoiced values against calculated values from your consumption data.
        </p>
      </div>

      {/* Summary */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-medium text-slate-900">
                Invoice {sampleReconciliation.invoiceNumber}
              </h2>
              <p className="text-sm text-slate-500">
                NMI: {sampleReconciliation.nmi} | Period: {sampleReconciliation.billingPeriod}
              </p>
            </div>
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                statusColors[sampleReconciliation.overallStatus]
              }`}
            >
              {statusLabels[sampleReconciliation.overallStatus]}
            </span>
          </div>
        </div>

        {/* Totals comparison */}
        <div className="grid grid-cols-3 divide-x divide-slate-200">
          <div className="px-6 py-4 text-center">
            <dt className="text-sm font-medium text-slate-500">Invoiced Total</dt>
            <dd className="mt-1 text-2xl font-semibold text-slate-900">
              ${sampleReconciliation.invoicedTotal.toFixed(2)}
            </dd>
          </div>
          <div className="px-6 py-4 text-center">
            <dt className="text-sm font-medium text-slate-500">Calculated Total</dt>
            <dd className="mt-1 text-2xl font-semibold text-slate-900">
              ${sampleReconciliation.calculatedTotal.toFixed(2)}
            </dd>
          </div>
          <div className="px-6 py-4 text-center">
            <dt className="text-sm font-medium text-slate-500">Difference</dt>
            <dd
              className={`mt-1 text-2xl font-semibold ${
                sampleReconciliation.totalDifference > 0 ? 'text-red-600' : 'text-green-600'
              }`}
            >
              ${Math.abs(sampleReconciliation.totalDifference).toFixed(2)}
              {sampleReconciliation.totalDifference > 0 ? ' over' : ' under'}
            </dd>
          </div>
        </div>
      </div>

      {/* Line items table */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="text-lg font-medium text-slate-900">Line Item Breakdown</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Description
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Invoiced
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Calculated
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Difference
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-slate-200">
              {sampleReconciliation.lineItems.map((item, idx) => (
                <tr
                  key={idx}
                  onClick={() => setSelectedItem(item)}
                  className="hover:bg-slate-50 cursor-pointer"
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-slate-900">{item.description}</div>
                    <div className="text-sm text-slate-500">{item.chargeType}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-slate-900">
                    ${item.invoicedAmount.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-slate-900">
                    ${item.calculatedAmount.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                    <span
                      className={item.difference !== 0 ? 'text-red-600' : 'text-slate-500'}
                    >
                      ${Math.abs(item.difference).toFixed(2)}
                      {item.difference !== 0 && ` (${item.percentageDiff.toFixed(1)}%)`}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-center">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        statusColors[item.status]
                      }`}
                    >
                      {statusLabels[item.status]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recommendations */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-blue-800 font-medium mb-2">Recommendations</h4>
        <ul className="list-disc list-inside text-sm text-blue-700 space-y-1">
          <li>Network charges show a 6.2% discrepancy - verify tariff rates used</li>
          <li>Peak usage shows minor discrepancy - may be due to meter read timing</li>
          <li>Overall invoice is $5.35 higher than calculated</li>
        </ul>
      </div>
    </div>
  )
}
