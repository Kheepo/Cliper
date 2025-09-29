import React, { createContext, useContext, useState, ReactNode } from 'react'
import { User, Session, AuthError } from '@supabase/supabase-js'
import { UserProfile } from '../lib/supabase'

interface AuthContextType {
  user: User | null
  profile: UserProfile | null
  session: Session | null
  loading: boolean
  isAuthenticated: boolean
  signIn: (email: string, password: string) => Promise<{ error?: AuthError }>
  signUp: (email: string, password: string) => Promise<{ error?: AuthError }>
  signOut: () => Promise<void>
  refreshSession: () => Promise<void>
  updateProfile: (updates: Partial<UserProfile>) => Promise<void>
  clearAuthState: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(false) // Set to false to avoid loading state

  const signIn = async (email: string, password: string) => {
    return { error: undefined }
  }

  const signUp = async (email: string, password: string) => {
    return { error: undefined }
  }

  const signOut = async () => {
    setUser(null)
    setProfile(null)
    setSession(null)
  }

  const refreshSession = async () => {
    // No-op for simplified version
  }

  const updateProfile = async (updates: Partial<UserProfile>) => {
    // No-op for simplified version
  }

  const clearAuthState = () => {
    setUser(null)
    setProfile(null)
    setSession(null)
  }

  const value: AuthContextType = {
    user,
    profile,
    session,
    loading,
    isAuthenticated: !!user,
    signIn,
    signUp,
    signOut,
    refreshSession,
    updateProfile,
    clearAuthState
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}