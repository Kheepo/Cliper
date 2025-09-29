import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { ChunkedUploadService } from '../services/chunkedUpload'
import { apiService } from '../services/api'
import { AuthError, NetworkError, ValidationError, APIError } from '../services/api'
import { supabase } from '../lib/supabase'

// Mock Supabase
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn()
    }
  }
}))

// Mock fetch
global.fetch = vi.fn()

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  key: vi.fn(),
  length: 0
}
Object.defineProperty(window, 'localStorage', { value: localStorageMock })

// Mock crypto.subtle for file hashing
Object.defineProperty(global, 'crypto', {
  value: {
    subtle: {
      digest: vi.fn().mockResolvedValue(new ArrayBuffer(32))
    }
  }
})

describe('Upload Service Tests', () => {
  let chunkedUploadService: ChunkedUploadService
  let mockFile: File

  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.clear()
    localStorageMock.getItem.mockReturnValue(null)
    
    // Create new service instance
    chunkedUploadService = new ChunkedUploadService()
    mockFile = new File(['test content'], 'test-video.mp4', {
      type: 'video/mp4',
      lastModified: Date.now()
    })

    // Mock valid session by default
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: {
        session: {
          access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsImV4cCI6OTk5OTk5OTk5OX0.test-signature',
          refresh_token: 'refresh-token',
          expires_in: 3600,
          token_type: 'bearer',
          user: { 
            id: 'user-123',
            app_metadata: {},
            user_metadata: {},
            aud: 'authenticated',
            created_at: new Date().toISOString(),
            email: 'test@example.com'
          },
          expires_at: 9999999999
        }
      },
      error: null
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('File Validation', () => {
    it('should validate file type and size', async () => {
      const validFile = new File(['content'], 'video.mp4', { type: 'video/mp4' })
      const { sessionId } = await chunkedUploadService.startUpload(validFile)
      expect(sessionId).toBeTruthy()
    })

    it('should reject empty files', async () => {
      const emptyFile = new File([], 'empty.mp4', { type: 'video/mp4' })
      await expect(chunkedUploadService.startUpload(emptyFile))
        .rejects.toThrow(ValidationError)
    })

    it('should reject oversized files', async () => {
      // Mock a file larger than 10GB
      const oversizedFile = new File(['content'], 'huge.mp4', { type: 'video/mp4' })
      Object.defineProperty(oversizedFile, 'size', { value: 11 * 1024 * 1024 * 1024 })
      
      await expect(chunkedUploadService.startUpload(oversizedFile))
        .rejects.toThrow(ValidationError)
    })

    it('should warn about unsupported file types', async () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const unsupportedFile = new File(['content'], 'video.xyz', { type: 'video/xyz' })
      
      await chunkedUploadService.startUpload(unsupportedFile)
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('File type video/xyz may not be supported')
      )
    })
  })

  describe('Session Management', () => {
    it('should create new upload session', async () => {
      const { sessionId, isResume } = await chunkedUploadService.startUpload(mockFile)
      
      expect(sessionId).toBeTruthy()
      expect(isResume).toBe(false)
      expect(sessionId).toMatch(/^upload_/)
    })

    it('should resume existing session', async () => {
      // First upload
      const { sessionId: firstSessionId } = await chunkedUploadService.startUpload(mockFile)
      
      // Mock existing session in localStorage
      const mockSession = {
        id: firstSessionId,
        fileName: mockFile.name,
        fileSize: mockFile.size,
        fileHash: 'mock-hash',
        totalChunks: 2,
        uploadedChunks: [0],
        failedChunks: [],
        chunkSize: 5242880,
        createdAt: Date.now(),
        lastActivity: Date.now(),
        lastHeartbeat: Date.now(),
        version: '1.0',
        retryCount: 0,
        options: {},
        serverSessionInitialized: false
      }
      
      localStorageMock.getItem.mockReturnValue(JSON.stringify(mockSession))
      
      // Mock file hash to match
      vi.mocked(crypto.subtle.digest).mockResolvedValue(
        new TextEncoder().encode('mock-hash').buffer
      )
      
      // Second upload (should resume)
      const { sessionId: secondSessionId, isResume } = await chunkedUploadService.startUpload(mockFile)
      
      expect(secondSessionId).toBe(firstSessionId)
      expect(isResume).toBe(true)
    })

    it('should not resume session with different file', async () => {
      const { sessionId: firstSessionId } = await chunkedUploadService.startUpload(mockFile)
      
      // Mock existing session with different file
      const mockSession = {
        id: firstSessionId,
        fileName: 'different-file.mp4',
        fileSize: mockFile.size,
        totalChunks: 2,
        uploadedChunks: [],
        failedChunks: [],
        chunkSize: 5242880,
        createdAt: Date.now(),
        lastActivity: Date.now(),
        lastHeartbeat: Date.now(),
        version: '1.0',
        retryCount: 0,
        options: {},
        serverSessionInitialized: false
      }
      
      localStorageMock.getItem.mockReturnValue(JSON.stringify(mockSession))
      
      const differentFile = new File(['content'], 'different.mp4', { type: 'video/mp4' })
      const { isResume } = await chunkedUploadService.startUpload(differentFile)
      
      expect(isResume).toBe(false)
    })

    it('should cleanup old sessions', async () => {
      const oldSession = {
        id: 'old-session',
        fileName: 'old.mp4',
        fileSize: 1000,
        totalChunks: 1,
        uploadedChunks: [],
        failedChunks: [],
        chunkSize: 5242880,
        createdAt: Date.now() - 8 * 24 * 60 * 60 * 1000, // 8 days ago
        lastActivity: Date.now() - 8 * 24 * 60 * 60 * 1000,
        lastHeartbeat: Date.now() - 8 * 24 * 60 * 60 * 1000,
        version: '1.0',
        retryCount: 0,
        options: {},
        serverSessionInitialized: false
      }
      
      const storageKey = 'cliper_upload_old-session'
      
      // Clear previous mocks and set up localStorage mock before creating service
      localStorageMock.clear()
      localStorageMock.removeItem.mockClear()
      
      // Mock localStorage to simulate having an old session
      Object.defineProperty(localStorageMock, 'length', { value: 1, writable: true })
      localStorageMock.key.mockImplementation((index: number) => {
        return index === 0 ? storageKey : null
      })
      localStorageMock.getItem.mockImplementation((key: string) => {
        return key === storageKey ? JSON.stringify(oldSession) : null
      })
      
      // Creating new service should cleanup old sessions
      new ChunkedUploadService()
      
      expect(localStorageMock.removeItem).toHaveBeenCalledWith(storageKey)
    })
  })

  describe('Chunked Upload Process', () => {
    it('should handle successful chunked upload', async () => {
      // Mock successful server responses for the upload flow
      vi.mocked(fetch)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ session_id: 'test-session' })
        } as Response) // Init response
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ chunk_index: 0, uploaded: true })
        } as Response) // Chunk upload response
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ job_id: 'job-123' })
        } as Response) // Finalize response
      
      const result = await chunkedUploadService.uploadFile(mockFile)
      
      expect(result.job_id).toBe('job-123')
    })

    it('should handle chunk upload failures with retry', async () => {
      // Mock init success, chunk failure then success, finalize success
      vi.mocked(fetch)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ session_id: 'test-session' })
        } as Response) // Init
        .mockResolvedValueOnce({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: 'Server error' })
        } as Response) // Chunk failure
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ chunk_index: 0, uploaded: true })
        } as Response) // Chunk retry success
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ job_id: 'job-123' })
        } as Response) // Finalize
      
      const result = await chunkedUploadService.uploadFile(mockFile)
      expect(result.job_id).toBe('job-123')
    })

    it('should handle authentication errors during upload', async () => {
      // Mock auth failure during init
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Authentication failed' })
      } as Response)
      
      await expect(chunkedUploadService.uploadFile(mockFile))
        .rejects.toThrow(AuthError)
    })

    it('should handle network errors during upload', async () => {
      // Mock network error during init
      vi.mocked(fetch).mockRejectedValueOnce(new Error('Network error'))
      
      await expect(chunkedUploadService.uploadFile(mockFile))
        .rejects.toThrow()
    })
  })

  describe('Progress Tracking', () => {
    it('should track upload progress', async () => {
      const progressCallback = vi.fn()
      
      // Mock successful responses
      vi.mocked(fetch)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ session_id: 'test-session' })
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ chunk_index: 0, uploaded: true })
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ job_id: 'job-123' })
        } as Response)
      
      await chunkedUploadService.uploadFile(mockFile, { onProgress: progressCallback })
      
      expect(progressCallback).toHaveBeenCalled()
      const lastCall = progressCallback.mock.calls[progressCallback.mock.calls.length - 1]
      expect(lastCall[0]).toBeGreaterThan(0) // Progress should be > 0
    })
  })

  describe('Session Cancellation', () => {
    it('should cancel upload session', async () => {
      const { sessionId } = await chunkedUploadService.startUpload(mockFile)
      
      chunkedUploadService.cancelUpload(sessionId)
      
      const session = chunkedUploadService.getSession(sessionId)
      expect(session).toBeNull()
    })
  })
})

describe('Regular Upload Tests', () => {
  let mockXHR: any
  let eventListeners: { [key: string]: Function[] }
  let timeoutIds: NodeJS.Timeout[] = []
  let originalSupabaseMock: any
  
  beforeEach(() => {
    // Store the original mock before clearing
    originalSupabaseMock = vi.mocked(supabase.auth.getSession)
    
    // Clear mocks but preserve the Supabase mock structure
    vi.clearAllMocks()
    
    // Clear any pending timeouts
    timeoutIds.forEach(id => clearTimeout(id))
    timeoutIds = []
    
    // Force re-establish Supabase mock with a fresh implementation
    const mockGetSession = vi.fn().mockResolvedValue({
      data: {
        session: {
          access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsImV4cCI6OTk5OTk5OTk5OX0.test-signature',
          user: { id: 'user-123' },
          expires_at: 9999999999
        }
      },
      error: null
    })
    
    // Also mock refreshSession to prevent any refresh attempts
    const mockRefreshSession = vi.fn().mockResolvedValue({
      data: {
        session: {
          access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsImV4cCI6OTk5OTk5OTk5OX0.test-signature',
          user: { id: 'user-123' },
          expires_at: 9999999999
        }
      },
      error: null
    })
    
    // Override the mocks completely to ensure they persist
    Object.defineProperty(supabase.auth, 'getSession', {
      value: mockGetSession,
      writable: true,
      configurable: true
    })
    
    Object.defineProperty(supabase.auth, 'refreshSession', {
      value: mockRefreshSession,
      writable: true,
      configurable: true
    })
    
    // Reset event listeners for each test
    eventListeners = {}
    
    // Mock XMLHttpRequest for regular uploads
    mockXHR = {
      open: vi.fn(),
      send: vi.fn(),
      setRequestHeader: vi.fn(),
      addEventListener: vi.fn((event: string, callback: Function) => {
        if (!eventListeners[event]) eventListeners[event] = []
        eventListeners[event].push(callback)
      }),
      upload: {
        addEventListener: vi.fn()
      },
      status: 200,
      responseText: '',
      timeout: 0,
      // Helper method to trigger events
      triggerEvent: (event: string) => {
        if (eventListeners[event]) {
          eventListeners[event].forEach(callback => callback())
        }
      }
    }
    
    // Make timeout property settable
    Object.defineProperty(mockXHR, 'timeout', {
      writable: true,
      value: 0
    })
    
    const XMLHttpRequestConstructor = vi.fn(() => mockXHR) as any
    XMLHttpRequestConstructor.UNSENT = 0
    XMLHttpRequestConstructor.OPENED = 1
    XMLHttpRequestConstructor.HEADERS_RECEIVED = 2
    XMLHttpRequestConstructor.LOADING = 3
    XMLHttpRequestConstructor.DONE = 4
    XMLHttpRequestConstructor.prototype = {}
    
    global.XMLHttpRequest = XMLHttpRequestConstructor
  })
  
  afterEach(() => {
    // Clean up timeouts
    timeoutIds.forEach(id => clearTimeout(id))
    timeoutIds = []
    
    // Clear event listeners
    eventListeners = {}
    
    // Reset XMLHttpRequest
    mockXHR = null
    
    // Force garbage collection if available
    if (global.gc) {
      global.gc()
    }
  })

  it('should handle successful regular upload', async () => {
    const mockFile = new File(['content'], 'small-video.mp4', { type: 'video/mp4' })
    
    // Mock successful xhr response
    mockXHR.status = 200
    mockXHR.responseText = JSON.stringify({ job_id: 'job-123', status: 'processing' })
    
    // Start upload and trigger success
    const uploadPromise = apiService.uploadVideo(mockFile)
    
    // Simulate successful load event
    const timeoutId = setTimeout(() => {
      mockXHR.triggerEvent('load')
    }, 0)
    timeoutIds.push(timeoutId)
    
    const result = await uploadPromise
    expect(result.job_id).toBe('job-123')
  })

  it('should handle 401 authentication errors', async () => {
    const mockFile = new File(['content'], 'video.mp4', { type: 'video/mp4' })
    
    mockXHR.status = 401
    mockXHR.responseText = JSON.stringify({ detail: 'Authentication failed' })
    
    // Override the send method to trigger the event immediately
    mockXHR.send = vi.fn(() => {
      // Trigger load event synchronously
      const timeoutId = setTimeout(() => mockXHR.triggerEvent('load'), 0)
      timeoutIds.push(timeoutId)
    })
    
    await expect(apiService.uploadVideo(mockFile)).rejects.toThrow(AuthError)
  })
  
  it('should handle 400 validation errors', async () => {
    const mockFile = new File(['content'], 'video.mp4', { type: 'video/mp4' })
    
    mockXHR.status = 400
    mockXHR.responseText = JSON.stringify({ detail: 'Invalid request' })
    
    // Override the send method to trigger the event immediately
    mockXHR.send = vi.fn(() => {
      // Trigger load event synchronously
      const timeoutId = setTimeout(() => mockXHR.triggerEvent('load'), 0)
      timeoutIds.push(timeoutId)
    })
    
    await expect(apiService.uploadVideo(mockFile)).rejects.toThrow(ValidationError)
  })
  
  it('should handle 500 server errors', async () => {
    const mockFile = new File(['content'], 'video.mp4', { type: 'video/mp4' })
    
    mockXHR.status = 500
    mockXHR.responseText = JSON.stringify({ detail: 'Server error' })
    
    // Override the send method to trigger the event immediately
    mockXHR.send = vi.fn(() => {
      // Trigger load event synchronously
      const timeoutId = setTimeout(() => mockXHR.triggerEvent('load'), 0)
      timeoutIds.push(timeoutId)
    })
    
    await expect(apiService.uploadVideo(mockFile)).rejects.toThrow(APIError)
  })

  it('should handle network timeouts', async () => {
    const mockFile = new File(['content'], 'video.mp4', { type: 'video/mp4' })
    
    // Override the send method to trigger timeout event immediately
    mockXHR.send = vi.fn(() => {
      // Trigger timeout event synchronously
      const timeoutId = setTimeout(() => mockXHR.triggerEvent('timeout'), 0)
      timeoutIds.push(timeoutId)
    })
    
    await expect(apiService.uploadVideo(mockFile)).rejects.toThrow(NetworkError)
  })
})