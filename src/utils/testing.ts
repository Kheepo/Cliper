import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { vi, expect, describe, it, beforeEach, afterEach } from 'vitest'
import '@testing-library/jest-dom'
import { toast } from 'sonner'
import { apiService } from '../services/api'
import { webSocketService } from '../services/websocket'
import { productionService } from '../services/production'
import { realTimeTrackingService } from '../services/realTimeTracking'
import { performanceService } from '../services/performance'
import { errorHandler } from '../services/errorHandling'

// Mock data generators
export const mockVideoAnalysis = () => ({
  id: `analysis_${Date.now()}`,
  videoId: `video_${Date.now()}`,
  status: 'completed' as const,
  duration: 120,
  segments: [
    {
      id: `segment_${Date.now()}_1`,
      startTime: 0,
      endTime: 30,
      title: 'Opening Hook',
      description: 'Engaging introduction that captures attention',
      viralScore: 85,
      platformScores: {
        tiktok: 90,
        youtube: 80,
        instagram: 85
      },
      keyMoments: ['0:05 - Hook statement', '0:15 - Visual transition'],
      suggestedTitles: ['Amazing Opening!', 'You Won\'t Believe This'],
      hashtags: ['#viral', '#amazing', '#trending'],
      transcript: 'Welcome to this incredible journey...'
    },
    {
      id: `segment_${Date.now()}_2`,
      startTime: 30,
      endTime: 60,
      title: 'Main Content',
      description: 'Core message delivery with strong engagement',
      viralScore: 78,
      platformScores: {
        tiktok: 75,
        youtube: 85,
        instagram: 75
      },
      keyMoments: ['0:35 - Key insight', '0:50 - Call to action'],
      suggestedTitles: ['The Secret Revealed', 'Game Changer'],
      hashtags: ['#secret', '#tips', '#lifehack'],
      transcript: 'Here\'s the main point you need to know...'
    }
  ],
  overallMetrics: {
    averageViralScore: 81.5,
    totalClips: 2,
    bestPlatform: 'tiktok' as const,
    estimatedViews: 50000,
    engagementRate: 12.5
  },
  processingTime: 45,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString()
})

export const mockHistoryItem = () => ({
  id: `history_${Date.now()}`,
  title: 'Test Video Analysis',
  status: 'completed' as const,
  uploadDate: new Date().toISOString(),
  duration: 120,
  fileSize: 50 * 1024 * 1024, // 50MB
  thumbnail: 'https://trae-api-sg.mchost.guru/api/ide/v1/text_to_image?prompt=video%20thumbnail&image_size=landscape_16_9',
  viralityScore: 85,
  clipsGenerated: 3,
  totalViews: 25000,
  engagement: 12.5,
  processingTime: 45,
  tags: ['viral', 'trending'],
  analysis: mockVideoAnalysis()
})

export const mockProgressUpdate = () => ({
  jobId: `job_${Date.now()}`,
  type: 'clip_generation' as const,
  status: 'processing' as const,
  progress: 45,
  stage: 'Analyzing segments',
  message: 'Processing video segments for optimal clips',
  estimatedTimeRemaining: 30000,
  currentStep: 2,
  totalSteps: 5,
  timestamp: new Date()
})

export const mockSystemLoad = () => ({
  status: 'healthy' as const,
  uptime: 3600000, // 1 hour
  memoryUsage: {
    used: 512 * 1024 * 1024, // 512MB
    total: 2 * 1024 * 1024 * 1024, // 2GB
    percentage: 25
  },
  errorRate: 2.5,
  responseTime: {
    avg: 250,
    p95: 500,
    p99: 1000
  },
  activeUsers: 15,
  cacheHitRate: 85
})

// Service mocks
export const createApiServiceMock = () => {
  const mock = {
    uploadVideo: vi.fn().mockResolvedValue({ id: 'video_123', status: 'uploaded' }),
    analyzeVideo: vi.fn().mockResolvedValue(mockVideoAnalysis()),
    getAnalysisResult: vi.fn().mockResolvedValue(mockVideoAnalysis()),
    generateClips: vi.fn().mockResolvedValue({ jobId: 'job_123', status: 'started' }),
    getClips: vi.fn().mockResolvedValue([]),
    downloadClip: vi.fn().mockResolvedValue(new Blob()),
    getUserHistory: vi.fn().mockResolvedValue([mockHistoryItem()]),
    getUserHistoryPaginated: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1 }),
    generatePreview: vi.fn().mockResolvedValue({ previewUrl: 'http://example.com/preview.mp4' }),
    getShareUrl: vi.fn().mockResolvedValue({ shareUrl: 'http://example.com/share/123' }),
    analyzeVideoSegments: vi.fn().mockResolvedValue({ segments: [], analysis: {} }),
    optimizeClip: vi.fn().mockResolvedValue({ optimizedClip: {} }),
    getClipGenerationStatus: vi.fn().mockResolvedValue({ status: 'completed' }),
    cancelClipGeneration: vi.fn().mockResolvedValue({ cancelled: true }),
    getClipAnalytics: vi.fn().mockResolvedValue({ views: 1000, engagement: 5.5 })
  }
  
  return mock
}

export const createWebSocketServiceMock = () => {
  const subscribers = new Map<string, Function[]>()
  
  const mock = {
    connect: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn(),
    subscribe: vi.fn().mockImplementation((event: string, callback: Function) => {
      if (!subscribers.has(event)) {
        subscribers.set(event, [])
      }
      subscribers.get(event)!.push(callback)
      
      return () => {
        const callbacks = subscribers.get(event)
        if (callbacks) {
          const index = callbacks.indexOf(callback)
          if (index > -1) {
            callbacks.splice(index, 1)
          }
        }
      }
    }),
    emit: vi.fn(),
    isConnected: vi.fn().mockReturnValue(true),
    // Test helper to simulate events
    simulateEvent: (event: string, data: any) => {
      const callbacks = subscribers.get(event)
      if (callbacks) {
        callbacks.forEach(callback => callback(data))
      }
    }
  }
  
  return mock
}

export const createProductionServiceMock = () => ({
  log: vi.fn(),
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  critical: vi.fn(),
  logApiCall: vi.fn(),
  logUserAction: vi.fn(),
  logPerformance: vi.fn(),
  getSystemHealth: vi.fn().mockReturnValue(mockSystemLoad()),
  getLogs: vi.fn().mockReturnValue([]),
  exportLogs: vi.fn().mockReturnValue(''),
  clearLogs: vi.fn(),
  checkApiRateLimit: vi.fn().mockReturnValue(true),
  checkUploadRateLimit: vi.fn().mockReturnValue(true),
  getRateLimitStatus: vi.fn().mockReturnValue({})
})

export const createRealTimeTrackingServiceMock = () => ({
  subscribeToProgress: vi.fn().mockReturnValue(() => {}),
  subscribeToMetrics: vi.fn().mockReturnValue(() => {}),
  subscribeToQueue: vi.fn().mockReturnValue(() => {}),
  subscribeToSystem: vi.fn().mockReturnValue(() => {}),
  startJob: vi.fn(),
  updateProgress: vi.fn(),
  completeJob: vi.fn(),
  failJob: vi.fn(),
  cancelJob: vi.fn(),
  getCurrentProgress: vi.fn().mockReturnValue(mockProgressUpdate()),
  getJobMetrics: vi.fn().mockReturnValue(null),
  getActiveJobs: vi.fn().mockReturnValue([]),
  getSystemLoad: vi.fn().mockReturnValue(mockSystemLoad()),
  getJobStatistics: vi.fn().mockReturnValue({
    total: 10,
    active: 2,
    completed: 7,
    failed: 1,
    cancelled: 0,
    averageDuration: 45000,
    successRate: 70
  }),
  exportJobData: vi.fn().mockReturnValue({
    activeJobs: [],
    completedJobs: [],
    metrics: {},
    systemLoad: mockSystemLoad(),
    statistics: {}
  })
})

export const createPerformanceServiceMock = () => ({
  getCachedData: vi.fn().mockReturnValue(null),
  setCachedData: vi.fn(),
  clearCache: vi.fn(),
  wrapApiCall: vi.fn().mockImplementation((fn) => fn),
  preloadComponent: vi.fn().mockResolvedValue(undefined),
  measurePerformance: vi.fn().mockReturnValue(0),
  getPerformanceMetrics: vi.fn().mockReturnValue({
    renderTime: 16,
    cacheHitRate: 85,
    apiResponseTime: 250,
    memoryUsage: 50
  }),
  debounce: vi.fn().mockImplementation((fn) => fn),
  throttle: vi.fn().mockImplementation((fn) => fn)
})

export const createErrorHandlerMock = () => ({
  handleError: vi.fn(),
  handleApiError: vi.fn(),
  handleValidationError: vi.fn(),
  showUserFriendlyError: vi.fn(),
  retryOperation: vi.fn().mockResolvedValue(undefined),
  getErrorStats: vi.fn().mockReturnValue({
    totalErrors: 5,
    errorsByType: { api: 3, validation: 1, network: 1 },
    recentErrors: []
  }),
  clearErrorStats: vi.fn()
})

// Test utilities
export const setupMocks = () => {
  const mocks = {
    apiService: createApiServiceMock(),
    webSocketService: createWebSocketServiceMock(),
    productionService: createProductionServiceMock(),
    realTimeTrackingService: createRealTimeTrackingServiceMock(),
    performanceService: createPerformanceServiceMock(),
    errorHandler: createErrorHandlerMock(),
    toast: {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
      loading: vi.fn().mockReturnValue({ dismiss: vi.fn() })
    }
  }
  
  // Mock the services
  vi.mocked(apiService).uploadVideo = mocks.apiService.uploadVideo
  vi.mocked(apiService).analyzeVideoSegments = mocks.apiService.analyzeVideoSegments
  vi.mocked(apiService).getAnalysisResult = mocks.apiService.getAnalysisResult
  vi.mocked(apiService).generateClips = mocks.apiService.generateClips
  vi.mocked(apiService).getClips = mocks.apiService.getClips
  vi.mocked(apiService).downloadClip = mocks.apiService.downloadClip
  vi.mocked(apiService).getUserHistoryPaginated = mocks.apiService.getUserHistoryPaginated
  
  // Mock toast
  vi.mocked(toast).success = mocks.toast.success
  vi.mocked(toast).error = mocks.toast.error
  vi.mocked(toast).info = mocks.toast.info
  vi.mocked(toast).loading = mocks.toast.loading
  
  return mocks
}

export const cleanupMocks = () => {
  vi.clearAllMocks()
  vi.resetAllMocks()
}

// Component testing utilities
export const renderWithProviders = (component: React.ReactElement) => {
  // In a real app, this would wrap with providers like Router, Theme, etc.
  return render(component)
}

export const waitForLoadingToFinish = async () => {
  await waitFor(() => {
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
  }, { timeout: 5000 })
}

export const simulateFileUpload = (input: HTMLInputElement, file: File) => {
  Object.defineProperty(input, 'files', {
    value: [file],
    writable: false
  })
  fireEvent.change(input)
}

export const createMockFile = (name: string = 'test.mp4', _size: number = 1024 * 1024) => {
  return new File(['mock content'], name, {
    type: 'video/mp4',
    lastModified: Date.now()
  })
}

// Validation utilities
export const validateVideoAnalysis = (analysis: any) => {
  expect(analysis).toHaveProperty('id')
  expect(analysis).toHaveProperty('videoId')
  expect(analysis).toHaveProperty('status')
  expect(analysis).toHaveProperty('segments')
  expect(analysis).toHaveProperty('overallMetrics')
  expect(Array.isArray(analysis.segments)).toBe(true)
  
  analysis.segments.forEach((segment: any) => {
    expect(segment).toHaveProperty('id')
    expect(segment).toHaveProperty('startTime')
    expect(segment).toHaveProperty('endTime')
    expect(segment).toHaveProperty('viralScore')
    expect(segment).toHaveProperty('platformScores')
    expect(typeof segment.viralScore).toBe('number')
    expect(segment.viralScore).toBeGreaterThanOrEqual(0)
    expect(segment.viralScore).toBeLessThanOrEqual(100)
  })
}

export const validateHistoryItem = (item: any) => {
  expect(item).toHaveProperty('id')
  expect(item).toHaveProperty('title')
  expect(item).toHaveProperty('status')
  expect(item).toHaveProperty('uploadDate')
  expect(item).toHaveProperty('duration')
  expect(item).toHaveProperty('viralityScore')
  expect(typeof item.viralityScore).toBe('number')
  expect(item.viralityScore).toBeGreaterThanOrEqual(0)
  expect(item.viralityScore).toBeLessThanOrEqual(100)
}

export const validateProgressUpdate = (update: any) => {
  expect(update).toHaveProperty('jobId')
  expect(update).toHaveProperty('type')
  expect(update).toHaveProperty('status')
  expect(update).toHaveProperty('progress')
  expect(update).toHaveProperty('stage')
  expect(update).toHaveProperty('message')
  expect(typeof update.progress).toBe('number')
  expect(update.progress).toBeGreaterThanOrEqual(0)
  expect(update.progress).toBeLessThanOrEqual(100)
}

// Performance testing utilities
export const measureRenderTime = async (renderFn: () => void) => {
  const start = performance.now()
  await act(async () => {
    renderFn()
  })
  const end = performance.now()
  return end - start
}

export const measureAsyncOperation = async (operation: () => Promise<any>) => {
  const start = performance.now()
  await operation()
  const end = performance.now()
  return end - start
}

// Error testing utilities
export const simulateNetworkError = () => {
  return new Error('Network request failed')
}

export const simulateApiError = (status: number = 500, message: string = 'Internal Server Error') => {
  const error = new Error(message) as any
  error.status = status
  error.response = {
    status,
    statusText: message,
    data: { error: message }
  }
  return error
}

export const simulateValidationError = (field: string, message: string) => {
  const error = new Error('Validation failed') as any
  error.type = 'validation'
  error.field = field
  error.message = message
  return error
}

// Integration testing utilities
export const createIntegrationTestSuite = (componentName: string, tests: (() => void)[]) => {
  describe(`${componentName} Integration Tests`, () => {
    beforeEach(() => {
      setupMocks()
    })
    
    afterEach(() => {
      cleanupMocks()
    })
    
    tests.forEach((test, index) => {
      it(`Integration test ${index + 1}`, test)
    })
  })
}

// Load testing utilities
export const simulateHighLoad = async (operations: (() => Promise<any>)[], concurrency: number = 10) => {
  const batches = []
  for (let i = 0; i < operations.length; i += concurrency) {
    batches.push(operations.slice(i, i + concurrency))
  }
  
  const results = []
  for (const batch of batches) {
    const batchResults = await Promise.allSettled(batch.map(op => op()))
    results.push(...batchResults)
  }
  
  return results
}

// Memory leak testing
export const checkForMemoryLeaks = () => {
  const initialMemory = (performance as any).memory?.usedJSHeapSize || 0
  
  return () => {
    // Force garbage collection if available
    if ((window as any).gc) {
      (window as any).gc()
    }
    
    const finalMemory = (performance as any).memory?.usedJSHeapSize || 0
    const memoryIncrease = finalMemory - initialMemory
    
    // Log memory usage for analysis
    console.log(`Memory usage: ${initialMemory} -> ${finalMemory} (${memoryIncrease > 0 ? '+' : ''}${memoryIncrease} bytes)`)
    
    return {
      initialMemory,
      finalMemory,
      memoryIncrease,
      potentialLeak: memoryIncrease > 1024 * 1024 // 1MB threshold
    }
  }
}

// Export React for component testing
import React from 'react'