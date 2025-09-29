/**
 * Cache Management Utility
 * Handles browser cache, localStorage, and sessionStorage cleanup
 * to prevent white screen issues and stale data problems
 */

export interface CacheConfig {
  version: string
  maxAge: number // in milliseconds
  storageKeys: string[]
}

class CacheManager {
  private readonly CACHE_VERSION_KEY = 'cliper_cache_version'
  private readonly CURRENT_VERSION = '1.0.0'
  private readonly MAX_STORAGE_AGE = 24 * 60 * 60 * 1000 // 24 hours

  /**
   * Initialize cache management
   * Checks for version mismatches and clears stale data
   */
  async initialize(): Promise<void> {
    try {
      await this.checkVersionCompatibility()
      await this.cleanupExpiredData()
      this.setupStorageEventListeners()
    } catch (error) {
      console.error('Cache manager initialization failed:', error)
      // Fallback: clear all cache on error
      await this.clearAllCache()
    }
  }

  /**
   * Check if cache version is compatible
   * Clear cache if version mismatch detected
   */
  private async checkVersionCompatibility(): Promise<void> {
    const storedVersion = localStorage.getItem(this.CACHE_VERSION_KEY)
    
    if (storedVersion !== this.CURRENT_VERSION) {
      console.log(`Cache version mismatch. Stored: ${storedVersion}, Current: ${this.CURRENT_VERSION}`)
      await this.clearAllCache()
      localStorage.setItem(this.CACHE_VERSION_KEY, this.CURRENT_VERSION)
    }
  }

  /**
   * Clear all application cache
   * Includes localStorage, sessionStorage, and browser cache
   */
  async clearAllCache(): Promise<void> {
    try {
      // Clear localStorage (except version key)
      const keysToKeep = [this.CACHE_VERSION_KEY]
      Object.keys(localStorage).forEach(key => {
        if (!keysToKeep.includes(key)) {
          localStorage.removeItem(key)
        }
      })

      // Clear sessionStorage
      sessionStorage.clear()

      // Clear service worker cache if available
      if ('serviceWorker' in navigator && 'caches' in window) {
        const cacheNames = await caches.keys()
        await Promise.all(
          cacheNames.map(cacheName => caches.delete(cacheName))
        )
      }

      console.log('All cache cleared successfully')
    } catch (error) {
      console.error('Failed to clear cache:', error)
    }
  }

  /**
   * Clear specific storage keys
   */
  clearStorageKeys(keys: string[]): void {
    keys.forEach(key => {
      localStorage.removeItem(key)
      sessionStorage.removeItem(key)
    })
  }

  /**
   * Clean up expired data based on timestamps
   */
  private async cleanupExpiredData(): Promise<void> {
    const now = Date.now()
    const expiredKeys: string[] = []

    // Check localStorage for expired items
    Object.keys(localStorage).forEach(key => {
      try {
        const item = localStorage.getItem(key)
        if (item) {
          const parsed = JSON.parse(item)
          if (parsed.timestamp && (now - parsed.timestamp) > this.MAX_STORAGE_AGE) {
            expiredKeys.push(key)
          }
        }
      } catch {
        // If parsing fails, consider it expired
        expiredKeys.push(key)
      }
    })

    // Remove expired keys
    expiredKeys.forEach(key => localStorage.removeItem(key))
    
    if (expiredKeys.length > 0) {
      console.log(`Cleaned up ${expiredKeys.length} expired cache entries`)
    }
  }

  /**
   * Setup storage event listeners for cross-tab synchronization
   */
  private setupStorageEventListeners(): void {
    window.addEventListener('storage', (event) => {
      // Handle auth state changes from other tabs
      if (event.key === 'cliper_auth_state' && !event.newValue) {
        // User signed out in another tab
        console.log('Auth state cleared in another tab, reloading...')
        window.location.reload()
      }
    })
  }

  /**
   * Add timestamp to data for expiration tracking
   */
  setWithTimestamp(key: string, data: any, storage: Storage = localStorage): void {
    const timestampedData = {
      ...data,
      timestamp: Date.now()
    }
    storage.setItem(key, JSON.stringify(timestampedData))
  }

  /**
   * Get data and check if it's expired
   */
  getWithExpiration(key: string, maxAge: number = this.MAX_STORAGE_AGE, storage: Storage = localStorage): any | null {
    try {
      const item = storage.getItem(key)
      if (!item) return null

      const parsed = JSON.parse(item)
      const now = Date.now()
      
      if (parsed.timestamp && (now - parsed.timestamp) > maxAge) {
        storage.removeItem(key)
        return null
      }

      return parsed
    } catch {
      storage.removeItem(key)
      return null
    }
  }

  /**
   * Force reload with cache bypass
   */
  forceReload(): void {
    // Clear cache first
    this.clearAllCache().then(() => {
      // Force reload with cache bypass
      window.location.reload()
    })
  }

  /**
   * Check if browser storage is available
   */
  isStorageAvailable(type: 'localStorage' | 'sessionStorage'): boolean {
    try {
      const storage = window[type]
      const test = '__storage_test__'
      storage.setItem(test, test)
      storage.removeItem(test)
      return true
    } catch {
      return false
    }
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): { localStorage: number; sessionStorage: number; version: string } {
    return {
      localStorage: Object.keys(localStorage).length,
      sessionStorage: Object.keys(sessionStorage).length,
      version: localStorage.getItem(this.CACHE_VERSION_KEY) || 'unknown'
    }
  }
}

export const cacheManager = new CacheManager()

// Initialize cache manager when module loads
cacheManager.initialize().catch(error => {
  console.error('Failed to initialize cache manager:', error)
})