import { webSocketService } from './websocket'
import { productionService } from './production'
import { errorHandler } from './errorHandling'

interface ProgressUpdate {
  jobId: string
  type: 'clip_generation' | 'video_analysis' | 'upload' | 'processing'
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number // 0-100
  stage: string
  message: string
  estimatedTimeRemaining?: number
  currentStep?: number
  totalSteps?: number
  metadata?: Record<string, any>
  timestamp: Date
}

interface JobMetrics {
  startTime: Date
  endTime?: Date
  duration?: number
  stepsCompleted: number
  totalSteps: number
  averageStepDuration: number
  estimatedCompletion: Date
  throughput: number // items per minute
}

interface QueueStatus {
  position: number
  estimatedWaitTime: number
  queueLength: number
  averageProcessingTime: number
}

interface SystemLoad {
  cpuUsage: number
  memoryUsage: number
  activeJobs: number
  queuedJobs: number
  completedJobs: number
  failedJobs: number
  averageJobDuration: number
}

type ProgressCallback = (update: ProgressUpdate) => void
type MetricsCallback = (metrics: JobMetrics) => void
type QueueCallback = (status: QueueStatus) => void
type SystemCallback = (load: SystemLoad) => void

class RealTimeTrackingService {
  private progressCallbacks: Map<string, ProgressCallback[]> = new Map()
  private metricsCallbacks: Map<string, MetricsCallback[]> = new Map()
  private queueCallbacks: QueueCallback[] = []
  private systemCallbacks: SystemCallback[] = []
  private jobMetrics: Map<string, JobMetrics> = new Map()
  private activeJobs: Set<string> = new Set()
  private completedJobs: Map<string, ProgressUpdate> = new Map()
  private systemLoad: SystemLoad = {
    cpuUsage: 0,
    memoryUsage: 0,
    activeJobs: 0,
    queuedJobs: 0,
    completedJobs: 0,
    failedJobs: 0,
    averageJobDuration: 0
  }

  constructor() {
    this.setupWebSocketListeners()
    this.setupPeriodicUpdates()
  }

  /**
   * Setup WebSocket listeners for real-time updates
   */
  private setupWebSocketListeners(): void {
    webSocketService.subscribe('progress_update', (data: ProgressUpdate) => {
      this.handleProgressUpdate(data)
    })

    webSocketService.subscribe('queue_status', (data: QueueStatus) => {
      this.handleQueueUpdate(data)
    })

    webSocketService.subscribe('system_load', (data: SystemLoad) => {
      this.handleSystemUpdate(data)
    })

    webSocketService.subscribe('job_metrics', (data: { jobId: string; metrics: JobMetrics }) => {
      this.handleMetricsUpdate(data.jobId, data.metrics)
    })
  }

  /**
   * Setup periodic updates for metrics calculation
   */
  private setupPeriodicUpdates(): void {
    // Update system metrics every 30 seconds
    setInterval(() => {
      this.updateSystemMetrics()
    }, 30000)

    // Clean up old completed jobs every 5 minutes
    setInterval(() => {
      this.cleanupOldJobs()
    }, 5 * 60 * 1000)
  }

  /**
   * Subscribe to progress updates for a specific job
   */
  subscribeToProgress(jobId: string, callback: ProgressCallback): () => void {
    if (!this.progressCallbacks.has(jobId)) {
      this.progressCallbacks.set(jobId, [])
    }
    
    this.progressCallbacks.get(jobId)!.push(callback)
    
    productionService.debug('Subscribed to progress updates', { jobId }, {
      component: 'RealTimeTracking',
      action: 'subscribe_progress'
    })

    // Send current progress if available
    const currentProgress = this.getCurrentProgress(jobId)
    if (currentProgress) {
      callback(currentProgress)
    }

    // Return unsubscribe function
    return () => {
      const callbacks = this.progressCallbacks.get(jobId)
      if (callbacks) {
        const index = callbacks.indexOf(callback)
        if (index > -1) {
          callbacks.splice(index, 1)
        }
        if (callbacks.length === 0) {
          this.progressCallbacks.delete(jobId)
        }
      }
    }
  }

  /**
   * Subscribe to job metrics
   */
  subscribeToMetrics(jobId: string, callback: MetricsCallback): () => void {
    if (!this.metricsCallbacks.has(jobId)) {
      this.metricsCallbacks.set(jobId, [])
    }
    
    this.metricsCallbacks.get(jobId)!.push(callback)
    
    // Send current metrics if available
    const currentMetrics = this.jobMetrics.get(jobId)
    if (currentMetrics) {
      callback(currentMetrics)
    }

    return () => {
      const callbacks = this.metricsCallbacks.get(jobId)
      if (callbacks) {
        const index = callbacks.indexOf(callback)
        if (index > -1) {
          callbacks.splice(index, 1)
        }
        if (callbacks.length === 0) {
          this.metricsCallbacks.delete(jobId)
        }
      }
    }
  }

  /**
   * Subscribe to queue status updates
   */
  subscribeToQueue(callback: QueueCallback): () => void {
    this.queueCallbacks.push(callback)
    
    return () => {
      const index = this.queueCallbacks.indexOf(callback)
      if (index > -1) {
        this.queueCallbacks.splice(index, 1)
      }
    }
  }

  /**
   * Subscribe to system load updates
   */
  subscribeToSystem(callback: SystemCallback): () => void {
    this.systemCallbacks.push(callback)
    
    // Send current system load
    callback(this.systemLoad)
    
    return () => {
      const index = this.systemCallbacks.indexOf(callback)
      if (index > -1) {
        this.systemCallbacks.splice(index, 1)
      }
    }
  }

  /**
   * Start tracking a new job
   */
  startJob(jobId: string, type: ProgressUpdate['type'], totalSteps: number = 1): void {
    const metrics: JobMetrics = {
      startTime: new Date(),
      stepsCompleted: 0,
      totalSteps,
      averageStepDuration: 0,
      estimatedCompletion: new Date(Date.now() + 60000), // Default 1 minute
      throughput: 0
    }
    
    this.jobMetrics.set(jobId, metrics)
    this.activeJobs.add(jobId)
    
    productionService.info('Job started', { jobId, type, totalSteps }, {
      component: 'RealTimeTracking',
      action: 'start_job'
    })

    // Send initial progress update
    const initialUpdate: ProgressUpdate = {
      jobId,
      type,
      status: 'queued',
      progress: 0,
      stage: 'Initializing',
      message: 'Job queued for processing',
      currentStep: 0,
      totalSteps,
      timestamp: new Date()
    }
    
    this.handleProgressUpdate(initialUpdate)
  }

  /**
   * Update job progress
   */
  updateProgress(
    jobId: string,
    progress: number,
    stage: string,
    message: string,
    metadata?: Record<string, any>
  ): void {
    const metrics = this.jobMetrics.get(jobId)
    if (!metrics) {
      productionService.warn('Attempted to update progress for unknown job', { jobId })
      return
    }

    // Update metrics
    const currentStep = Math.floor((progress / 100) * metrics.totalSteps)
    if (currentStep > metrics.stepsCompleted) {
      const stepDuration = (Date.now() - metrics.startTime.getTime()) / currentStep
      metrics.averageStepDuration = stepDuration
      metrics.stepsCompleted = currentStep
      
      // Calculate estimated completion
      const remainingSteps = metrics.totalSteps - currentStep
      const estimatedRemainingTime = remainingSteps * stepDuration
      metrics.estimatedCompletion = new Date(Date.now() + estimatedRemainingTime)
      
      // Calculate throughput
      const elapsedMinutes = (Date.now() - metrics.startTime.getTime()) / (1000 * 60)
      metrics.throughput = currentStep / Math.max(elapsedMinutes, 0.1)
    }

    const update: ProgressUpdate = {
      jobId,
      type: this.getJobType(jobId),
      status: progress >= 100 ? 'completed' : 'processing',
      progress,
      stage,
      message,
      estimatedTimeRemaining: progress < 100 ? 
        Math.max(0, metrics.estimatedCompletion.getTime() - Date.now()) : undefined,
      currentStep,
      totalSteps: metrics.totalSteps,
      metadata,
      timestamp: new Date()
    }

    this.handleProgressUpdate(update)
    
    // Notify metrics subscribers
    this.notifyMetricsSubscribers(jobId, metrics)
  }

  /**
   * Complete a job
   */
  completeJob(jobId: string, message: string = 'Job completed successfully'): void {
    const metrics = this.jobMetrics.get(jobId)
    if (metrics) {
      metrics.endTime = new Date()
      metrics.duration = metrics.endTime.getTime() - metrics.startTime.getTime()
      metrics.stepsCompleted = metrics.totalSteps
    }

    const update: ProgressUpdate = {
      jobId,
      type: this.getJobType(jobId),
      status: 'completed',
      progress: 100,
      stage: 'Completed',
      message,
      currentStep: metrics?.totalSteps || 1,
      totalSteps: metrics?.totalSteps || 1,
      timestamp: new Date()
    }

    this.handleProgressUpdate(update)
    this.activeJobs.delete(jobId)
    this.completedJobs.set(jobId, update)
    
    productionService.info('Job completed', { 
      jobId, 
      duration: metrics?.duration,
      throughput: metrics?.throughput 
    }, {
      component: 'RealTimeTracking',
      action: 'complete_job',
      duration: metrics?.duration
    })
  }

  /**
   * Fail a job
   */
  failJob(jobId: string, error: string, metadata?: Record<string, any>): void {
    const metrics = this.jobMetrics.get(jobId)
    if (metrics) {
      metrics.endTime = new Date()
      metrics.duration = metrics.endTime.getTime() - metrics.startTime.getTime()
    }

    const update: ProgressUpdate = {
      jobId,
      type: this.getJobType(jobId),
      status: 'failed',
      progress: 0,
      stage: 'Failed',
      message: error,
      metadata,
      timestamp: new Date()
    }

    this.handleProgressUpdate(update)
    this.activeJobs.delete(jobId)
    
    productionService.error('Job failed', { 
      jobId, 
      error,
      duration: metrics?.duration 
    }, {
      component: 'RealTimeTracking',
      action: 'fail_job',
      duration: metrics?.duration
    })
  }

  /**
   * Cancel a job
   */
  cancelJob(jobId: string): void {
    const update: ProgressUpdate = {
      jobId,
      type: this.getJobType(jobId),
      status: 'cancelled',
      progress: 0,
      stage: 'Cancelled',
      message: 'Job cancelled by user',
      timestamp: new Date()
    }

    this.handleProgressUpdate(update)
    this.activeJobs.delete(jobId)
    this.jobMetrics.delete(jobId)
    
    productionService.info('Job cancelled', { jobId }, {
      component: 'RealTimeTracking',
      action: 'cancel_job'
    })
  }

  /**
   * Get current progress for a job
   */
  getCurrentProgress(jobId: string): ProgressUpdate | null {
    return this.completedJobs.get(jobId) || null
  }

  /**
   * Get job metrics
   */
  getJobMetrics(jobId: string): JobMetrics | null {
    return this.jobMetrics.get(jobId) || null
  }

  /**
   * Get all active jobs
   */
  getActiveJobs(): string[] {
    return Array.from(this.activeJobs)
  }

  /**
   * Get system load
   */
  getSystemLoad(): SystemLoad {
    return { ...this.systemLoad }
  }

  /**
   * Handle progress update from WebSocket
   */
  private handleProgressUpdate(update: ProgressUpdate): void {
    // Store the update
    if (update.status === 'completed' || update.status === 'failed' || update.status === 'cancelled') {
      this.completedJobs.set(update.jobId, update)
      this.activeJobs.delete(update.jobId)
    }

    // Notify subscribers
    const callbacks = this.progressCallbacks.get(update.jobId)
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(update)
        } catch (error) {
          productionService.error('Error in progress callback', {
            jobId: update.jobId,
            error: (error as Error).message
          })
        }
      })
    }
  }

  /**
   * Handle queue update from WebSocket
   */
  private handleQueueUpdate(status: QueueStatus): void {
    this.queueCallbacks.forEach(callback => {
      try {
        callback(status)
      } catch (error) {
        productionService.error('Error in queue callback', {
          error: (error as Error).message
        })
      }
    })
  }

  /**
   * Handle system update from WebSocket
   */
  private handleSystemUpdate(load: SystemLoad): void {
    this.systemLoad = load
    
    this.systemCallbacks.forEach(callback => {
      try {
        callback(load)
      } catch (error) {
        productionService.error('Error in system callback', {
          error: (error as Error).message
        })
      }
    })
  }

  /**
   * Handle metrics update
   */
  private handleMetricsUpdate(jobId: string, metrics: JobMetrics): void {
    this.jobMetrics.set(jobId, metrics)
    this.notifyMetricsSubscribers(jobId, metrics)
  }

  /**
   * Notify metrics subscribers
   */
  private notifyMetricsSubscribers(jobId: string, metrics: JobMetrics): void {
    const callbacks = this.metricsCallbacks.get(jobId)
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(metrics)
        } catch (error) {
          productionService.error('Error in metrics callback', {
            jobId,
            error: (error as Error).message
          })
        }
      })
    }
  }

  /**
   * Get job type (fallback for unknown jobs)
   */
  private getJobType(jobId: string): ProgressUpdate['type'] {
    // Try to infer from job ID or return default
    if (jobId.includes('clip')) return 'clip_generation'
    if (jobId.includes('analysis')) return 'video_analysis'
    if (jobId.includes('upload')) return 'upload'
    return 'processing'
  }

  /**
   * Update system metrics
   */
  private updateSystemMetrics(): void {
    const activeJobsCount = this.activeJobs.size
    const completedJobsCount = this.completedJobs.size
    
    // Calculate average job duration from completed jobs
    const completedJobsArray = Array.from(this.completedJobs.values())
    const jobsWithDuration = completedJobsArray.filter(job => {
      const metrics = this.jobMetrics.get(job.jobId)
      return metrics && metrics.duration
    })
    
    const averageJobDuration = jobsWithDuration.length > 0 ?
      jobsWithDuration.reduce((sum, job) => {
        const metrics = this.jobMetrics.get(job.jobId)!
        return sum + (metrics.duration || 0)
      }, 0) / jobsWithDuration.length : 0

    // Count failed jobs
    const failedJobsCount = completedJobsArray.filter(job => job.status === 'failed').length

    // Get memory usage if available
    const memory = (performance as any).memory
    const memoryUsage = memory ? (memory.usedJSHeapSize / memory.totalJSHeapSize) * 100 : 0

    this.systemLoad = {
      cpuUsage: 0, // Would need to be calculated server-side
      memoryUsage,
      activeJobs: activeJobsCount,
      queuedJobs: 0, // Would come from server
      completedJobs: completedJobsCount,
      failedJobs: failedJobsCount,
      averageJobDuration
    }
  }

  /**
   * Clean up old completed jobs
   */
  private cleanupOldJobs(): void {
    const oneHourAgo = Date.now() - (60 * 60 * 1000)
    
    for (const [jobId, update] of this.completedJobs.entries()) {
      if (update.timestamp.getTime() < oneHourAgo) {
        this.completedJobs.delete(jobId)
        this.jobMetrics.delete(jobId)
        this.progressCallbacks.delete(jobId)
        this.metricsCallbacks.delete(jobId)
      }
    }
    
    productionService.debug('Cleaned up old jobs', {
      remainingJobs: this.completedJobs.size
    }, {
      component: 'RealTimeTracking',
      action: 'cleanup_jobs'
    })
  }

  /**
   * Get job statistics
   */
  getJobStatistics(): {
    total: number
    active: number
    completed: number
    failed: number
    cancelled: number
    averageDuration: number
    successRate: number
  } {
    const completedJobsArray = Array.from(this.completedJobs.values())
    const total = completedJobsArray.length + this.activeJobs.size
    const completed = completedJobsArray.filter(job => job.status === 'completed').length
    const failed = completedJobsArray.filter(job => job.status === 'failed').length
    const cancelled = completedJobsArray.filter(job => job.status === 'cancelled').length
    
    const jobsWithDuration = completedJobsArray.filter(job => {
      const metrics = this.jobMetrics.get(job.jobId)
      return metrics && metrics.duration
    })
    
    const averageDuration = jobsWithDuration.length > 0 ?
      jobsWithDuration.reduce((sum, job) => {
        const metrics = this.jobMetrics.get(job.jobId)!
        return sum + (metrics.duration || 0)
      }, 0) / jobsWithDuration.length : 0
    
    const successRate = total > 0 ? (completed / total) * 100 : 0
    
    return {
      total,
      active: this.activeJobs.size,
      completed,
      failed,
      cancelled,
      averageDuration,
      successRate
    }
  }

  /**
   * Export job data for analysis
   */
  exportJobData(): {
    activeJobs: string[]
    completedJobs: ProgressUpdate[]
    metrics: Record<string, JobMetrics>
    systemLoad: SystemLoad
    statistics: ReturnType<typeof this.getJobStatistics>
  } {
    return {
      activeJobs: Array.from(this.activeJobs),
      completedJobs: Array.from(this.completedJobs.values()),
      metrics: Object.fromEntries(this.jobMetrics),
      systemLoad: this.systemLoad,
      statistics: this.getJobStatistics()
    }
  }
}

// Create singleton instance
export const realTimeTrackingService = new RealTimeTrackingService()

// Export types
export type {
  ProgressUpdate,
  JobMetrics,
  QueueStatus,
  SystemLoad,
  ProgressCallback,
  MetricsCallback,
  QueueCallback,
  SystemCallback
}

// React hooks for easy integration
export const useJobProgress = (jobId: string) => {
  const [progress, setProgress] = React.useState<ProgressUpdate | null>(null)
  
  React.useEffect(() => {
    const unsubscribe = realTimeTrackingService.subscribeToProgress(jobId, setProgress)
    return unsubscribe
  }, [jobId])
  
  return progress
}

export const useJobMetrics = (jobId: string) => {
  const [metrics, setMetrics] = React.useState<JobMetrics | null>(null)
  
  React.useEffect(() => {
    const unsubscribe = realTimeTrackingService.subscribeToMetrics(jobId, setMetrics)
    return unsubscribe
  }, [jobId])
  
  return metrics
}

export const useSystemLoad = () => {
  const [systemLoad, setSystemLoad] = React.useState<SystemLoad>(realTimeTrackingService.getSystemLoad())
  
  React.useEffect(() => {
    const unsubscribe = realTimeTrackingService.subscribeToSystem(setSystemLoad)
    return unsubscribe
  }, [])
  
  return systemLoad
}

// Import React for hooks
import React from 'react'