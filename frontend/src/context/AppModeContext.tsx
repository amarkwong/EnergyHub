import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type AppMode = 'residential' | 'business'

type AppModeContextValue = {
  mode: AppMode
  setMode: (mode: AppMode) => void
}

const STORAGE_KEY = 'energyhub_app_mode'

const AppModeContext = createContext<AppModeContextValue | undefined>(undefined)

export function AppModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<AppMode>('residential')

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === 'residential' || saved === 'business') {
      setModeState(saved)
    }
  }, [])

  const setMode = (next: AppMode) => {
    setModeState(next)
    window.localStorage.setItem(STORAGE_KEY, next)
  }

  const value = useMemo(() => ({ mode, setMode }), [mode])
  return <AppModeContext.Provider value={value}>{children}</AppModeContext.Provider>
}

export function useAppMode() {
  const ctx = useContext(AppModeContext)
  if (!ctx) {
    throw new Error('useAppMode must be used within AppModeProvider')
  }
  return ctx
}
