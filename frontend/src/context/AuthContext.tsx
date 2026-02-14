import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'

type AccountType = 'residential' | 'business'

type User = {
  id: number
  email: string
  account_type: AccountType
  display_name?: string | null
  created_at: string
}

type RegisterPayload = {
  email: string
  password: string
  account_type: AccountType
  display_name?: string
}

type AuthContextValue = {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => Promise<void>
  refreshMe: () => Promise<void>
}

const TOKEN_KEY = 'token'
const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshMe = async () => {
    const token = window.localStorage.getItem(TOKEN_KEY)
    if (!token) {
      setUser(null)
      return
    }
    try {
      const response = await api.get('/api/auth/me')
      setUser(response.data as User)
    } catch {
      window.localStorage.removeItem(TOKEN_KEY)
      setUser(null)
    }
  }

  useEffect(() => {
    refreshMe().finally(() => setIsLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    const response = await api.post('/api/auth/login', { email, password })
    const token = response.data?.access_token as string
    if (!token) throw new Error('Missing access token in login response')
    window.localStorage.setItem(TOKEN_KEY, token)
    setUser(response.data.user as User)
  }

  const register = async (payload: RegisterPayload) => {
    const response = await api.post('/api/auth/register', payload)
    const token = response.data?.access_token as string
    if (!token) throw new Error('Missing access token in register response')
    window.localStorage.setItem(TOKEN_KEY, token)
    setUser(response.data.user as User)
  }

  const logout = async () => {
    const token = window.localStorage.getItem(TOKEN_KEY)
    if (token) {
      try {
        await api.post('/api/auth/logout')
      } catch {
        // Best-effort logout.
      }
    }
    window.localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: !!user,
      login,
      register,
      logout,
      refreshMe,
    }),
    [user, isLoading]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

