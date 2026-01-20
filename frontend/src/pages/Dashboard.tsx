import { Link } from 'react-router-dom'

const stats = [
  { name: 'Total Consumption', value: '1,234 kWh', change: '+4.75%', changeType: 'increase' },
  { name: 'Invoice Discrepancy', value: '$45.20', change: '-2.3%', changeType: 'decrease' },
  { name: 'Reconciled Invoices', value: '12', change: '+3', changeType: 'increase' },
  { name: 'Pending Reviews', value: '2', change: '0', changeType: 'neutral' },
]

const quickActions = [
  { name: 'Upload NEM12', description: 'Upload consumption data', href: '/upload', icon: '📊' },
  { name: 'Upload Invoice', description: 'Parse invoice PDF', href: '/upload', icon: '📄' },
  { name: 'Run Reconciliation', description: 'Compare invoice vs calculated', href: '/reconciliation', icon: '🔍' },
  { name: 'View Tariffs', description: 'Browse network tariffs', href: '/tariffs', icon: '💰' },
]

export default function Dashboard() {
  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Overview of your energy consumption and invoice reconciliation status.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.name}
            className="bg-white overflow-hidden rounded-lg border border-slate-200 px-4 py-5 sm:p-6"
          >
            <dt className="text-sm font-medium text-slate-500 truncate">{stat.name}</dt>
            <dd className="mt-1 flex items-baseline justify-between md:block lg:flex">
              <div className="text-2xl font-semibold text-slate-900">{stat.value}</div>
              <div
                className={`inline-flex items-baseline px-2.5 py-0.5 rounded-full text-sm font-medium ${
                  stat.changeType === 'increase'
                    ? 'bg-green-100 text-green-800'
                    : stat.changeType === 'decrease'
                    ? 'bg-red-100 text-red-800'
                    : 'bg-slate-100 text-slate-800'
                }`}
              >
                {stat.change}
              </div>
            </dd>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="text-lg font-medium text-slate-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {quickActions.map((action) => (
            <Link
              key={action.name}
              to={action.href}
              className="relative group bg-white p-6 rounded-lg border border-slate-200 hover:border-primary-300 hover:shadow-md transition-all"
            >
              <div className="text-3xl mb-3">{action.icon}</div>
              <h3 className="text-base font-medium text-slate-900 group-hover:text-primary-600">
                {action.name}
              </h3>
              <p className="mt-1 text-sm text-slate-500">{action.description}</p>
            </Link>
          ))}
        </div>
      </div>

      {/* Recent activity */}
      <div>
        <h2 className="text-lg font-medium text-slate-900 mb-4">Recent Activity</h2>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="p-6 text-center text-slate-500">
            <p>No recent activity. Upload your first NEM12 file to get started.</p>
            <Link
              to="/upload"
              className="inline-flex items-center mt-4 px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700"
            >
              Upload Data
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
