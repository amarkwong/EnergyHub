import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../api/client'

export default function Login() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email, password)
      const nmis = await api.get('/api/account/nmis')
      navigate(nmis.data?.length > 0 ? '/' : '/onboarding')
    } catch (err) {
      setError((err as Error)?.message || 'Login failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
      <form onSubmit={onSubmit} className="w-full max-w-md bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <h1 className="text-2xl font-bold text-slate-900">Sign In</h1>
        <input
          type="email"
          placeholder="Email"
          className="w-full rounded-md border border-slate-300 px-3 py-2"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          className="w-full rounded-md border border-slate-300 px-3 py-2"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button disabled={isSubmitting} className="w-full rounded-md bg-primary-600 text-white py-2 font-medium">
          {isSubmitting ? 'Signing in...' : 'Sign In'}
        </button>
        <p className="text-sm text-slate-600">
          No account yet? <Link className="text-primary-700 font-medium" to="/register">Create one</Link>
        </p>
      </form>
    </div>
  )
}

