import { toast } from 'sonner'

interface ErrorContext {
  component: string
  action: string
  userId?: string
  sessionId?: string
  timestamp: Date
  userAgent: string
  url: string
  additionalData?: Record<string, any>
}

interface ErrorReport {
  id: string
  error: Error
  context: ErrorContext
  severity: 'low' | 'medium' | 'high' | 'critical'
  category: 'network' | 'validation' | 'processing' | 'ui' | 'auth' | 'unknown'
  resolved: boolean
  reportedAt: Date
}

interface RetryConfig {
  maxAttempts: number
  baseDelay: number
  maxDelay: number
  backoffFactor: number
  retryCondition?: (error: Error) => boolean
}

class ErrorHandlingService {
  private errorReports: ErrorReport[] = []
  private retryConfigs: Map<string, RetryConfig> = new Map()
  private errorCallbacks: Map<string, (error: ErrorReport) => void> = new Map()

  constructor() {
    this.setupGlobalErrorHandlers()
    this.setupDefaultRetryConfigs()
  }

  /**
   * Setup global error handlers
   */
  private setupGlobalErrorHandlers(): void {
    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.handleError(
        new Error(event.reason?.message || 'Unhandled promise rejection'),
        {
          component: 'Global',
          action: 'unhandledrejection',
          timestamp: new Date(),
          userAgent: navigator.userAgent,
          url: window.location.href,
          additionalData: { reason: event.reason }
        },
        'high'
      )
    })

    // Handle JavaScript errors
    window.addEventListener('error', (event) => {
      this.handleError(
        new Error(event.message),
        {
          component: 'Global',
          action: 'javascript_error',
          timestamp: new Date(),
          userAgent: navigator.userAgent,
          url: window.location.href,
          additionalData: {
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno
          }
        },
        'high'
      )
    })
  }

  /**
   * Setup default retry configurations
   */
  private setupDefaultRetryConfigs(): void {
    // Network requests
    this.retryConfigs.set('network', {
      maxAttempts: 3,
      baseDelay: 1000,
      maxDelay: 10000,
      backoffFactor: 2,
      retryCondition: (error) => {
        return error.message.includes('fetch') || 
               error.message.includes('network') ||
               error.message.includes('timeout')
      }
    })

    // File operations
    this.retryConfigs.set('file', {
      maxAttempts: 2,
      baseDelay: 500,
      maxDelay: 2000,
      backoffFactor: 2,
      retryCondition: (error) => {
        return !error.message.includes('invalid') &&
               !error.message.includes('format')
      }
    })

    // Processing operations
    this.retryConfigs.set('processing', {
      maxAttempts: 2,
      baseDelay: 2000,
      maxDelay: 8000,
      backoffFactor: 2,
      retryCondition: (error) => {
        return error.message.includes('temporary') ||
               error.message.includes('busy')
      }
    })
  }

  /**
   * Handle and categorize errors
   */
  handleError(
    error: Error,
    context: Partial<ErrorContext>,
    severity: 'low' | 'medium' | 'high' | 'critical' = 'medium'
  ): string {
    const errorId = this.generateErrorId()
    const fullContext: ErrorContext = {
      component: 'Unknown',
      action: 'unknown',
      timestamp: new Date(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      ...context
    }

    const category = this.categorizeError(error)
    
    const errorReport: ErrorReport = {
      id: errorId,
      error,
      context: fullContext,
      severity,
      category,
      resolved: false,
      reportedAt: new Date()
    }

    this.errorReports.push(errorReport)
    this.logError(errorReport)
    this.showUserFeedback(errorReport)
    this.notifyCallbacks(errorReport)

    // Auto-resolve low severity errors after 5 minutes
    if (severity === 'low') {
      setTimeout(() => {
        this.resolveError(errorId)
      }, 5 * 60 * 1000)
    }

    return errorId
  }

  /**
   * Categorize error based on message and context
   */
  private categorizeError(error: Error): ErrorReport['category'] {
    const message = error.message.toLowerCase()
    
    if (message.includes('fetch') || message.includes('network') || message.includes('timeout')) {
      return 'network'
    }
    
    if (message.includes('validation') || message.includes('invalid') || message.includes('required')) {
      return 'validation'
    }
    
    if (message.includes('processing') || message.includes('generation') || message.includes('analysis')) {
      return 'processing'
    }
    
    if (message.includes('unauthorized') || message.includes('forbidden') || message.includes('auth')) {
      return 'auth'
    }
    
    if (message.includes('render') || message.includes('component') || message.includes('ui')) {
      return 'ui'
    }
    
    return 'unknown'
  }

  /**
   * Show appropriate user feedback based on error
   */
  private showUserFeedback(errorReport: ErrorReport): void {
    const { error, severity, category, context } = errorReport
    
    let message = this.getUserFriendlyMessage(error, category)
    let action: (() => void) | undefined

    // Add retry action for retryable errors
    if (this.isRetryable(error, category)) {
      action = () => {
        this.retryOperation(context.component, context.action, error)
      }
    }

    switch (severity) {
      case 'low':
        toast.info(message, {
          duration: 3000,
          action: action ? {
            label: 'Retry',
            onClick: action
          } : undefined
        })
        break
        
      case 'medium':
        toast.warning(message, {
          duration: 5000,
          action: action ? {
            label: 'Retry',
            onClick: action
          } : undefined
        })
        break
        
      case 'high':
        toast.error(message, {
          duration: 8000,
          action: action ? {
            label: 'Retry',
            onClick: action
          } : {
            label: 'Report',
            onClick: () => this.reportError(errorReport.id)
          }
        })
        break
        
      case 'critical':
        toast.error(message, {
          duration: 0, // Persistent
          action: {
            label: 'Report Issue',
            onClick: () => this.reportError(errorReport.id)
          }
        })
        break
    }
  }

  /**
   * Get user-friendly error message
   */
  private getUserFriendlyMessage(error: Error, category: ErrorReport['category']): string {
    switch (category) {
      case 'network':
        return 'Connection issue. Please check your internet and try again.'
      case 'validation':
        return 'Please check your input and try again.'
      case 'processing':
        return 'Processing failed. This might be temporary - please try again.'
      case 'auth':
        return 'Authentication required. Please log in and try again.'
      case 'ui':
        return 'Display issue encountered. Refreshing might help.'
      default:
        return 'Something went wrong. Please try again or contact support.'
    }
  }

  /**
   * Check if error is retryable
   */
  private isRetryable(error: Error, category: ErrorReport['category']): boolean {
    const nonRetryableMessages = [
      'invalid',
      'forbidden',
      'unauthorized',
      'not found',
      'bad request',
      'validation failed'
    ]
    
    const message = error.message.toLowerCase()
    return !nonRetryableMessages.some(msg => message.includes(msg)) &&
           ['network', 'processing'].includes(category)
  }

  /**
   * Retry operation with exponential backoff
   */
  async retryOperation(
    component: string,
    action: string,
    originalError: Error,
    configKey: string = 'network'
  ): Promise<any> {
    const config = this.retryConfigs.get(configKey) || this.retryConfigs.get('network')!
    
    for (let attempt = 1; attempt <= config.maxAttempts; attempt++) {
      try {
        // This would need to be implemented by the calling component
        // For now, we'll just show a retry message
        toast.info(`Retrying... (${attempt}/${config.maxAttempts})`)
        
        // Simulate retry delay
        const delay = Math.min(
          config.baseDelay * Math.pow(config.backoffFactor, attempt - 1),
          config.maxDelay
        )
        
        await new Promise(resolve => setTimeout(resolve, delay))
        
        // The actual retry logic would be implemented by the component
        // This is just a placeholder
        return { success: true, attempt }
        
      } catch (error) {
        const isLastAttempt = attempt === config.maxAttempts
        const shouldRetry = config.retryCondition ? config.retryCondition(error as Error) : true
        
        if (isLastAttempt || !shouldRetry) {
          this.handleError(
            error as Error,
            { component, action: `${action}_retry_failed` },
            'high'
          )
          throw error
        }
      }
    }
  }

  /**
   * Log error for debugging
   */
  private logError(errorReport: ErrorReport): void {
    const { error, context, severity, category } = errorReport
    
    console.group(`🚨 Error [${severity.toUpperCase()}] - ${category}`)
    console.error('Message:', error.message)
    console.error('Stack:', error.stack)
    console.log('Context:', context)
    console.log('Report ID:', errorReport.id)
    console.groupEnd()
    
    // In production, send to logging service
    if (process.env.NODE_ENV === 'production') {
      this.sendToLoggingService(errorReport)
    }
  }

  /**
   * Send error to external logging service
   */
  private async sendToLoggingService(errorReport: ErrorReport): Promise<void> {
    try {
      // This would integrate with services like Sentry, LogRocket, etc.
      await fetch('/api/errors', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          id: errorReport.id,
          message: errorReport.error.message,
          stack: errorReport.error.stack,
          context: errorReport.context,
          severity: errorReport.severity,
          category: errorReport.category,
          timestamp: errorReport.reportedAt
        })
      })
    } catch (loggingError) {
      console.error('Failed to send error to logging service:', loggingError)
    }
  }

  /**
   * Report error to support
   */
  private reportError(errorId: string): void {
    const errorReport = this.errorReports.find(report => report.id === errorId)
    if (!errorReport) return

    // Open support form or email with error details
    const subject = encodeURIComponent(`Error Report: ${errorReport.error.message}`)
    const body = encodeURIComponent(`
Error ID: ${errorId}
Component: ${errorReport.context.component}
Action: ${errorReport.context.action}
Time: ${errorReport.reportedAt.toISOString()}

Please describe what you were doing when this error occurred:

`)
    
    window.open(`mailto:support@cliper.app?subject=${subject}&body=${body}`)
  }

  /**
   * Register error callback
   */
  onError(component: string, callback: (error: ErrorReport) => void): void {
    this.errorCallbacks.set(component, callback)
  }

  /**
   * Notify registered callbacks
   */
  private notifyCallbacks(errorReport: ErrorReport): void {
    const callback = this.errorCallbacks.get(errorReport.context.component)
    if (callback) {
      try {
        callback(errorReport)
      } catch (callbackError) {
        console.error('Error in error callback:', callbackError)
      }
    }
  }

  /**
   * Resolve error
   */
  resolveError(errorId: string): void {
    const errorReport = this.errorReports.find(report => report.id === errorId)
    if (errorReport) {
      errorReport.resolved = true
    }
  }

  /**
   * Get error statistics
   */
  getErrorStats(): {
    total: number
    byCategory: Record<string, number>
    bySeverity: Record<string, number>
    resolved: number
    recent: number
  } {
    const now = new Date()
    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000)
    
    const byCategory: Record<string, number> = {}
    const bySeverity: Record<string, number> = {}
    let resolved = 0
    let recent = 0
    
    this.errorReports.forEach(report => {
      byCategory[report.category] = (byCategory[report.category] || 0) + 1
      bySeverity[report.severity] = (bySeverity[report.severity] || 0) + 1
      
      if (report.resolved) resolved++
      if (report.reportedAt > oneHourAgo) recent++
    })
    
    return {
      total: this.errorReports.length,
      byCategory,
      bySeverity,
      resolved,
      recent
    }
  }

  /**
   * Clear old error reports
   */
  clearOldErrors(olderThanDays: number = 7): void {
    const cutoffDate = new Date()
    cutoffDate.setDate(cutoffDate.getDate() - olderThanDays)
    
    this.errorReports = this.errorReports.filter(
      report => report.reportedAt > cutoffDate
    )
  }

  /**
   * Generate unique error ID
   */
  private generateErrorId(): string {
    return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
}

// Create singleton instance
export const errorHandler = new ErrorHandlingService()

// Export types
export type {
  ErrorContext,
  ErrorReport,
  RetryConfig
}

// Utility function for components
export const withErrorHandling = <T extends any[], R>(
  fn: (...args: T) => Promise<R>,
  component: string,
  action: string
) => {
  return async (...args: T): Promise<R> => {
    try {
      return await fn(...args)
    } catch (error) {
      errorHandler.handleError(
        error as Error,
        { component, action },
        'medium'
      )
      throw error
    }
  }
}