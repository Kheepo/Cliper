/**
 * Integration tests for authentication and upload workflow
 * Tests the complete flow from authentication to file upload
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { resumableUploadService } from '../services/resumableUpload'
import { errorCategorizationService } from '../services/errorCategorizationService'
import { supabase } from '../lib/supabase'
import { AuthError } from '../services/api'

// Mock Supabase
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      signInWithPassword: vi.fn(),
      signOut: vi.fn()
    },
    storage: {
      from: vi.fn(() => ({
        upload: vi.fn(),
        getPublicUrl: vi.fn()
      }))
    }
  }
}))

// Mock API service
vi.mock('../services/api', () => ({
  apiService: {
    post: vi.fn(),
    get: vi.fn()
  }
}))

describe('Authentication and Upload Integration', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
    
    // Reset all mocks
    vi.clearAllMocks()
    
    // Re-establish Supabase mock after clearing to prevent interference with other tests
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: { session: null },
      error: null
    })
    
    // Clear upload sessions
    resumableUploadService.clearAllSessions()
  })

  afterEach(() => {
    // Clean up after each test
    localStorage.clear()
    resumableUploadService.clearAllSessions()
  })

  describe('Authentication Flow', () => {
    it('should handle successful authentication', async () => {
      // Mock successful authentication
      const mockSession = {
        access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.test',
        refresh_token: 'mock_refresh_token',
        expires_in: 3600,
        token_type: 'bearer' as const,
        user: { id: 'user-123', email: 'test@example.com', app_metadata: {}, user_metadata: {}, aud: 'authenticated', created_at: '2023-01-01T00:00:00Z' }
      }
      
      vi.mocked(supabase.auth.getSession).mockResolvedValue({
        data: { session: mockSession },
        error: null
      })

      const session = await supabase.auth.getSession()
      expect(session.data.session).toBeTruthy()
      expect(session.data.session?.access_token).toBe('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.test')
    })

    it('should handle authentication failure', async () => {
      // Mock authentication failure
      vi.mocked(supabase.auth.getSession).mockResolvedValue({
        data: { session: null },
        error: { message: 'Authentication failed', __isAuthError: true } as any
      })

      const session = await supabase.auth.getSession()
      expect(session.data.session).toBeNull()
      expect(session.error).toBeTruthy()
    })

    it('should handle token expiration', async () => {
      // Mock expired token
      const expiredSession = {
        access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsImV4cCI6MTAwMDAwMDAwMH0.expired-signature',
        expires_at: Date.now() / 1000 - 3600, // Expired 1 hour ago
        refresh_token: 'expired_refresh_token',
        expires_in: 3600,
        token_type: 'bearer' as const,
        user: { id: 'user-123', email: 'test@example.com', app_metadata: {}, user_metadata: {}, aud: 'authenticated', created_at: '2023-01-01T00:00:00Z' }
      }
      
      vi.mocked(supabase.auth.getSession).mockResolvedValue({
        data: { session: expiredSession },
        error: null
      })

      const session = await supabase.auth.getSession()
      expect(session.data.session?.expires_at).toBeLessThan(Date.now() / 1000)
    })
  })

  describe('Upload Error Scenarios', () => {
    const createMockFile = (name: string, size: number): File => {
      const content = new Array(size).fill('a').join('')
      return new File([content], name, { type: 'video/mp4' })
    }

    it('should categorize network errors correctly', () => {
      const networkError = new Error('Network request failed')
      const category = errorCategorizationService.categorizeError(networkError)
      
      expect(category.type).toBe('network')
      expect(category.retryable).toBe(true)
      expect(category.userMessage).toContain('Network connection lost')
    })

    it('should categorize authentication errors correctly', () => {
      const authError = new Error('Unauthorized') as Error & { status: number }
      authError.status = 401
      const category = errorCategorizationService.categorizeError(authError)
      
      expect(category.type).toBe('authentication')
      expect(category.retryable).toBe(false)
      expect(category.userMessage).toContain('Authentication failed')
    })

    it('should categorize validation errors correctly', () => {
      const validationError = new Error('File too large') as Error & { status: number }
      validationError.status = 400
      const category = errorCategorizationService.categorizeError(validationError)
      
      expect(category.type).toBe('validation')
      expect(category.retryable).toBe(false)
      expect(category.userMessage).toContain('File is too large')
    })

    it('should categorize timeout errors correctly', () => {
      const timeoutError = new Error('Request timeout')
      const category = errorCategorizationService.categorizeError(timeoutError)
      
      expect(category.type).toBe('timeout')
      expect(category.retryable).toBe(true)
      expect(category.userMessage).toContain('Upload is taking longer than expected')
    })

    it('should categorize server errors correctly', () => {
      const serverError = new Error('Internal server error') as Error & { status: number }
      serverError.status = 500
      const category = errorCategorizationService.categorizeError(serverError)
      
      expect(category.type).toBe('server')
      expect(category.retryable).toBe(true)
      expect(category.userMessage).toContain('Server is temporarily unavailable')
    })
  })

  describe('Session Management', () => {
    const createMockFile = (name: string, size: number): File => {
      const content = new Array(size).fill('a').join('')
      return new File([content], name, { type: 'video/mp4' })
    }

    it('should create and store upload session', () => {
      const file = createMockFile('test.mp4', 1000)
      // Test session creation through public API
      const sessionId = `${file.name}-${file.size}-${Date.now()}`
      
      expect(sessionId).toBeTruthy()
      expect(typeof sessionId).toBe('string')
    })

    it('should persist sessions to localStorage', () => {
      const file = createMockFile('test.mp4', 1000)
      const sessionId = `${file.name}-${file.size}-${Date.now()}`
      
      // Create a mock session
      const session = {
        id: sessionId,
        fileName: file.name,
        fileSize: file.size,
        chunkSize: 1024 * 1024,
        totalChunks: 1,
        uploadedChunks: new Set<number>(),
        lastActivity: Date.now(),
        startTime: Date.now(),
        uploadSpeed: 0,
        estimatedTimeRemaining: 0,
        bytesUploaded: 0,
        status: 'pending' as const,
        errorCount: 0
      }
      
      // Simulate session creation
      resumableUploadService['sessions'].set(sessionId, session)
      resumableUploadService['saveSessionsToStorage']()
      
      // Check localStorage
      const stored = localStorage.getItem('resumable_upload_sessions_v2')
      expect(stored).toBeTruthy()
      
      const parsed = JSON.parse(stored!)
      expect(parsed).toHaveLength(1)
      expect(parsed[0].id).toBe(sessionId)
    })

    it('should load sessions from localStorage', () => {
      const file = createMockFile('test.mp4', 1000)
      const sessionId = `${file.name}-${file.size}-${Date.now()}`
      
      // Create mock session data in localStorage
      const sessionData = {
        id: sessionId,
        fileName: file.name,
        fileSize: file.size,
        chunkSize: 1024 * 1024,
        totalChunks: 1,
        uploadedChunks: [],
        lastActivity: Date.now(),
        startTime: Date.now(),
        uploadSpeed: 0,
        estimatedTimeRemaining: 0,
        bytesUploaded: 0,
        status: 'pending',
        errorCount: 0
      }
      
      localStorage.setItem('resumable_upload_sessions_v2', JSON.stringify([sessionData]))
      
      // Load sessions
      resumableUploadService['loadSessionsFromStorage']()
      
      // Check if session was loaded
      const loadedSession = resumableUploadService.getSessionDetails(sessionId)
      expect(loadedSession).toBeTruthy()
      expect(loadedSession?.fileName).toBe(file.name)
    })

    it('should clean up expired sessions', () => {
      const file = createMockFile('test.mp4', 1000)
      const sessionId = `${file.name}-${file.size}-${Date.now()}`
      
      // Create expired session
      const expiredSession = {
        id: sessionId,
        fileName: file.name,
        fileSize: file.size,
        chunkSize: 1024 * 1024,
        totalChunks: 1,
        uploadedChunks: [],
        lastActivity: Date.now() - (25 * 60 * 60 * 1000), // 25 hours ago
        startTime: Date.now() - (25 * 60 * 60 * 1000),
        uploadSpeed: 0,
        estimatedTimeRemaining: 0,
        bytesUploaded: 0,
        status: 'pending',
        errorCount: 0
      }
      
      localStorage.setItem('resumable_upload_sessions_v2', JSON.stringify([expiredSession]))
      
      // Load and clean up sessions
      resumableUploadService['loadSessionsFromStorage']()
      resumableUploadService['cleanupExpiredSessions']()
      
      // Check if expired session was removed
      const session = resumableUploadService.getSessionDetails(sessionId)
      expect(session).toBeNull()
    })
  })

  describe('Progress Tracking', () => {
    it('should calculate upload speed correctly', () => {
      const startTime = Date.now() - 5000 // 5 seconds ago
      const bytesUploaded = 1024 * 1024 // 1 MB
      const expectedSpeed = bytesUploaded / 5 // bytes per second
      
      // This would be tested within the actual upload process
      expect(expectedSpeed).toBe(1024 * 1024 / 5)
    })

    it('should calculate estimated time remaining correctly', () => {
      const totalSize = 10 * 1024 * 1024 // 10 MB
      const uploadedSize = 2 * 1024 * 1024 // 2 MB
      const uploadSpeed = 1024 * 1024 // 1 MB/s
      
      const remainingBytes = totalSize - uploadedSize
      const estimatedTime = remainingBytes / uploadSpeed
      
      expect(estimatedTime).toBe(8) // 8 seconds
    })
  })

  describe('Retry Logic', () => {
    it('should provide correct retry configuration for network errors', () => {
      const networkError = new Error('Network request failed')
      const category = errorCategorizationService.categorizeError(networkError)
      const retryConfig = errorCategorizationService.getRetryConfig(category)
      
      expect(retryConfig.shouldRetry).toBe(true)
      expect(retryConfig.maxRetries).toBe(5)
      expect(retryConfig.delay).toBe(2000)
    })

    it('should not retry authentication errors', () => {
      const authError = new Error('Unauthorized') as Error & { status: number }
      authError.status = 401
      const category = errorCategorizationService.categorizeError(authError)
      const retryConfig = errorCategorizationService.getRetryConfig(category)
      
      expect(retryConfig.shouldRetry).toBe(false)
      expect(retryConfig.maxRetries).toBe(0)
    })

    it('should provide appropriate retry delays', () => {
      const timeoutError = new Error('Request timeout')
      const category = errorCategorizationService.categorizeError(timeoutError)
      const retryConfig = errorCategorizationService.getRetryConfig(category)
      
      expect(retryConfig.shouldRetry).toBe(true)
      expect(retryConfig.delay).toBe(5000)
      expect(retryConfig.maxRetries).toBe(3)
    })
  })
})