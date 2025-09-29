import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import Upload from '../pages/Upload'
import Results from '../pages/Results'
import { supabase } from '../lib/supabase'
import { apiService } from '../services/api'
import { ChunkedUploadService } from '../services/chunkedUpload'
import { AuthError, NetworkError, ValidationError } from '../services/api'
import { AuthProvider } from '../contexts/AuthContext'

// Mock dependencies
vi.mock('../lib/supabase')
vi.mock('../services/chunkedUpload')

// Mock apiService with proper structure
vi.mock('../services/api', () => ({
  apiService: {
    uploadVideo: vi.fn(),
    getVideo: vi.fn(),
    getVideos: vi.fn(),
    deleteVideo: vi.fn(),
    getAnalysis: vi.fn(),
    getAnalysisResult: vi.fn(),
    getClips: vi.fn(),
    getUserProfile: vi.fn(),
    updateUserProfile: vi.fn(),
    getUserSettings: vi.fn(),
    updateUserSettings: vi.fn(),
    getDashboardStats: vi.fn(),
    getJobAnalytics: vi.fn()
  },
  AuthError: class AuthError extends Error {
    constructor(message = 'Authentication failed') {
      super(message)
      this.name = 'AuthError'
    }
  },
  NetworkError: class NetworkError extends Error {
    constructor(message = 'Network error') {
      super(message)
      this.name = 'NetworkError'
    }
  },
  ValidationError: class ValidationError extends Error {
    constructor(message = 'Validation failed') {
      super(message)
      this.name = 'ValidationError'
    }
  }
}))
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ jobId: 'test-video-id' }),
    useLocation: () => ({ state: null })
  }
})

// Mock toast notifications
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    loading: vi.fn(),
    dismiss: vi.fn()
  }
}))

// Mock file input
const createMockFile = (name: string, size: number, type: string) => {
  const file = new File(['mock content'], name, { type })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

describe('Video Upload Integration Tests', () => {
  beforeEach(() => {
    // Reset all mocks to clear previous test state
    vi.resetAllMocks()
    
    // Set up Supabase mocks
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: {
        session: {
          access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.test',
          refresh_token: 'mock-refresh-token',
          expires_in: 3600,
          token_type: 'bearer',
          user: {
            id: 'user-123',
            email: 'test@example.com',
            app_metadata: {},
            user_metadata: {},
            aud: 'authenticated',
            created_at: new Date().toISOString()
          }
        }
      },
      error: null
    })
    
    vi.mocked(supabase.auth.getUser).mockResolvedValue({
      data: {
        user: {
          id: 'user-123',
          email: 'test@example.com',
          app_metadata: {},
          user_metadata: {},
          aud: 'authenticated',
          created_at: new Date().toISOString()
        }
      },
      error: null
    })
    
    // Mock onAuthStateChange
    vi.mocked(supabase.auth.onAuthStateChange).mockImplementation((callback) => {
      // Call the callback immediately with initial auth state
      const mockUser = {
        id: 'user-123',
        email: 'test@example.com',
        app_metadata: {},
        user_metadata: {},
        aud: 'authenticated',
        created_at: new Date().toISOString()
      }
      setTimeout(() => callback('SIGNED_IN', { 
        user: mockUser, 
        access_token: 'mock-token', 
        refresh_token: 'mock-refresh',
        expires_in: 3600,
        token_type: 'bearer'
      }), 0)
      return {
        data: { 
          subscription: { 
            id: 'mock-subscription-id',
            callback,
            unsubscribe: vi.fn() 
          } 
        }
      }
    })
    
    // Set up default apiService mock implementations
    vi.mocked(apiService.uploadVideo).mockResolvedValue({
      job_id: 'default-video-id'
    })
    
    // Remove non-existent API methods
    
    // Mock Results page API calls
    vi.mocked(apiService.getAnalysisResult).mockResolvedValue({
      id: 'test-video-id',
      job_id: 'job-123',
      video_id: 'test-video-id',
      original_filename: 'test-video.mp4',
      overall_viral_score: 8.5,
      transcription: {
        text: 'Test transcription',
        segments: []
      },
      scenes: [],
      emotions: [],
      faces: [],
      viral_score: {
        overall_score: 8.5,
        factors: ['engagement', 'trending'],
        breakdown: { engagement: 8.0, trending: 9.0 }
      },
      processing_time: 120,
      metadata: {
        duration: 180,
        highlights: ['Highlight 1', 'Highlight 2'],
        summary: 'Test video analysis summary'
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    })
    
    vi.mocked(apiService.getClips).mockResolvedValue({
      clips: [
        {
          id: 'clip-1',
          start_time: 10,
          end_time: 40,
          duration: 30,
          viral_score: 8.5,
          title: 'Test Clip 1',
          description: 'A great viral moment',
          engagement_potential: 8.2,
          shareability: 8.8
        },
        {
          id: 'clip-2',
          start_time: 60,
          end_time: 90,
          duration: 30,
          viral_score: 7.8,
          title: 'Test Clip 2',
          description: 'Another engaging segment',
          engagement_potential: 7.5,
          shareability: 8.0
        }
      ]
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('File Upload Workflow', () => {
    it('should complete small file upload successfully', async () => {
      const mockFile = createMockFile('small-video.mp4', 50 * 1024 * 1024, 'video/mp4') // 50MB
      
      // Mock successful upload
      vi.mocked(apiService.uploadVideo).mockResolvedValue({
        job_id: 'video-123'
      })
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      // Find file input and upload file
      const fileInput = screen.getByLabelText(/choose file/i)
      fireEvent.change(fileInput, { target: { files: [mockFile] } })
      
      // Wait for file to be processed
      await waitFor(() => {
        expect(screen.getByText(/small-video.mp4/)).toBeInTheDocument()
      })
      
      // Click upload button
      const uploadButton = screen.getByRole('button', { name: /upload video/i })
      fireEvent.click(uploadButton)
      
      // Verify upload was called
      await waitFor(() => {
        expect(apiService.uploadVideo).toHaveBeenCalledWith(
          mockFile,
          expect.any(Object)
        )
      })
    })

    it('should use chunked upload for large files', async () => {
      const mockFile = createMockFile('large-video.mp4', 200 * 1024 * 1024, 'video/mp4') // 200MB
      
      // Mock chunked upload service
      const mockChunkedService = {
        startUpload: vi.fn().mockResolvedValue({ sessionId: 'session-123', isResume: false }),
        uploadFile: vi.fn().mockResolvedValue({ job_id: 'video-123' }),
        getProgress: vi.fn().mockReturnValue(0)
      }
      
      vi.mocked(ChunkedUploadService).mockImplementation(() => mockChunkedService as any)
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      // Upload large file
      const fileInput = screen.getByLabelText(/choose file/i)
      fireEvent.change(fileInput, { target: { files: [mockFile] } })
      
      await waitFor(() => {
        expect(screen.getByText(/large-video.mp4/)).toBeInTheDocument()
      })
      
      const uploadButton = screen.getByRole('button', { name: /upload video/i })
      fireEvent.click(uploadButton)
      
      // Verify chunked upload was used
      await waitFor(() => {
        expect(mockChunkedService.startUpload).toHaveBeenCalledWith(mockFile)
        expect(mockChunkedService.uploadFile).toHaveBeenCalled()
      })
    })

    it('should handle upload errors gracefully', async () => {
      const mockFile = createMockFile('error-video.mp4', 50 * 1024 * 1024, 'video/mp4')
      
      // Mock upload error
      vi.mocked(apiService.uploadVideo).mockRejectedValue(
        new Error('Upload failed: Server error')
      )
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      const fileInput = screen.getByLabelText(/choose file/i)
      fireEvent.change(fileInput, { target: { files: [mockFile] } })
      
      await waitFor(() => {
        expect(screen.getByText(/error-video.mp4/)).toBeInTheDocument()
      })
      
      const uploadButton = screen.getByRole('button', { name: /upload video/i })
      fireEvent.click(uploadButton)
      
      // Should show error state
      await waitFor(() => {
        expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
      })
    })

    it('should validate file types', async () => {
      const invalidFile = createMockFile('document.pdf', 10 * 1024 * 1024, 'application/pdf')
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      const fileInput = screen.getByLabelText(/choose file/i)
      fireEvent.change(fileInput, { target: { files: [invalidFile] } })
      
      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/invalid file type/i)).toBeInTheDocument()
      })
    })

    it('should validate file size limits', async () => {
      const oversizedFile = createMockFile('huge-video.mp4', 15 * 1024 * 1024 * 1024, 'video/mp4') // 15GB
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      const fileInput = screen.getByLabelText(/choose file/i)
      fireEvent.change(fileInput, { target: { files: [oversizedFile] } })
      
      // Should show size validation error
      await waitFor(() => {
        expect(screen.getByText(/file too large/i)).toBeInTheDocument()
      })
    })
  })

  describe('URL Upload Workflow', () => {
    it('should process YouTube URL successfully', async () => {
      const youtubeUrl = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
      
      // Mock successful URL processing
      vi.mocked(apiService.processUrl).mockResolvedValue({
        job_id: 'task-123'
      })
      
      vi.mocked(apiService.getJobStatus).mockResolvedValue({
        job_id: 'task-123',
        status: 'completed',
        progress: 100,
        current_step: 'Analysis complete',
        estimated_remaining: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      // Switch to URL tab
      const urlTab = screen.getByRole('tab', { name: /url/i })
      fireEvent.click(urlTab)
      
      // Enter URL
      const urlInput = screen.getByPlaceholderText(/enter video url/i)
      fireEvent.change(urlInput, { target: { value: youtubeUrl } })
      
      // Submit URL
      const submitButton = screen.getByRole('button', { name: /process url/i })
      fireEvent.click(submitButton)
      
      // Verify URL processing
      await waitFor(() => {
        expect(apiService.processUrl).toHaveBeenCalledWith(youtubeUrl)
      })
      
      // Should show processing state
      expect(screen.getByText(/processing/i)).toBeInTheDocument()
    })

    it('should handle invalid URLs', async () => {
      const invalidUrl = 'not-a-valid-url'
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      const urlTab = screen.getByRole('tab', { name: /url/i })
      fireEvent.click(urlTab)
      
      const urlInput = screen.getByPlaceholderText(/enter video url/i)
      fireEvent.change(urlInput, { target: { value: invalidUrl } })
      
      const submitButton = screen.getByRole('button', { name: /process url/i })
      fireEvent.click(submitButton)
      
      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/invalid url/i)).toBeInTheDocument()
      })
    })

    it('should handle URL processing timeout', async () => {
      const youtubeUrl = 'https://www.youtube.com/watch?v=timeout'
      
      // Mock processing that never completes
      vi.mocked(apiService.processUrl).mockResolvedValue({
        job_id: 'task-timeout'
      })
      
      vi.mocked(apiService.getJobStatus).mockResolvedValue({
        job_id: 'task-timeout',
        status: 'processing',
        progress: 50,
        current_step: 'Processing video',
        estimated_remaining: 120,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      const urlTab = screen.getByRole('tab', { name: /url/i })
      fireEvent.click(urlTab)
      
      const urlInput = screen.getByPlaceholderText(/enter video url/i)
      fireEvent.change(urlInput, { target: { value: youtubeUrl } })
      
      const submitButton = screen.getByRole('button', { name: /process url/i })
      fireEvent.click(submitButton)
      
      // Should eventually show timeout error
      await waitFor(() => {
        expect(screen.getByText(/timeout/i)).toBeInTheDocument()
      }, { timeout: 6000 })
    })
  })

  describe('Authentication Integration', () => {
    it('should handle authentication errors during upload', async () => {
      const mockFile = createMockFile('auth-test.mp4', 50 * 1024 * 1024, 'video/mp4')
      
      // Mock auth error
      vi.mocked(apiService.uploadVideo).mockRejectedValue(
        new Error('Authentication failed')
      )
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      const fileInput = screen.getByLabelText(/choose file/i)
      fireEvent.change(fileInput, { target: { files: [mockFile] } })
      
      await waitFor(() => {
        expect(screen.getByText(/auth-test.mp4/)).toBeInTheDocument()
      })
      
      const uploadButton = screen.getByRole('button', { name: /upload video/i })
      fireEvent.click(uploadButton)
      
      // Should show auth error with retry option
      await waitFor(() => {
        expect(screen.getByText(/authentication failed/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
      })
    })

    it('should redirect to login when not authenticated', async () => {
      // Mock no session
      vi.mocked(supabase.auth.getSession).mockResolvedValue({
        data: { session: null },
        error: null
      })
      
      vi.mocked(supabase.auth.getUser).mockResolvedValue({
        data: { user: null },
        error: null
      })
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      // Should show login prompt
      await waitFor(() => {
        expect(screen.getByText(/sign in/i)).toBeInTheDocument()
      })
    })
  })

  describe('Results Page Integration', () => {
    it('should display video processing results', async () => {
      // Mock video data
      vi.mocked(apiService.getJobStatus).mockResolvedValue({
        id: 'test-video-id',
        title: 'Test Video',
        status: 'completed',
        duration: 180,
        file_size: 50 * 1024 * 1024,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        user_id: 'user-123',
        file_path: '/videos/test-video.mp4',
        thumbnail_url: '/thumbnails/test-video.jpg',
        metadata: {
          format: 'mp4',
          resolution: '1920x1080',
          fps: 30,
          bitrate: 5000
        }
      })
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Results />
          </AuthProvider>
        </BrowserRouter>
      )
      
      // Should display video information
      await waitFor(() => {
        expect(screen.getByText('Test Video')).toBeInTheDocument()
        expect(screen.getByText(/completed/i)).toBeInTheDocument()
        expect(screen.getByText(/3:00/)).toBeInTheDocument() // 180 seconds = 3:00
      })
    })

    it('should handle video not found', async () => {
      vi.mocked(apiService.getJobStatus).mockRejectedValue(
        new Error('Video not found')
      )
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Results />
          </AuthProvider>
        </BrowserRouter>
      )
      
      await waitFor(() => {
        expect(screen.getByText(/video not found/i)).toBeInTheDocument()
      })
    })

    it('should show processing status for pending videos', async () => {
      vi.mocked(apiService.getJobStatus).mockResolvedValue({
        id: 'processing-video-id',
        title: 'Processing Video',
        status: 'processing',
        duration: null,
        file_size: 100 * 1024 * 1024,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        user_id: 'user-123',
        file_path: '/videos/processing-video.mp4',
        thumbnail_url: null,
        metadata: null
      })
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Results />
          </AuthProvider>
        </BrowserRouter>
      )
      
      await waitFor(() => {
        expect(screen.getByText('Processing Video')).toBeInTheDocument()
        expect(screen.getByText(/processing/i)).toBeInTheDocument()
        expect(screen.getByRole('progressbar')).toBeInTheDocument()
      })
    })
  })

  describe('Error Recovery', () => {
    it('should allow retry after network errors', async () => {
      const mockFile = createMockFile('retry-test.mp4', 50 * 1024 * 1024, 'video/mp4')
      
      // First call fails, second succeeds
      vi.mocked(apiService.uploadVideo)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          job_id: 'video-123'
        })
      
      render(
        <BrowserRouter>
          <AuthProvider>
            <Upload />
          </AuthProvider>
        </BrowserRouter>
      )
      
      const fileInput = screen.getByLabelText(/choose file/i)
      fireEvent.change(fileInput, { target: { files: [mockFile] } })
      
      await waitFor(() => {
        expect(screen.getByText(/retry-test.mp4/)).toBeInTheDocument()
      })
      
      const uploadButton = screen.getByRole('button', { name: /upload video/i })
      fireEvent.click(uploadButton)
      
      // Should show error with retry button
      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
      })
      
      // Click retry
      const retryButton = screen.getByRole('button', { name: /retry/i })
      fireEvent.click(retryButton)
      
      // Should succeed on retry
      await waitFor(() => {
        expect(apiService.uploadVideo).toHaveBeenCalledTimes(2)
      })
    })
  })
})