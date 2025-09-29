import { supabase } from '../lib/supabase'

export interface WebSocketMessage {
  type: 'job_update' | 'analysis_complete' | 'clip_generated' | 'error'
  job_id?: string
  data: any
  timestamp: string
}

export interface JobUpdateData {
  job_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  current_step: string
  estimated_remaining: number
}

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private listeners: Map<string, Set<(data: any) => void>> = new Map()
  private isConnecting = false

  async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
      return
    }

    this.isConnecting = true

    try {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        console.warn('No authenticated user for WebSocket connection')
        this.isConnecting = false
        return
      }
      
      const clientId = user.id || 'anonymous'
      const wsUrl = `ws://localhost:8001/ws/${clientId}`
      
      this.ws = new WebSocket(wsUrl)
      
      this.ws.onopen = () => {
        console.log('WebSocket connected')
        this.reconnectAttempts = 0
        this.isConnecting = false
      }
      
      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }
      
      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        this.isConnecting = false
        this.ws = null
        
        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect()
        }
      }
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.isConnecting = false
      }
    } catch (error) {
      console.error('Failed to connect WebSocket:', error)
      this.isConnecting = false
      throw error
    }
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    
    console.log(`Scheduling WebSocket reconnect attempt ${this.reconnectAttempts} in ${delay}ms`)
    
    setTimeout(() => {
      this.connect().catch(error => {
        console.error('WebSocket reconnect failed:', error)
      })
    }, delay)
  }

  private handleMessage(message: WebSocketMessage): void {
    const listeners = this.listeners.get(message.type)
    if (listeners) {
      listeners.forEach(listener => {
        try {
          listener(message.data)
        } catch (error) {
          console.error('Error in WebSocket listener:', error)
        }
      })
    }

    // Also notify job-specific listeners
    if (message.job_id) {
      const jobListeners = this.listeners.get(`job_${message.job_id}`)
      if (jobListeners) {
        jobListeners.forEach(listener => {
          try {
            listener(message.data)
          } catch (error) {
            console.error('Error in job-specific WebSocket listener:', error)
          }
        })
      }
    }
  }

  subscribe(eventType: string, callback: (data: any) => void): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set())
    }
    
    this.listeners.get(eventType)!.add(callback)
    
    // Auto-connect if not already connected
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connect().catch(error => {
        console.error('Failed to connect WebSocket for subscription:', error)
      })
    }
    
    // Return unsubscribe function
    return () => {
      const listeners = this.listeners.get(eventType)
      if (listeners) {
        listeners.delete(callback)
        if (listeners.size === 0) {
          this.listeners.delete(eventType)
        }
      }
    }
  }

  subscribeToJob(jobId: string, callback: (data: any) => void): () => void {
    return this.subscribe(`job_${jobId}`, callback)
  }

  unsubscribe(eventType: string, callback?: (data: any) => void): void {
    if (callback) {
      const listeners = this.listeners.get(eventType)
      if (listeners) {
        listeners.delete(callback)
        if (listeners.size === 0) {
          this.listeners.delete(eventType)
        }
      }
    } else {
      // Remove all listeners for this event type
      this.listeners.delete(eventType)
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect')
      this.ws = null
    }
    this.listeners.clear()
    this.reconnectAttempts = 0
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket not connected, cannot send message')
    }
  }
}

export const webSocketService = new WebSocketService()

// Auto-connect when user is authenticated
supabase.auth.onAuthStateChange((event, session) => {
  if (session?.user) {
    webSocketService.connect().catch(error => {
      console.error('Failed to auto-connect WebSocket:', error)
    })
  } else {
    webSocketService.disconnect()
  }
})