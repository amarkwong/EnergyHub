import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { LATEST_INVOICE_FILE_KEY } from '../constants/storage'

type AccountNmi = {
  id: number
  nmi: string
  label?: string | null
  created_at: string
}

export default function Onboarding() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [invoiceError, setInvoiceError] = useState<string | null>(null)

  const { data: nmis = [], isLoading } = useQuery({
    queryKey: ['account-nmis'],
    queryFn: async () => {
      const response = await api.get('/api/account/nmis')
      return response.data as AccountNmi[]
    },
  })

  const addNmi = useMutation({
    mutationFn: async (nmi: string) => api.post('/api/account/nmis', { nmi }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['account-nmis'] }),
  })

  const uploadInvoice = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.post('/api/invoices/upload', form)
    },
    onSuccess: async (response) => {
      setInvoiceError(null)
      const fileId = response.data?.file_id
      if (typeof fileId === 'string' && fileId) {
        window.localStorage.setItem(LATEST_INVOICE_FILE_KEY, fileId)
      }
      await queryClient.invalidateQueries({ queryKey: ['account-nmis'] })
    },
    onError: (err) => {
      setInvoiceError((err as Error)?.message || 'Invoice upload failed')
    },
  })

  const candidates = useMemo(
    () => Array.from(new Set(input.split(/[\n,\s]+/).map((v) => v.trim().toUpperCase()).filter(Boolean))),
    [input]
  )

  const submit = async () => {
    setError(null)
    const valid = candidates.filter((nmi) => /^[A-Z0-9]{10,11}$/.test(nmi))
    if (valid.length === 0) {
      setError('Enter at least one valid NMI (10-11 letters/numbers).')
      return
    }
    for (const nmi of valid) {
      await addNmi.mutateAsync(nmi)
    }
    setInput('')
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">NMI Setup</h1>
        <p className="mt-1 text-sm text-slate-600">
          Add one or more NMIs to your account. Each NMI will keep its own invoice-linked retailer plan and network tariff history.
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter one NMI per line, or comma-separated"
          className="w-full min-h-24 rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex gap-2">
          <button onClick={submit} className="px-4 py-2 rounded-md bg-primary-600 text-white text-sm font-medium">
            Add NMI(s)
          </button>
          <button
            onClick={() => navigate('/')}
            disabled={nmis.length === 0}
            className={`px-4 py-2 rounded-md text-sm font-medium ${nmis.length === 0 ? 'bg-slate-200 text-slate-500' : 'bg-slate-800 text-white'}`}
          >
            Continue to Dashboard
          </button>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
        <h2 className="text-lg font-medium text-slate-900">Or Add NMI from Invoice</h2>
        <p className="text-sm text-slate-600">
          Upload an invoice PDF and we will extract NMI and link retailer/tariff period to your account automatically.
        </p>
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (!file) return
            uploadInvoice.mutate(file)
          }}
          className="block w-full text-sm text-slate-700 file:mr-4 file:rounded-md file:border-0 file:bg-primary-600 file:px-4 file:py-2 file:text-white"
        />
        {uploadInvoice.isPending && <p className="text-sm text-slate-500">Parsing invoice...</p>}
        {invoiceError && <p className="text-sm text-red-600">{invoiceError}</p>}
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-5">
        <h2 className="text-lg font-medium text-slate-900">Registered NMIs</h2>
        {isLoading ? (
          <p className="text-sm text-slate-500 mt-2">Loading...</p>
        ) : nmis.length === 0 ? (
          <p className="text-sm text-slate-500 mt-2">No NMIs yet.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {nmis.map((item) => (
              <li key={item.id} className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700">
                {item.nmi}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
