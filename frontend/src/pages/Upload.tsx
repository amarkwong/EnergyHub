import { useState, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'

type UploadType = 'nem12' | 'invoice'

export default function Upload() {
  const [uploadType, setUploadType] = useState<UploadType>('nem12')
  const [dragActive, setDragActive] = useState(false)

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)

      const endpoint = uploadType === 'nem12' ? '/api/nem12/upload' : '/api/invoices/upload'
      return api.post(endpoint, formData)
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
          Upload NEM12 consumption data or invoice PDFs for reconciliation.
        </p>
      </div>

      {/* Upload type selector */}
      <div className="flex space-x-4">
        <button
          onClick={() => setUploadType('nem12')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            uploadType === 'nem12'
              ? 'bg-primary-600 text-white'
              : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
          }`}
        >
          NEM12 File
        </button>
        <button
          onClick={() => setUploadType('invoice')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            uploadType === 'invoice'
              ? 'bg-primary-600 text-white'
              : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50'
          }`}
        >
          Invoice PDF
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
          accept={uploadType === 'nem12' ? '.csv,.txt,.nem12' : '.pdf'}
          onChange={handleChange}
        />
        <label htmlFor="file-upload" className="cursor-pointer">
          <div className="text-4xl mb-4">
            {uploadType === 'nem12' ? '📊' : '📄'}
          </div>
          <p className="text-lg font-medium text-slate-900">
            {dragActive
              ? 'Drop file here'
              : `Upload ${uploadType === 'nem12' ? 'NEM12' : 'Invoice'} file`}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {uploadType === 'nem12'
              ? 'Drag and drop or click to select a .csv, .txt, or .nem12 file'
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
