import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { supabase } from '../lib/supabase'
import { AuthError as SupabaseAuthError } from '@supabase/supabase-js'
import { AuthError, NetworkError, ValidationError, APIError } from '../services/api'
import { apiService } from '../services/api'

// Mock Supabase
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      signInWithOAuth: vi.fn(),
      signOut: vi.fn(),
      onAuthStateChange: vi.fn((callback) => {
        // Call the callback immediately with initial auth state
        setTimeout(() => callback('SIGNED_IN', { user: { id: 'user-123', email: 'test@example.com' } }), 0)
        return {
          data: { subscription: { unsubscribe: vi.fn() } }
        }
      })
    }
  }
}))

// Mock fetch
global.fetch = vi.fn()

describe('Authentication Flow Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    // Re-establish Supabase mock after clearing to prevent interference with other tests
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: {
        session: {
          access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsImV4cCI6OTk5OTk5OTk5OX0.test-signature',
          user: { id: 'user-123', email: 'test@example.com', app_metadata: {}, user_metadata: {}, aud: 'authenticated', created_at: '2023-01-01T00:00:00Z' },
          expires_at: 9999999999,
          refresh_token: 'refresh-token-123',
          expires_in: 3600,
          token_type: 'bearer'
        }
      },
      error: null
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Session Management', () => {
    it('should handle valid session', async () => {
      const mockSession = {
        access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.test',
        user: { id: 'user-123', email: 'test@example.com', app_metadata: {}, user_metadata: {}, aud: 'authenticated', created_at: '2023-01-01T00:00:00Z' },
        refresh_token: 'refresh-token-123',
        expires_in: 3600,
        token_type: 'bearer'
      }

      vi.mocked(supabase.auth.getSession).mockResolvedValue({
        data: { session: mockSession },
        error: null
      })

      const { data } = await supabase.auth.getSession()
      expect(data.session).toBeTruthy()
      expect(data.session?.access_token).toBe('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.test')
    })

    it('should handle expired session', async () => {
      vi.mocked(supabase.auth.getSession).mockResolvedValue({
        data: { session: null },
        error: new SupabaseAuthError('Session expired')
      })

      const { data, error } = await supabase.auth.getSession()
      expect(data.session).toBeNull()
      expect(error?.message).toBe('Session expired')
    })

    it('should handle network errors during session check', async () => {
      vi.mocked(supabase.auth.getSession).mockRejectedValue(
        new Error('Network error')
      )

      await expect(supabase.auth.getSession()).rejects.toThrow('Network error')
    })
  })

  describe('API Authentication', () => {
    it('should include auth header in API requests', async () => {
      const mockSession = {
        access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.test',
        user: { id: 'user-123', app_metadata: {}, user_metadata: {}, aud: 'authenticated', created_at: '2023-01-01T00:00:00Z' },
        refresh_token: 'refresh-token-123',
        expires_in: 3600,
        token_type: 'bearer'
      }

      vi.mocked(supabase.auth.getSession).mockResolvedValue({
        data: { session: mockSession },
        error: null
      })

      // Mock XMLHttpRequest for upload testing
      const mockXHR = {
        open: vi.fn(),
        send: vi.fn(),
        setRequestHeader: vi.fn(),
        addEventListener: vi.fn(),
        upload: {
          addEventListener: vi.fn()
        },
        status: 200,
        responseText: JSON.stringify({ job_id: 'test-job-123' }),
        timeout: 0
      }

      // Mock XMLHttpRequest constructor
      global.XMLHttpRequest = vi.fn(() => mockXHR) as any

      // Simulate successful upload
      mockXHR.addEventListener.mockImplementation((event, callback) => {
        if (event === 'load') {
          setTimeout(() => callback(), 0)
        }
      })

      // Test API call with auth
      const uploadPromise = apiService.uploadVideo(new File(['test'], 'test.mp4', { type: 'video/mp4' }))
      
      // Wait for async operations
      await new Promise(resolve => setTimeout(resolve, 10))
      
      const result = await uploadPromise

      expect(mockXHR.setRequestHeader).toHaveBeenCalledWith(
        'Authorization',
        'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.test'
      )
      expect(result.job_id).toBe('test-job-123')
    })

    it('should handle 401 authentication errors', async () => {
      const mockSession = {
        access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.invalid',
        user: { id: 'user-123', app_metadata: {}, user_metadata: {}, aud: 'authenticated', created_at: '2023-01-01T00:00:00Z' },
        refresh_token: 'refresh-token-123',
        expires_in: 3600,
        token_type: 'bearer'
      }

      vi.mocked(supabase.auth.getSession).mockResolvedValue({
        data: { session: mockSession },
        error: null
      })

      // Mock XMLHttpRequest for 401 error testing
      const mockXHR = {
        open: vi.fn(),
        send: vi.fn(),
        setRequestHeader: vi.fn(),
        addEventListener: vi.fn(),
        upload: {
          addEventListener: vi.fn()
        },
        status: 401,
        responseText: JSON.stringify({ detail: 'Invalid token' }),
        timeout: 0
      }

      global.XMLHttpRequest = vi.fn(() => mockXHR) as any

      // Simulate 401 error
      mockXHR.addEventListener.mockImplementation((event, callback) => {
        if (event === 'load') {
          setTimeout(() => callback(), 0)
        }
      })

      await expect(apiService.uploadVideo(new File(['test'], 'test.mp4', { type: 'video/mp4' })))
        .rejects.toThrow(AuthError)
    })

    it('should handle missing session', async () => {
      vi.mocked(supabase.auth.getSession).mockResolvedValue({
        data: { session: null },
        error: null
      })

      await expect(apiService.uploadVideo(new File(['test'], 'test.mp4', { type: 'video/mp4' })))
        .rejects.toThrow(AuthError)
    })
  })

  describe('OAuth Flow', () => {
    it('should initiate Google OAuth', async () => {
      vi.mocked(supabase.auth.signInWithOAuth).mockResolvedValue({
        data: { url: 'https://oauth.url', provider: 'google' },
        error: null
      })

      const result = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: 'http://localhost:3000/auth/callback'
        }
      })

      expect(result.data?.provider).toBe('google')
      expect(result.data?.url).toBeTruthy()
    })

    it('should handle OAuth errors', async () => {
      vi.mocked(supabase.auth.signInWithOAuth).mockResolvedValue({
        data: null,
        error: new SupabaseAuthError('OAuth provider error')
      })

      const result = await supabase.auth.signInWithOAuth({
        provider: 'google'
      })

      expect(result.error?.message).toBe('OAuth provider error')
    })
  })

  describe('Sign Out', () => {
    it('should sign out successfully', async () => {
      vi.mocked(supabase.auth.signOut).mockResolvedValue({
        error: null
      })

      const result = await supabase.auth.signOut()
      expect(result.error).toBeNull()
    })

    it('should handle sign out errors', async () => {
      vi.mocked(supabase.auth.signOut).mockResolvedValue({
        error: new SupabaseAuthError('Sign out failed')
      })

      const result = await supabase.auth.signOut()
      expect(result.error?.message).toBe('Sign out failed')
    })
  })

  describe('Auth State Changes', () => {
    it('should handle auth state change events', () => {
      const mockCallback = vi.fn()
      const mockUnsubscribe = vi.fn()

      vi.mocked(supabase.auth.onAuthStateChange).mockReturnValue({
        data: {
          subscription: {
            id: 'mock-subscription-id',
            callback: vi.fn(),
            unsubscribe: mockUnsubscribe
          }
        }
      })

      const { data } = supabase.auth.onAuthStateChange(mockCallback)
      expect(data.subscription.unsubscribe).toBe(mockUnsubscribe)
    })
  })
})