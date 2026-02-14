import { useState, useCallback, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAppMode } from '../context/AppModeContext'
import { LATEST_INVOICE_FILE_KEY, LATEST_METER_FILE_KEY } from '../constants/storage'

type UploadType = 'nem12' | 'retailer_csv' | 'invoice'

export default function Upload() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { mode } = useAppMode()
  const [uploadType, setUploadType] = useState<UploadType>('nem12')
  const [dragActive, setDragActive] = useState(false)
  const stage = searchParams.get('stage') === 'invoice' ? 'invoice' : 'meter'

  useEffect(() => {
    if (stage === 'invoice') {
      setUploadType('invoice')
      return
    }
    setUploadType((prev) => (prev === 'invoice' ? 'nem12' : prev))
  }, [stage])

  const handleSelectUploadType = useCallback(
    (next: UploadType) => {
      setUploadType(next)
      if (mode !== 'residential') return
      setSearchParams({ stage: next === 'invoice' ? 'invoice' : 'meter' })
    },
    [mode, setSearchParams]
  )

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)

      const endpoint =
        uploadType === 'nem12'
          ? '/api/nem12/upload'
          : uploadType === 'retailer_csv'
            ? '/api/nem12/upload-retailer-csv'
            : '/api/invoices/upload'
      return api.post(endpoint, formData)
    },
    onSuccess: (response) => {
      const fileId = response.data?.file_id
      if (typeof fileId === 'string' && fileId) {
        if (uploadType !== 'invoice') {
          window.localStorage.setItem(LATEST_METER_FILE_KEY, fileId)
        } else {
          window.localStorage.setItem(LATEST_INVOICE_FILE_KEY, fileId)
        }
      }
      if (mode !== 'residential') return
      if (uploadType === 'invoice') {
        navigate('/reconciliation')
        return
      }
      setSearchParams({ stage: 'invoice' })
      setUploadType('invoice')
    },
  })

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setDragActive(false)

      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        uploadMutation.mutate(e.dataTransfer.files[0])
      }
    },
    [uploadMutation]
  )

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      uploadMutation.mutate(e.target.files[0])
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Upload Data</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload NEM12 files, retailer interval CSV data, or invoice PDFs for reconciliation.
        </p>
        {mode === 'residential' && (
          <p className="mt-2 text-sm text-slate-600">
            Step {stage === 'meter' ? '1 of 2' : '2 of 2'}: {stage === 'meter' ? 'Meter Data Module' : 'Invoice Module'}
          </p>
        )}
      </div>

      {/* Upload type selector */}
      <div className="flex space-x-4">
        <button
          onClick={() => handleSelectUploadType('nem12')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            uploadType === 'nem12'
              ? 'bg-primary-600 text-white'
              : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
          }`}
        >
          NEM12 File
        </button>
        <button
          onClick={() => handleSelectUploadType('invoice')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            uploadType === 'invoice'
              ? 'bg-primary-600 text-white'
              : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
          }`}
        >
          Invoice PDF
        </button>
        <button
          onClick={() => handleSelectUploadType('retailer_csv')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            uploadType === 'retailer_csv'
              ? 'bg-primary-600 text-white'
              : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
          }`}
        >
          Retailer CSV
        </button>
      </div>

      {/* Drop zone */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          dragActive
            ? 'border-primary-500 bg-primary-50'
            : 'border-slate-300 hover:border-slate-400'
        }`}
      >
        <input
          type="file"
          id="file-upload"
          className="sr-only"
          accept={uploadType === 'nem12' ? '.csv,.txt,.nem12' : uploadType === 'retailer_csv' ? '.csv' : '.pdf'}
          onChange={handleChange}
        />
        <label htmlFor="file-upload" className="cursor-pointer">
          <div className="text-4xl mb-4">
            {uploadType === 'invoice' ? '📄' : '📊'}
          </div>
          <p className="text-lg font-medium text-slate-900">
            {dragActive
              ? 'Drop file here'
              : `Upload ${uploadType === 'nem12' ? 'NEM12' : uploadType === 'retailer_csv' ? 'Retailer CSV' : 'Invoice'} file`}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {uploadType === 'nem12'
              ? 'Drag and drop or click to select a .csv, .txt, or .nem12 file'
              : uploadType === 'retailer_csv'
                ? 'Drag and drop or click to select a retailer interval .csv file'
                : 'Drag and drop or click to select a PDF file'}
          </p>
        </label>

        {uploadMutation.isPending && (
          <div className="absolute inset-0 bg-white/80 flex items-center justify-center rounded-lg">
            <div className="text-primary-600">Processing...</div>
          </div>
        )}
      </div>

      {/* Upload result */}
      {uploadMutation.isSuccess && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h3 className="text-green-800 font-medium">Upload Successful</h3>
          <pre className="mt-2 text-sm text-green-700 overflow-auto">
            {JSON.stringify(uploadMutation.data?.data, null, 2)}
          </pre>
        </div>
      )}

      {uploadMutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h3 className="text-red-800 font-medium">Upload Failed</h3>
          <p className="mt-1 text-sm text-red-700">
            {(uploadMutation.error as Error)?.message || 'An error occurred'}
          </p>
        </div>
      )}
    </div>
  )
}
