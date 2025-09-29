import { expect, afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers)

// Cleanup after each test case
afterEach(() => {
  cleanup()
})

// Mock environment variables
vi.mock('../../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      getUser: vi.fn(),
      signInWithOAuth: vi.fn(),
      signOut: vi.fn(),
      onAuthStateChange: vi.fn((callback) => {
        // Call the callback immediately with initial auth state
        setTimeout(() => callback('SIGNED_IN', { user: { id: 'user-123', email: 'test@example.com' } }), 0)
        return {
          data: { subscription: { unsubscribe: vi.fn() } }
        }
      })
    },
    from: vi.fn(() => ({
      select: vi.fn().mockReturnThis(),
      insert: vi.fn().mockReturnThis(),
      update: vi.fn().mockReturnThis(),
      delete: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      single: vi.fn()
    }))
  }
}))

// Mock API service
vi.mock('../../services/api', () => ({
  apiService: {
    uploadVideo: vi.fn(),
    processUrl: vi.fn(),
    getTaskStatus: vi.fn(),
    getVideo: vi.fn(),
    getUserVideos: vi.fn()
  }
}))

// Mock chunked upload service
vi.mock('../../services/chunkedUpload', () => ({
  ChunkedUploadService: vi.fn().mockImplementation(() => ({
    startUpload: vi.fn(),
    uploadFile: vi.fn(),
    cancelUpload: vi.fn(),
    getProgress: vi.fn(),
    getSession: vi.fn(),
    getActiveSessions: vi.fn()
  }))
}))

// Mock toast notifications
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    loading: vi.fn(),
    dismiss: vi.fn(),
    promise: vi.fn()
  }
}))

// Mock React Router
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({}),
    useLocation: () => ({ pathname: '/', state: null, search: '', hash: '' }),
    useSearchParams: () => [new URLSearchParams(), vi.fn()]
  }
})

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn()
  }))
})

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn()
}))

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn()
}))

// Mock URL.createObjectURL
global.URL.createObjectURL = vi.fn(() => 'mocked-object-url')
global.URL.revokeObjectURL = vi.fn()

// Mock File and FileReader
global.File = class MockFile {
  name: string
  size: number
  type: string
  lastModified: number
  
  constructor(chunks: any[], filename: string, options: any = {}) {
    this.name = filename
    this.size = options.size || chunks.join('').length
    this.type = options.type || ''
    this.lastModified = options.lastModified || Date.now()
  }
  
  arrayBuffer() {
    return Promise.resolve(new ArrayBuffer(this.size))
  }
  
  text() {
    return Promise.resolve('')
  }
  
  stream() {
    return new ReadableStream()
  }
  
  slice() {
    return new MockFile([], this.name, { type: this.type })
  }
} as any

global.FileReader = class MockFileReader {
  result: any = null
  error: any = null
  readyState: number = 0
  onload: any = null
  onerror: any = null
  onabort: any = null
  onloadstart: any = null
  onloadend: any = null
  onprogress: any = null
  
  readAsDataURL() {
    this.readyState = 2
    this.result = 'data:text/plain;base64,dGVzdA=='
    if (this.onload) this.onload({ target: this })
  }
  
  readAsText() {
    this.readyState = 2
    this.result = 'test'
    if (this.onload) this.onload({ target: this })
  }
  
  readAsArrayBuffer() {
    this.readyState = 2
    this.result = new ArrayBuffer(4)
    if (this.onload) this.onload({ target: this })
  }
  
  abort() {
    this.readyState = 2
    if (this.onabort) this.onabort({ target: this })
  }
} as any

// Mock crypto.subtle for testing
if (!global.crypto) {
  global.crypto = {} as any
}

Object.defineProperty(global.crypto, 'subtle', {
  value: {
    digest: vi.fn().mockImplementation(async (algorithm, data) => {
      // Simple mock hash based on data length
      const hash = new Array(32).fill(0).map((_, i) => (data.byteLength || 0) + i)
      return new Uint8Array(hash).buffer
    })
  },
  writable: true
})

// Mock localStorage
const localStorageMock = {
  data: new Map<string, string>(),
  getItem: vi.fn((key: string) => localStorageMock.data.get(key) || null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageMock.data.set(key, value)
  }),
  removeItem: vi.fn((key: string) => {
    localStorageMock.data.delete(key)
  }),
  clear: vi.fn(() => {
    localStorageMock.data.clear()
  }),
  key: vi.fn((index: number) => {
    const keys = Array.from(localStorageMock.data.keys())
    return keys[index] || null
  }),
  get length() {
    return localStorageMock.data.size
  }
}

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
})

Object.defineProperty(window, 'sessionStorage', {
  value: localStorageMock
})

// Mock console methods to reduce noise in tests
const originalConsole = { ...console }
global.console = {
  ...console,
  log: vi.fn(),
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn()
}

// Restore console for debugging when needed
;(global as any).restoreConsole = () => {
  global.console = originalConsole
}

// Global test utilities
;(global as any).createMockFile = (name: string, size: number, type: string = 'video/mp4') => {
  const content = new Array(size).fill('a').join('')
  return new File([content], name, { type })
}

;(global as any).createMockUser = () => ({
  id: 'test-user-' + Date.now(),
  email: 'test@example.com',
  access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSJ9.test'
})

// Setup fetch mock
global.fetch = vi.fn()

// Reset all mocks before each test
beforeEach(() => {
  vi.clearAllMocks()
  localStorageMock.clear()
})