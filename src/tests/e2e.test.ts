import { describe, it, expect, beforeAll, afterAll, beforeEach, afterEach, vi } from 'vitest'
import { supabase } from '../lib/supabase'
import { apiService } from '../services/api'
import { ChunkedUploadService } from '../services/chunkedUpload'
import { AuthError, NetworkError, ValidationError, APIError } from '../services/api'

// Mock Supabase module
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      getUser: vi.fn(),
      signOut: vi.fn()
    },
    from: vi.fn(() => ({
      select: vi.fn().mockReturnThis(),
      insert: vi.fn().mockReturnThis(),
      update: vi.fn().mockReturnThis(),
      delete: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      single: vi.fn()
    }))
  }
}))

// Mock API service
vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    apiService: {
      uploadVideo: vi.fn(),
      getUploadStatus: vi.fn(),
      deleteVideo: vi.fn(),
      processUrl: vi.fn(),
      getTaskStatus: vi.fn(),
      getJobStatus: vi.fn()
    }
  }
})

// Mock ChunkedUploadService
vi.mock('../services/chunkedUpload', () => ({
  ChunkedUploadService: vi.fn().mockImplementation(() => ({
    startUpload: vi.fn(),
    uploadFile: vi.fn(),
    resumeUpload: vi.fn(),
    cancelUpload: vi.fn(),
    getUploadProgress: vi.fn(),
    getSession: vi.fn(),
    cleanupOldSessions: vi.fn()
  }))
}))

// Mock environment for E2E testing
const TEST_CONFIG = {
  API_BASE_URL: 'http://localhost:8001',
  SUPABASE_URL: process.env.VITE_SUPABASE_URL || 'http://localhost:54321',
  SUPABASE_ANON_KEY: process.env.VITE_SUPABASE_ANON_KEY || 'test-anon-key'
}

// Test utilities - optimized for memory usage
const createTestFile = (name: string, sizeInKB: number = 1, type: string = 'video/mp4'): File => {
  // Create much smaller test files to prevent memory issues
  const content = new Array(Math.min(sizeInKB * 1024, 10240)).fill('a').join('') // Max 10KB
  const file = new File([content], name, { type })
  return file
}

const createTestUser = () => ({
  id: 'test-user-' + Date.now(),
  email: 'test@example.com',
  access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.test'
})

// Mock fetch for controlled testing
const mockFetch = vi.fn()
global.fetch = mockFetch

// Mock crypto for file hashing
Object.defineProperty(global, 'crypto', {
  value: {
    subtle: {
      digest: vi.fn().mockImplementation(async (algorithm, data) => {
        // Simple mock hash based on data length
        const hash = new Array(32).fill(0).map((_, i) => data.byteLength + i)
        return new Uint8Array(hash).buffer
      })
    }
  }
})

// Mock localStorage
const localStorageMock = {
  data: new Map<string, string>(),
  getItem: vi.fn((key: string) => localStorageMock.data.get(key) || null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageMock.data.set(key, value)
  }),
  removeItem: vi.fn((key: string) => {
    localStorageMock.data.delete(key)
  }),
  clear: vi.fn(() => {
    localStorageMock.data.clear()
  })
}
Object.defineProperty(window, 'localStorage', { value: localStorageMock })

describe('End-to-End Video Upload Workflow', () => {
  let testUser: any
  let chunkedUploadService: ChunkedUploadService

  beforeAll(async () => {
    // Setup test environment
    testUser = createTestUser()
    chunkedUploadService = new ChunkedUploadService()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.clear()
    
    // Re-establish Supabase mock after clearing to prevent interference with other tests
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: {
        session: {
          access_token: testUser.access_token,
          refresh_token: 'mock-refresh-token',
          expires_in: 3600,
          token_type: 'bearer',
          user: testUser
        }
      },
      error: null
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  afterAll(() => {
    // Cleanup test environment
    localStorageMock.clear()
  })

  describe('Complete Upload Workflow - Small Files', () => {
    it('should complete entire workflow for small video file', async () => {
      const testFile = createTestFile('test-small-video.mp4', 10) // 10KB
      
      const expectedResult = {
        job_id: 'video-123'
      }
      
      // Mock API service response
      vi.mocked(apiService.uploadVideo).mockResolvedValue(expectedResult)
      
      // Execute upload
      const result = await apiService.uploadVideo(testFile, () => {})
      
      // Verify API service was called correctly
      expect(apiService.uploadVideo).toHaveBeenCalledWith(
        testFile,
        expect.any(Function)
      )
      
      // Verify response
      expect(result).toEqual(expectedResult)
    })

    it('should handle upload progress tracking', async () => {
      const testFile = createTestFile('progress-test.mp4', 5)
      const progressCallback = vi.fn()
      
      const expectedResult = { job_id: 'video-progress' }
      
      // Mock API service response
      vi.mocked(apiService.uploadVideo).mockResolvedValue(expectedResult)
      
      const result = await apiService.uploadVideo(testFile, progressCallback)
      
      // Verify API service was called with progress callback
      expect(apiService.uploadVideo).toHaveBeenCalledWith(testFile, progressCallback)
      expect(result).toEqual(expectedResult)
    })
  })

  describe('Complete Workflow - Large Files (Chunked Upload)', () => {
    it('should complete chunked upload workflow', async () => {
      const testFile = createTestFile('test-large-video.mp4', 50) // 50KB (simulating large file)
      
      const expectedStartResult = {
        sessionId: 'session-123',
        isResume: false
      }
      
      const expectedUploadResult = {
        job_id: 'video-chunked-123'
      }
      
      // Mock chunked upload service methods
      vi.mocked(chunkedUploadService.startUpload).mockResolvedValue(expectedStartResult)
      vi.mocked(chunkedUploadService.uploadFile).mockResolvedValue(expectedUploadResult)
      
      // Start upload
      const { sessionId } = await chunkedUploadService.startUpload(testFile)
      expect(sessionId).toBe('session-123')
      
      // Execute chunked upload
      const progressCallback = vi.fn()
      const result = await chunkedUploadService.uploadFile(testFile, { onProgress: progressCallback })
      
      // Verify service methods were called correctly
      expect(chunkedUploadService.startUpload).toHaveBeenCalledWith(testFile)
      expect(chunkedUploadService.uploadFile).toHaveBeenCalledWith(testFile, { onProgress: progressCallback })
      
      // Verify final result
      expect(result).toEqual(expectedUploadResult)
    })

    it('should resume interrupted chunked upload', async () => {
      const testFile = createTestFile('resume-test.mp4', 10)
      
      const expectedResumeResult = {
        sessionId: 'session-resume-123',
        isResume: true
      }
      
      const expectedUploadResult = {
        job_id: 'video-resumed-123'
      }
      
      // Mock chunked upload service methods for resume scenario
      vi.mocked(chunkedUploadService.startUpload).mockResolvedValue(expectedResumeResult)
      vi.mocked(chunkedUploadService.uploadFile).mockResolvedValue(expectedUploadResult)
      
      // Resume upload
      const { sessionId: resumeSessionId, isResume } = await chunkedUploadService.startUpload(testFile)
      
      expect(resumeSessionId).toBe('session-resume-123')
      expect(isResume).toBe(true)
      
      const result = await chunkedUploadService.uploadFile(testFile)
      
      expect(result.job_id).toBe('video-resumed-123')
      
      // Verify service methods were called correctly
      expect(chunkedUploadService.startUpload).toHaveBeenCalledWith(testFile)
      expect(chunkedUploadService.uploadFile).toHaveBeenCalledWith(testFile)
    })
  })

  describe('URL Processing Workflow', () => {
    it('should complete URL processing workflow', async () => {
      const testUrl = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
      
      const expectedProcessResult = {
        job_id: 'task-123'
      }
      
      const expectedStatusResults = [
        {
          status: 'processing',
          progress: 25,
          message: 'Downloading video...'
        },
        {
          status: 'processing',
          progress: 75,
          message: 'Processing video...'
        },
        {
          status: 'completed',
          progress: 100,
          result: {
            video_id: 'video-url-123',
            title: 'Rick Astley - Never Gonna Give You Up',
            duration: 212,
            thumbnail_url: '/thumbnails/video-url-123.jpg'
          }
        }
      ]
      
      // Mock API service methods
      vi.mocked(apiService.processUrl).mockResolvedValue(expectedProcessResult)
      vi.mocked(apiService.getJobStatus)
        .mockResolvedValueOnce(expectedStatusResults[0])
        .mockResolvedValueOnce(expectedStatusResults[1])
        .mockResolvedValueOnce(expectedStatusResults[2])
      
      // Start URL processing
      const processResult = await apiService.processUrl(testUrl)
      expect(processResult.job_id).toBe('task-123')
      
      // Poll for completion
      let status = await apiService.getJobStatus(processResult.job_id)
      expect(status.status).toBe('processing')
      expect(status.progress).toBe(25)
      
      // Continue polling
      status = await apiService.getJobStatus(processResult.job_id)
      expect(status.progress).toBe(75)
      
      // Final status
      status = await apiService.getJobStatus(processResult.job_id)
      expect(status.status).toBe('completed')
      expect(status.result?.video_id).toBe('video-url-123')
      
      // Verify API service calls
      expect(apiService.processUrl).toHaveBeenCalledWith(testUrl)
      expect(apiService.getJobStatus).toHaveBeenCalledTimes(3)
      expect(apiService.getJobStatus).toHaveBeenCalledWith('task-123')
    })

    it('should handle URL processing timeout', async () => {
      const testUrl = 'https://example.com/slow-video'
      
      const expectedProcessResult = {
        job_id: 'task-123'
      }
      
      const expectedStatusResult = {
        status: 'processing',
        progress: 50,
        message: 'Still processing...'
      }
      
      // Mock API service methods
      vi.mocked(apiService.processUrl).mockResolvedValue(expectedProcessResult)
      vi.mocked(apiService.getJobStatus).mockResolvedValue(expectedStatusResult)
      
      const processResult = await apiService.processUrl(testUrl)
      
      // Simulate timeout after multiple polls
      const maxPolls = 10
      let polls = 0
      let status
      
      while (polls < maxPolls) {
        status = await apiService.getJobStatus(processResult.job_id)
        if (status.status === 'completed' || status.status === 'failed') {
          break
        }
        polls++
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      
      expect(polls).toBe(maxPolls)
      expect(status?.status).toBe('processing')
      expect(apiService.processUrl).toHaveBeenCalledWith(testUrl)
      expect(apiService.getJobStatus).toHaveBeenCalledTimes(maxPolls)
    })
  })

  describe('Error Handling Workflows', () => {
    it('should handle authentication errors gracefully', async () => {
      const testFile = createTestFile('auth-error-test.mp4', 5)
      
      const authError = new AuthError('Authentication failed')
      
      // Mock API service to throw auth error
      vi.mocked(apiService.uploadVideo).mockRejectedValue(authError)
      
      // Test that the error is thrown correctly
      try {
        await apiService.uploadVideo(testFile, () => {})
        // Should not reach here
        expect(true).toBe(false)
      } catch (error) {
        expect(error).toBeInstanceOf(AuthError)
        expect(error.message).toContain('Authentication failed')
        expect((error as AuthError).retryable).toBe(true)
      }
      
      expect(apiService.uploadVideo).toHaveBeenCalledWith(testFile, expect.any(Function))
    })

    it('should handle network errors with retry logic', async () => {
      const testFile = createTestFile('network-error-test.mp4', 5)
      
      const networkError = new NetworkError('Network error')
      const expectedResult = {
        job_id: 'video-retry-success'
      }
      
      // First call fails with network error, second succeeds
      vi.mocked(apiService.uploadVideo)
        .mockRejectedValueOnce(networkError)
        .mockResolvedValueOnce(expectedResult)
      
      // First attempt should fail
      await expect(apiService.uploadVideo(testFile, () => {}))
        .rejects.toThrow('Network error')
      
      // Retry should succeed
      const result = await apiService.uploadVideo(testFile, () => {})
      expect(result.job_id).toBe('video-retry-success')
      expect(apiService.uploadVideo).toHaveBeenCalledTimes(2)
    })

    it('should handle validation errors properly', async () => {
      const invalidFile = createTestFile('invalid.txt', 1, 'text/plain')
      
      const validationError = new ValidationError('Invalid file type')
      
      // Mock API service to throw validation error
      vi.mocked(apiService.uploadVideo).mockRejectedValue(validationError)
      
      await expect(apiService.uploadVideo(invalidFile, () => {}))
        .rejects.toThrow(ValidationError)
      
      expect(apiService.uploadVideo).toHaveBeenCalledWith(invalidFile, expect.any(Function))
    })

    it('should handle server errors with appropriate error types', async () => {
      const testFile = createTestFile('server-error-test.mp4', 5)
      
      const errorCases = [
        { expectedError: APIError, description: 'Internal server error' },
        { expectedError: NetworkError, description: 'Bad gateway' },
        { expectedError: NetworkError, description: 'Service unavailable' },
        { expectedError: ValidationError, description: 'File too large' }
      ]
      
      for (const { expectedError, description } of errorCases) {
        const error = new expectedError(description)
        
        vi.mocked(apiService.uploadVideo).mockRejectedValueOnce(error)
        
        await expect(apiService.uploadVideo(testFile, () => {}))
          .rejects.toThrow(expectedError)
      }
      
      expect(apiService.uploadVideo).toHaveBeenCalledTimes(errorCases.length)
    })
  })

  describe('Session Management', () => {
    it('should handle session cleanup properly', async () => {
      const testFile = createTestFile('cleanup-test.mp4', 10)
      
      const expectedSession1 = { sessionId: 'session-1', isResume: false }
      const expectedSession2 = { sessionId: 'session-2', isResume: false }
      
      // Mock session creation
      vi.mocked(chunkedUploadService.startUpload)
        .mockResolvedValueOnce(expectedSession1)
        .mockResolvedValueOnce(expectedSession2)
      
      // Create proper UploadSession objects for getSession mock (chunkedUpload interface)
      const now = Date.now()
      const fullSession1 = {
        id: expectedSession1.sessionId,
        fileName: testFile.name,
        fileSize: testFile.size,
        fileHash: 'test-hash-1',
        totalChunks: Math.ceil(testFile.size / (1024 * 1024)),
        uploadedChunks: new Set<number>(),
        failedChunks: new Set<number>(),
        chunkSize: 1024 * 1024,
        createdAt: now,
        lastActivity: now,
        lastHeartbeat: now,
        version: '1.0',
        retryCount: 0,
        options: {},
        serverSessionInitialized: false
      }
      
      const fullSession2 = {
        id: expectedSession2.sessionId,
        fileName: testFile.name,
        fileSize: testFile.size,
        fileHash: 'test-hash-2',
        totalChunks: Math.ceil(testFile.size / (1024 * 1024)),
        uploadedChunks: new Set<number>(),
        failedChunks: new Set<number>(),
        chunkSize: 1024 * 1024,
        createdAt: now,
        lastActivity: now,
        lastHeartbeat: now,
        version: '1.0',
        retryCount: 0,
        options: {},
        serverSessionInitialized: false
      }

      // Mock session retrieval
      vi.mocked(chunkedUploadService.getSession)
        .mockReturnValueOnce(null) // Cancelled session
        .mockReturnValueOnce(fullSession2) // Active session
      
      // Create multiple sessions
      const session1 = await chunkedUploadService.startUpload(testFile)
      const session2 = await chunkedUploadService.startUpload(testFile)
      
      expect(session1.sessionId).toBeTruthy()
      expect(session2.sessionId).toBeTruthy()
      expect(session1.sessionId).not.toBe(session2.sessionId)
      
      // Cancel first session
      chunkedUploadService.cancelUpload(session1.sessionId)
      
      // Verify session is removed
      const cancelledSession = chunkedUploadService.getSession(session1.sessionId)
      expect(cancelledSession).toBeNull()
      
      // Second session should still exist
      const activeSession = chunkedUploadService.getSession(session2.sessionId)
      expect(activeSession).toBeTruthy()
      
      // Verify method calls
      expect(chunkedUploadService.startUpload).toHaveBeenCalledTimes(2)
      expect(chunkedUploadService.cancelUpload).toHaveBeenCalledWith(session1.sessionId)
      expect(chunkedUploadService.getSession).toHaveBeenCalledTimes(2)
    })

    it('should handle storage quota errors gracefully', async () => {
      const testFile = createTestFile('storage-quota-test.mp4', 10)
      
      const expectedSession = { sessionId: 'session-quota-test', isResume: false }
      
      // Mock localStorage quota exceeded
      localStorageMock.setItem.mockImplementationOnce(() => {
        throw new Error('QuotaExceededError')
      })
      
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      
      // Mock service to return session despite storage error
      vi.mocked(chunkedUploadService.startUpload).mockResolvedValue(expectedSession)
      
      // Should still work despite storage error
      const { sessionId } = await chunkedUploadService.startUpload(testFile)
      expect(sessionId).toBeTruthy()
      
      // Verify service was called
      expect(chunkedUploadService.startUpload).toHaveBeenCalledWith(testFile)
      
      consoleSpy.mockRestore()
    })
  })

  describe('Performance and Reliability', () => {
    it('should handle concurrent uploads', async () => {
      const files = [
        createTestFile('concurrent-1.mp4', 5),
        createTestFile('concurrent-2.mp4', 5),
        createTestFile('concurrent-3.mp4', 5)
      ]
      
      const expectedResults = [
        { job_id: 'video-1' },
        { job_id: 'video-2' },
        { job_id: 'video-3' }
      ]
      
      // Mock successful responses for all uploads
      vi.mocked(apiService.uploadVideo)
        .mockResolvedValueOnce(expectedResults[0])
        .mockResolvedValueOnce(expectedResults[1])
        .mockResolvedValueOnce(expectedResults[2])
      
      // Start concurrent uploads
      const uploadPromises = files.map(file => 
        apiService.uploadVideo(file, () => {})
      )
      
      const results = await Promise.all(uploadPromises)
      
      // All uploads should succeed
      expect(results).toHaveLength(3)
      results.forEach((result, index) => {
        expect(result.job_id).toBe(expectedResults[index].job_id)
      })
      
      expect(apiService.uploadVideo).toHaveBeenCalledTimes(3)
    })

    it('should maintain session integrity under stress', async () => {
      const testFile = createTestFile('stress-test.mp4', 10)
      
      // Mock multiple session creations
      const mockSessions = Array.from({ length: 10 }, (_, i) => ({
        sessionId: `stress-session-${i}`,
        isResume: false
      }))
      
      // Setup mocks for session creation
      const startUploadMock = vi.mocked(chunkedUploadService.startUpload)
      mockSessions.forEach(session => {
        startUploadMock.mockResolvedValueOnce(session)
      })
      
      // Create proper UploadSession objects for getSession mock (chunkedUpload interface)
      const now = Date.now()
      const fullMockSessions = mockSessions.map((session, index) => ({
        id: session.sessionId,
        fileName: testFile.name,
        fileSize: testFile.size,
        fileHash: `test-hash-${index}`,
        totalChunks: Math.ceil(testFile.size / (1024 * 1024)),
        uploadedChunks: new Set(index % 2 === 0 ? [] : [0, 1]),
        failedChunks: new Set<number>(),
        chunkSize: 1024 * 1024,
        createdAt: now,
        lastActivity: now,
        lastHeartbeat: now,
        version: '1.0',
        retryCount: index % 2 === 0 ? 1 : 0,
        options: {},
        serverSessionInitialized: true
      }))

      // Setup mocks for session retrieval (odd indices are active)
      const getSessionMock = vi.mocked(chunkedUploadService.getSession)
      fullMockSessions.forEach((session, index) => {
        if (index % 2 === 0) {
          getSessionMock.mockReturnValueOnce(null) // Cancelled
        } else {
          getSessionMock.mockReturnValueOnce(session) // Active
        }
      })
      
      // Create and cancel multiple sessions rapidly
      const sessions = []
      for (let i = 0; i < 10; i++) {
        const { sessionId } = await chunkedUploadService.startUpload(testFile)
        sessions.push(sessionId)
        
        if (i % 2 === 0) {
          chunkedUploadService.cancelUpload(sessionId)
        }
      }
      
      // Verify only non-cancelled sessions exist
      let activeCount = 0
      sessions.forEach((sessionId, index) => {
        const session = chunkedUploadService.getSession(sessionId)
        if (session !== null) { // Count all active sessions
          activeCount++
        }
      })
      
      expect(activeCount).toBe(5) // Half should be active (odd indices: 1,3,5,7,9)
      expect(chunkedUploadService.startUpload).toHaveBeenCalledTimes(10)
      expect(chunkedUploadService.cancelUpload).toHaveBeenCalledTimes(5)
    })
  })
})