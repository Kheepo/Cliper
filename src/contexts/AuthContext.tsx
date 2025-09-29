import React, { createContext, useContext, useEffect, useState, ReactNode, useCallback } from 'react'
import { User, Session, AuthError } from '@supabase/supabase-js'
import { supabase, getUserProfile, createUserProfile, UserProfile } from '../lib/supabase'
import { toast } from 'sonner'
import { authService, AuthState } from '../services/authService'
import { cacheManager } from '../utils/cacheManager'

interface AuthContextType {
  user: User | null
  profile: UserProfile | null
  session: Session | null
  loading: boolean
  isAuthenticated: boolean
  maintenanceMode: boolean
  signIn: (email: string, password: string) => Promise<{ error?: AuthError; success?: boolean }>
  signUp: (email: string, password: string, displayName?: string) => Promise<{ error?: AuthError; success?: boolean }>
  signOut: () => Promise<void>
  refreshSession: () => Promise<void>
  updateProfile: (updates: Partial<UserProfile>) => Promise<void>
  clearAuthState: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
  children: ReactNode
}

// Auth state persistence keys
const AUTH_STORAGE_KEY = 'cliper_auth_state'
const PROFILE_STORAGE_KEY = 'cliper_user_profile'

// Helper functions for auth state persistence
const saveAuthState = (user: User | null, session: Session | null) => {
  try {
    if (user && session) {
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ user, session }))
    } else {
      localStorage.removeItem(AUTH_STORAGE_KEY)
    }
  } catch (error) {
    console.warn('Failed to save auth state:', error)
  }
}

const loadAuthState = (): { user: User | null; session: Session | null } => {
  try {
    const stored = localStorage.getItem(AUTH_STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      // Validate that the session hasn't expired
      if (parsed.session?.expires_at && parsed.session.expires_at * 1000 > Date.now()) {
        return { user: parsed.user, session: parsed.session }
      }
    }
  } catch (error) {
    console.warn('Failed to load auth state:', error)
  }
  return { user: null, session: null }
}

const saveProfile = (profile: UserProfile | null) => {
  try {
    if (profile) {
      cacheManager.setWithTimestamp(PROFILE_STORAGE_KEY, profile)
    } else {
      localStorage.removeItem(PROFILE_STORAGE_KEY)
    }
  } catch (error) {
    console.warn('Failed to save profile:', error)
  }
}

const loadProfile = (): UserProfile | null => {
  try {
    return cacheManager.getWithExpiration(PROFILE_STORAGE_KEY)
  } catch (error) {
    console.warn('Failed to load profile:', error)
    return null
  }
}

export function AuthProvider({ children }: AuthProviderProps) {
  // Initialize state from localStorage
  const [user, setUser] = useState<User | null>(() => loadAuthState().user)
  const [profile, setProfile] = useState<UserProfile | null>(() => loadProfile())
  const [session, setSession] = useState<Session | null>(() => loadAuthState().session)
  const [loading, setLoading] = useState(true)
  const [retryCount, setRetryCount] = useState(0)
  const [maintenanceMode] = useState(true) // Temporarily disable auth services

  // Clear auth state function
  const clearAuthState = useCallback(() => {
    setUser(null)
    setProfile(null)
    setSession(null)
    saveAuthState(null, null)
    saveProfile(null)
    
    // Clear auth-related cache with cache manager
    cacheManager.clearStorageKeys([
      'cliper_user_profile',
      'cliper_auth_state', 
      'cliper_session_data',
      'sb-' // Clear all Supabase keys
    ])
    
    // Also clear any Supabase auth keys
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith('sb-')) {
        localStorage.removeItem(key)
      }
    })
  }, [])

  // Enhanced session validation
  const validateSession = useCallback(async (currentSession: Session | null): Promise<boolean> => {
    if (!currentSession) return false
    
    // Check if session is expired
    if (currentSession.expires_at && currentSession.expires_at * 1000 <= Date.now()) {
      console.log('Session expired, attempting refresh')
      try {
        const { data, error } = await supabase.auth.refreshSession()
        if (error || !data.session) {
          clearAuthState()
          return false
        }
        return true
      } catch (error) {
        console.error('Session refresh failed:', error)
        clearAuthState()
        return false
      }
    }
    
    return true
  }, [clearAuthState])

  // Initialize auth state and set up listeners
  useEffect(() => {
    let mounted = true

    // Get initial session with retry logic
    const initializeAuth = async () => {
      try {
        // First try to validate existing session from localStorage
        const storedState = loadAuthState()
        if (storedState.session && await validateSession(storedState.session)) {
          if (mounted) {
            setSession(storedState.session)
            setUser(storedState.user)
            if (storedState.user) {
              await loadUserProfile(storedState.user.id)
            }
            setLoading(false)
          }
          return
        }

        // Get fresh session from Supabase
        const { data: { session: initialSession }, error } = await supabase.auth.getSession()
        
        if (error) {
          console.error('Error getting initial session:', error)
          if (mounted) {
            clearAuthState()
            setLoading(false)
          }
          return
        }

        if (mounted) {
          if (initialSession && await validateSession(initialSession)) {
            setSession(initialSession)
            setUser(initialSession.user)
            saveAuthState(initialSession.user, initialSession)
            await loadUserProfile(initialSession.user.id)
          } else {
            clearAuthState()
          }
          setLoading(false)
        }
      } catch (error) {
        console.error('Auth initialization error:', error)
        if (mounted) {
          clearAuthState()
          setLoading(false)
        }
      }
    }

    initializeAuth()

    // Listen for auth changes with enhanced error handling
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log('Auth state changed:', event, session?.user?.id)
        
        if (!mounted) return

        try {
          // Update state and persist
          setSession(session)
          setUser(session?.user ?? null)
          
          if (session?.user) {
            saveAuthState(session.user, session)
            await loadUserProfile(session.user.id)
            setRetryCount(0) // Reset retry count on successful auth
          } else {
            clearAuthState()
          }
          
          setLoading(false)

          // Handle specific auth events
          switch (event) {
            case 'SIGNED_IN':
              toast.success('Successfully signed in!')
              break
            case 'SIGNED_OUT':
              toast.success('Successfully signed out!')
              break
            case 'TOKEN_REFRESHED':
              console.log('Token refreshed successfully')
              if (session) {
                saveAuthState(session.user, session)
              }
              break
            case 'USER_UPDATED':
              if (session?.user) {
                await loadUserProfile(session.user.id)
              }
              break
            case 'PASSWORD_RECOVERY':
              toast.info('Password recovery email sent')
              break
          }
        } catch (error) {
          console.error('Auth state change error:', error)
          if (retryCount < 3) {
            setRetryCount(prev => prev + 1)
            setTimeout(() => {
              if (session) {
                loadUserProfile(session.user.id)
              }
            }, 1000 * Math.pow(2, retryCount)) // Exponential backoff
          } else {
            toast.error('Authentication error. Please refresh the page.')
          }
        }
      }
    )

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [])

  // Load user profile from database with retry logic
  const loadUserProfile = async (authId: string, retryAttempt = 0) => {
    try {
      let userProfile = await getUserProfile(authId)
      
      // Create profile if it doesn't exist
      if (!userProfile && user) {
        const newProfile = {
          auth_id: authId,
          email: user.email || '',
          display_name: user.email || 'User',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
        
        userProfile = await createUserProfile(newProfile)
      }
      
      setProfile(userProfile)
      saveProfile(userProfile)
    } catch (error) {
      console.error('Error loading user profile:', error)
      
      // Retry logic for profile loading
      if (retryAttempt < 2) {
        setTimeout(() => {
          loadUserProfile(authId, retryAttempt + 1)
        }, 1000 * (retryAttempt + 1))
      } else {
        // Don't show error toast for profile loading failures
        // as the user can still use the app without a profile
        console.warn('Failed to load user profile after retries')
      }
    }
  }

  // Sign in with email and password
  const signIn = async (email: string, password: string) => {
    if (maintenanceMode) {
      return { error: { message: 'Login services are temporarily unavailable for maintenance. Please try again later.' } as AuthError }
    }
    
    try {
      setLoading(true)
      const { data, error } = await supabase.auth.signInWithPassword({ email, password })
      
      if (error) {
        toast.error(error.message)
        setLoading(false)
        return { error }
      }
      
      // Wait for session to be established
      if (data.session) {
        setSession(data.session)
        setUser(data.session.user)
        saveAuthState(data.session.user, data.session)
        await loadUserProfile(data.session.user.id)
      }
      
      setLoading(false)
      return { success: true }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred'
      toast.error(errorMessage)
      setLoading(false)
      return { error: { message: errorMessage } as AuthError }
    }
  }

  // Sign up with email and password
  const signUp = async (email: string, password: string, displayName?: string) => {
    if (maintenanceMode) {
      return { error: { message: 'Registration services are temporarily unavailable for maintenance. Please try again later.' } as AuthError }
    }
    
    try {
      setLoading(true)
      const signUpData: any = { email, password }
      if (displayName) {
        signUpData.options = {
          data: {
            display_name: displayName
          }
        }
      }
      
      const { error } = await supabase.auth.signUp(signUpData)
      
      if (error) {
        toast.error(error.message)
        return { error }
      }
      
      toast.success('Check your email for the confirmation link!')
      return { success: true }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred'
      toast.error(errorMessage)
      return { error: { message: errorMessage } as AuthError }
    } finally {
      setLoading(false)
    }
  }

  // Sign out
  const signOut = async () => {
    try {
      setLoading(true)
      await authService.signOut()
      clearAuthState()
      toast.success('Signed out successfully')
    } catch (error) {
      console.error('Sign out error:', error)
      const authError = authService.handleAuthError(error)
      toast.error(authError.message)
      // Still clear auth state even if sign out fails
      clearAuthState()
    } finally {
      setLoading(false)
    }
  }

  // Refresh session manually with enhanced error handling
  const refreshSession = async () => {
    try {
      setLoading(true)
      const refreshedSession = await authService.refreshSession()
      
      if (refreshedSession) {
        setSession(refreshedSession)
        setUser(refreshedSession.user)
        saveAuthState(refreshedSession.user, refreshedSession)
        
        // Reload profile if user changed
        if (refreshedSession.user.id !== user?.id) {
          await loadUserProfile(refreshedSession.user.id)
        }
        
        toast.success('Session refreshed successfully', {
          duration: 2000
        })
      } else {
        // Session refresh failed, clear auth state
        clearAuthState()
        
        toast.error('Session expired', {
          description: 'Please sign in again',
          duration: 4000
        })
      }
    } catch (error) {
      console.error('Failed to refresh session:', error)
      const authError = authService.handleAuthError(error)
      
      toast.error(authError.message, {
        description: 'Please sign in again',
        duration: 4000
      })
      
      // Clear auth state on refresh failure
      clearAuthState()
    } finally {
      setLoading(false)
    }
  }

  // Update user profile
  const updateProfile = async (updates: Partial<UserProfile>) => {
    if (!user || !profile) {
      toast.error('No user profile to update')
      return
    }

    try {
      const { data, error } = await supabase
        .from('users')
        .update({ ...updates, updated_at: new Date().toISOString() })
        .eq('auth_id', user.id)
        .select()
        .single()

      if (error) {
        toast.error('Failed to update profile')
        throw error
      }

      setProfile(data)
      toast.success('Profile updated successfully!')
    } catch (error) {
      console.error('Profile update error:', error)
      toast.error('Failed to update profile')
    }
  }

  const value: AuthContextType = {
    user,
    profile,
    session,
    loading,
    isAuthenticated: !!user && !!session,
    maintenanceMode,
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

// Hook for protected routes
export function useRequireAuth() {
  const auth = useAuth()
  
  useEffect(() => {
    if (!auth.loading && !auth.user) {
      toast.error('Please sign in to access this page')
      // You can redirect to login page here if using React Router
    }
  }, [auth.loading, auth.user])
  
  return auth
}

// Hook for automatic token refresh with enhanced timing
export function useTokenRefresh() {
  const { session, refreshSession, isAuthenticated } = useAuth()
  
  useEffect(() => {
    if (!session || !isAuthenticated) return
    
    // Calculate time until token expires (refresh 5 minutes before expiry)
    const expiresAt = session.expires_at ? session.expires_at * 1000 : Date.now() + 3600000
    const now = Date.now()
    const refreshTime = expiresAt - now - 5 * 60 * 1000 // 5 minutes before expiry
    
    // If token is already expired or expires very soon, refresh immediately
    if (refreshTime <= 0) {
      refreshSession()
      return
    }
    
    // Set up automatic refresh
    const timeoutId = setTimeout(() => {
      refreshSession()
    }, refreshTime)
    
    // Also set up a backup refresh closer to expiry
    const backupRefreshTime = expiresAt - now - 1 * 60 * 1000 // 1 minute before expiry
    const backupTimeoutId = backupRefreshTime > 0 ? setTimeout(() => {
      refreshSession()
    }, backupRefreshTime) : null
    
    return () => {
      clearTimeout(timeoutId)
      if (backupTimeoutId) clearTimeout(backupTimeoutId)
    }
  }, [session, refreshSession, isAuthenticated])
}

// Hook for auth state persistence monitoring
export function useAuthPersistence() {
  const { user, session, isAuthenticated } = useAuth()
  
  useEffect(() => {
    // Monitor for storage events from other tabs
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === AUTH_STORAGE_KEY) {
        // Auth state changed in another tab
        if (!e.newValue && isAuthenticated) {
          // User signed out in another tab
          window.location.reload()
        } else if (e.newValue && !isAuthenticated) {
          // User signed in in another tab
          window.location.reload()
        }
      }
    }
    
    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [isAuthenticated])
  
  // Persist auth state changes
  useEffect(() => {
    if (isAuthenticated && user && session) {
      saveAuthState(user, session)
    }
  }, [user, session, isAuthenticated])
}