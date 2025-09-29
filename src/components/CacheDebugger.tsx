import React, { useState, useEffect } from 'react'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Badge } from './ui/badge'
import { RefreshCw, Trash2, AlertTriangle, CheckCircle } from 'lucide-react'
import { cacheManager } from '../utils/cacheManager'
import { toast } from 'sonner'

interface CacheDebuggerProps {
  isOpen: boolean
  onClose: () => void
}

export const CacheDebugger: React.FC<CacheDebuggerProps> = ({ isOpen, onClose }) => {
  const [cacheStats, setCacheStats] = useState({ localStorage: 0, sessionStorage: 0, version: 'unknown' })
  const [isClearing, setIsClearing] = useState(false)
  const [lastCleared, setLastCleared] = useState<Date | null>(null)

  useEffect(() => {
    if (isOpen) {
      updateCacheStats()
    }
  }, [isOpen])

  const updateCacheStats = () => {
    setCacheStats(cacheManager.getCacheStats())
  }

  const handleClearCache = async () => {
    setIsClearing(true)
    try {
      await cacheManager.clearAllCache()
      setLastCleared(new Date())
      updateCacheStats()
      toast.success('Cache cleared successfully')
    } catch (error) {
      console.error('Failed to clear cache:', error)
      toast.error('Failed to clear cache')
    } finally {
      setIsClearing(false)
    }
  }

  const handleForceReload = () => {
    cacheManager.forceReload()
  }

  const getCacheHealthStatus = () => {
    const totalItems = cacheStats.localStorage + cacheStats.sessionStorage
    if (totalItems > 100) {
      return { status: 'warning', message: 'High cache usage detected' }
    }
    if (cacheStats.version === 'unknown') {
      return { status: 'error', message: 'Cache version mismatch' }
    }
    return { status: 'healthy', message: 'Cache is healthy' }
  }

  if (!isOpen) return null

  const healthStatus = getCacheHealthStatus()

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <Card className="w-full max-w-md mx-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="h-5 w-5" />
            Cache Debugger
          </CardTitle>
          <CardDescription>
            Diagnose and fix cache-related issues
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Cache Health Status */}
          <div className="flex items-center gap-2">
            {healthStatus.status === 'healthy' && <CheckCircle className="h-4 w-4 text-green-500" />}
            {healthStatus.status === 'warning' && <AlertTriangle className="h-4 w-4 text-yellow-500" />}
            {healthStatus.status === 'error' && <AlertTriangle className="h-4 w-4 text-red-500" />}
            <span className="text-sm">{healthStatus.message}</span>
            <Badge variant={healthStatus.status === 'healthy' ? 'default' : 'destructive'}>
              {healthStatus.status}
            </Badge>
          </div>

          {/* Cache Statistics */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="font-medium">Local Storage</div>
              <div className="text-muted-foreground">{cacheStats.localStorage} items</div>
            </div>
            <div>
              <div className="font-medium">Session Storage</div>
              <div className="text-muted-foreground">{cacheStats.sessionStorage} items</div>
            </div>
            <div className="col-span-2">
              <div className="font-medium">Cache Version</div>
              <div className="text-muted-foreground">{cacheStats.version}</div>
            </div>
          </div>

          {/* Last Cleared */}
          {lastCleared && (
            <div className="text-sm text-muted-foreground">
              Last cleared: {lastCleared.toLocaleTimeString()}
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col gap-2">
            <Button
              onClick={handleClearCache}
              disabled={isClearing}
              variant="outline"
              className="w-full"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              {isClearing ? 'Clearing...' : 'Clear Cache'}
            </Button>
            
            <Button
              onClick={handleForceReload}
              variant="destructive"
              className="w-full"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Force Reload
            </Button>
          </div>

          {/* Help Text */}
          <div className="text-xs text-muted-foreground bg-muted p-3 rounded">
            <strong>When to use:</strong>
            <ul className="mt-1 space-y-1">
              <li>• White screen after updates</li>
              <li>• Authentication issues</li>
              <li>• Stale data problems</li>
              <li>• App not loading properly</li>
            </ul>
          </div>

          {/* Close Button */}
          <Button onClick={onClose} variant="ghost" className="w-full">
            Close
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

export default CacheDebugger