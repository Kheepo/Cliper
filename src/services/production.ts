import { errorHandler } from './errorHandling'

interface RateLimitConfig {
  windowMs: number // Time window in milliseconds
  maxRequests: number // Maximum requests per window
  skipSuccessfulRequests?: boolean
  skipFailedRequests?: boolean
  keyGenerator?: (identifier: string) => string
}

interface LogEntry {
  id: string
  timestamp: Date
  level: 'debug' | 'info' | 'warn' | 'error' | 'critical'
  message: string
  context?: Record<string, any>
  userId?: string
  sessionId?: string
  component?: string
  action?: string
  duration?: number
  metadata?: Record<string, any>
}

interface RateLimitEntry {
  count: number
  resetTime: number
  blocked: boolean
}

interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy'
  uptime: number
  memoryUsage: {
    used: number
    total: number
    percentage: number
  }
  errorRate: number
  responseTime: {
    avg: number
    p95: number
    p99: number
  }
  activeUsers: number
  cacheHitRate: number
}

class ProductionService {
  private rateLimitStore: Map<string, RateLimitEntry> = new Map()
  private logs: LogEntry[] = []
  private maxLogEntries = 10000
  private sessionId: string
  private startTime: Date
  private responseTimes: number[] = []
  private activeUsers: Set<string> = new Set()

  constructor() {
    this.sessionId = this.generateSessionId()
    this.startTime = new Date()
    this.setupCleanupIntervals()
    this.setupBeforeUnloadHandler()
  }

  /**
   * Rate limiting functionality
   */
  createRateLimit(name: string, config: RateLimitConfig): (identifier: string) => boolean {
    return (identifier: string): boolean => {
      const key = config.keyGenerator ? config.keyGenerator(identifier) : `${name}:${identifier}`
      const now = Date.now()
      const entry = this.rateLimitStore.get(key)

      if (!entry || now > entry.resetTime) {
        // Reset or create new entry
        this.rateLimitStore.set(key, {
          count: 1,
          resetTime: now + config.windowMs,
          blocked: false
        })
        return true
      }

      if (entry.count >= config.maxRequests) {
        entry.blocked = true
        this.log('warn', `Rate limit exceeded for ${key}`, {
          identifier,
          count: entry.count,
          maxRequests: config.maxRequests,
          windowMs: config.windowMs
        })
        return false
      }

      entry.count++
      return true
    }
  }

  /**
   * API rate limiter
   */
  private apiRateLimit = this.createRateLimit('api', {
    windowMs: 60 * 1000, // 1 minute
    maxRequests: 100,
    keyGenerator: (identifier) => `api:${identifier}`
  })

  /**
   * Upload rate limiter
   */
  private uploadRateLimit = this.createRateLimit('upload', {
    windowMs: 60 * 1000, // 1 minute
    maxRequests: 5,
    keyGenerator: (identifier) => `upload:${identifier}`
  })

  /**
   * Check if API request is allowed
   */
  checkApiRateLimit(userId: string): boolean {
    return this.apiRateLimit(userId)
  }

  /**
   * Check if upload is allowed
   */
  checkUploadRateLimit(userId: string): boolean {
    return this.uploadRateLimit(userId)
  }

  /**
   * Comprehensive logging system
   */
  log(
    level: LogEntry['level'],
    message: string,
    context?: Record<string, any>,
    options?: {
      userId?: string
      component?: string
      action?: string
      duration?: number
      metadata?: Record<string, any>
    }
  ): void {
    const logEntry: LogEntry = {
      id: this.generateLogId(),
      timestamp: new Date(),
      level,
      message,
      context,
      sessionId: this.sessionId,
      ...options
    }

    this.logs.push(logEntry)

    // Maintain log size limit
    if (this.logs.length > this.maxLogEntries) {
      this.logs.shift()
    }

    // Console output for development
    if (process.env.NODE_ENV === 'development') {
      this.outputToConsole(logEntry)
    }

    // Send to external logging service in production
    if (process.env.NODE_ENV === 'production') {
      this.sendToLoggingService(logEntry)
    }

    // Handle critical logs
    if (level === 'critical') {
      this.handleCriticalLog(logEntry)
    }
  }

  /**
   * Convenience logging methods
   */
  debug(message: string, context?: Record<string, any>, options?: any): void {
    this.log('debug', message, context, options)
  }

  info(message: string, context?: Record<string, any>, options?: any): void {
    this.log('info', message, context, options)
  }

  warn(message: string, context?: Record<string, any>, options?: any): void {
    this.log('warn', message, context, options)
  }

  error(message: string, context?: Record<string, any>, options?: any): void {
    this.log('error', message, context, options)
  }

  critical(message: string, context?: Record<string, any>, options?: any): void {
    this.log('critical', message, context, options)
  }

  /**
   * Log API request/response
   */
  logApiCall(
    method: string,
    url: string,
    statusCode: number,
    duration: number,
    userId?: string,
    requestSize?: number,
    responseSize?: number
  ): void {
    this.responseTimes.push(duration)
    
    // Keep only last 1000 response times
    if (this.responseTimes.length > 1000) {
      this.responseTimes.shift()
    }

    const level = statusCode >= 500 ? 'error' : statusCode >= 400 ? 'warn' : 'info'
    
    this.log(level, `API ${method} ${url}`, {
      method,
      url,
      statusCode,
      duration,
      requestSize,
      responseSize
    }, {
      userId,
      component: 'API',
      action: `${method}_${url.split('/').pop()}`,
      duration
    })
  }

  /**
   * Log user action
   */
  logUserAction(
    action: string,
    component: string,
    userId?: string,
    metadata?: Record<string, any>
  ): void {
    if (userId) {
      this.activeUsers.add(userId)
    }

    this.log('info', `User action: ${action}`, {
      action,
      component,
      userAgent: navigator.userAgent,
      url: window.location.href,
      timestamp: new Date().toISOString()
    }, {
      userId,
      component,
      action,
      metadata
    })
  }

  /**
   * Log performance metrics
   */
  logPerformance(
    metric: string,
    value: number,
    component?: string,
    metadata?: Record<string, any>
  ): void {
    this.log('info', `Performance: ${metric}`, {
      metric,
      value,
      unit: this.getMetricUnit(metric),
      ...metadata
    }, {
      component: component || 'Performance',
      action: 'metric_recorded',
      metadata: { metric, value }
    })
  }

  /**
   * Get metric unit based on metric name
   */
  private getMetricUnit(metric: string): string {
    if (metric.includes('time') || metric.includes('duration')) return 'ms'
    if (metric.includes('memory') || metric.includes('size')) return 'bytes'
    if (metric.includes('rate') || metric.includes('percentage')) return '%'
    return 'count'
  }

  /**
   * Output log to console with formatting
   */
  private outputToConsole(logEntry: LogEntry): void {
    const timestamp = logEntry.timestamp.toISOString()
    const prefix = `[${timestamp}] [${logEntry.level.toUpperCase()}]`
    
    const style = this.getConsoleStyle(logEntry.level)
    
    console.group(`%c${prefix} ${logEntry.message}`, style)
    
    if (logEntry.context) {
      console.log('Context:', logEntry.context)
    }
    
    if (logEntry.component) {
      console.log('Component:', logEntry.component)
    }
    
    if (logEntry.action) {
      console.log('Action:', logEntry.action)
    }
    
    if (logEntry.duration) {
      console.log('Duration:', `${logEntry.duration}ms`)
    }
    
    if (logEntry.metadata) {
      console.log('Metadata:', logEntry.metadata)
    }
    
    console.groupEnd()
  }

  /**
   * Get console styling for log levels
   */
  private getConsoleStyle(level: LogEntry['level']): string {
    switch (level) {
      case 'debug':
        return 'color: #888; font-weight: normal;'
      case 'info':
        return 'color: #2196F3; font-weight: normal;'
      case 'warn':
        return 'color: #FF9800; font-weight: bold;'
      case 'error':
        return 'color: #F44336; font-weight: bold;'
      case 'critical':
        return 'color: #FFFFFF; background-color: #F44336; font-weight: bold; padding: 2px 4px;'
      default:
        return 'color: #000; font-weight: normal;'
    }
  }

  /**
   * Send log to external logging service
   */
  private async sendToLoggingService(logEntry: LogEntry): Promise<void> {
    try {
      // Batch logs to reduce requests
      if (this.shouldBatchLog(logEntry)) {
        return
      }

      await fetch('/api/logs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(logEntry)
      })
    } catch (error) {
      // Fallback to local storage if logging service fails
      this.storeLogLocally(logEntry)
    }
  }

  /**
   * Determine if log should be batched
   */
  private shouldBatchLog(logEntry: LogEntry): boolean {
    // Batch debug and info logs, send warn/error/critical immediately
    return ['debug', 'info'].includes(logEntry.level)
  }

  /**
   * Store log locally as fallback
   */
  private storeLogLocally(logEntry: LogEntry): void {
    try {
      const storedLogs = JSON.parse(localStorage.getItem('cliper_logs') || '[]')
      storedLogs.push(logEntry)
      
      // Keep only last 100 logs in localStorage
      if (storedLogs.length > 100) {
        storedLogs.shift()
      }
      
      localStorage.setItem('cliper_logs', JSON.stringify(storedLogs))
    } catch (error) {
      console.warn('Failed to store log locally:', error)
    }
  }

  /**
   * Handle critical logs
   */
  private handleCriticalLog(logEntry: LogEntry): void {
    // Send immediate alert
    console.error('CRITICAL LOG:', logEntry)
    
    // Could integrate with alerting services like PagerDuty, Slack, etc.
    if (process.env.NODE_ENV === 'production') {
      this.sendCriticalAlert(logEntry)
    }
  }

  /**
   * Send critical alert
   */
  private async sendCriticalAlert(logEntry: LogEntry): Promise<void> {
    try {
      await fetch('/api/alerts/critical', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: logEntry.message,
          context: logEntry.context,
          timestamp: logEntry.timestamp,
          sessionId: logEntry.sessionId
        })
      })
    } catch (error) {
      console.error('Failed to send critical alert:', error)
    }
  }

  /**
   * Get system health status
   */
  getSystemHealth(): SystemHealth {
    const now = Date.now()
    const uptime = now - this.startTime.getTime()
    
    // Calculate error rate (errors in last hour)
    const oneHourAgo = new Date(now - 60 * 60 * 1000)
    const recentLogs = this.logs.filter(log => log.timestamp > oneHourAgo)
    const errorLogs = recentLogs.filter(log => ['error', 'critical'].includes(log.level))
    const errorRate = recentLogs.length > 0 ? (errorLogs.length / recentLogs.length) * 100 : 0
    
    // Calculate response times
    const recentResponseTimes = this.responseTimes.slice(-100)
    const avgResponseTime = recentResponseTimes.length > 0 
      ? recentResponseTimes.reduce((sum, time) => sum + time, 0) / recentResponseTimes.length 
      : 0
    
    const sortedTimes = [...recentResponseTimes].sort((a, b) => a - b)
    const p95Index = Math.floor(sortedTimes.length * 0.95)
    const p99Index = Math.floor(sortedTimes.length * 0.99)
    
    // Memory usage (if available)
    const memory = (performance as any).memory
    const memoryUsage = memory ? {
      used: memory.usedJSHeapSize,
      total: memory.totalJSHeapSize,
      percentage: (memory.usedJSHeapSize / memory.totalJSHeapSize) * 100
    } : {
      used: 0,
      total: 0,
      percentage: 0
    }
    
    // Determine overall status
    let status: SystemHealth['status'] = 'healthy'
    if (errorRate > 10 || avgResponseTime > 5000 || memoryUsage.percentage > 90) {
      status = 'unhealthy'
    } else if (errorRate > 5 || avgResponseTime > 2000 || memoryUsage.percentage > 70) {
      status = 'degraded'
    }
    
    return {
      status,
      uptime,
      memoryUsage,
      errorRate: Math.round(errorRate * 100) / 100,
      responseTime: {
        avg: Math.round(avgResponseTime * 100) / 100,
        p95: sortedTimes[p95Index] || 0,
        p99: sortedTimes[p99Index] || 0
      },
      activeUsers: this.activeUsers.size,
      cacheHitRate: 0 // Would be calculated from performance service
    }
  }

  /**
   * Get logs with filtering
   */
  getLogs(options: {
    level?: LogEntry['level']
    component?: string
    userId?: string
    startTime?: Date
    endTime?: Date
    limit?: number
  } = {}): LogEntry[] {
    let filteredLogs = [...this.logs]
    
    if (options.level) {
      filteredLogs = filteredLogs.filter(log => log.level === options.level)
    }
    
    if (options.component) {
      filteredLogs = filteredLogs.filter(log => log.component === options.component)
    }
    
    if (options.userId) {
      filteredLogs = filteredLogs.filter(log => log.userId === options.userId)
    }
    
    if (options.startTime) {
      filteredLogs = filteredLogs.filter(log => log.timestamp >= options.startTime!)
    }
    
    if (options.endTime) {
      filteredLogs = filteredLogs.filter(log => log.timestamp <= options.endTime!)
    }
    
    // Sort by timestamp (newest first)
    filteredLogs.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
    
    if (options.limit) {
      filteredLogs = filteredLogs.slice(0, options.limit)
    }
    
    return filteredLogs
  }

  /**
   * Export logs for analysis
   */
  exportLogs(format: 'json' | 'csv' = 'json'): string {
    if (format === 'csv') {
      const headers = ['timestamp', 'level', 'message', 'component', 'action', 'userId', 'duration']
      const csvRows = [headers.join(',')]
      
      this.logs.forEach(log => {
        const row = [
          log.timestamp.toISOString(),
          log.level,
          `"${log.message.replace(/"/g, '""')}"`,
          log.component || '',
          log.action || '',
          log.userId || '',
          log.duration?.toString() || ''
        ]
        csvRows.push(row.join(','))
      })
      
      return csvRows.join('\n')
    }
    
    return JSON.stringify(this.logs, null, 2)
  }

  /**
   * Setup cleanup intervals
   */
  private setupCleanupIntervals(): void {
    // Clean up rate limit entries every 5 minutes
    setInterval(() => {
      const now = Date.now()
      for (const [key, entry] of this.rateLimitStore.entries()) {
        if (now > entry.resetTime) {
          this.rateLimitStore.delete(key)
        }
      }
    }, 5 * 60 * 1000)
    
    // Clean up old active users every hour
    setInterval(() => {
      this.activeUsers.clear()
    }, 60 * 60 * 1000)
  }

  /**
   * Setup beforeunload handler to flush logs
   */
  private setupBeforeUnloadHandler(): void {
    window.addEventListener('beforeunload', () => {
      // Flush any pending logs
      this.flushLogs()
    })
  }

  /**
   * Flush pending logs
   */
  private flushLogs(): void {
    // In a real implementation, this would send any batched logs
    this.info('Session ending', {
      sessionDuration: Date.now() - this.startTime.getTime(),
      totalLogs: this.logs.length,
      activeUsers: this.activeUsers.size
    })
  }

  /**
   * Generate unique session ID
   */
  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * Generate unique log ID
   */
  private generateLogId(): string {
    return `log_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * Clear all logs
   */
  clearLogs(): void {
    this.logs = []
    localStorage.removeItem('cliper_logs')
  }

  /**
   * Get rate limit status
   */
  getRateLimitStatus(): Record<string, { count: number; limit: number; resetTime: number; blocked: boolean }> {
    const status: Record<string, any> = {}
    
    this.rateLimitStore.forEach((entry, key) => {
      const [type, identifier] = key.split(':')
      if (!status[type]) {
        status[type] = []
      }
      
      status[type].push({
        identifier,
        count: entry.count,
        resetTime: entry.resetTime,
        blocked: entry.blocked
      })
    })
    
    return status
  }
}

// Create singleton instance
export const productionService = new ProductionService()

// Export types
export type {
  RateLimitConfig,
  LogEntry,
  SystemHealth
}

// Utility decorators for automatic logging
export const withLogging = <T extends any[], R>(
  fn: (...args: T) => Promise<R>,
  component: string,
  action: string
) => {
  return async (...args: T): Promise<R> => {
    const startTime = performance.now()
    
    try {
      productionService.debug(`Starting ${action}`, { args }, { component, action })
      const result = await fn(...args)
      const duration = performance.now() - startTime
      
      productionService.info(`Completed ${action}`, { duration }, { component, action, duration })
      return result
    } catch (error) {
      const duration = performance.now() - startTime
      productionService.error(`Failed ${action}`, { error: (error as Error).message, duration }, { component, action, duration })
      throw error
    }
  }
}

export const withRateLimit = <T extends any[], R>(
  fn: (...args: T) => Promise<R>,
  rateLimitCheck: (userId: string) => boolean,
  getUserId: (...args: T) => string
) => {
  return async (...args: T): Promise<R> => {
    const userId = getUserId(...args)
    
    if (!rateLimitCheck(userId)) {
      throw new Error('Rate limit exceeded. Please try again later.')
    }
    
    return fn(...args)
  }
}