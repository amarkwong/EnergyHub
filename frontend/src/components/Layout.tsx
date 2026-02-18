import { useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import { useAppMode } from '../context/AppModeContext'
import { useAuth } from '../context/AuthContext'

const residentialNavigation = [
  { name: 'Home', href: '/' },
  { name: 'Upload Data', href: '/upload' },
  { name: 'My Usage', href: '/consumption' },
  { name: 'Bill Check', href: '/reconciliation' },
  { name: 'Emulator', href: '/emulator' },
  { name: 'Summary', href: '/summary' },
  { name: 'Network', href: '/network' },
  { name: 'Retailers', href: '/retailers' },
]

const businessNavigation = [
  { name: 'Portfolio Home', href: '/' },
  { name: 'Data Intake', href: '/upload' },
  { name: 'Meter Portfolio', href: '/consumption' },
  { name: 'Invoice Audit', href: '/reconciliation' },
  { name: 'Emulator', href: '/emulator' },
  { name: 'Summary', href: '/summary' },
  { name: 'Network Charges', href: '/network' },
  { name: 'Retail Contracts', href: '/retailers' },
]

export default function Layout() {
  const { mode, setMode } = useAppMode()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const navigation = mode === 'business' ? businessNavigation : residentialNavigation

  useEffect(() => {
    if (!user) return
    setMode(user.account_type)
  }, [user, setMode])

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="md:grid md:grid-cols-[270px_1fr]">
        <aside className="bg-slate-950 text-slate-100 md:min-h-screen">
          <div className="px-5 py-5 border-b border-slate-800">
            <div className="text-2xl font-bold tracking-tight">EnergyHub</div>
            <div className="text-xs text-slate-400 mt-1">Data-backed tariff intelligence</div>
          </div>

          <div className="p-5 space-y-5">
            <div className="rounded-lg bg-slate-900 p-3 border border-slate-800">
              <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">View</div>
              <div className="px-2 py-2 rounded-md text-sm font-medium bg-primary-600 text-white text-center capitalize">
                {mode}
              </div>
            </div>

            <nav className="space-y-1">
              {navigation.map((item) => (
                <NavLink
                  key={item.name}
                  to={item.href}
                  className={({ isActive }) =>
                    clsx(
                      'block px-3 py-2 rounded-md text-sm font-medium transition-colors',
                      isActive ? 'bg-slate-100 text-slate-950' : 'text-slate-300 hover:bg-slate-900 hover:text-white'
                    )
                  }
                >
                  {item.name}
                </NavLink>
              ))}
            </nav>

            <div className="rounded-lg bg-slate-900 p-3 border border-slate-800">
              <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Trust Signals</div>
              <ul className="space-y-2 text-xs text-slate-300">
                <li>Source-traceable tariffs and plans</li>
                <li>TOU mapping aligned to local timezone</li>
                <li>Yearly history retained for audit</li>
              </ul>
            </div>

            <button
              onClick={async () => {
                await logout()
                navigate('/login')
              }}
              className="w-full rounded-md bg-slate-800 text-slate-200 text-sm px-3 py-2 border border-slate-700 hover:bg-slate-700"
            >
              Sign Out
            </button>
          </div>
        </aside>

        <div className="min-h-screen flex flex-col">
          <header className="bg-white border-b border-slate-200 px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-lg font-semibold text-slate-900">
                  {mode === 'business' ? 'Business Workspace' : 'Residential Workspace'}
                </h1>
                <p className="text-sm text-slate-500">Transparent billing intelligence with source-backed pricing.</p>
              </div>
              <div className="text-sm text-slate-500">{user?.email}</div>
            </div>
          </header>

          <main className="px-4 sm:px-6 lg:px-8 py-8 flex-1">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
