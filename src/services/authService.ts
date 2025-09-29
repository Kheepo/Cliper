import { supabase } from '../lib/supabase'
import { User, Session } from '@supabase/supabase-js'
import { toast } from 'sonner'

export interface AuthState {
  user: User | null
  session: Session | null
  isAuthenticated: boolean
  isLoading: boolean
}

export interface AuthError {
  message: string
  code?: string
  status?: number
}

class AuthService {
  private refreshPromise: Promise<Session | null> | null = null
  private refreshTimeout: NodeJS.Timeout | null = null
  private readonly REFRESH_THRESHOLD = 5 * 60 * 1000 // 5 minutes before expiry
  private readonly MAX_RETRY_ATTEMPTS = 3
  private retryCount = 0

  /**
   * Get current session with automatic refresh if needed
   */
  async getCurrentSession(): Promise<Session | null> {
    try {
      const { data: { session }, error } = await supabase.auth.getSession()
      
      if (error) {
        console.error('Error getting session:', error)
        return null
      }

      if (!session) {
        return null
      }

      // Check if token needs refresh
      if (this.shouldRefreshToken(session)) {
        return await this.refreshSession()
      }

      return session
    } catch (error) {
      console.error('Failed to get current session:', error)
      return null
    }
  }

  /**
   * Refresh the current session
   */
  async refreshSession(): Promise<Session | null> {
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      return await this.refreshPromise
    }

    this.refreshPromise = this.performRefresh()
    
    try {
      const session = await this.refreshPromise
      this.retryCount = 0 // Reset retry count on success
      return session
    } catch (error) {
      console.error('Session refresh failed:', error)
      return null
    } finally {
      this.refreshPromise = null
    }
  }

  /**
   * Perform the actual session refresh
   */
  private async performRefresh(): Promise<Session | null> {
    try {
      const { data: { session }, error } = await supabase.auth.refreshSession()
      
      if (error) {
        console.error('Refresh session error:', error)
        
        // Handle specific error cases
        if (error.message.includes('refresh_token_not_found') || 
            error.message.includes('invalid_grant')) {
          // Token is completely invalid, user needs to sign in again
          await this.signOut()
          throw new Error('Session expired. Please sign in again.')
        }
        
        // Retry for network or temporary errors
        if (this.retryCount < this.MAX_RETRY_ATTEMPTS && 
            (error.message.includes('network') || error.message.includes('timeout'))) {
          this.retryCount++
          await this.delay(1000 * this.retryCount) // Exponential backoff
          return await this.performRefresh()
        }
        
        throw error
      }

      if (session) {
        // Schedule next refresh
        this.scheduleTokenRefresh(session)
      }

      return session
    } catch (error) {
      console.error('Failed to refresh session:', error)
      throw error
    }
  }

  /**
   * Check if token should be refreshed
   */
  private shouldRefreshToken(session: Session): boolean {
    if (!session.expires_at) {
      return false
    }

    const expiryTime = session.expires_at * 1000 // Convert to milliseconds
    const currentTime = Date.now()
    const timeUntilExpiry = expiryTime - currentTime

    return timeUntilExpiry <= this.REFRESH_THRESHOLD
  }

  /**
   * Schedule automatic token refresh
   */
  private scheduleTokenRefresh(session: Session): void {
    if (this.refreshTimeout) {
      clearTimeout(this.refreshTimeout)
    }

    if (!session.expires_at) {
      return
    }

    const expiryTime = session.expires_at * 1000
    const currentTime = Date.now()
    const refreshTime = expiryTime - this.REFRESH_THRESHOLD
    const delay = Math.max(0, refreshTime - currentTime)

    this.refreshTimeout = setTimeout(async () => {
      try {
        await this.refreshSession()
      } catch (error) {
        console.error('Scheduled refresh failed:', error)
      }
    }, delay)
  }

  /**
   * Get authentication headers for API requests
   */
  async getAuthHeaders(): Promise<Record<string, string>> {
    const session = await this.getCurrentSession()
    
    if (!session?.access_token) {
      throw new Error('No valid session found')
    }

    return {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json'
    }
  }

  /**
   * Validate current authentication state
   */
  async validateAuth(): Promise<boolean> {
    try {
      const session = await this.getCurrentSession()
      return !!session?.access_token
    } catch (error) {
      console.error('Auth validation failed:', error)
      return false
    }
  }

  /**
   * Sign out user and clean up
   */
  async signOut(): Promise<void> {
    try {
      // Clear refresh timeout
      if (this.refreshTimeout) {
        clearTimeout(this.refreshTimeout)
        this.refreshTimeout = null
      }

      // Clear any pending refresh promise
      this.refreshPromise = null
      this.retryCount = 0

      // Sign out from Supabase
      const { error } = await supabase.auth.signOut()
      
      if (error) {
        console.error('Sign out error:', error)
      }
    } catch (error) {
      console.error('Failed to sign out:', error)
    }
  }

  /**
   * Handle authentication errors
   */
  handleAuthError(error: any): AuthError {
    let message = 'Authentication failed'
    let code = 'AUTH_ERROR'
    let status = 401

    if (error?.message) {
      if (error.message.includes('JWT expired') || 
          error.message.includes('token_expired')) {
        message = 'Your session has expired. Please sign in again.'
        code = 'TOKEN_EXPIRED'
      } else if (error.message.includes('invalid_token') || 
                 error.message.includes('malformed')) {
        message = 'Invalid authentication token. Please sign in again.'
        code = 'INVALID_TOKEN'
      } else if (error.message.includes('network') || 
                 error.message.includes('timeout')) {
        message = 'Network error during authentication. Please try again.'
        code = 'NETWORK_ERROR'
        status = 0
      } else {
        message = error.message
      }
    }

    return { message, code, status }
  }

  /**
   * Retry authentication operation with exponential backoff
   */
  async retryAuthOperation<T>(
    operation: () => Promise<T>,
    maxRetries: number = 3
  ): Promise<T> {
    let lastError: any

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation()
      } catch (error) {
        lastError = error
        
        // Don't retry for certain error types
        if (error?.message?.includes('invalid_grant') || 
            error?.message?.includes('refresh_token_not_found')) {
          throw error
        }

        if (attempt < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000)
          await this.delay(delay)
        }
      }
    }

    throw lastError
  }

  /**
   * Utility function for delays
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * Clean up resources
   */
  cleanup(): void {
    if (this.refreshTimeout) {
      clearTimeout(this.refreshTimeout)
      this.refreshTimeout = null
    }
    this.refreshPromise = null
    this.retryCount = 0
  }
}

// Export singleton instance
export const authService = new AuthService()

// Export class for testing
export { AuthService }