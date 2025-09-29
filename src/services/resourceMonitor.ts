interface ResourceMetrics {
  memoryUsage: number // MB
  activeUploads: number
  queuedUploads: number
  networkSpeed: number // KB/s
  lastUpdate: number
}

interface UploadTask {
  id: string
  fileName: string
  fileSize: number
  startTime: number
  lastActivity: number
  status: 'queued' | 'uploading' | 'processing' | 'completed' | 'failed'
  retryCount: number
}

class ResourceMonitorService {
  private readonly MAX_CONCURRENT_UPLOADS = 3
  private readonly MAX_MEMORY_USAGE = 512 // MB
  private readonly CLEANUP_INTERVAL = 30000 // 30 seconds
  private readonly TASK_TIMEOUT = 300000 // 5 minutes
  private readonly MAX_QUEUE_SIZE = 10
  
  private metrics: ResourceMetrics = {
    memoryUsage: 0,
    activeUploads: 0,
    queuedUploads: 0,
    networkSpeed: 0,
    lastUpdate: Date.now()
  }
  
  private uploadTasks = new Map<string, UploadTask>()
  private uploadQueue: string[] = []
  private cleanupInterval: NodeJS.Timeout | null = null
  private networkSpeedSamples: number[] = []
  
  constructor() {
    this.startMonitoring()
  }
  
  /**
   * Start resource monitoring
   */
  private startMonitoring(): void {
    this.cleanupInterval = setInterval(() => {
      this.updateMetrics()
      this.cleanupStaleUploads()
      this.processQueue()
    }, this.CLEANUP_INTERVAL)
    
    // Monitor memory usage if available
    if ('memory' in performance) {
      this.monitorMemoryUsage()
    }
  }
  
  /**
   * Stop resource monitoring
   */
  stopMonitoring(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval)
      this.cleanupInterval = null
    }
  }
  
  /**
   * Register a new upload task
   */
  registerUpload(fileName: string, fileSize: number): string {
    const taskId = this.generateTaskId()
    const task: UploadTask = {
      id: taskId,
      fileName,
      fileSize,
      startTime: Date.now(),
      lastActivity: Date.now(),
      status: 'queued',
      retryCount: 0
    }
    
    this.uploadTasks.set(taskId, task)
    
    // Check if we can start immediately or need to queue
    if (this.canStartUpload()) {
      this.startUpload(taskId)
    } else {
      this.queueUpload(taskId)
    }
    
    this.updateMetrics()
    return taskId
  }
  
  /**
   * Update upload task status
   */
  updateUploadStatus(taskId: string, status: UploadTask['status'], progress?: number): void {
    const task = this.uploadTasks.get(taskId)
    if (!task) return
    
    task.status = status
    task.lastActivity = Date.now()
    
    if (status === 'completed' || status === 'failed') {
      this.completeUpload(taskId)
    }
    
    this.updateMetrics()
  }
  
  /**
   * Update network speed measurement
   */
  updateNetworkSpeed(bytesTransferred: number, timeMs: number): void {
    if (timeMs > 0) {
      const speedKBps = (bytesTransferred / 1024) / (timeMs / 1000)
      this.networkSpeedSamples.push(speedKBps)
      
      // Keep only last 10 samples
      if (this.networkSpeedSamples.length > 10) {
        this.networkSpeedSamples.shift()
      }
      
      // Calculate average speed
      this.metrics.networkSpeed = this.networkSpeedSamples.reduce((a, b) => a + b, 0) / this.networkSpeedSamples.length
    }
  }
  
  /**
   * Check if system can handle new upload
   */
  canStartUpload(): boolean {
    const activeUploads = Array.from(this.uploadTasks.values())
      .filter(task => task.status === 'uploading' || task.status === 'processing').length
    
    return activeUploads < this.MAX_CONCURRENT_UPLOADS && 
           this.metrics.memoryUsage < this.MAX_MEMORY_USAGE &&
           this.uploadQueue.length < this.MAX_QUEUE_SIZE
  }
  
  /**
   * Get system resource status
   */
  getResourceStatus(): {
    canUpload: boolean
    reason?: string
    metrics: ResourceMetrics
    activeTasks: UploadTask[]
    queueLength: number
  } {
    const canUpload = this.canStartUpload()
    let reason: string | undefined
    
    if (!canUpload) {
      if (this.metrics.activeUploads >= this.MAX_CONCURRENT_UPLOADS) {
        reason = 'Maximum concurrent uploads reached'
      } else if (this.metrics.memoryUsage >= this.MAX_MEMORY_USAGE) {
        reason = 'Memory usage too high'
      } else if (this.uploadQueue.length >= this.MAX_QUEUE_SIZE) {
        reason = 'Upload queue is full'
      }
    }
    
    return {
      canUpload,
      reason,
      metrics: { ...this.metrics },
      activeTasks: Array.from(this.uploadTasks.values())
        .filter(task => task.status === 'uploading' || task.status === 'processing'),
      queueLength: this.uploadQueue.length
    }
  }
  
  /**
   * Force cleanup of resources
   */
  forceCleanup(): void {
    // Cancel stale uploads
    const now = Date.now()
    const staleTasks: string[] = []
    
    this.uploadTasks.forEach((task, id) => {
      if (now - task.lastActivity > this.TASK_TIMEOUT) {
        staleTasks.push(id)
      }
    })
    
    staleTasks.forEach(id => {
      this.cancelUpload(id)
    })
    
    // Clear queue if needed
    if (this.uploadQueue.length > this.MAX_QUEUE_SIZE) {
      this.uploadQueue.splice(this.MAX_QUEUE_SIZE)
    }
    
    // Force garbage collection if available
    if ('gc' in window && typeof (window as any).gc === 'function') {
      try {
        (window as any).gc()
      } catch (error) {
        console.warn('Failed to trigger garbage collection:', error)
      }
    }
    
    this.updateMetrics()
  }
  
  /**
   * Cancel an upload task
   */
  cancelUpload(taskId: string): void {
    const task = this.uploadTasks.get(taskId)
    if (!task) return
    
    // Remove from queue if queued
    const queueIndex = this.uploadQueue.indexOf(taskId)
    if (queueIndex !== -1) {
      this.uploadQueue.splice(queueIndex, 1)
    }
    
    // Update task status
    task.status = 'failed'
    
    // Clean up task
    this.uploadTasks.delete(taskId)
    this.updateMetrics()
    
    // Process next in queue
    this.processQueue()
  }
  
  /**
   * Get upload task info
   */
  getUploadTask(taskId: string): UploadTask | undefined {
    return this.uploadTasks.get(taskId)
  }
  
  /**
   * Get all active uploads
   */
  getActiveUploads(): UploadTask[] {
    return Array.from(this.uploadTasks.values())
      .filter(task => task.status === 'uploading' || task.status === 'processing')
  }
  
  /**
   * Private methods
   */
  
  private generateTaskId(): string {
    return `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
  
  private startUpload(taskId: string): void {
    const task = this.uploadTasks.get(taskId)
    if (!task) return
    
    task.status = 'uploading'
    task.lastActivity = Date.now()
  }
  
  private queueUpload(taskId: string): void {
    if (!this.uploadQueue.includes(taskId)) {
      this.uploadQueue.push(taskId)
    }
  }
  
  private completeUpload(taskId: string): void {
    const task = this.uploadTasks.get(taskId)
    if (!task) return
    
    // Remove from active tasks after a delay to allow for cleanup
    setTimeout(() => {
      this.uploadTasks.delete(taskId)
      this.updateMetrics()
    }, 5000)
    
    // Process next in queue
    this.processQueue()
  }
  
  private processQueue(): void {
    while (this.uploadQueue.length > 0 && this.canStartUpload()) {
      const nextTaskId = this.uploadQueue.shift()
      if (nextTaskId && this.uploadTasks.has(nextTaskId)) {
        this.startUpload(nextTaskId)
      }
    }
  }
  
  private updateMetrics(): void {
    const now = Date.now()
    const activeTasks = Array.from(this.uploadTasks.values())
    
    this.metrics = {
      memoryUsage: this.estimateMemoryUsage(),
      activeUploads: activeTasks.filter(task => 
        task.status === 'uploading' || task.status === 'processing'
      ).length,
      queuedUploads: this.uploadQueue.length,
      networkSpeed: this.metrics.networkSpeed, // Keep current value
      lastUpdate: now
    }
  }
  
  private cleanupStaleUploads(): void {
    const now = Date.now()
    const staleTasks: string[] = []
    
    this.uploadTasks.forEach((task, id) => {
      if (now - task.lastActivity > this.TASK_TIMEOUT) {
        console.warn(`Cleaning up stale upload task: ${task.fileName}`)
        staleTasks.push(id)
      }
    })
    
    staleTasks.forEach(id => {
      this.cancelUpload(id)
    })
  }
  
  private estimateMemoryUsage(): number {
    // Estimate memory usage based on active uploads and file sizes
    let estimatedUsage = 0
    
    this.uploadTasks.forEach(task => {
      if (task.status === 'uploading' || task.status === 'processing') {
        // Estimate 10% of file size is held in memory during upload
        estimatedUsage += (task.fileSize * 0.1) / (1024 * 1024) // Convert to MB
      }
    })
    
    // Add base application memory usage estimate
    estimatedUsage += 50 // Base 50MB
    
    return Math.round(estimatedUsage)
  }
  
  private monitorMemoryUsage(): void {
    if ('memory' in performance) {
      setInterval(() => {
        try {
          const memInfo = (performance as any).memory
          if (memInfo && memInfo.usedJSHeapSize) {
            this.metrics.memoryUsage = Math.round(memInfo.usedJSHeapSize / (1024 * 1024))
          }
        } catch (error) {
          // Fallback to estimation
          this.metrics.memoryUsage = this.estimateMemoryUsage()
        }
      }, 10000) // Update every 10 seconds
    }
  }
}

export const resourceMonitor = new ResourceMonitorService()
export type { ResourceMetrics, UploadTask }