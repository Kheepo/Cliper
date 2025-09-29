import { LRUCache } from 'lru-cache'

interface CacheConfig {
  maxSize: number
  ttl: number // Time to live in milliseconds
  staleWhileRevalidate?: number
}

interface PerformanceMetrics {
  componentRenderTime: Map<string, number[]>
  apiResponseTimes: Map<string, number[]>
  cacheHitRates: Map<string, { hits: number; misses: number }>
  memoryUsage: number[]
  bundleLoadTimes: Map<string, number>
}

interface LazyComponentConfig {
  componentPath: string
  chunkName?: string
  preload?: boolean
  prefetch?: boolean
}

class PerformanceService {
  private caches: Map<string, LRUCache<string, any>> = new Map()
  private metrics: PerformanceMetrics = {
    componentRenderTime: new Map(),
    apiResponseTimes: new Map(),
    cacheHitRates: new Map(),
    memoryUsage: [],
    bundleLoadTimes: new Map()
  }
  private observers: Map<string, PerformanceObserver> = new Map()
  private preloadedComponents: Set<string> = new Set()

  constructor() {
    this.setupDefaultCaches()
    this.setupPerformanceObservers()
    this.startMemoryMonitoring()
  }

  /**
   * Setup default cache instances
   */
  private setupDefaultCaches(): void {
    // API response cache
    this.createCache('api', {
      maxSize: 100,
      ttl: 5 * 60 * 1000, // 5 minutes
      staleWhileRevalidate: 2 * 60 * 1000 // 2 minutes
    })

    // Video analysis cache
    this.createCache('analysis', {
      maxSize: 50,
      ttl: 30 * 60 * 1000, // 30 minutes
      staleWhileRevalidate: 10 * 60 * 1000
    })

    // User data cache
    this.createCache('user', {
      maxSize: 20,
      ttl: 15 * 60 * 1000, // 15 minutes
      staleWhileRevalidate: 5 * 60 * 1000
    })

    // Clip generation cache
    this.createCache('clips', {
      maxSize: 200,
      ttl: 60 * 60 * 1000, // 1 hour
      staleWhileRevalidate: 30 * 60 * 1000
    })

    // Static assets cache
    this.createCache('assets', {
      maxSize: 500,
      ttl: 24 * 60 * 60 * 1000, // 24 hours
      staleWhileRevalidate: 12 * 60 * 60 * 1000
    })
  }

  /**
   * Create a new cache instance
   */
  createCache(name: string, config: CacheConfig): void {
    const cache = new LRUCache<string, any>({
      max: config.maxSize,
      ttl: config.ttl,
      allowStale: !!config.staleWhileRevalidate,
      updateAgeOnGet: true,
      updateAgeOnHas: true
    })

    this.caches.set(name, cache)
    this.metrics.cacheHitRates.set(name, { hits: 0, misses: 0 })
  }

  /**
   * Get item from cache
   */
  getFromCache<T>(cacheName: string, key: string): T | undefined {
    const cache = this.caches.get(cacheName)
    if (!cache) return undefined

    const value = cache.get(key)
    const stats = this.metrics.cacheHitRates.get(cacheName)!
    
    if (value !== undefined) {
      stats.hits++
    } else {
      stats.misses++
    }

    return value
  }

  /**
   * Set item in cache
   */
  setInCache(cacheName: string, key: string, value: any, customTtl?: number): void {
    const cache = this.caches.get(cacheName)
    if (!cache) return

    if (customTtl) {
      cache.set(key, value, { ttl: customTtl })
    } else {
      cache.set(key, value)
    }
  }

  /**
   * Remove item from cache
   */
  removeFromCache(cacheName: string, key: string): void {
    const cache = this.caches.get(cacheName)
    if (cache) {
      cache.delete(key)
    }
  }

  /**
   * Clear entire cache
   */
  clearCache(cacheName: string): void {
    const cache = this.caches.get(cacheName)
    if (cache) {
      cache.clear()
    }
  }

  /**
   * Cached API request wrapper
   */
  async cachedApiRequest<T>(
    key: string,
    requestFn: () => Promise<T>,
    cacheName: string = 'api',
    customTtl?: number
  ): Promise<T> {
    // Try to get from cache first
    const cached = this.getFromCache<T>(cacheName, key)
    if (cached !== undefined) {
      return cached
    }

    // Make the request and cache the result
    const startTime = performance.now()
    try {
      const result = await requestFn()
      const endTime = performance.now()
      
      // Record API response time
      this.recordApiResponseTime(key, endTime - startTime)
      
      // Cache the result
      this.setInCache(cacheName, key, result, customTtl)
      
      return result
    } catch (error) {
      const endTime = performance.now()
      this.recordApiResponseTime(key, endTime - startTime)
      throw error
    }
  }

  /**
   * Preload component for better performance
   */
  async preloadComponent(config: LazyComponentConfig): Promise<void> {
    if (this.preloadedComponents.has(config.componentPath)) {
      return
    }

    try {
      const startTime = performance.now()
      
      // Dynamic import with webpack magic comments for chunk naming
      const chunkName = config.chunkName || config.componentPath.split('/').pop()
      await import(
        /* webpackChunkName: "[request]" */
        /* webpackPrefetch: true */
        config.componentPath
      )
      
      const endTime = performance.now()
      this.metrics.bundleLoadTimes.set(config.componentPath, endTime - startTime)
      this.preloadedComponents.add(config.componentPath)
      
    } catch (error) {
      console.warn(`Failed to preload component: ${config.componentPath}`, error)
    }
  }

  /**
   * Batch preload multiple components
   */
  async batchPreloadComponents(configs: LazyComponentConfig[]): Promise<void> {
    const preloadPromises = configs.map(config => this.preloadComponent(config))
    await Promise.allSettled(preloadPromises)
  }

  /**
   * Setup performance observers
   */
  private setupPerformanceObservers(): void {
    if (!('PerformanceObserver' in window)) {
      console.warn('PerformanceObserver not supported')
      return
    }

    // Observe navigation timing
    try {
      const navObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries()
        entries.forEach(entry => {
          if (entry.entryType === 'navigation') {
            const navEntry = entry as PerformanceNavigationTiming
            console.log('Navigation timing:', {
              domContentLoaded: navEntry.domContentLoadedEventEnd - navEntry.domContentLoadedEventStart,
              loadComplete: navEntry.loadEventEnd - navEntry.loadEventStart,
              firstPaint: navEntry.responseEnd - navEntry.requestStart
            })
          }
        })
      })
      navObserver.observe({ entryTypes: ['navigation'] })
      this.observers.set('navigation', navObserver)
    } catch (error) {
      console.warn('Failed to setup navigation observer:', error)
    }

    // Observe resource timing
    try {
      const resourceObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries()
        entries.forEach(entry => {
          if (entry.entryType === 'resource') {
            const resourceEntry = entry as PerformanceResourceTiming
            if (resourceEntry.name.includes('.js') || resourceEntry.name.includes('.css')) {
              this.metrics.bundleLoadTimes.set(
                resourceEntry.name,
                resourceEntry.responseEnd - resourceEntry.requestStart
              )
            }
          }
        })
      })
      resourceObserver.observe({ entryTypes: ['resource'] })
      this.observers.set('resource', resourceObserver)
    } catch (error) {
      console.warn('Failed to setup resource observer:', error)
    }

    // Observe largest contentful paint
    try {
      const lcpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries()
        const lastEntry = entries[entries.length - 1]
        console.log('Largest Contentful Paint:', lastEntry.startTime)
      })
      lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] })
      this.observers.set('lcp', lcpObserver)
    } catch (error) {
      console.warn('Failed to setup LCP observer:', error)
    }

    // Observe cumulative layout shift
    try {
      const clsObserver = new PerformanceObserver((list) => {
        let clsValue = 0
        const entries = list.getEntries()
        entries.forEach(entry => {
          if (!(entry as any).hadRecentInput) {
            clsValue += (entry as any).value
          }
        })
        if (clsValue > 0) {
          console.log('Cumulative Layout Shift:', clsValue)
        }
      })
      clsObserver.observe({ entryTypes: ['layout-shift'] })
      this.observers.set('cls', clsObserver)
    } catch (error) {
      console.warn('Failed to setup CLS observer:', error)
    }
  }

  /**
   * Record component render time
   */
  recordComponentRenderTime(componentName: string, renderTime: number): void {
    if (!this.metrics.componentRenderTime.has(componentName)) {
      this.metrics.componentRenderTime.set(componentName, [])
    }
    
    const times = this.metrics.componentRenderTime.get(componentName)!
    times.push(renderTime)
    
    // Keep only last 100 measurements
    if (times.length > 100) {
      times.shift()
    }
  }

  /**
   * Record API response time
   */
  private recordApiResponseTime(endpoint: string, responseTime: number): void {
    if (!this.metrics.apiResponseTimes.has(endpoint)) {
      this.metrics.apiResponseTimes.set(endpoint, [])
    }
    
    const times = this.metrics.apiResponseTimes.get(endpoint)!
    times.push(responseTime)
    
    // Keep only last 50 measurements
    if (times.length > 50) {
      times.shift()
    }
  }

  /**
   * Start memory usage monitoring
   */
  private startMemoryMonitoring(): void {
    if (!('memory' in performance)) {
      console.warn('Memory API not supported')
      return
    }

    const recordMemoryUsage = () => {
      const memory = (performance as any).memory
      if (memory) {
        this.metrics.memoryUsage.push(memory.usedJSHeapSize)
        
        // Keep only last 100 measurements
        if (this.metrics.memoryUsage.length > 100) {
          this.metrics.memoryUsage.shift()
        }
      }
    }

    // Record memory usage every 30 seconds
    setInterval(recordMemoryUsage, 30000)
    recordMemoryUsage() // Initial measurement
  }

  /**
   * Get performance metrics
   */
  getMetrics(): {
    cacheStats: Record<string, { hitRate: number; size: number }>
    avgComponentRenderTimes: Record<string, number>
    avgApiResponseTimes: Record<string, number>
    memoryTrend: number[]
    bundleLoadTimes: Record<string, number>
  } {
    const cacheStats: Record<string, { hitRate: number; size: number }> = {}
    
    // Calculate cache hit rates
    this.metrics.cacheHitRates.forEach((stats, cacheName) => {
      const total = stats.hits + stats.misses
      const hitRate = total > 0 ? (stats.hits / total) * 100 : 0
      const cache = this.caches.get(cacheName)
      
      cacheStats[cacheName] = {
        hitRate: Math.round(hitRate * 100) / 100,
        size: cache ? cache.size : 0
      }
    })

    // Calculate average render times
    const avgComponentRenderTimes: Record<string, number> = {}
    this.metrics.componentRenderTime.forEach((times, component) => {
      const avg = times.reduce((sum, time) => sum + time, 0) / times.length
      avgComponentRenderTimes[component] = Math.round(avg * 100) / 100
    })

    // Calculate average API response times
    const avgApiResponseTimes: Record<string, number> = {}
    this.metrics.apiResponseTimes.forEach((times, endpoint) => {
      const avg = times.reduce((sum, time) => sum + time, 0) / times.length
      avgApiResponseTimes[endpoint] = Math.round(avg * 100) / 100
    })

    // Convert bundle load times map to object
    const bundleLoadTimes: Record<string, number> = {}
    this.metrics.bundleLoadTimes.forEach((time, bundle) => {
      bundleLoadTimes[bundle] = Math.round(time * 100) / 100
    })

    return {
      cacheStats,
      avgComponentRenderTimes,
      avgApiResponseTimes,
      memoryTrend: [...this.metrics.memoryUsage],
      bundleLoadTimes
    }
  }

  /**
   * Optimize images for better performance
   */
  optimizeImage(src: string, options: {
    width?: number
    height?: number
    quality?: number
    format?: 'webp' | 'avif' | 'jpeg' | 'png'
  } = {}): string {
    // If it's already an optimized URL, return as is
    if (src.includes('trae-api-sg.mchost.guru')) {
      return src
    }

    // For local images, we could implement client-side optimization
    // For now, return the original src
    return src
  }

  /**
   * Debounce function for performance optimization
   */
  debounce<T extends (...args: any[]) => any>(
    func: T,
    wait: number,
    immediate?: boolean
  ): (...args: Parameters<T>) => void {
    let timeout: NodeJS.Timeout | null = null
    
    return (...args: Parameters<T>) => {
      const later = () => {
        timeout = null
        if (!immediate) func(...args)
      }
      
      const callNow = immediate && !timeout
      
      if (timeout) clearTimeout(timeout)
      timeout = setTimeout(later, wait)
      
      if (callNow) func(...args)
    }
  }

  /**
   * Throttle function for performance optimization
   */
  throttle<T extends (...args: any[]) => any>(
    func: T,
    limit: number
  ): (...args: Parameters<T>) => void {
    let inThrottle: boolean
    
    return (...args: Parameters<T>) => {
      if (!inThrottle) {
        func(...args)
        inThrottle = true
        setTimeout(() => inThrottle = false, limit)
      }
    }
  }

  /**
   * Cleanup performance observers
   */
  cleanup(): void {
    this.observers.forEach(observer => {
      observer.disconnect()
    })
    this.observers.clear()
  }

  /**
   * Get cache size information
   */
  getCacheSizes(): Record<string, { size: number; maxSize: number; usage: number }> {
    const sizes: Record<string, { size: number; maxSize: number; usage: number }> = {}
    
    this.caches.forEach((cache, name) => {
      const size = cache.size
      const maxSize = cache.max || 0
      const usage = maxSize > 0 ? (size / maxSize) * 100 : 0
      
      sizes[name] = {
        size,
        maxSize,
        usage: Math.round(usage * 100) / 100
      }
    })
    
    return sizes
  }

  /**
   * Clear all caches
   */
  clearAllCaches(): void {
    this.caches.forEach(cache => cache.clear())
    
    // Reset hit rate stats
    this.metrics.cacheHitRates.forEach(stats => {
      stats.hits = 0
      stats.misses = 0
    })
  }
}

// Create singleton instance
export const performanceService = new PerformanceService()

// Export types
export type {
  CacheConfig,
  PerformanceMetrics,
  LazyComponentConfig
}

// React hook for component render time tracking
export const useRenderTimeTracking = (componentName: string) => {
  const startTime = performance.now()
  
  return () => {
    const endTime = performance.now()
    performanceService.recordComponentRenderTime(componentName, endTime - startTime)
  }
}