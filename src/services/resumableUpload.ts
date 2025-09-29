import { supabase } from '../lib/supabase'
import { apiService } from './api'
import { errorCategorizationService } from './errorCategorization'

interface UploadChunk {
  data: Blob
  start: number
  end: number
  index: number
}

interface UploadSession {
  id: string
  fileName: string
  fileSize: number
  chunkSize: number
  totalChunks: number
  uploadedChunks: Set<number>
  lastActivity: number
  startTime: number
  uploadSpeed: number
  estimatedTimeRemaining: number
  bytesUploaded: number
  status: 'pending' | 'uploading' | 'paused' | 'completed' | 'error'
  errorCount: number
  lastError?: string
}

class ResumableUploadService {
  private readonly CHUNK_SIZE = 1024 * 1024 // 1MB chunks for better reliability
  private readonly SESSION_TIMEOUT = 24 * 60 * 60 * 1000 // 24 hours
  private readonly MAX_RETRIES = 5 // Increased retries
  private readonly RETRY_DELAY = 2000 // 2 second base delay
  private readonly UPLOAD_TIMEOUT = 1200000 // 20 minutes per chunk (increased)
  private readonly MIN_TIMEOUT = 600000 // Minimum 10 minutes timeout
  private readonly MAX_TIMEOUT = 2400000 // Maximum 40 minutes timeout
  private readonly PROGRESSIVE_TIMEOUT_FACTOR = 1.5 // Scale timeout based on file size
  private readonly STORAGE_KEY = 'resumable_upload_sessions_v2'
  private readonly PROGRESS_UPDATE_INTERVAL = 1000 // Update progress every second
  
  private sessions = new Map<string, UploadSession>()
  private progressTimers = new Map<string, NodeJS.Timeout>()
  
  constructor() {
    this.loadSessionsFromStorage()
    this.cleanupExpiredSessions()
  }
  
  /**
   * Upload file with chunked upload (alias for startUpload)
   */
  async uploadFile(
    file: File,
    options: {
      niche?: string
      quality?: string
      onProgress?: (progress: number) => void
      onChunkComplete?: (chunkIndex: number, totalChunks: number) => void
      onStatusUpdate?: (status: string, details?: string) => void
      onError?: (error: Error, isRetryable: boolean) => void
    } = {}
  ): Promise<{ job_id: string }> {
    return this.startUpload(file, options, options.onProgress);
  }

  /**
   * Start or resume an upload session
   */
 private async startUpload(
    file: File,
    options: {
      niche?: string
      quality?: string
      onProgress?: (progress: number) => void
      onChunkComplete?: (chunkIndex: number, totalChunks: number) => void
      onStatusUpdate?: (status: string, details?: string) => void
      onError?: (error: Error, isRetryable: boolean) => void
    },
    onProgress?: (progress: number) => void
  ): Promise<any> {
    const sessionId = this.generateSessionId(file)
    let session = this.sessions.get(sessionId)
    
    if (!session) {
      // Create new session
      const now = Date.now()
      session = {
        id: sessionId,
        fileName: file.name,
        fileSize: file.size,
        chunkSize: this.CHUNK_SIZE,
        totalChunks: Math.ceil(file.size / this.CHUNK_SIZE),
        uploadedChunks: new Set(),
        lastActivity: now,
        startTime: now,
        uploadSpeed: 0,
        estimatedTimeRemaining: 0,
        bytesUploaded: 0,
        status: 'pending',
        errorCount: 0
      }
      this.sessions.set(sessionId, session)
    } else {
      // Resume existing session
      session.lastActivity = Date.now()
      session.status = 'pending'
      console.log(`Resuming upload for ${file.name}, ${session.uploadedChunks.size}/${session.totalChunks} chunks completed`)
    }
    
    this.saveSessionsToStorage()
    
    try {
      const result = await this.uploadChunks(file, session, options, onProgress)
      
      // Clean up successful session
      this.sessions.delete(sessionId)
      this.saveSessionsToStorage()
      
      return result
    } catch (error) {
      // Save session state for potential resume
      this.saveSessionsToStorage()
      throw error
    }
  }
  
  /**
   * Upload chunks in parallel with retry logic
   */
  private async uploadChunks(
    file: File,
    session: UploadSession,
    options: {
      niche?: string
      quality?: string
      onProgress?: (progress: number) => void
      onChunkComplete?: (chunkIndex: number, totalChunks: number) => void
      onStatusUpdate?: (status: string, details?: string) => void
      onError?: (error: Error, isRetryable: boolean) => void
    },
    onProgress?: (progress: number) => void
  ): Promise<any> {
    const chunks = this.createChunks(file, session)
    const pendingChunks = chunks.filter(chunk => !session.uploadedChunks.has(chunk.index))
    
    // Update session status
    session.status = 'uploading'
    session.bytesUploaded = session.uploadedChunks.size * session.chunkSize
    
    // Start progress tracking
    this.startProgressTracking(session, onProgress, options.onProgress)
    
    // Notify status update
    if (options.onStatusUpdate) {
      options.onStatusUpdate('uploading', `Uploading ${pendingChunks.length} chunks...`)
    }
    
    // Upload chunks in parallel (max 2 concurrent for better stability)
    const concurrency = 2
    const results: any[] = []
    
    for (let i = 0; i < pendingChunks.length; i += concurrency) {
      const batch = pendingChunks.slice(i, i + concurrency)
      const batchPromises = batch.map(chunk => this.uploadChunkWithRetry(chunk, session, file.size, options))
      
      try {
        const batchResults = await Promise.all(batchPromises)
        results.push(...batchResults)
        
        // Update bytes uploaded for completed chunks
        batch.forEach(chunk => {
          session.bytesUploaded += chunk.data.size
        })
        
        // Notify chunk completion for each chunk in the batch
        if (options.onChunkComplete) {
          batch.forEach(chunk => {
            options.onChunkComplete!(chunk.index, session.totalChunks)
          })
        }
        
        // Update progress (will be handled by progress tracking timer)
        // Save progress
        session.lastActivity = Date.now()
        this.saveSessionsToStorage()
        
      } catch (error) {
        console.error('Batch upload failed:', error)
        
        // Update session error tracking
        session.status = 'error'
        session.errorCount++
        session.lastError = error instanceof Error ? error.message : 'Unknown error'
        this.stopProgressTracking(session.id)
        
        // Notify error with retry information
        if (options.onError) {
          const isRetryable = !(error instanceof Error && (
            error.message.includes('401') || 
            error.message.includes('403') || 
            error.message.includes('400')
          ))
          options.onError(error as Error, isRetryable)
        }
        
        throw error
      }
    }
    
    // Stop progress tracking and finalize upload
    this.stopProgressTracking(session.id)
    session.status = 'completed'
    
    if (options.onStatusUpdate) {
      options.onStatusUpdate('finalizing', 'Processing uploaded chunks...')
    }
    
    return this.finalizeUpload(session, options)
  }
  
  /**
   * Calculate progressive timeout based on chunk index, total chunks, and file size
   */
  private calculateTimeout(chunkIndex: number, totalChunks: number, fileSize: number): number {
    // Progressive timeout: longer for later chunks and larger files
    const baseTimeout = this.UPLOAD_TIMEOUT
    const progressFactor = 1 + (chunkIndex / totalChunks) * 0.5 // Up to 50% increase
    
    // Scale timeout based on file size (larger files get more time)
    const fileSizeMB = fileSize / (1024 * 1024)
    const fileSizeFactor = Math.min(1 + (fileSizeMB / 100) * this.PROGRESSIVE_TIMEOUT_FACTOR, 3) // Max 3x timeout for very large files
    
    const calculatedTimeout = baseTimeout * progressFactor * fileSizeFactor
    
    return Math.min(Math.max(calculatedTimeout, this.MIN_TIMEOUT), this.MAX_TIMEOUT)
  }

  /**
   * Upload a single chunk with retry logic
   */
  private async uploadChunkWithRetry(
    chunk: UploadChunk,
    session: UploadSession,
    fileSize: number,
    options: {
      niche?: string
      quality?: string
      onProgress?: (progress: number) => void
      onChunkComplete?: (chunkIndex: number, totalChunks: number) => void
      onStatusUpdate?: (status: string, details?: string) => void
      onError?: (error: Error, isRetryable: boolean) => void
    }
  ): Promise<any> {
    let lastError: Error | null = null
    
    for (let attempt = 0; attempt < this.MAX_RETRIES; attempt++) {
      try {
        // Calculate progressive timeout based on chunk index, total chunks, and file size
        const timeout = this.calculateTimeout(chunk.index, session.totalChunks, fileSize)
        
        // Update status with attempt information
        if (options.onStatusUpdate) {
          options.onStatusUpdate('uploading', `Uploading chunk ${chunk.index + 1}/${session.totalChunks} (attempt ${attempt + 1})`)
        }
        
        const result = await this.uploadSingleChunk(chunk, session, timeout, options)
        session.uploadedChunks.add(chunk.index)
        return result
      } catch (error) {
        lastError = error as Error
        console.warn(`Chunk ${chunk.index} upload attempt ${attempt + 1} failed:`, error)
        
        // Use error categorization service to determine if error is retryable
        const errorCategory = errorCategorizationService.categorizeError(error)
        
        // Don't retry non-retryable errors (like authentication failures)
        if (!errorCategory.retryable) {
          throw error
        }
        
        if (attempt < this.MAX_RETRIES - 1) {
          // Use the delay from error categorization or exponential backoff with jitter
          const delay = errorCategory.retryDelay || (this.RETRY_DELAY * Math.pow(2, attempt) + Math.random() * 1000)
          await new Promise(resolve => setTimeout(resolve, Math.min(delay, 30000)))
        }
      }
    }
    
    throw lastError || new Error(`Failed to upload chunk ${chunk.index} after ${this.MAX_RETRIES} attempts`)
  }
  
  /**
   * Upload a single chunk
   */
  private async uploadSingleChunk(
    chunk: UploadChunk,
    session: UploadSession,
    timeout: number,
    options: { niche?: string; quality?: string }
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const formData = new FormData()
      
      formData.append('chunk', chunk.data)
      formData.append('chunkIndex', chunk.index.toString())
      formData.append('totalChunks', session.totalChunks.toString())
      formData.append('sessionId', session.id)
      formData.append('fileName', session.fileName)
      formData.append('target_niche', options.niche || 'general')
      
      // Use the calculated progressive timeout
      xhr.timeout = timeout
      
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText)
            resolve(response)
          } catch (error) {
            reject(new Error('Invalid response format'))
          }
        } else {
          reject(new Error(`Chunk upload failed with status ${xhr.status}`))
        }
      })
      
      xhr.addEventListener('error', () => {
        reject(new Error('Network error during chunk upload'))
      })
      
      xhr.addEventListener('timeout', () => {
        reject(new Error(`Upload timeout after ${Math.round(xhr.timeout/1000)}s. Please check your connection and try again.`))
      })
      
      // Set auth header
      supabase.auth.getSession().then(({ data: { session }, error }) => {
        if (error || !session) {
          reject(new Error('Authentication failed'))
          return
        }
        
        xhr.open('POST', `${process.env.REACT_APP_API_URL || 'http://localhost:8001'}/videos/upload-chunk`)
        xhr.setRequestHeader('Authorization', `Bearer ${session.access_token}`)
        xhr.send(formData)
      }).catch(error => {
        reject(new Error('Authentication failed'))
      })
    })
  }
  
  /**
   * Finalize the upload after all chunks are uploaded
   */
  private async finalizeUpload(
    session: UploadSession,
    options: {
      niche?: string
      quality?: string
      onStatusUpdate?: (status: string, details?: string) => void
      onError?: (error: Error, isRetryable: boolean) => void
    }
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const formData = new FormData()
      
      formData.append('sessionId', session.id)
      formData.append('fileName', session.fileName)
      formData.append('totalChunks', session.totalChunks.toString())
      formData.append('target_niche', options.niche || 'general')
      
      xhr.timeout = 600000 // 10 minutes timeout for finalization (optimized)
      
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText)
            resolve(response)
          } catch (error) {
            reject(new Error('Invalid response format'))
          }
        } else {
          reject(new Error(`Upload finalization failed with status ${xhr.status}`))
        }
      })
      
      xhr.addEventListener('error', () => {
        const error = new Error('Network error during upload finalization')
        console.error('Finalization failed:', error)
        
        // Use error categorization service for better error handling
        const errorCategory = errorCategorizationService.categorizeError(error)
        
        if (options.onError) {
          options.onError(error, errorCategory.retryable)
        }
        
        reject(error)
      })
      
      xhr.addEventListener('timeout', () => {
        const error = new Error('Upload finalization timeout')
        console.error('Finalization timeout:', error)
        
        // Use error categorization service for better error handling
        const errorCategory = errorCategorizationService.categorizeError(error)
        
        if (options.onError) {
          options.onError(error, errorCategory.retryable)
        }
        
        reject(error)
      })
      
      // Set auth header
      supabase.auth.getSession().then(({ data: { session }, error }) => {
        if (error || !session) {
          reject(new Error('Authentication failed'))
          return
        }
        
        xhr.open('POST', `${process.env.REACT_APP_API_URL || 'http://localhost:8001'}/videos/finalize-upload`)
        xhr.setRequestHeader('Authorization', `Bearer ${session.access_token}`)
        xhr.send(formData)
      }).catch(error => {
        reject(new Error('Authentication failed'))
      })
    })
  }
  
  /**
   * Create chunks from file
   */
  private createChunks(file: File, session: UploadSession): UploadChunk[] {
    const chunks: UploadChunk[] = []
    
    for (let i = 0; i < session.totalChunks; i++) {
      const start = i * session.chunkSize
      const end = Math.min(start + session.chunkSize, file.size)
      const data = file.slice(start, end)
      
      chunks.push({
        data,
        start,
        end,
        index: i
      })
    }
    
    return chunks
  }
  
  /**
   * Generate unique session ID based on file properties
   */
  public generateSessionId(file: File): string {
    const fileInfo = `${file.name}-${file.size}-${file.lastModified}`
    // Use TextEncoder to safely encode Unicode characters, then convert to hex
    const encoder = new TextEncoder()
    const data = encoder.encode(fileInfo)
    const hexString = Array.from(data)
      .map(byte => byte.toString(16).padStart(2, '0'))
      .join('')
    return hexString.substring(0, 32)
  }
  
  /**
   * Start progress tracking for a session
   */
  private startProgressTracking(
    session: UploadSession,
    onProgress?: (progress: number) => void,
    optionsOnProgress?: (progress: number) => void
  ): void {
    // Clear existing timer if any
    this.stopProgressTracking(session.id)
    
    const timer = setInterval(() => {
      const now = Date.now()
      const elapsedTime = now - session.startTime
      const progress = Math.round((session.uploadedChunks.size / session.totalChunks) * 100)
      
      // Calculate upload speed (bytes per second)
      if (elapsedTime > 0) {
        session.uploadSpeed = session.bytesUploaded / (elapsedTime / 1000)
        
        // Calculate estimated time remaining
        const remainingBytes = session.fileSize - session.bytesUploaded
        if (session.uploadSpeed > 0) {
          session.estimatedTimeRemaining = remainingBytes / session.uploadSpeed
        }
      }
      
      // Update progress callbacks
      if (onProgress) {
        onProgress(progress)
      }
      if (optionsOnProgress) {
        optionsOnProgress(progress)
      }
      
      // Save session state
      this.saveSessionsToStorage()
    }, this.PROGRESS_UPDATE_INTERVAL)
    
    this.progressTimers.set(session.id, timer)
  }
  
  /**
   * Stop progress tracking for a session
   */
  private stopProgressTracking(sessionId: string): void {
    const timer = this.progressTimers.get(sessionId)
    if (timer) {
      clearInterval(timer)
      this.progressTimers.delete(sessionId)
    }
  }
  
  /**
   * Save sessions to localStorage
   */
  private saveSessionsToStorage(): void {
    try {
      const sessionsData = Array.from(this.sessions.entries()).map(([id, session]) => ({
        id,
        ...session,
        uploadedChunks: Array.from(session.uploadedChunks)
      }))
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(sessionsData))
    } catch (error) {
      console.warn('Failed to save upload sessions to localStorage:', error)
    }
  }
  
  /**
   * Load sessions from localStorage
   */
  private loadSessionsFromStorage(): void {
    try {
      // Try new storage key first, fallback to old key for migration
      let stored = localStorage.getItem(this.STORAGE_KEY)
      if (!stored) {
        stored = localStorage.getItem('resumable_upload_sessions')
        if (stored) {
          // Migrate old data to new format
          console.log('Migrating upload sessions to new format')
        }
      }
      
      if (stored) {
        const sessionsData = JSON.parse(stored)
        sessionsData.forEach((sessionData: any) => {
          const session: UploadSession = {
            ...sessionData,
            uploadedChunks: new Set(sessionData.uploadedChunks),
            // Provide defaults for new fields if missing (migration)
            startTime: sessionData.startTime || sessionData.lastActivity || Date.now(),
            uploadSpeed: sessionData.uploadSpeed || 0,
            estimatedTimeRemaining: sessionData.estimatedTimeRemaining || 0,
            bytesUploaded: sessionData.bytesUploaded || (sessionData.uploadedChunks?.length || 0) * sessionData.chunkSize,
            status: sessionData.status || 'pending',
            errorCount: sessionData.errorCount || 0,
            lastError: sessionData.lastError
          }
          this.sessions.set(session.id, session)
        })
        
        // Save migrated data if we used old key
        if (localStorage.getItem('resumable_upload_sessions') && !localStorage.getItem(this.STORAGE_KEY)) {
          this.saveSessionsToStorage()
          localStorage.removeItem('resumable_upload_sessions')
        }
      }
    } catch (error) {
      console.warn('Failed to load upload sessions from localStorage:', error)
    }
  }
  
  /**
   * Clean up expired sessions
   */
  private cleanupExpiredSessions(): void {
    const now = Date.now()
    const expiredSessions: string[] = []
    
    this.sessions.forEach((session, id) => {
      if (now - session.lastActivity > this.SESSION_TIMEOUT) {
        expiredSessions.push(id)
      }
    })
    
    expiredSessions.forEach(id => {
      this.sessions.delete(id)
    })
    
    if (expiredSessions.length > 0) {
      this.saveSessionsToStorage()
      console.log(`Cleaned up ${expiredSessions.length} expired upload sessions`)
    }
  }
  
  /**
   * Get active upload sessions
   */
  getActiveSessions(): UploadSession[] {
    return Array.from(this.sessions.values())
  }
  
  /**
   * Cancel an upload session
   */
  cancelUpload(sessionId: string): void {
    this.stopProgressTracking(sessionId)
    this.sessions.delete(sessionId)
    this.saveSessionsToStorage()
  }
  
  /**
   * Clear all upload sessions
   */
  clearAllSessions(): void {
    // Stop all progress tracking
    this.progressTimers.forEach((timer, sessionId) => {
      this.stopProgressTracking(sessionId)
    })
    
    this.sessions.clear()
    this.saveSessionsToStorage()
  }
  
  /**
   * Get detailed session information including progress metrics
   */
  getSessionDetails(sessionId: string): UploadSession | null {
    return this.sessions.get(sessionId) || null
  }
  
  /**
   * Pause an upload session
   */
  pauseUpload(sessionId: string): void {
    const session = this.sessions.get(sessionId)
    if (session) {
      session.status = 'paused'
      this.stopProgressTracking(sessionId)
      this.saveSessionsToStorage()
    }
  }
  
  /**
   * Resume a paused upload session
   */
  resumeUpload(sessionId: string): void {
    const session = this.sessions.get(sessionId)
    if (session && session.status === 'paused') {
      session.status = 'uploading'
      this.saveSessionsToStorage()
    }
  }
}

export const resumableUploadService = new ResumableUploadService()
export type { UploadSession }