import { ErrorCategorizationService, ErrorRecoveryAction, CategorizedError } from './errorCategorization'
import { toast } from 'sonner'

export interface RetryOptions {
  maxRetries?: number
  baseDelay?: number
  exponentialBackoff?: boolean
  jitter?: boolean
  onRetry?: (error: CategorizedError, retryCount: number) => void
  onMaxRetriesReached?: (error: CategorizedError) => void
  shouldRetry?: (error: CategorizedError) => boolean
}

export interface RetryResult<T> {
  success: boolean
  data?: T
  error?: CategorizedError
  retryCount: number
  totalDuration: number
}

export class RetryService {
  private errorCategorization = new ErrorCategorizationService()

  /**
   * Execute a function with automatic retry logic based on error categorization
   */
  async executeWithRetry<T>(
    operation: () => Promise<T>,
    context?: {
      fileName?: string
      fileSize?: number
      operation?: string
    },
    options: RetryOptions = {}
  ): Promise<RetryResult<T>> {
    const startTime = Date.now()
    let lastError: CategorizedError | null = null
    let retryCount = 0

    while (true) {
      try {
        const result = await operation()
        return {
          success: true,
          data: result,
          retryCount,
          totalDuration: Date.now() - startTime
        }
      } catch (error) {
        const categorizedError = this.errorCategorization.categorizeError(
          error,
          undefined,
          { ...context, retryCount }
        )
        lastError = categorizedError

        // Check if we should retry
        const shouldRetry = this.shouldRetryError(categorizedError, retryCount, options)
        
        if (!shouldRetry) {
          // Handle recovery action
          await this.handleRecoveryAction(categorizedError)
          
          if (options.onMaxRetriesReached) {
            options.onMaxRetriesReached(categorizedError)
          }
          
          return {
            success: false,
            error: categorizedError,
            retryCount,
            totalDuration: Date.now() - startTime
          }
        }

        retryCount++
        
        // Notify about retry
        if (options.onRetry) {
          options.onRetry(categorizedError, retryCount)
        }

        // Calculate delay
        const retryConfig = this.errorCategorization.getRetryConfig(error)
        const baseDelay = options.baseDelay || retryConfig.baseDelay
        const delay = options.exponentialBackoff !== false
          ? this.errorCategorization.calculateRetryDelay(baseDelay, retryCount - 1, options.jitter)
          : baseDelay

        // Show retry notification
        this.showRetryNotification(categorizedError, retryCount, delay)

        // Wait before retry
        await this.delay(delay)
      }
    }
  }

  /**
   * Determine if an error should be retried
   */
  private shouldRetryError(
    error: CategorizedError,
    retryCount: number,
    options: RetryOptions
  ): boolean {
    // Custom retry logic takes precedence
    if (options.shouldRetry) {
      return options.shouldRetry(error)
    }

    // Check if error is retryable
    if (!error.retryable) {
      return false
    }

    // Check retry limits
    const retryConfig = this.errorCategorization.getRetryConfig(error)
    const maxRetries = options.maxRetries ?? retryConfig.maxRetries
    
    return retryCount < maxRetries
  }

  /**
   * Handle recovery actions based on error type
   */
  private async handleRecoveryAction(error: CategorizedError): Promise<void> {
    switch (error.recoveryAction) {
      case ErrorRecoveryAction.REFRESH_AUTH:
        // Trigger auth refresh - this should be handled by the auth context
        window.dispatchEvent(new CustomEvent('auth:refresh-required'))
        break
        
      case ErrorRecoveryAction.CLEAR_CACHE:
        // Clear relevant caches
        if ('caches' in window) {
          try {
            const cacheNames = await caches.keys()
            await Promise.all(cacheNames.map(name => caches.delete(name)))
          } catch (e) {
            console.warn('Failed to clear caches:', e)
          }
        }
        break
        
      case ErrorRecoveryAction.CHECK_CONNECTION:
        // Check network connectivity
        if (!navigator.onLine) {
          toast.error('No internet connection detected. Please check your network.')
        }
        break
        
      case ErrorRecoveryAction.CONTACT_SUPPORT:
        // Show support contact information
        toast.error(
          'Please contact support for assistance.',
          {
            duration: 10000,
            action: {
              label: 'Contact Support',
              onClick: () => window.open('mailto:support@example.com', '_blank')
            }
          }
        )
        break
        
      case ErrorRecoveryAction.REDUCE_FILE_SIZE:
        toast.error(
          'File is too large. Please reduce the file size and try again.',
          { duration: 8000 }
        )
        break
        
      case ErrorRecoveryAction.CHANGE_FORMAT:
        toast.error(
          'File format not supported. Please convert to MP4, AVI, MOV, or WMV.',
          { duration: 8000 }
        )
        break
    }
  }

  /**
   * Show retry notification to user
   */
  private showRetryNotification(
    error: CategorizedError,
    retryCount: number,
    delay: number
  ): void {
    const delaySeconds = Math.round(delay / 1000)
    
    toast.info(
      `Retrying in ${delaySeconds}s... (Attempt ${retryCount})`,
      {
        duration: Math.min(delay, 5000),
        description: error.userMessage
      }
    )
  }

  /**
   * Utility method to create a delay
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * Create a retry wrapper for upload operations
   */
  createUploadRetryWrapper<T>(
    uploadFn: () => Promise<T>,
    fileName?: string,
    fileSize?: number
  ) {
    return this.executeWithRetry(
      uploadFn,
      {
        fileName,
        fileSize,
        operation: 'upload'
      },
      {
        onRetry: (error, retryCount) => {
          console.log(`Upload retry ${retryCount} for ${fileName}:`, error.message)
        },
        onMaxRetriesReached: (error) => {
          toast.error(
            `Upload failed for ${fileName}: ${error.userMessage}`,
            { duration: 8000 }
          )
        }
      }
    )
  }

  /**
   * Create a retry wrapper for API operations
   */
  createApiRetryWrapper<T>(
    apiFn: () => Promise<T>,
    operation: string
  ) {
    return this.executeWithRetry(
      apiFn,
      { operation },
      {
        onRetry: (error, retryCount) => {
          console.log(`API retry ${retryCount} for ${operation}:`, error.message)
        },
        onMaxRetriesReached: (error) => {
          toast.error(
            `${operation} failed: ${error.userMessage}`,
            { duration: 6000 }
          )
        }
      }
    )
  }
}

// Export singleton instance
export const retryService = new RetryService()