export default function Emulator() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Plan Emulator</h1>
        <p className="mt-1 text-sm text-slate-500">
          Emulate your bill using your meter data with alternative retailer plans and selectable network tariffs.
        </p>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <p className="text-slate-700">
          This module will compare your historic usage against alternative plans and tariff options.
        </p>
        <p className="mt-2 text-sm text-slate-500">Next: plug in meter intervals + plan/tariff selectors + cost delta chart.</p>
      </div>
    </div>
  )
}

