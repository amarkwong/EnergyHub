import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Register() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [accountType, setAccountType] = useState<'residential' | 'business'>('residential')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await register({
        email,
        password,
        account_type: accountType,
        display_name: displayName || undefined,
      })
      navigate('/onboarding')
    } catch (err) {
      setError((err as Error)?.message || 'Registration failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
      <form onSubmit={onSubmit} className="w-full max-w-md bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <h1 className="text-2xl font-bold text-slate-900">Create Account</h1>
        <input
          type="text"
          placeholder="Display name (optional)"
          className="w-full rounded-md border border-slate-300 px-3 py-2"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
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
          placeholder="Password (min 8 chars)"
          className="w-full rounded-md border border-slate-300 px-3 py-2"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setAccountType('residential')}
            className={`rounded-md border px-3 py-2 text-sm font-medium ${
              accountType === 'residential' ? 'bg-primary-600 text-white border-primary-600' : 'bg-white border-slate-300 text-slate-700'
            }`}
          >
            Residential
          </button>
          <button
            type="button"
            onClick={() => setAccountType('business')}
            className={`rounded-md border px-3 py-2 text-sm font-medium ${
              accountType === 'business' ? 'bg-primary-600 text-white border-primary-600' : 'bg-white border-slate-300 text-slate-700'
            }`}
          >
            Business
          </button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button disabled={isSubmitting} className="w-full rounded-md bg-primary-600 text-white py-2 font-medium">
          {isSubmitting ? 'Creating...' : 'Create Account'}
        </button>
        <p className="text-sm text-slate-600">
          Already have an account? <Link className="text-primary-700 font-medium" to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  )
}

