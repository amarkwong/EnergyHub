import { Outlet, NavLink } from 'react-router-dom'
import { clsx } from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/' },
  { name: 'Upload Data', href: '/upload' },
  { name: 'Consumption', href: '/consumption' },
  { name: 'Reconciliation', href: '/reconciliation' },
  { name: 'Tariffs', href: '/tariffs' },
]

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              {/* Logo */}
              <div className="flex-shrink-0 flex items-center">
                <span className="text-2xl font-bold text-primary-600">
                  EnergyHub
                </span>
              </div>

              {/* Navigation */}
              <nav className="hidden sm:ml-8 sm:flex sm:space-x-4">
                {navigation.map((item) => (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    className={({ isActive }) =>
                      clsx(
                        'inline-flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
                        isActive
                          ? 'bg-primary-50 text-primary-700'
                          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                      )
                    }
                  >
                    {item.name}
                  </NavLink>
                ))}
              </nav>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-sm text-slate-500 text-center">
            EnergyHub - Invoice Reconciliation Platform
          </p>
        </div>
      </footer>
    </div>
  )
}
