import { useQuery } from '@tanstack/react-query'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { useAuth } from './context/AuthContext'
import { api } from './api/client'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Consumption from './pages/Consumption'
import Reconciliation from './pages/Reconciliation'
import Tariffs from './pages/Tariffs'
import Retailers from './pages/Retailers'
import Emulator from './pages/Emulator'
import Login from './pages/Login'
import Register from './pages/Register'
import Onboarding from './pages/Onboarding'

function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) return <div className="p-8 text-slate-600">Loading...</div>
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Outlet />
}

function RequireNmi() {
  const { data, isLoading } = useQuery({
    queryKey: ['account-nmis'],
    queryFn: async () => {
      const response = await api.get('/api/account/nmis')
      return response.data as Array<{ id: number; nmi: string }>
    },
  })
  if (isLoading) return <div className="p-8 text-slate-600">Loading account...</div>
  if (!data || data.length === 0) return <Navigate to="/onboarding" replace />
  return <Outlet />
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<RequireAuth />}>
        <Route path="/" element={<Layout />}>
          <Route path="onboarding" element={<Onboarding />} />
          <Route path="upload" element={<Upload />} />
          <Route element={<RequireNmi />}>
            <Route index element={<Dashboard />} />
            <Route path="consumption" element={<Consumption />} />
            <Route path="reconciliation" element={<Reconciliation />} />
            <Route path="network" element={<Tariffs />} />
            <Route path="tariffs" element={<Tariffs />} />
            <Route path="retailers" element={<Retailers />} />
            <Route path="emulator" element={<Emulator />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  )
}

export default App
