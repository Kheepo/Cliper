import { authService } from './authService'
import { errorCategorizationService, ErrorCategory } from './errorCategorization'

// Base API configuration
const API_BASE_URL = 'http://localhost:8001/api'

// Enhanced error types for better error handling
export class APIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public code?: string,
    public retryable: boolean = false
  ) {
    super(message)
    this.name = 'APIError'
  }
}

export class AuthError extends APIError {
  constructor(message: string = 'Authentication failed') {
    super(message, 401, 'AUTH_ERROR', true)
    this.name = 'AuthError'
  }
}

export class NetworkError extends APIError {
  constructor(message: string = 'Network error') {
    super(message, 0, 'NETWORK_ERROR', true)
    this.name = 'NetworkError'
  }
}

export class ValidationError extends APIError {
  constructor(message: string = 'Validation failed') {
    super(message, 400, 'VALIDATION_ERROR', false)
    this.name = 'ValidationError'
  }
}

// Types for API responses
export interface AnalysisResult {
  id: string
  job_id: string
  video_id: string
  original_filename: string
  overall_viral_score: number
  transcription: {
    text: string
    segments: Array<{
      start: number
      end: number
      text: string
      confidence: number
    }>
  }
  scenes: Array<{
    start_time: number
    end_time: number
    description: string
    confidence: number
  }>
  emotions: Array<{
    start_time: number
    end_time: number
    emotion: string
    confidence: number
  }>
  faces: Array<{
    start_time: number
    end_time: number
    face_count: number
    expressions: string[]
  }>
  viral_score: {
    overall_score: number
    factors: string[]
    breakdown: Record<string, number>
  }
  processing_time: number
  metadata: Record<string, any>
  created_at: string
  updated_at: string
}

export interface JobAnalytics {
  total_jobs: number
  completed_jobs: number
  processing_jobs: number
  failed_jobs: number
  success_rate: number
  average_viral_score: number
  total_clips_generated: number
  average_processing_time: number
}

export interface ClipSegment {
  id: string
  start_time: number
  end_time: number
  duration: number
  viral_score: number
  title: string
  description: string
  confidence?: number
  type?: 'highlight' | 'transition' | 'action' | 'dialogue' | 'music'
  keywords?: string[]
  transcript_snippet?: string
  key_moments?: string[]
  suggested_titles?: string[]
  hashtags?: string[]
  thumbnail_timestamp?: number
  engagement_hooks?: string[]
}

export interface VideoAnalysis {
  id: string
  videoId: string
  viralScore: number
  segments: {
    id: string
    startTime: number
    endTime: number
    score: number
    description: string
    thumbnail?: string
  }[]
  clips: {
    id: string
    segmentId: string
    url: string
    duration: number
    platform: string
    status: 'pending' | 'processing' | 'completed' | 'failed'
  }[]
  metadata: {
    duration: number
    resolution: string
    frameRate: number
    fileSize: number
  }
  createdAt: string
  updatedAt: string
}

export interface UserSettings {
  // Profile settings
  name?: string
  email?: string
  
  // Video processing settings
  defaultQuality: string
  defaultNiche: string
  defaultDuration: number
  autoProcess: boolean
  maxClips: number
  
  // Output preferences
  outputFormat: string
  resolution: string
  frameRate: number
  watermark: boolean
  compressionLevel: string
  
  // Platform settings
  platforms: {
    youtube: boolean
    tiktok: boolean
    instagram: boolean
    twitter: boolean
  }
  
  // Notification settings
  emailNotifications: boolean
  pushNotifications: boolean
  processingUpdates: boolean
  marketingEmails: boolean
  
  // Appearance
  theme: 'light' | 'dark' | 'auto'
  language: string
}

export interface UserProfile {
  id: string
  name: string
  email: string
  avatar?: string
  plan: 'free' | 'premium' | 'enterprise'
  role?: string
  subscription?: {
    expiresAt: string
  }
  lastLoginAt?: string
  createdAt: string
  created_at: string
  updatedAt: string
}

export interface DashboardStats {
  totalVideos: number
  totalClips: number
  totalViews: number
  averageViralScore: number
  processingTime: number
  storageUsed: number
  storageLimit: number
}

export interface RecentActivity {
  id: string
  type: 'upload' | 'analysis' | 'clip_generated' | 'download'
  description: string
  timestamp: string
  videoId?: string
  clipId?: string
}

export interface ProcessingJob {
  id: string
  videoId: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  stage: string
  estimatedTime?: number
  error?: string
  error_message?: string
  progress_message?: string
  job_id?: string
  createdAt: string
  updatedAt: string
}

// Enhanced auth headers with Supabase authentication
const getAuthHeaders = async (retryCount = 0): Promise<Record<string, string>> => {
  const maxRetries = 2
  
  try {
    // Check if user is authenticated
    if (!await authService.validateAuth()) {
      throw new AuthError('No active session. Please log in again.')
    }
    
    // Get auth headers from Supabase auth service
    const headers = await authService.getAuthHeaders()
    
    return {
      ...headers,
      'X-Token-Status': 'valid'
    }
    
  } catch (error) {
    if (error instanceof AuthError) {
      throw error
    }
    
    console.error('Auth headers error:', error)
    throw new AuthError(`Authentication service error: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

// Enhanced API request with retry logic and better error handling
const apiRequest = async (
  endpoint: string, 
  options: RequestInit = {}, 
  retryCount = 0
): Promise<any> => {
  const maxRetries = 3
  const baseDelay = 1000
  
  try {
    const headers = await getAuthHeaders()
    
    // Create AbortController for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        ...headers,
        ...options.headers
      },
      signal: controller.signal
    })
    
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      let errorData: any = { message: 'Unknown error' }
      
      try {
        const contentType = response.headers.get('content-type')
        if (contentType && contentType.includes('application/json')) {
          errorData = await response.json()
        } else {
          errorData = { message: await response.text() || `HTTP ${response.status}` }
        }
      } catch {
        errorData = { message: `HTTP ${response.status}` }
      }
      
      // Categorize errors
      switch (response.status) {
        case 401:
          throw new AuthError(errorData.message || 'Authentication failed')
        case 400:
          throw new ValidationError(errorData.message || 'Invalid request')
        case 403:
          throw new APIError(errorData.message || 'Access denied', 403, 'FORBIDDEN', false)
        case 404:
          throw new APIError(errorData.message || 'Resource not found', 404, 'NOT_FOUND', false)
        case 429:
          throw new APIError(errorData.message || 'Too many requests', 429, 'RATE_LIMIT', true)
        case 500:
        case 502:
        case 503:
        case 504:
          throw new APIError(
            errorData.message || 'Server error', 
            response.status, 
            'SERVER_ERROR', 
            true
          )
        default:
          throw new APIError(
            errorData.message || `HTTP ${response.status}`, 
            response.status, 
            'UNKNOWN_ERROR', 
            response.status >= 500
          )
      }
    }
    
    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      return response.json()
    }
    
    return response.text()
  } catch (error: any) {
    // Handle AbortError (timeout)
    if (error.name === 'AbortError') {
      const timeoutError = new NetworkError('Request timeout')
      
      if (retryCount < maxRetries) {
        const delay = baseDelay * Math.pow(2, retryCount)
        console.log(`Request timeout, retrying in ${delay}ms... (${retryCount + 1}/${maxRetries})`)
        await new Promise(resolve => setTimeout(resolve, delay))
        return apiRequest(endpoint, options, retryCount + 1)
      }
      
      throw timeoutError
    }
    
    // Handle network errors
    if (error instanceof TypeError && error.message.includes('fetch')) {
      const networkError = new NetworkError('Network connection failed')
      
      if (retryCount < maxRetries) {
        const delay = baseDelay * Math.pow(2, retryCount)
        console.log(`Network error, retrying in ${delay}ms... (${retryCount + 1}/${maxRetries})`)
        await new Promise(resolve => setTimeout(resolve, delay))
        return apiRequest(endpoint, options, retryCount + 1)
      }
      
      throw networkError
    }
    
    // Handle retryable API errors
    if (error instanceof APIError && error.retryable && retryCount < maxRetries) {
      const delay = baseDelay * Math.pow(2, retryCount)
      console.log(`API error (${error.status}), retrying in ${delay}ms... (${retryCount + 1}/${maxRetries})`)
      await new Promise(resolve => setTimeout(resolve, delay))
      return apiRequest(endpoint, options, retryCount + 1)
    }
    
    // Re-throw the error if not retryable or max retries reached
    throw error
  }
}

// API service object
export const apiService = {
  // Enhanced video upload with better auth integration and error handling
  uploadVideo: async (
    file: File, 
    onProgress?: (progress: number) => void, 
    options: { niche?: string; quality?: string } = {},
    retryCount = 0
  ): Promise<{ job_id: string }> => {
    const maxRetries = 2
    
    return new Promise((resolve, reject) => {
      // Check authentication first
      getAuthHeaders().then(headers => {
        try {
        
        // Then validate file
        if (!file) {
          throw new ValidationError('No file provided');
        }

        if (!file.type.startsWith('video/')) {
          throw new ValidationError('File must be a video');
        }

        const maxSize = 500 * 1024 * 1024; // 500MB
        if (file.size > maxSize) {
          throw new ValidationError('File size must be less than 500MB');
        }
        
        const xhr = new XMLHttpRequest()
        const formData = new FormData()
        
        formData.append('file', file)
        formData.append('target_niche', options.niche || 'general')
        
        // Enhanced dynamic timeout based on file size
        const fileSizeMB = file.size / (1024 * 1024)
        const dynamicTimeout = Math.max(300000, Math.min(fileSizeMB * 600, 1800000))
        xhr.timeout = dynamicTimeout
        
        // Track upload progress with throttling
        let lastProgressTime = 0
        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable && onProgress) {
            const now = Date.now()
            // Throttle progress updates to every 100ms
            if (now - lastProgressTime > 100) {
              const progress = Math.round((event.loaded / event.total) * 100)
              onProgress(progress)
              lastProgressTime = now
            }
          }
        })
        
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const response = JSON.parse(xhr.responseText)
              resolve(response)
            } catch (error) {
              const categorizedError = errorCategorizationService.categorizeError(
                'Invalid response format',
                xhr.status,
                { operation: 'upload', fileName: file.name }
              )
              reject(new ValidationError(categorizedError.userMessage))
            }
          } else {
            // Use comprehensive error categorization service
            let errorResponse: any = {}
            try {
              errorResponse = JSON.parse(xhr.responseText)
            } catch {
              // Keep empty object for error categorization
            }
            
            const errorMessage = errorResponse.message || `HTTP ${xhr.status}`
            const context = { operation: 'upload', filename: file.name }
            
            const categorizedError = errorCategorizationService.categorizeError(errorMessage, xhr.status, context)
            
            // Retry logic for retryable errors
            if (categorizedError.retryable && retryCount < maxRetries) {
              const retryStrategy = errorCategorizationService.getRetryStrategy(categorizedError)
              const delay = Math.min(retryStrategy.baseDelay * Math.pow(retryStrategy.backoffMultiplier, retryCount), retryStrategy.maxDelay)
              console.log(`${categorizedError.category} error during upload, retrying in ${delay}ms... (${retryCount + 1}/${maxRetries})`)
              setTimeout(() => {
                apiService.uploadVideo(file, onProgress, options, retryCount + 1)
                  .then(resolve)
                  .catch(reject)
              }, delay)
              return
            }
            
            // Create appropriate error type based on category
            let errorInstance: Error
            switch (categorizedError.category) {
              case ErrorCategory.AUTHENTICATION:
                errorInstance = new AuthError(categorizedError.userMessage)
                break
              case ErrorCategory.VALIDATION:
              case ErrorCategory.FILE_FORMAT:
              case ErrorCategory.FILE_SIZE:
                errorInstance = new ValidationError(categorizedError.userMessage)
                break
              case ErrorCategory.NETWORK:
              case ErrorCategory.TIMEOUT:
                errorInstance = new NetworkError(categorizedError.userMessage)
                break
              default:
                errorInstance = new APIError(categorizedError.userMessage)
            }
            
            reject(errorInstance)
          }
        })
        
        xhr.addEventListener('error', () => {
          const errorMessage = 'Network error during upload'
          const context = { operation: 'upload', filename: file.name }
          
          const categorizedError = errorCategorizationService.categorizeError(errorMessage, undefined, context)
          
          if (categorizedError.retryable && retryCount < maxRetries) {
            const retryStrategy = errorCategorizationService.getRetryStrategy(categorizedError)
            const delay = Math.min(retryStrategy.baseDelay * Math.pow(retryStrategy.backoffMultiplier, retryCount), retryStrategy.maxDelay)
            console.log(`Network error during upload, retrying in ${delay}ms... (${retryCount + 1}/${maxRetries})`)
            setTimeout(() => {
              apiService.uploadVideo(file, onProgress, options, retryCount + 1)
                .then(resolve)
                .catch(reject)
            }, delay)
            return
          }
          reject(new NetworkError(categorizedError.userMessage))
        })
        
        xhr.addEventListener('abort', () => {
          reject(new APIError('Upload was aborted by user or system.', 0, 'ABORTED', false))
        })
        
        xhr.addEventListener('timeout', () => {
          const errorMessage = 'Upload timeout'
          const context = { operation: 'upload', filename: file.name, timeout: dynamicTimeout }
          
          const categorizedError = errorCategorizationService.categorizeError(errorMessage, undefined, context)
          
          if (categorizedError.retryable && retryCount < maxRetries) {
            const retryStrategy = errorCategorizationService.getRetryStrategy(categorizedError)
            const delay = Math.min(retryStrategy.baseDelay * Math.pow(retryStrategy.backoffMultiplier, retryCount), retryStrategy.maxDelay)
            console.log(`Upload timeout, retrying in ${delay}ms... (${retryCount + 1}/${maxRetries})`)
            setTimeout(() => {
              apiService.uploadVideo(file, onProgress, options, retryCount + 1)
                .then(resolve)
                .catch(reject)
            }, delay)
            return
          }
          
          // Create appropriate error type based on categorization
          let errorInstance: Error;
          switch (categorizedError.category) {
            case ErrorCategory.TIMEOUT:
            case ErrorCategory.NETWORK:
              errorInstance = new NetworkError(categorizedError.userMessage);
              break;
            case ErrorCategory.AUTHENTICATION:
              errorInstance = new AuthError(categorizedError.userMessage);
              break;
            case ErrorCategory.VALIDATION:
              errorInstance = new ValidationError(categorizedError.userMessage);
              break;
            default:
              errorInstance = new APIError(categorizedError.userMessage);
          }
          
          reject(errorInstance)
        })
        
        // Initialize upload with auth headers
        try {
          xhr.open('POST', `${API_BASE_URL}/videos/upload`)
          xhr.setRequestHeader('Authorization', headers.Authorization)
          xhr.send(formData)
        } catch (error) {
          reject(new APIError('Failed to initiate upload request.'))
        }
        
        } catch (error) {
          reject(new APIError('Failed to setup upload request.'))
        }
      }).catch(error => {
        if (error instanceof AuthError && retryCount < maxRetries) {
          setTimeout(() => {
            apiService.uploadVideo(file, onProgress, options, retryCount + 1)
              .then(resolve)
              .catch(reject)
          }, 1000 * (retryCount + 1))
          return
        }

        // Preserve specific error types
        if (error instanceof AuthError || error instanceof ValidationError || error instanceof NetworkError) {
          reject(error)
        } else {
          reject(error instanceof APIError ? error : new APIError(`Upload preparation failed: ${error instanceof Error ? error.message : 'Unknown error'}`))
        }
      })
    })
  },
  
  // Process video from URL with enhanced validation and error handling
  processUrl: async (url: string, options: { niche?: string; quality?: string } = {}, retryCount = 0): Promise<{ job_id: string }> => {
    const maxRetries = 3;
    
    // Input validation
    if (!url || typeof url !== 'string') {
      throw new ValidationError('Valid URL is required');
    }
    
    // Basic URL validation
    try {
      new URL(url);
    } catch {
      throw new ValidationError('Invalid URL format');
    }
    
    // Check for supported video platforms/formats
    const supportedDomains = ['youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com', 'twitch.tv'];
    const urlObj = new URL(url);
    const isSupported = supportedDomains.some(domain => 
      urlObj.hostname.includes(domain) || url.match(/\.(mp4|mov|avi|mkv|webm|flv)$/i)
    );
    
    if (!isSupported) {
      throw new ValidationError('URL must be from a supported platform (YouTube, Vimeo, etc.) or a direct video file link');
    }
    
    try {
      // Get auth headers with enhanced error handling
      const headers = await getAuthHeaders();
      
      const formData = new FormData();
      formData.append('url', url);
      formData.append('target_niche', options.niche || 'general');
      if (options.quality) {
        formData.append('quality', options.quality);
      }
      
      // Enhanced timeout based on URL processing complexity
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minute timeout
      
      try {
        const response = await fetch(`${API_BASE_URL}/api/videos/process-url`, {
          method: 'POST',
          headers: {
            'Authorization': headers.Authorization,
            'X-Request-ID': `url-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
          },
          body: formData,
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
          // Use comprehensive error categorization service
          let errorResponse: any = {};
          try {
            errorResponse = await response.json();
          } catch {
            // Keep empty object for error categorization
          }
          
          const errorMessage = errorResponse.message || errorResponse.detail || `HTTP ${response.status}`
          const context = { operation: 'processUrl', url: url }
          
          const categorizedError = errorCategorizationService.categorizeError(errorMessage, response.status, context);
          
          // Create appropriate error type based on category
          let errorInstance: Error;
          switch (categorizedError.category) {
            case ErrorCategory.AUTHENTICATION:
              errorInstance = new AuthError(categorizedError.userMessage);
              break;
            case ErrorCategory.VALIDATION:
            case ErrorCategory.FILE_FORMAT:
            case ErrorCategory.FILE_SIZE:
              errorInstance = new ValidationError(categorizedError.userMessage);
              break;
            case ErrorCategory.NETWORK:
            case ErrorCategory.TIMEOUT:
              errorInstance = new NetworkError(categorizedError.userMessage);
              break;
            default:
              errorInstance = new APIError(categorizedError.userMessage);
          }
          
          throw errorInstance;
        }
        
        const result = await response.json();
        if (!result.job_id) {
          throw new ValidationError('Invalid response: missing job ID');
        }
        
        return result;
        
      } catch (error: any) {
        clearTimeout(timeoutId);
        
        if (error.name === 'AbortError') {
          throw new NetworkError('Request timeout - URL processing is taking too long. Please try again.');
        }
        
        // Re-throw known error types
        if (error instanceof AuthError || error instanceof ValidationError || error instanceof APIError) {
          throw error;
        }
        
        throw new NetworkError(`Network error during URL processing: ${error.message}`);
      }
      
    } catch (error: any) {
      // Use error categorization service for retry logic
      const errorMessage = error.message || 'Unknown error during URL processing'
      const statusCode = error.status || error.statusCode
      const context = { operation: 'processUrl', url: url, retryCount }
      
      const categorizedError = errorCategorizationService.categorizeError(errorMessage, statusCode, context);
      
      // Retry logic based on error categorization
      if (categorizedError.retryable && retryCount < maxRetries) {
        const retryStrategy = errorCategorizationService.getRetryStrategy(categorizedError);
        const delay = Math.min(retryStrategy.baseDelay * Math.pow(retryStrategy.backoffMultiplier, retryCount), retryStrategy.maxDelay);
        
        console.log(`Retrying URL processing (${categorizedError.category}) in ${delay}ms... (attempt ${retryCount + 2}/${maxRetries + 1})`);
        
        await new Promise(resolve => setTimeout(resolve, delay));
        return apiService.processUrl(url, options, retryCount + 1);
      }
      
      // Preserve specific error types or create appropriate error based on categorization
      if (error instanceof AuthError || error instanceof ValidationError || error instanceof NetworkError || error instanceof APIError) {
        throw error;
      }
      
      // Create error based on categorization
      let errorInstance: Error;
      switch (categorizedError.category) {
        case ErrorCategory.AUTHENTICATION:
          errorInstance = new AuthError(categorizedError.userMessage);
          break;
        case ErrorCategory.VALIDATION:
        case ErrorCategory.FILE_FORMAT:
        case ErrorCategory.FILE_SIZE:
          errorInstance = new ValidationError(categorizedError.userMessage);
          break;
        case ErrorCategory.NETWORK:
        case ErrorCategory.TIMEOUT:
          errorInstance = new NetworkError(categorizedError.userMessage);
          break;
        default:
          errorInstance = new APIError(categorizedError.userMessage);
      }
      
      throw errorInstance;
    }
  },
  
  // Get video analysis
  getVideoAnalysis: async (videoId: string): Promise<VideoAnalysis> => {
    return apiRequest(`/api/videos/${videoId}/analysis`)
  },
  
  // Get all user videos
  getUserVideos: async () => {
    return apiRequest('/api/videos')
  },
  
  // Delete video
  deleteVideo: async (videoId: string) => {
    return apiRequest(`/api/videos/${videoId}`, { method: 'DELETE' })
  },
  
  // Generate clips from segments
  generateClips: async (formData: FormData) => {
    const headers = await getAuthHeaders()
    const response = await fetch(`${API_BASE_URL}/api/clips/generate`, {
      method: 'POST',
      headers: {
        ...headers
      },
      body: formData
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    return response.json()
  },
  

  
  // User settings
  getUserSettings: async (): Promise<UserSettings> => {
    return apiRequest('/api/user/settings')
  },
  
  updateUserSettings: async (settings: Partial<UserSettings>) => {
    return apiRequest('/api/user/settings', {
      method: 'PUT',
      body: JSON.stringify(settings)
    })
  },
  
  // User profile
  getUserProfile: async (): Promise<UserProfile> => {
    return apiRequest('/api/user/profile')
  },
  
  updateUserProfile: async (profile: Partial<UserProfile>) => {
    return apiRequest('/api/user/profile', {
      method: 'PUT',
      body: JSON.stringify(profile)
    })
  },
  
  // Dashboard analytics
  getDashboardStats: async (): Promise<DashboardStats> => {
    return apiRequest('/api/analytics/dashboard')
  },
  
  getRecentActivity: async (limit: number = 10): Promise<RecentActivity[]> => {
    return apiRequest(`/api/analytics/activity?limit=${limit}`)
  },
  
  getProcessingJobs: async (): Promise<ProcessingJob[]> => {
    return apiRequest('/api/analytics/jobs')
  },
  
  // Analytics endpoints
  getVideoMetrics: async (videoId: string) => {
    return apiRequest(`/api/analytics/videos/${videoId}/metrics`)
  },
  
  getPerformanceMetrics: async (timeRange: '7d' | '30d' | '90d' = '30d') => {
    return apiRequest(`/api/analytics/performance?range=${timeRange}`)
  },
  
  getViralScoreHistory: async (videoId: string) => {
    return apiRequest(`/api/analytics/videos/${videoId}/viral-score-history`)
  },
  
  // Clip management
  getClipDetails: async (clipId: string) => {
    return apiRequest(`/api/clips/${clipId}`)
  },
  
  updateClipMetadata: async (clipId: string, metadata: any) => {
    return apiRequest(`/api/clips/${clipId}/metadata`, {
      method: 'PUT',
      body: JSON.stringify(metadata)
    })
  },
  
  shareClip: async (clipId: string, platform: string) => {
    return apiRequest(`/api/clips/${clipId}/share`, {
      method: 'POST',
      body: JSON.stringify({ platform })
    })
  },
  
  // Processing status
  getProcessingStatus: async (jobId: string): Promise<ProcessingJob> => {
    return apiRequest(`/api/processing/${jobId}/status`)
  },
  
  cancelProcessing: async (jobId: string) => {
    return apiRequest(`/api/processing/${jobId}/cancel`, {
      method: 'POST'
    })
  },
  
  // Monitor processing with timeout (5 minutes)
  monitorProcessing: async (
    jobId: string, 
    onProgress?: (status: ProcessingJob) => void,
    timeoutMs: number = 300000 // 5 minutes
  ): Promise<ProcessingJob> => {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      
      const checkStatus = async () => {
        try {
          // Check if timeout exceeded
          if (Date.now() - startTime > timeoutMs) {
            reject(new Error('Processing timeout - the operation took longer than expected'));
            return;
          }
          
          const status = await apiService.getProcessingStatus(jobId);
          
          if (onProgress) {
            onProgress(status);
          }
          
          // Check if processing is complete
          if (status.status === 'completed') {
            resolve(status);
          } else if (status.status === 'failed' || status.status === 'cancelled') {
            reject(new Error(status.error_message || `Processing ${status.status}`));
          } else {
            // Continue monitoring
            setTimeout(checkStatus, 2000); // Check every 2 seconds
          }
        } catch (error) {
          reject(error);
        }
      };
      
      checkStatus();
    });
  },
  
  // Search and filtering
  searchVideos: async (query: string, filters: any = {}) => {
    const params = new URLSearchParams({
      q: query,
      ...filters
    })
    return apiRequest(`/api/videos/search?${params}`)
  },
  
  // Batch operations
  batchDeleteVideos: async (videoIds: string[]) => {
    return apiRequest('/api/videos/batch-delete', {
      method: 'POST',
      body: JSON.stringify({ videoIds })
    })
  },
  
  batchGenerateClips: async (requests: { videoId: string; segmentIds: string[]; platforms: string[] }[]) => {
    return apiRequest('/api/clips/batch-generate', {
      method: 'POST',
      body: JSON.stringify({ requests })
    })
  },
  
  // Export and backup
  exportUserData: async () => {
    const headers = await getAuthHeaders()
    const response = await fetch(`${API_BASE_URL}/api/user/export`, {
      headers
    })
    
    if (!response.ok) {
      throw new Error('Export failed')
    }
    
    return response.blob()
  },
  
  // Subscription and billing
  getSubscriptionStatus: async () => {
    return apiRequest('/api/user/subscription')
  },
  
  upgradeSubscription: async (plan: string) => {
    return apiRequest('/api/user/subscription/upgrade', {
      method: 'POST',
      body: JSON.stringify({ plan })
    })
  },
  
  // Notifications
  getNotifications: async () => {
    return apiRequest('/api/user/notifications')
  },
  
  markNotificationRead: async (notificationId: string) => {
    return apiRequest(`/api/user/notifications/${notificationId}/read`, {
      method: 'PUT'
    })
  },
  
  // System health
  getSystemStatus: async () => {
    return apiRequest('/api/system/status')
  },

  // Get user analytics with date range
  getUserAnalytics: async (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams()
    if (startDate) params.append('start_date', startDate)
    if (endDate) params.append('end_date', endDate)
    
    return apiRequest(`/api/analytics/user?${params.toString()}`)
  },

  // Get paginated user history
  getUserHistoryPaginated: async (page: number = 1, limit: number = 10) => {
    return apiRequest(`/api/history?page=${page}&limit=${limit}`)
  },

  // Generate clip preview
  generatePreview: async (data: any) => {
    return apiRequest('/api/clips/preview', {
      method: 'POST',
      body: JSON.stringify(data)
    })
  },

  // Get clip share URL
  getShareUrl: async (clipId: string): Promise<string> => {
    const response = await apiRequest(`/api/clips/${clipId}/share`)
    return response.share_url
  },

  // Get clips for a job
  getClips: async (jobId: string) => {
    return apiRequest(`/api/jobs/${jobId}/clips`)
  },
  
  // Get analysis result
  getAnalysisResult: async (jobId: string): Promise<AnalysisResult> => {
    return apiRequest(`/api/jobs/${jobId}/analysis`)
  },

  // Generate clip
  generateClip: async (clipData: any) => {
    return apiRequest('/api/clips/generate', {
      method: 'POST',
      body: JSON.stringify(clipData)
    })
  },

  // Download clip
  downloadClip: async (clipId: string, format?: string): Promise<Blob> => {
    const headers = await getAuthHeaders()
    const params = format ? `?format=${format}` : ''
    const response = await fetch(`${API_BASE_URL}/api/clips/${clipId}/download${params}`, {
      headers
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    return response.blob()
  },

  // Clip generation methods
  analyzeVideoSegments: async (formData: FormData) => {
    const response = await fetch(`${API_BASE_URL}/api/clips/analyze`, {
      method: 'POST',
      body: formData,
    });
    return response.json();
  },



  optimizeClip: async (clipId: string, platform: string, customizations?: any) => {
    const response = await fetch(`${API_BASE_URL}/api/clips/${clipId}/optimize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ platform, customizations }),
    });
    return response.json();
  },

  getClipGenerationStatus: async (jobId: string) => {
    const response = await fetch(`${API_BASE_URL}/api/clips/status/${jobId}`);
    return response.json();
  },

  cancelClipGeneration: async (jobId: string) => {
    const response = await fetch(`${API_BASE_URL}/api/clips/cancel/${jobId}`, {
      method: 'POST',
    });
    return response.json();
  },

  getClipAnalytics: async (clipIds: string[]) => {
    const response = await fetch(`${API_BASE_URL}/api/clips/analytics`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ clipIds }),
    });
    return response.json();
  },

  // Authentication methods
  verifyToken: async () => {
    return apiRequest('/api/auth/verify', {
      method: 'POST'
    });
  },

  // Job analytics
  getJobAnalytics: async (jobId?: string) => {
    const endpoint = jobId ? `/api/analytics/jobs/${jobId}` : '/api/analytics/jobs';
    return apiRequest(endpoint);
  },
  
  // Get job status
  getJobStatus: async (jobId: string) => {
    return apiRequest(`/api/jobs/${jobId}/status`);
  },
  
  // Get job logs
  getJobLogs: async (jobId: string) => {
    return apiRequest(`/api/jobs/${jobId}/logs`);
  },
  
  // Restart stuck jobs
  restartStuckJobs: async () => {
    return apiRequest('/api/jobs/restart-stuck', {
      method: 'POST'
    });
  },
  
  // Restart specific job
  restartJob: async (jobId: string) => {
    return apiRequest(`/api/jobs/${jobId}/restart`, {
      method: 'POST'
    });
  },
  
  // Cancel job
  cancelJob: async (jobId: string) => {
    return apiRequest(`/api/jobs/${jobId}/cancel`, {
      method: 'POST'
    });
  }
}

export default apiService