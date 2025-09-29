import { toast } from 'sonner'

interface LoginResponse {
  user: {
    id: string
    email: string
    display_name: string
    photo_url?: string
    is_active: boolean
    email_verified: boolean
    role: string
    created_at: string
    updated_at: string
    last_login: string
  }
  tokens: {
    access_token: string
    refresh_token: string
    token_type: string
    expires_in: number
  }
}

interface RegisterData {
  email: string
  password: string
  full_name?: string
}

interface LoginData {
  email: string
  password: string
}

class BackendAuthService {
  private baseUrl = 'http://localhost:8001'
  private accessToken: string | null = null
  private refreshToken: string | null = null
  private user: any = null

  constructor() {
    // Load tokens from localStorage on initialization
    this.loadTokensFromStorage()
  }

  private saveTokensToStorage(tokens: LoginResponse['tokens'], user: LoginResponse['user']) {
    localStorage.setItem('cliper_access_token', tokens.access_token)
    localStorage.setItem('cliper_refresh_token', tokens.refresh_token)
    localStorage.setItem('cliper_user', JSON.stringify(user))
    this.accessToken = tokens.access_token
    this.refreshToken = tokens.refresh_token
    this.user = user
  }

  private loadTokensFromStorage() {
    this.accessToken = localStorage.getItem('cliper_access_token')
    this.refreshToken = localStorage.getItem('cliper_refresh_token')
    const userStr = localStorage.getItem('cliper_user')
    if (userStr) {
      try {
        this.user = JSON.parse(userStr)
      } catch (error) {
        console.error('Failed to parse user from storage:', error)
      }
    }
  }

  private clearTokensFromStorage() {
    localStorage.removeItem('cliper_access_token')
    localStorage.removeItem('cliper_refresh_token')
    localStorage.removeItem('cliper_user')
    this.accessToken = null
    this.refreshToken = null
    this.user = null
  }

  async register(data: RegisterData): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })

      if (!response.ok) {
        const errorData = await response.json()
        return { success: false, error: errorData.detail || 'Registration failed' }
      }

      const result: LoginResponse = await response.json()
      this.saveTokensToStorage(result.tokens, result.user)
      
      toast.success('Registration successful!')
      return { success: true }
    } catch (error) {
      console.error('Registration error:', error)
      return { success: false, error: 'Network error during registration' }
    }
  }

  async login(data: LoginData): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })

      if (!response.ok) {
        const errorData = await response.json()
        return { success: false, error: errorData.detail || 'Login failed' }
      }

      const result: LoginResponse = await response.json()
      this.saveTokensToStorage(result.tokens, result.user)
      
      toast.success('Login successful!')
      return { success: true }
    } catch (error) {
      console.error('Login error:', error)
      return { success: false, error: 'Network error during login' }
    }
  }

  async logout(): Promise<void> {
    try {
      // Call backend logout endpoint if available
      if (this.accessToken) {
        await fetch(`${this.baseUrl}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.accessToken}`,
            'Content-Type': 'application/json',
          },
        })
      }
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      this.clearTokensFromStorage()
      toast.success('Logged out successfully')
    }
  }

  async verifyToken(): Promise<{ success: boolean; user?: any }> {
    if (!this.accessToken) {
      return { success: false }
    }

    try {
      const response = await fetch(`${this.baseUrl}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        this.clearTokensFromStorage()
        return { success: false }
      }

      const user = await response.json()
      this.user = user
      localStorage.setItem('cliper_user', JSON.stringify(user))
      
      return { success: true, user }
    } catch (error) {
      console.error('Token verification error:', error)
      this.clearTokensFromStorage()
      return { success: false }
    }
  }

  getAccessToken(): string | null {
    return this.accessToken
  }

  getUser(): any {
    return this.user
  }

  isAuthenticated(): boolean {
    return !!this.accessToken && !!this.user
  }

  async getAuthHeaders(): Promise<Record<string, string>> {
    if (!this.accessToken) {
      throw new Error('No access token available')
    }

    return {
      'Authorization': `Bearer ${this.accessToken}`,
      'Content-Type': 'application/json',
    }
  }
}

export const backendAuthService = new BackendAuthService()
export default backendAuthService