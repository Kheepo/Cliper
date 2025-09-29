export enum ErrorCategory {
  NETWORK = 'network',
  AUTHENTICATION = 'authentication',
  FILE_FORMAT = 'file_format',
  FILE_SIZE = 'file_size',
  SERVER = 'server',
  RATE_LIMIT = 'rate_limit',
  PERMISSION = 'permission',
  TIMEOUT = 'timeout',
  UPLOAD_FAILED = 'upload_failed',
  PROCESSING_FAILED = 'processing_failed',
  STORAGE_FULL = 'storage_full',
  QUOTA_EXCEEDED = 'quota_exceeded',
  VALIDATION = 'validation',
  UNKNOWN = 'unknown'
}

export enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export enum ErrorRecoveryAction {
  RETRY = 'retry',
  REFRESH_AUTH = 'refresh_auth',
  REDUCE_FILE_SIZE = 'reduce_file_size',
  CHANGE_FORMAT = 'change_format',
  WAIT_AND_RETRY = 'wait_and_retry',
  CONTACT_SUPPORT = 'contact_support',
  CHECK_CONNECTION = 'check_connection',
  CLEAR_CACHE = 'clear_cache',
  USER_ACTION = 'user_action',
  NONE = 'none'
}

export interface CategorizedError {
  category: ErrorCategory
  severity: ErrorSeverity
  message: string
  userMessage: string
  retryable: boolean
  suggestedAction: string
  recoveryAction: ErrorRecoveryAction
  retryDelay?: number
  technicalDetails?: string
  context?: {
    fileName?: string
    fileSize?: number
    operation?: string
    retryCount?: number
  }
}

export interface ErrorPattern {
  pattern: RegExp
  category: ErrorCategory
  severity: ErrorSeverity
  retryable: boolean
  userMessage: string
  suggestedAction: string
  recoveryAction: ErrorRecoveryAction
  maxRetries?: number
  baseDelay?: number
}

class ErrorCategorizationService {
  private readonly errorPatterns: ErrorPattern[] = [
    // Network errors
    {
      pattern: /network error|connection failed|fetch failed|ERR_NETWORK|connection refused/i,
      category: ErrorCategory.NETWORK,
      severity: ErrorSeverity.MEDIUM,
      retryable: true,
      userMessage: 'Network connection issue detected.',
      suggestedAction: 'Please check your internet connection and try again.',
      recoveryAction: ErrorRecoveryAction.CHECK_CONNECTION,
      maxRetries: 3,
      baseDelay: 2000
    },
    {
      pattern: /timeout|timed out|request timeout|upload timeout/i,
      category: ErrorCategory.TIMEOUT,
      severity: ErrorSeverity.MEDIUM,
      retryable: true,
      userMessage: 'Upload timeout - the file is taking too long to upload',
      suggestedAction: 'Please try again. If the problem persists, try uploading a smaller file.',
      recoveryAction: ErrorRecoveryAction.RETRY,
      maxRetries: 2,
      baseDelay: 3000
    },
    {
      pattern: /dns|name resolution|getaddrinfo/i,
      category: ErrorCategory.NETWORK,
      severity: ErrorSeverity.HIGH,
      retryable: true,
      userMessage: 'Unable to connect to the server.',
      suggestedAction: 'Please check your internet connection and try again later.',
      recoveryAction: ErrorRecoveryAction.CHECK_CONNECTION,
      maxRetries: 3,
      baseDelay: 2000
    },
    
    // Authentication errors
    {
      pattern: /unauthorized|authentication failed|invalid token|token expired|401|jwt expired|session expired/i,
      category: ErrorCategory.AUTHENTICATION,
      severity: ErrorSeverity.HIGH,
      retryable: true,
      userMessage: 'Authentication failed.',
      suggestedAction: 'Please sign in again to continue.',
      recoveryAction: ErrorRecoveryAction.REFRESH_AUTH,
      maxRetries: 1,
      baseDelay: 1000
    },
    
    // Permission errors
    {
      pattern: /forbidden|access denied|permission denied|403|insufficient permissions/i,
      category: ErrorCategory.PERMISSION,
      severity: ErrorSeverity.HIGH,
      retryable: false,
      userMessage: 'Access denied.',
      suggestedAction: 'You do not have permission to perform this action.',
      recoveryAction: ErrorRecoveryAction.CONTACT_SUPPORT,
      maxRetries: 0
    },
    
    // File format errors
    {
      pattern: /415|unsupported media type|invalid file format|file format not supported|unsupported format|invalid file type/i,
      category: ErrorCategory.FILE_FORMAT,
      severity: ErrorSeverity.MEDIUM,
      retryable: false,
      userMessage: 'File format not supported.',
      suggestedAction: 'Please upload a video file in MP4, AVI, MOV, or WMV format.',
      recoveryAction: ErrorRecoveryAction.CHANGE_FORMAT,
      maxRetries: 0
    },
    {
      pattern: /corrupted file|invalid file|malformed file/i,
      category: ErrorCategory.FILE_FORMAT,
      severity: ErrorSeverity.MEDIUM,
      retryable: false,
      userMessage: 'The file appears to be corrupted or invalid.',
      suggestedAction: 'Please try uploading a different file.',
      recoveryAction: ErrorRecoveryAction.CHANGE_FORMAT,
      maxRetries: 0
    },
    
    // File size errors
    {
      pattern: /413|payload too large|file too large|size limit exceeded|file size exceeded|entity too large/i,
      category: ErrorCategory.FILE_SIZE,
      severity: ErrorSeverity.MEDIUM,
      retryable: false,
      userMessage: 'File size is too large.',
      suggestedAction: 'Please upload a file smaller than 500MB.',
      recoveryAction: ErrorRecoveryAction.REDUCE_FILE_SIZE,
      maxRetries: 0
    },
    
    // Rate limiting
    {
      pattern: /429|too many requests|rate limit exceeded|quota exceeded/i,
      category: ErrorCategory.RATE_LIMIT,
      severity: ErrorSeverity.MEDIUM,
      retryable: true,
      userMessage: 'Too many requests.',
      suggestedAction: 'Please wait a moment before trying again.',
      recoveryAction: ErrorRecoveryAction.WAIT_AND_RETRY,
      maxRetries: 2,
      baseDelay: 30000
    },
    
    // Server errors
    {
      pattern: /500|internal server error|server error|unexpected error/i,
      category: ErrorCategory.SERVER,
      severity: ErrorSeverity.HIGH,
      retryable: true,
      userMessage: 'Server error occurred.',
      suggestedAction: 'Please try again later. If the problem persists, contact support.',
      recoveryAction: ErrorRecoveryAction.WAIT_AND_RETRY,
      maxRetries: 2,
      baseDelay: 5000
    },
    {
      pattern: /502|bad gateway|503|service unavailable|504|gateway timeout/i,
      category: ErrorCategory.SERVER,
      severity: ErrorSeverity.HIGH,
      retryable: true,
      userMessage: 'Service temporarily unavailable.',
      suggestedAction: 'Please try again in a few minutes.',
      recoveryAction: ErrorRecoveryAction.WAIT_AND_RETRY,
      maxRetries: 3,
      baseDelay: 10000
    },
    {
      pattern: /database error|db error|connection pool|sql error/i,
      category: ErrorCategory.SERVER,
      severity: ErrorSeverity.HIGH,
      retryable: true,
      userMessage: 'A database error occurred.',
      suggestedAction: 'Please try again later. If the problem persists, contact support.',
      recoveryAction: ErrorRecoveryAction.WAIT_AND_RETRY,
      maxRetries: 1,
      baseDelay: 10000
    },
    
    // Upload-specific errors
    {
      pattern: /upload failed|upload error|chunk upload failed|resumable upload failed/i,
      category: ErrorCategory.UPLOAD_FAILED,
      severity: ErrorSeverity.MEDIUM,
      retryable: true,
      userMessage: 'Upload failed.',
      suggestedAction: 'Please try uploading the file again.',
      recoveryAction: ErrorRecoveryAction.RETRY,
      maxRetries: 3,
      baseDelay: 2000
    },
    {
      pattern: /processing failed|video processing error|analysis failed/i,
      category: ErrorCategory.PROCESSING_FAILED,
      severity: ErrorSeverity.MEDIUM,
      retryable: true,
      userMessage: 'Video processing failed.',
      suggestedAction: 'Please try again or contact support if the issue persists.',
      recoveryAction: ErrorRecoveryAction.RETRY,
      maxRetries: 2,
      baseDelay: 5000
    },
    {
      pattern: /storage full|disk full|insufficient storage|no space left/i,
      category: ErrorCategory.STORAGE_FULL,
      severity: ErrorSeverity.HIGH,
      retryable: false,
      userMessage: 'Storage space is full.',
      suggestedAction: 'Please contact support to increase your storage quota.',
      recoveryAction: ErrorRecoveryAction.CONTACT_SUPPORT,
      maxRetries: 0
    },
    {
      pattern: /validation error|invalid input|malformed request|bad request/i,
      category: ErrorCategory.VALIDATION,
      severity: ErrorSeverity.MEDIUM,
      retryable: false,
      userMessage: 'Please check your input and try again.',
      suggestedAction: 'Verify your input data and correct any errors.',
      recoveryAction: ErrorRecoveryAction.USER_ACTION,
      maxRetries: 0,
      baseDelay: 0
    },
    // 400 status code (Bad Request)
    {
      pattern: /^400$/,
      category: ErrorCategory.VALIDATION,
      severity: ErrorSeverity.MEDIUM,
      userMessage: 'Invalid request. Please check your input and try again.',
      retryable: false,
      suggestedAction: 'Verify your input data and correct any errors.',
      recoveryAction: ErrorRecoveryAction.USER_ACTION,
      maxRetries: 0,
      baseDelay: 0
    }
  ]
  
  /**
   * Categorize an error based on its message and properties
   */
  categorizeError(error: Error | string, statusCode?: number, context?: { fileName?: string; fileSize?: number; operation?: string; retryCount?: number }): CategorizedError {
    const errorMessage = typeof error === 'string' ? error : error.message
    const errorStack = typeof error === 'object' ? error.stack : undefined
    
    // Check status code first
    if (statusCode) {
      const statusPattern = this.getPatternByStatusCode(statusCode)
      if (statusPattern) {
        return this.createCategorizedError(statusPattern, errorMessage, errorStack, context)
      }
    }
    
    // Check error message patterns
    for (const pattern of this.errorPatterns) {
      if (this.matchesPattern(errorMessage, pattern.pattern)) {
        return this.createCategorizedError(pattern, errorMessage, errorStack, context)
      }
    }
    
    // Default categorization for unknown errors
    return {
      category: ErrorCategory.UNKNOWN,
      severity: ErrorSeverity.MEDIUM,
      message: errorMessage,
      userMessage: 'An unexpected error occurred.',
      retryable: true,
      suggestedAction: 'Please try again. If the problem persists, contact support.',
      recoveryAction: ErrorRecoveryAction.RETRY,
      technicalDetails: errorStack,
      context
    }
  }
  
  /**
   * Get retry strategy based on error category
   */
  getRetryStrategy(categorizedError: CategorizedError): {
    shouldRetry: boolean
    maxRetries: number
    baseDelay: number
    maxDelay: number
    backoffMultiplier: number
  } {
    if (!categorizedError.retryable) {
      return {
        shouldRetry: false,
        maxRetries: 0,
        baseDelay: 0,
        maxDelay: 0,
        backoffMultiplier: 1
      }
    }
    
    switch (categorizedError.category) {
      case ErrorCategory.NETWORK:
      case ErrorCategory.TIMEOUT:
        return {
          shouldRetry: true,
          maxRetries: 5,
          baseDelay: 1000,
          maxDelay: 30000,
          backoffMultiplier: 2
        }
      
      case ErrorCategory.SERVER:
        return {
          shouldRetry: true,
          maxRetries: 3,
          baseDelay: 2000,
          maxDelay: 60000,
          backoffMultiplier: 2.5
        }
      
      case ErrorCategory.RATE_LIMIT:
        return {
          shouldRetry: true,
          maxRetries: 3,
          baseDelay: 5000,
          maxDelay: 120000,
          backoffMultiplier: 3
        }
      
      default:
        return {
          shouldRetry: true,
          maxRetries: 2,
          baseDelay: 1000,
          maxDelay: 10000,
          backoffMultiplier: 2
        }
    }
  }
  
  /**
   * Get user-friendly error message with context
   */
  getUserFriendlyMessage(categorizedError: CategorizedError, context?: {
    fileName?: string
    fileSize?: number
    operation?: string
  }): string {
    let message = categorizedError.userMessage
    
    if (context) {
      if (context.fileName) {
        message += ` (File: ${context.fileName})`
      }
      
      if (context.operation) {
        message = `${context.operation}: ${message}`
      }
    }
    
    return message
  }
  
  /**
   * Get suggested actions based on error category and context
   */
  getSuggestedActions(categorizedError: CategorizedError, context?: {
    retryCount?: number
    maxRetries?: number
  }): string[] {
    const actions = [categorizedError.suggestedAction]
    
    if (context?.retryCount && context?.maxRetries) {
      if (context.retryCount >= context.maxRetries) {
        actions.push('Maximum retry attempts reached. Please contact support if the issue persists.')
      } else {
        actions.push(`Retry attempt ${context.retryCount + 1} of ${context.maxRetries} will be attempted automatically.`)
      }
    }
    
    // Add category-specific additional actions
    switch (categorizedError.category) {
      case ErrorCategory.NETWORK:
        actions.push('Check your internet connection stability.')
        actions.push('Try switching to a different network if available.')
        break
      
      case ErrorCategory.FILE_SIZE:
        actions.push('Consider compressing your video file.')
        actions.push('Try uploading during off-peak hours for better performance.')
        break
      
      case ErrorCategory.FILE_FORMAT:
        actions.push('Convert your file to MP4 format for best compatibility.')
        actions.push('Ensure your file is not corrupted by playing it locally first.')
        break
      
      case ErrorCategory.AUTHENTICATION:
        actions.push('Clear your browser cache and cookies.')
        actions.push('Try logging out and logging back in.')
        break
    }
    
    return actions
  }
  
  /**
   * Check if error should trigger immediate user notification
   */
  shouldNotifyUser(categorizedError: CategorizedError): boolean {
    return categorizedError.severity === ErrorSeverity.HIGH || 
           categorizedError.severity === ErrorSeverity.CRITICAL ||
           !categorizedError.retryable
  }
  
  /**
   * Check if an error is retryable
   */
  isRetryable(error: any): boolean {
    const categorized = this.categorizeError(error)
    return categorized.retryable
  }

  /**
   * Get user-friendly error message
   */
  getUserMessage(error: any): string {
    const categorized = this.categorizeError(error)
    return categorized.userMessage
  }

  /**
   * Get suggested action for error
   */
  getSuggestedAction(error: any): string {
    const categorized = this.categorizeError(error)
    return categorized.suggestedAction
  }

  /**
   * Get retry configuration for an error
   */
  getRetryConfig(error: any): { maxRetries: number; baseDelay: number } {
    const errorMessage = this.extractErrorMessage(error)
    const statusCode = this.extractStatusCode(error)
    
    for (const pattern of this.errorPatterns) {
      if (pattern.pattern.test(errorMessage) || 
          (statusCode && pattern.pattern.test(statusCode.toString()))) {
        return {
          maxRetries: pattern.maxRetries || 3,
          baseDelay: pattern.baseDelay || 1000
        }
      }
    }
    
    return { maxRetries: 3, baseDelay: 1000 }
  }

  /**
   * Get recovery action for an error
   */
  getRecoveryAction(error: any): ErrorRecoveryAction {
    const categorized = this.categorizeError(error)
    return categorized.recoveryAction
  }

  /**
   * Calculate delay for retry with exponential backoff
   */
  calculateRetryDelay(baseDelay: number, retryCount: number, jitter: boolean = true): number {
    const exponentialDelay = baseDelay * Math.pow(2, retryCount)
    const maxDelay = 30000 // 30 seconds max
    let delay = Math.min(exponentialDelay, maxDelay)
    
    if (jitter) {
      // Add random jitter (±25%)
      const jitterAmount = delay * 0.25
      delay += (Math.random() - 0.5) * 2 * jitterAmount
    }
    
    return Math.max(delay, 100) // Minimum 100ms
  }

  /**
   * Extract error message from various error types
   */
  private extractErrorMessage(error: any): string {
    if (typeof error === 'string') return error
    if (error?.message) return error.message
    if (error?.error) return error.error
    return String(error)
  }

  /**
   * Extract status code from error object
   */
  private extractStatusCode(error: any): number | null {
    if (error?.status) return error.status
    if (error?.statusCode) return error.statusCode
    if (error?.response?.status) return error.response.status
    return null
  }

  /**
   * Private helper methods
   */
  
  private matchesPattern(message: string, pattern: RegExp | string): boolean {
    if (pattern instanceof RegExp) {
      return pattern.test(message)
    }
    return message.toLowerCase().includes(pattern.toLowerCase())
  }
  
  private getPatternByStatusCode(statusCode: number): ErrorPattern | null {
    const statusString = statusCode.toString()
    return this.errorPatterns.find(pattern => {
      if (pattern.pattern instanceof RegExp) {
        return pattern.pattern.test(statusString)
      }
      return statusString.includes(String(pattern.pattern))
    }) || null
  }
  
  private createCategorizedError(
    pattern: ErrorPattern, 
    originalMessage: string, 
    technicalDetails?: string,
    context?: { fileName?: string; fileSize?: number; operation?: string; retryCount?: number }
  ): CategorizedError {
    return {
      category: pattern.category,
      severity: pattern.severity,
      message: originalMessage,
      userMessage: pattern.userMessage,
      retryable: pattern.retryable,
      suggestedAction: pattern.suggestedAction,
      recoveryAction: pattern.recoveryAction,
      technicalDetails,
      context
    }
  }
}

export { ErrorCategorizationService }
export const errorCategorizationService = new ErrorCategorizationService()