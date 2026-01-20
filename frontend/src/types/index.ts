// NEM12 Types
export interface IntervalReading {
  nmi: string
  intervalDate: string
  intervalNumber: number
  value: number
  qualityFlag?: string
  unitOfMeasure: string
}

export interface MeterData {
  nmi: string
  meterSerial?: string
  registerId: string
  intervalLength: number
  unitOfMeasure: string
  startDate: string
  endDate: string
  totalConsumption: number
  totalGeneration?: number
}

export interface ConsumptionSummary {
  nmi: string
  periodStart: string
  periodEnd: string
  totalKwh: number
  peakKwh: number
  offPeakKwh: number
  shoulderKwh?: number
  demandKw?: number
}

// Invoice Types
export type ChargeType = 'usage' | 'demand' | 'supply' | 'network' | 'metering' | 'environmental' | 'gst' | 'other'

export interface InvoiceLineItem {
  description: string
  chargeType: ChargeType
  quantity?: number
  unit?: string
  rate?: number
  amount: number
  tariffCode?: string
  periodStart?: string
  periodEnd?: string
}

export interface ParsedInvoice {
  invoiceNumber: string
  invoiceDate: string
  dueDate?: string
  retailer: string
  nmi: string
  billingPeriodStart: string
  billingPeriodEnd: string
  lineItems: InvoiceLineItem[]
  subtotal: number
  gst: number
  total: number
  amountDue: number
}

// Tariff Types
export type TariffType = 'flat' | 'tou' | 'demand' | 'controlled_load'

export interface TimePeriod {
  name: string
  startTime: string
  endTime: string
  days: number[]
  rateCentsPerKwh: number
}

export interface NetworkTariff {
  tariffCode: string
  tariffName: string
  networkProvider: string
  tariffType: TariffType
  effectiveFrom: string
  effectiveTo?: string
  dailySupplyChargeCents: number
  usageRateCentsPerKwh?: number
  timePeriods?: TimePeriod[]
}

// Reconciliation Types
export type DiscrepancyStatus = 'match' | 'minor' | 'significant' | 'missing_invoiced' | 'missing_calculated'

export interface LineItemReconciliation {
  description: string
  chargeType: ChargeType
  invoicedQuantity?: number
  invoicedRate?: number
  invoicedAmount: number
  calculatedQuantity?: number
  calculatedRate?: number
  calculatedAmount?: number
  amountDifference: number
  percentageDifference?: number
  status: DiscrepancyStatus
  notes?: string
}

export interface ReconciliationSummary {
  reconciliationId: string
  nmi: string
  invoiceNumber: string
  billingPeriodStart: string
  billingPeriodEnd: string
  invoicedTotal: number
  calculatedTotal: number
  totalDifference: number
  totalPercentageDifference: number
  lineItems: LineItemReconciliation[]
  matchedItems: number
  minorDiscrepancies: number
  significantDiscrepancies: number
  missingItems: number
  overallStatus: DiscrepancyStatus
  confidenceScore: number
  recommendations: string[]
}
