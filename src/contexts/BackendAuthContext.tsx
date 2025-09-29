import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { backendAuthService } from '../services/backendAuthService'
import { toast } from 'sonner'

interface User {
  id: string
  email: string
  display_name: string
  photo_url?: string
  is_active: boolean
  email_verified: boolean
  role: string
  created_at: string
  updated_at: string
  last_login: string
}

interface AuthContextType {
  user: User | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<{ success: boolean; error?: string }>
  signUp: (email: string, password: string, fullName?: string) => Promise<{ success: boolean; error?: string }>
  signOut: () => Promise<void>
  refreshSession: () => Promise<void>
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if user is already authenticated on app start
    const initializeAuth = async () => {
      try {
        const result = await backendAuthService.verifyToken()
        if (result.success && result.user) {
          setUser(result.user)
        }
      } catch (error) {
        console.error('Auth initialization error:', error)
      } finally {
        setLoading(false)
      }
    }

    initializeAuth()
  }, [])

  const signIn = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    setLoading(true)
    try {
      const result = await backendAuthService.login({ email, password })
      
      if (result.success) {
        // Verify the token and get user data
        const verifyResult = await backendAuthService.verifyToken()
        if (verifyResult.success && verifyResult.user) {
          setUser(verifyResult.user)
        }
      }
      
      return result
    } catch (error) {
      console.error('Sign in error:', error)
      return { success: false, error: 'An unexpected error occurred' }
    } finally {
      setLoading(false)
    }
  }

  const signUp = async (email: string, password: string, fullName?: string): Promise<{ success: boolean; error?: string }> => {
    setLoading(true)
    try {
      const result = await backendAuthService.register({ 
        email, 
        password, 
        full_name: fullName 
      })
      
      if (result.success) {
        // Verify the token and get user data
        const verifyResult = await backendAuthService.verifyToken()
        if (verifyResult.success && verifyResult.user) {
          setUser(verifyResult.user)
        }
      }
      
      return result
    } catch (error) {
      console.error('Sign up error:', error)
      return { success: false, error: 'An unexpected error occurred' }
    } finally {
      setLoading(false)
    }
  }

  const signOut = async (): Promise<void> => {
    setLoading(true)
    try {
      await backendAuthService.logout()
      setUser(null)
    } catch (error) {
      console.error('Sign out error:', error)
      toast.error('Error signing out')
    } finally {
      setLoading(false)
    }
  }

  const refreshSession = async (): Promise<void> => {
    setLoading(true)
    try {
      const result = await backendAuthService.verifyToken()
      if (result.success && result.user) {
        setUser(result.user)
        toast.success('Session refreshed successfully')
      } else {
        setUser(null)
        toast.error('Session expired. Please sign in again.')
      }
    } catch (error) {
      console.error('Session refresh error:', error)
      setUser(null)
      toast.error('Failed to refresh session')
    } finally {
      setLoading(false)
    }
  }

  const isAuthenticated = !!user && backendAuthService.isAuthenticated()

  const value: AuthContextType = {
    user,
    loading,
    signIn,
    signUp,
    signOut,
    refreshSession,
    isAuthenticated,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export default AuthContext