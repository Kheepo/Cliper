import { supabase } from '../lib/supabase'
import { APIError, AuthError, NetworkError, ValidationError } from './api'
import { errorCategorizationService, ErrorCategory } from './errorCategorization'

const API_BASE_URL = 'http://localhost:8001/api'
const CHUNK_SIZE = 5 * 1024 * 1024 // 5MB chunks
const MAX_RETRIES = 3
const STORAGE_PREFIX = 'cliper_upload_'
const SESSION_STORAGE_VERSION = '1.0'
const MAX_CONCURRENT_CHUNKS = 3
const SESSION_HEARTBEAT_INTERVAL = 30000 // 30 seconds
const MAX_SESSION_AGE = 7 * 24 * 60 * 60 * 1000 // 7 days
const SESSION_RESUME_TIMEOUT = 24 * 60 * 60 * 1000 // 24 hours

export interface ChunkedUploadOptions {
  niche?: string
  quality?: string
  onProgress?: (progress: number) => void
  onChunkProgress?: (chunkIndex: number, totalChunks: number) => void
}

export interface UploadSession {
  id: string
  fileName: string
  fileSize: number
  fileHash?: string
  totalChunks: number
  uploadedChunks: Set<number>
  failedChunks: Set<number>
  chunkSize: number
  createdAt: number
  lastActivity: number
  lastHeartbeat: number
  version: string
  retryCount: number
  options: ChunkedUploadOptions
  serverSessionInitialized: boolean
}

export interface ChunkUploadResult {
  chunkIndex: number
  success: boolean
  error?: string
}

class ChunkedUploadService {
  private activeSessions = new Map<string, UploadSession>()
  private uploadControllers = new Map<string, AbortController>()
  private heartbeatIntervals = new Map<string, NodeJS.Timeout>()
  private storageQuotaWarned = false

  constructor() {
    this.loadSessionsFromStorage()
    this.cleanupOldSessions()
  }

  /**
   * Start a new chunked upload or resume an existing one
   */
  async startUpload(
    file: File,
    options: ChunkedUploadOptions = {}
  ): Promise<{ sessionId: string; isResume: boolean }> {
    // Validate file
    this.validateFile(file)
    
    const sessionId = this.generateSessionId(file)
    const existingSession = this.getSession(sessionId)
    const fileHash = await this.generateFileHash(file)

    if (existingSession && await this.canResumeSession(existingSession, file, fileHash)) {
      console.log(`Resuming upload session: ${sessionId} (${existingSession.uploadedChunks.size}/${existingSession.totalChunks} chunks completed)`)
      
      // Update session with new options and reset failed chunks
      existingSession.lastActivity = Date.now()
      existingSession.lastHeartbeat = Date.now()
      existingSession.options = { ...existingSession.options, ...options }
      existingSession.failedChunks.clear()
      existingSession.retryCount = 0
      
      this.saveSessionToStorage(existingSession)
      
      return { sessionId, isResume: true }
    }

    // Cleanup any existing session with same ID
    if (existingSession) {
      this.cleanupSession(sessionId)
    }

    // Create new session
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE)
    const now = Date.now()
    const session: UploadSession = {
      id: sessionId,
      fileName: file.name,
      fileSize: file.size,
      fileHash,
      totalChunks,
      uploadedChunks: new Set(),
      failedChunks: new Set(),
      chunkSize: CHUNK_SIZE,
      createdAt: now,
      lastActivity: now,
      lastHeartbeat: now,
      version: SESSION_STORAGE_VERSION,
      retryCount: 0,
      options,
      serverSessionInitialized: false
    }

    this.activeSessions.set(sessionId, session)
    this.saveSessionToStorage(session)
    console.log(`Started new upload session: ${sessionId} (${totalChunks} chunks, ${(file.size / 1024 / 1024).toFixed(2)}MB)`)
    return { sessionId, isResume: false }
  }

  /**
   * Upload file using chunked upload with resume capability
   */
  async uploadFile(
    file: File,
    options: ChunkedUploadOptions = {}
  ): Promise<{ job_id: string }> {
    const { sessionId, isResume } = await this.startUpload(file, options)
    const session = this.getSession(sessionId)!

    // Validate session integrity
    if (!await this.validateSessionIntegrity(session, file)) {
      throw new ValidationError('Session validation failed - file mismatch detected')
    }

    try {
      // Create abort controller for this upload
      const controller = new AbortController()
      this.uploadControllers.set(sessionId, controller)

      // Initialize upload session on server if not already done
      if (!session.serverSessionInitialized) {
        await this.initializeServerSession(sessionId, file, options)
        session.serverSessionInitialized = true
        this.saveSessionToStorage(session)
      }

      // Upload chunks with improved error handling
      const results = await this.uploadChunks(file, session, controller.signal)
      
      // Finalize upload
      const finalResult = await this.finalizeUpload(sessionId)
      
      // Cleanup
      this.cleanupSession(sessionId)
      
      console.log(`Upload completed successfully for session ${sessionId}`)
      return finalResult
    } catch (error) {
      session.retryCount++
      session.lastActivity = Date.now()
      
      if (error instanceof AuthError) {
        console.warn(`Auth error for session ${sessionId}, session preserved for retry`)
        session.serverSessionInitialized = false // Reset server session flag
        this.saveSessionToStorage(session)
        throw error
      }
      
      if (error instanceof ValidationError) {
        console.error(`Validation error for session ${sessionId}, cleaning up`)
        this.cleanupSession(sessionId)
        throw error
      }
      
      // For network/server errors, preserve session for retry
      if (session.retryCount >= MAX_RETRIES) {
        console.error(`Max retries exceeded for session ${sessionId}, cleaning up`)
        this.cleanupSession(sessionId)
        throw new APIError(`Upload failed after ${MAX_RETRIES} attempts: ${error.message}`)
      }
      
      console.warn(`Upload error for session ${sessionId} (attempt ${session.retryCount}/${MAX_RETRIES}):`, error)
      this.saveSessionToStorage(session)
      throw error
    }
  }

  /**
   * Cancel an active upload
   */
  cancelUpload(sessionId: string): void {
    const controller = this.uploadControllers.get(sessionId)
    if (controller) {
      controller.abort()
      this.uploadControllers.delete(sessionId)
    }
    
    this.cleanupSession(sessionId)
    console.log(`Upload cancelled: ${sessionId}`)
  }

  /**
   * Get upload progress for a session
   */
  getProgress(sessionId: string): number {
    const session = this.getSession(sessionId)
    if (!session) return 0
    
    return (session.uploadedChunks.size / session.totalChunks) * 100
  }

  /**
   * Get all active sessions
   */
  getActiveSessions(): UploadSession[] {
    return Array.from(this.activeSessions.values())
  }

  /**
   * Get a specific session by ID
   */
  getSession(sessionId: string): UploadSession | null {
    return this.activeSessions.get(sessionId) || null
  }

  /**
   * Resume a paused upload
   */
  async resumeUpload(sessionId: string, file: File): Promise<{ job_id: string }> {
    const session = this.getSession(sessionId)
    if (!session) {
      throw new ValidationError('Upload session not found')
    }

    if (!this.canResumeSession(session, file)) {
      throw new ValidationError('Cannot resume upload - file mismatch')
    }

    console.log(`Resuming upload: ${sessionId}`)
    return this.uploadFile(file, session.options)
  }

  private async initializeServerSession(
    sessionId: string,
    file: File,
    options: ChunkedUploadOptions
  ): Promise<void> {
    try {
      const { data: { session }, error } = await supabase.auth.getSession()
      if (error || !session) {
        throw new AuthError('Authentication required')
      }

      const response = await fetch(`${API_BASE_URL}/videos/upload/init`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: sessionId,
          filename: file.name,
          file_size: file.size,
          total_chunks: Math.ceil(file.size / CHUNK_SIZE),
          target_niche: options.niche || 'general'
        })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: 'Server error' }))
        
        // Use error categorization service
        const errorMessage = errorData.message || 'Failed to initialize upload'
        const context = { operation: 'initializeServerSession', sessionId }
        
        const categorizedError = errorCategorizationService.categorizeError(errorMessage, response.status, context)
        
        // Create appropriate error based on categorization
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
            errorInstance = new APIError(categorizedError.userMessage, response.status)
        }
        
        throw errorInstance
      }
    } catch (error) {
      if (error instanceof APIError) throw error
      throw new APIError(`Upload initialization failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  private async uploadChunks(
    file: File,
    session: UploadSession,
    signal: AbortSignal
  ): Promise<ChunkUploadResult[]> {
    const results: ChunkUploadResult[] = []
    const pendingChunks = this.getPendingChunks(session)
    
    console.log(`Uploading ${pendingChunks.length} pending chunks for session ${session.id}`)

    if (pendingChunks.length === 0) {
      console.log(`All chunks already uploaded for session ${session.id}`)
      return results
    }

    // Upload chunks in controlled batches
    const batchSize = Math.min(MAX_CONCURRENT_CHUNKS, pendingChunks.length)
    let currentIndex = 0
    const errors: Array<{ chunkIndex: number; error: Error }> = []

    while (currentIndex < pendingChunks.length) {
      const batch = pendingChunks.slice(currentIndex, currentIndex + batchSize)
      const batchPromises = batch.map(async (chunkIndex) => {
        try {
          await this.uploadChunk(file, session, chunkIndex, signal)
          
          // Mark chunk as completed
          session.uploadedChunks.add(chunkIndex)
          session.failedChunks.delete(chunkIndex)
          results.push({ chunkIndex, success: true })
          
          // Update progress
          const progress = (session.uploadedChunks.size / session.totalChunks) * 100
          session.options.onProgress?.(progress)
          session.options.onChunkProgress?.(chunkIndex, session.totalChunks)
          
        } catch (error) {
          console.error(`Failed to upload chunk ${chunkIndex}:`, error)
          session.failedChunks.add(chunkIndex)
          results.push({ 
            chunkIndex, 
            success: false, 
            error: error instanceof Error ? error.message : 'Unknown error' 
          })
          errors.push({ chunkIndex, error: error as Error })
          
          // For non-retryable errors, stop immediately
          if (error instanceof AuthError || error instanceof ValidationError) {
            throw error
          }
        }
      })

      await Promise.allSettled(batchPromises)
      currentIndex += batchSize
      
      // Update session progress
      session.lastActivity = Date.now()
      session.lastHeartbeat = Date.now()
      this.saveSessionToStorage(session)
      
      // Check if upload was cancelled
      if (signal.aborted) {
        throw new APIError('Upload cancelled', 0, 'CANCELLED', false)
      }
    }

    // Handle any failed chunks
    if (session.failedChunks.size > 0) {
      const failedChunksList = Array.from(session.failedChunks)
      console.warn(`${failedChunksList.length} chunks failed for session ${session.id}:`, failedChunksList)
      
      // If too many chunks failed, throw error
      if (session.failedChunks.size > session.totalChunks * 0.1) { // More than 10% failed
        throw new APIError(`Too many chunks failed (${session.failedChunks.size}/${session.totalChunks})`)
      }
      
      // Retry failed chunks once
      console.log(`Retrying ${failedChunksList.length} failed chunks...`)
      session.failedChunks.clear()
      const retryResults = await this.uploadChunks(file, session, signal)
      results.push(...retryResults)
    }

    return results
  }

  private async uploadChunk(
    file: File,
    session: UploadSession,
    chunkIndex: number,
    signal: AbortSignal,
    retryCount = 0
  ): Promise<void> {
    const start = chunkIndex * session.chunkSize
    const end = Math.min(start + session.chunkSize, file.size)
    const chunk = file.slice(start, end)
    
    try {
      const { data: { session: authSession }, error } = await supabase.auth.getSession()
      if (error || !authSession) {
        throw new AuthError('Authentication required')
      }

      const formData = new FormData()
      formData.append('chunk', chunk)
      formData.append('chunk_index', chunkIndex.toString())
      formData.append('session_id', session.id)

      const response = await fetch(`${API_BASE_URL}/videos/upload/chunk`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authSession.access_token}`
        },
        body: formData,
        signal
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: 'Server error' }))
        
        // Use error categorization service
        const errorMessage = errorData.message || `Chunk ${chunkIndex} upload failed`
        const context = { operation: 'uploadChunk', chunkIndex, sessionId: session.id, retryCount }
        
        const categorizedError = errorCategorizationService.categorizeError(errorMessage, response.status, context)
        
        // Retry logic based on error categorization
        if (categorizedError.retryable && retryCount < MAX_RETRIES) {
          const retryStrategy = errorCategorizationService.getRetryStrategy(categorizedError)
          const delay = Math.min(retryStrategy.baseDelay * Math.pow(retryStrategy.backoffMultiplier, retryCount), retryStrategy.maxDelay)
          console.log(`Retrying chunk ${chunkIndex} (${categorizedError.category}) in ${delay}ms...`)
          await new Promise(resolve => setTimeout(resolve, delay))
          return this.uploadChunk(file, session, chunkIndex, signal, retryCount + 1)
        }
        
        // Create appropriate error based on categorization
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
            errorInstance = new APIError(
              categorizedError.userMessage,
              response.status,
              'CHUNK_UPLOAD_ERROR',
              categorizedError.retryable
            )
        }
        
        throw errorInstance
      }
    } catch (error) {
      if (error instanceof APIError || error instanceof AuthError || error instanceof ValidationError || error instanceof NetworkError) {
        throw error
      }
      
      if (signal.aborted) throw new APIError('Upload cancelled', 0, 'CANCELLED', false)
      
      // Use error categorization service for network errors
      const errorMessage = error instanceof Error ? error.message : 'Unknown network error'
      const context = { operation: 'uploadChunk', chunkIndex, sessionId: session.id, retryCount }
      
      const categorizedError = errorCategorizationService.categorizeError(errorMessage, undefined, context)
      
      // Retry logic based on error categorization
      if (categorizedError.retryable && retryCount < MAX_RETRIES) {
        const retryStrategy = errorCategorizationService.getRetryStrategy(categorizedError)
        const delay = Math.min(retryStrategy.baseDelay * Math.pow(retryStrategy.backoffMultiplier, retryCount), retryStrategy.maxDelay)
        console.log(`Network error for chunk ${chunkIndex} (${categorizedError.category}), retrying in ${delay}ms...`)
        await new Promise(resolve => setTimeout(resolve, delay))
        return this.uploadChunk(file, session, chunkIndex, signal, retryCount + 1)
      }
      
      throw new NetworkError(categorizedError.userMessage)
    }
  }

  private async finalizeUpload(sessionId: string): Promise<{ job_id: string }> {
    try {
      const { data: { session }, error } = await supabase.auth.getSession()
      if (error || !session) {
        throw new AuthError('Authentication required')
      }

      const response = await fetch(`${API_BASE_URL}/videos/upload/finalize`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ session_id: sessionId })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: 'Server error' }))
        
        // Use error categorization service
        const errorMessage = errorData.message || 'Failed to finalize upload'
        const context = { operation: 'finalizeUpload', sessionId }
        
        const categorizedError = errorCategorizationService.categorizeError(errorMessage, response.status, context)
        
        // Create appropriate error based on categorization
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
            errorInstance = new APIError(categorizedError.userMessage, response.status)
        }
        
        throw errorInstance
      }

      return response.json()
    } catch (error) {
      if (error instanceof APIError || error instanceof AuthError || error instanceof ValidationError || error instanceof NetworkError) {
        throw error
      }
      
      // Use error categorization service for unknown errors
      const errorMessage = error instanceof Error ? error.message : 'Unknown error during upload finalization'
      const context = { operation: 'finalizeUpload', sessionId }
      
      const categorizedError = errorCategorizationService.categorizeError(errorMessage, undefined, context)
      throw new APIError(categorizedError.userMessage)
    }
  }

  private generateSessionId(file: File): string {
    const timestamp = file.lastModified || Date.now()
    const hash = this.simpleHash(`${file.name}_${file.size}_${timestamp}`)
    return `upload_${hash}_${timestamp}`
  }

  private simpleHash(str: string): string {
    let hash = 0
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(36)
  }

  private async generateFileHash(file: File): Promise<string> {
    try {
      // For large files, only hash the first and last chunks for performance
      const sampleSize = Math.min(file.size, 1024 * 1024) // 1MB sample
      const firstChunk = file.slice(0, sampleSize / 2)
      const lastChunk = file.slice(file.size - sampleSize / 2)
      
      const buffer1 = await firstChunk.arrayBuffer()
      const buffer2 = await lastChunk.arrayBuffer()
      
      const hashBuffer = await crypto.subtle.digest('SHA-256', 
        new Uint8Array([...new Uint8Array(buffer1), ...new Uint8Array(buffer2)])
      )
      
      return Array.from(new Uint8Array(hashBuffer))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('')
    } catch (error) {
      console.warn('Failed to generate file hash:', error)
      return `fallback_${file.name}_${file.size}_${file.lastModified}`
    }
  }

  private validateFile(file: File): void {
    if (!file) {
      throw new ValidationError('No file provided')
    }
    
    if (file.size === 0) {
      throw new ValidationError('File is empty')
    }
    
    if (file.size > 10 * 1024 * 1024 * 1024) { // 10GB limit
      throw new ValidationError('File size exceeds maximum limit (10GB)')
    }
    
    // Check file type
    const allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm']
    if (!allowedTypes.includes(file.type)) {
      console.warn(`File type ${file.type} may not be supported`)
    }
  }

  private async validateSessionIntegrity(session: UploadSession, file: File): Promise<boolean> {
    try {
      // Basic validation
      if (session.fileName !== file.name || session.fileSize !== file.size) {
        return false
      }
      
      // Hash validation if available
      if (session.fileHash) {
        const currentHash = await this.generateFileHash(file)
        return session.fileHash === currentHash
      }
      
      return true
     } catch (error) {
       console.error('Session integrity validation failed:', error)
       return false
     }
   }



   private async canResumeSession(session: UploadSession, file: File, fileHash?: string): Promise<boolean> {
    const isBasicMatch = session.fileName === file.name &&
                        session.fileSize === file.size &&
                        Date.now() - session.lastActivity < SESSION_RESUME_TIMEOUT
    
    if (!isBasicMatch) return false
    
    // Additional hash verification if available
    if (session.fileHash && fileHash) {
      return session.fileHash === fileHash
    }
    
    return true
  }

  private getPendingChunks(session: UploadSession): number[] {
    const pending = []
    for (let i = 0; i < session.totalChunks; i++) {
      if (!session.uploadedChunks.has(i)) {
        pending.push(i)
      }
    }
    return pending
  }

  // Removed private getSession method - using public one instead

  private saveSessionToStorage(session: UploadSession): void {
    try {
      // Optimize storage by only saving essential data
      const sessionData = {
        id: session.id,
        fileName: session.fileName,
        fileSize: session.fileSize,
        fileHash: session.fileHash,
        totalChunks: session.totalChunks,
        chunkSize: session.chunkSize,
        uploadedChunks: Array.from(session.uploadedChunks),
        failedChunks: Array.from(session.failedChunks),
        createdAt: session.createdAt,
        lastActivity: session.lastActivity,
        lastHeartbeat: session.lastHeartbeat,
        version: session.version,
        retryCount: session.retryCount,
        options: {
          niche: session.options.niche,
          quality: session.options.quality
          // Exclude callback functions from storage
        },
        serverSessionInitialized: session.serverSessionInitialized
      }
      
      // Compress session data for large uploads
      const serializedData = JSON.stringify(sessionData)
      if (serializedData.length > 50000) { // 50KB threshold
        console.warn(`Large session data (${Math.round(serializedData.length / 1024)}KB) for session ${session.id}`)
      }
      
      localStorage.setItem(`${STORAGE_PREFIX}${session.id}`, serializedData)
      
      // Update storage usage tracking
      this.updateStorageUsage()
      
    } catch (error) {
      console.warn('Failed to save session to storage:', error)
      if (!this.storageQuotaWarned && error instanceof Error && error.name === 'QuotaExceededError') {
        this.storageQuotaWarned = true
        console.error('Local storage quota exceeded. Attempting cleanup...')
        this.performEmergencyCleanup()
        
        // Try saving again after cleanup
        try {
          const minimalData = {
            id: session.id,
            fileName: session.fileName,
            fileSize: session.fileSize,
            uploadedChunks: Array.from(session.uploadedChunks),
            lastActivity: session.lastActivity
          }
          localStorage.setItem(`${STORAGE_PREFIX}${session.id}`, JSON.stringify(minimalData))
        } catch (retryError) {
          console.error('Failed to save even minimal session data:', retryError)
        }
      }
    }
  }

  private loadSessionsFromStorage(): void {
    try {
      const loadedSessions: UploadSession[] = []
      
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key?.startsWith(STORAGE_PREFIX)) {
          try {
            const sessionData = JSON.parse(localStorage.getItem(key)!)
            
            // Validate session data structure
            if (!sessionData.id || !sessionData.fileName || !sessionData.fileSize) {
              console.warn(`Invalid session data for key ${key}, removing...`)
              localStorage.removeItem(key)
              continue
            }
            
            // Check if session is too old
            const now = Date.now()
            if (sessionData.lastActivity && now - sessionData.lastActivity > MAX_SESSION_AGE) {
              console.log(`Removing expired session: ${sessionData.id}`)
              localStorage.removeItem(key)
              continue
            }
            
            // Reconstruct session with proper defaults
            const session: UploadSession = {
              id: sessionData.id,
              fileName: sessionData.fileName,
              fileSize: sessionData.fileSize,
              fileHash: sessionData.fileHash || '',
              totalChunks: sessionData.totalChunks || Math.ceil(sessionData.fileSize / CHUNK_SIZE),
              chunkSize: sessionData.chunkSize || CHUNK_SIZE,
              uploadedChunks: new Set(sessionData.uploadedChunks || []),
              failedChunks: new Set(sessionData.failedChunks || []),
              createdAt: sessionData.createdAt || now,
              lastActivity: sessionData.lastActivity || now,
              lastHeartbeat: sessionData.lastHeartbeat || now,
              version: sessionData.version || SESSION_STORAGE_VERSION,
              retryCount: sessionData.retryCount || 0,
              options: {
                niche: sessionData.options?.niche,
                quality: sessionData.options?.quality,
                // Callbacks will be set when upload resumes
                onProgress: undefined,
                onChunkProgress: undefined
              },
              serverSessionInitialized: sessionData.serverSessionInitialized || false
            }
            
            loadedSessions.push(session)
            
          } catch (parseError) {
            console.warn(`Failed to parse session data for key ${key}:`, parseError)
            localStorage.removeItem(key)
          }
        }
      }
      
      // Sort sessions by last activity (most recent first)
      loadedSessions.sort((a, b) => b.lastActivity - a.lastActivity)
      
      // Load sessions into memory
      for (const session of loadedSessions) {
        this.activeSessions.set(session.id, session)
        console.log(`Loaded session: ${session.id} (${session.uploadedChunks.size}/${session.totalChunks} chunks completed)`)
      }
      
      console.log(`Loaded ${loadedSessions.length} upload sessions from storage`)
      
    } catch (error) {
      console.warn('Failed to load sessions from storage:', error)
    }
  }

  private cleanupSession(sessionId: string): void {
    this.activeSessions.delete(sessionId)
    this.uploadControllers.delete(sessionId)
    
    // Clear heartbeat interval
    const heartbeatInterval = this.heartbeatIntervals.get(sessionId)
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
      this.heartbeatIntervals.delete(sessionId)
    }
    
    try {
      localStorage.removeItem(`${STORAGE_PREFIX}${sessionId}`)
    } catch (error) {
      console.warn('Failed to remove session from storage:', error)
    }
  }

  private cleanupOldSessions(): void {
    const now = Date.now()
    
    // Cleanup old sessions from memory
    for (const [sessionId, session] of this.activeSessions.entries()) {
      if (now - session.lastActivity > MAX_SESSION_AGE) {
        console.log(`Cleaning up old session: ${sessionId}`)
        this.cleanupSession(sessionId)
      }
    }
    
    // Also cleanup old sessions from localStorage that weren't loaded into memory
    try {
      const keysToRemove: string[] = []
      
      // First, collect all keys that need to be removed
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key?.startsWith(STORAGE_PREFIX)) {
          try {
            const sessionData = JSON.parse(localStorage.getItem(key)!)
            if (sessionData.lastActivity && now - sessionData.lastActivity > MAX_SESSION_AGE) {
              keysToRemove.push(key)
            }
          } catch (parseError) {
            // If we can't parse the session data, remove it
            keysToRemove.push(key)
          }
        }
      }
      
      // Then remove all the collected keys
      for (const key of keysToRemove) {
        console.log(`Cleaning up old session from storage: ${key}`)
        localStorage.removeItem(key)
      }
    } catch (error) {
      console.warn('Failed to cleanup old sessions from storage:', error)
    }
  }

  private updateStorageUsage(): void {
    try {
      let totalSize = 0
      let sessionCount = 0
      
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key?.startsWith(STORAGE_PREFIX)) {
          const value = localStorage.getItem(key)
          if (value) {
            totalSize += value.length
            sessionCount++
          }
        }
      }
      
      // Log storage usage if significant
      if (totalSize > 100000) { // 100KB threshold
        console.log(`Upload session storage: ${Math.round(totalSize / 1024)}KB across ${sessionCount} sessions`)
      }
      
      // Warn if approaching storage limits
      if (totalSize > 2000000) { // 2MB threshold
        console.warn('Upload session storage usage is high. Consider cleaning up old sessions.')
        this.performEmergencyCleanup()
      }
      
    } catch (error) {
      console.warn('Failed to calculate storage usage:', error)
    }
  }

  private performEmergencyCleanup(): void {
    try {
      const now = Date.now()
      const sessionsToRemove: string[] = []
      
      // Find sessions older than 1 hour for emergency cleanup
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key?.startsWith(STORAGE_PREFIX)) {
          try {
            const sessionData = JSON.parse(localStorage.getItem(key)!)
            if (sessionData.lastActivity && now - sessionData.lastActivity > 3600000) { // 1 hour
              sessionsToRemove.push(key)
            }
          } catch (error) {
            // Remove corrupted data
            sessionsToRemove.push(key)
          }
        }
      }
      
      // Remove old sessions
      for (const key of sessionsToRemove) {
        localStorage.removeItem(key)
      }
      
      console.log(`Emergency cleanup removed ${sessionsToRemove.length} old sessions`)
      
    } catch (error) {
      console.error('Emergency cleanup failed:', error)
    }
  }
}

// Export class and singleton instance
export { ChunkedUploadService }
export const chunkedUploadService = new ChunkedUploadService()