export default function Summary() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Best Plan Summary</h1>
        <p className="mt-1 text-sm text-slate-500">
          Ranked recommendation of best-fit plan based on your past usage profile and available tariffs.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <p className="text-slate-700">
          This summary will consolidate reconciliation and emulator results into a clear recommendation.
        </p>
        <p className="mt-2 text-sm text-slate-500">Next: add ranked plan cards, annual savings estimate, and confidence notes.</p>
      </div>
    </div>
  )
}

