import React, { useState, useEffect } from 'react'
import { User, Video, Download, Share2, Bell, Palette, Save, Check, Camera, Mail, Smartphone, Settings as SettingsIcon, AlertCircle, Loader2 } from 'lucide-react'
import { apiService, UserSettings } from '../services/api'
import { webSocketService } from '../services/websocket'
import { toast } from 'sonner'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

interface SettingsState extends UserSettings {
  // Additional UI state
  plan: string
  avatar: string
}

const Settings = () => {
  const { user, loading: authLoading, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('profile')
  const [settings, setSettings] = useState<SettingsState>({
    // Profile settings
    name: '',
    email: '',
    avatar: '',
    plan: 'free',
    
    // Video processing settings
    defaultQuality: 'high',
    defaultNiche: 'general',
    defaultDuration: 30,
    autoProcess: true,
    maxClips: 5,
    
    // Output preferences
    outputFormat: 'mp4',
    resolution: '1080p',
    frameRate: 30,
    watermark: false,
    compressionLevel: 'medium',
    
    // Platform settings
    platforms: {
      youtube: true,
      tiktok: true,
      instagram: true,
      twitter: false
    },
    
    // Notification settings
    emailNotifications: true,
    pushNotifications: false,
    processingUpdates: true,
    marketingEmails: false,
    
    // Appearance
    theme: 'light',
    language: 'en'
  })
  
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [saveError, setSaveError] = useState<string | null>(null)

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User, color: 'blue' },
    { id: 'processing', label: 'Video Processing', icon: Video, color: 'orange' },
    { id: 'output', label: 'Output Preferences', icon: Download, color: 'green' },
    { id: 'platforms', label: 'Platforms', icon: Share2, color: 'purple' },
    { id: 'notifications', label: 'Notifications', icon: Bell, color: 'yellow' },
    { id: 'appearance', label: 'Appearance', icon: Palette, color: 'pink' }
  ]

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      navigate('/login')
    }
  }, [authLoading, isAuthenticated, navigate])

  // Load user settings on component mount
  useEffect(() => {
    if (!user || authLoading || !isAuthenticated) return
      
    const loadSettings = async () => {
      try {
        setIsLoading(true)
        const userSettings = await apiService.getUserSettings()
        const userProfile = await apiService.getUserProfile()
        
        setSettings(prev => ({
          ...prev,
          ...userSettings,
          name: userProfile.name || user.user_metadata?.full_name || '',
          email: userProfile.email || user.email || '',
          avatar: userProfile.avatar || user.user_metadata?.avatar_url || ''
        }))
      } catch (error) {
        console.error('Failed to load settings:', error)
        toast.error('Failed to load settings')
      } finally {
        setIsLoading(false)
      }
    }

    loadSettings()
  }, [user, authLoading, isAuthenticated])

  // WebSocket integration for real-time updates
  useEffect(() => {
    if (!user) return

    const handleSettingsUpdate = (data: any) => {
      if (data.type === 'settings_updated') {
        setSettings(prev => ({ ...prev, ...data.settings }))
        toast.success('Settings updated from another device')
      }
    }

    webSocketService.subscribe('settings', handleSettingsUpdate)

    return () => {
      webSocketService.unsubscribe('settings', handleSettingsUpdate)
    }
  }, [user])

  const handleSave = async () => {
    if (!user) {
      toast.error('Please log in to save settings')
      return
    }

    setIsSaving(true)
    setSaveError(null)
    
    try {
      // Extract settings without UI-only fields
      const { plan, avatar, ...settingsToSave } = settings
      
      await apiService.updateUserSettings(settingsToSave)
      
      // Update profile if name or email changed
      if (settings.name !== user.user_metadata?.full_name || settings.email !== user.email) {
        await apiService.updateUserProfile({
          name: settings.name,
          email: settings.email,
          avatar: settings.avatar
        })
      }
      
      toast.success('Settings saved successfully!')
    } catch (error: any) {
      console.error('Failed to save settings:', error)
      setSaveError(error.message || 'Failed to save settings')
      toast.error('Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  const updateSettings = (updates: Partial<SettingsState>) => {
    setSettings(prev => ({ ...prev, ...updates }))
  }

  const updateSetting = (key: string, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  const updatePlatform = (platform: string, enabled: boolean) => {
    setSettings(prev => ({
      ...prev,
      platforms: { ...prev.platforms, [platform]: enabled }
    }))
  }

  // Show loading state while authentication is being checked
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading settings...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-8 w-8 text-red-600 mx-auto mb-4" />
          <p className="text-gray-600">Please log in to access settings</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="bg-gradient-to-r from-blue-600 to-orange-500 p-3 rounded-full">
              <SettingsIcon className="h-8 w-8 text-white" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Settings
          </h1>
          <p className="text-xl text-gray-600">
            Customize your video processing preferences
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
          {/* Tab Navigation */}
          <div className="border-b border-gray-200">
            <nav className="flex overflow-x-auto">
              {tabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-2 px-6 py-4 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                      activeTab === tab.id
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {tab.label}
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {/* Profile Tab */}
            {activeTab === 'profile' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Full Name
                    </label>
                    <input
                      type="text"
                      value={settings.name}
                      onChange={(e) => updateSettings({ name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Email Address
                    </label>
                    <input
                      type="email"
                      value={settings.email}
                      onChange={(e) => updateSettings({ email: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>
                
                <div className="bg-gradient-to-r from-blue-50 to-orange-50 p-4 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-gray-900">Current Plan</h3>
                      <p className="text-sm text-gray-600 capitalize">{settings.plan} Plan</p>
                    </div>
                    {settings.plan === 'free' && (
                      <button className="bg-gradient-to-r from-blue-600 to-orange-500 text-white px-4 py-2 rounded-lg font-medium hover:shadow-lg transition-shadow">
                        Upgrade to Premium
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Video Processing Tab */}
            {activeTab === 'processing' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Default Niche
                    </label>
                    <select
                      value={settings.defaultNiche}
                      onChange={(e) => updateSettings({ defaultNiche: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="general">General Content</option>
                      <option value="gaming">Gaming</option>
                      <option value="education">Educational</option>
                      <option value="entertainment">Entertainment</option>
                      <option value="business">Business</option>
                      <option value="lifestyle">Lifestyle</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Default Quality
                    </label>
                    <select
                      value={settings.defaultQuality}
                      onChange={(e) => updateSettings({ defaultQuality: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="high">High Quality (1080p)</option>
                      <option value="medium">Medium Quality (720p)</option>
                      <option value="low">Low Quality (480p)</option>
                    </select>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Default Clip Duration: {settings.defaultDuration}s
                  </label>
                  <input
                    type="range"
                    min="15"
                    max="180"
                    step="15"
                    value={settings.defaultDuration}
                    onChange={(e) => updateSettings({ defaultDuration: parseInt(e.target.value) })}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>15s</span>
                    <span>3min</span>
                  </div>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <h3 className="font-medium text-gray-900">Auto-process uploads</h3>
                    <p className="text-sm text-gray-600">Automatically start processing when files are uploaded</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.autoProcess}
                      onChange={(e) => updateSettings({ autoProcess: e.target.checked })}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>
              </div>
            )}

            {/* Output Preferences Tab */}
            {activeTab === 'output' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Output Format
                    </label>
                    <div className="flex gap-2">
                      {['mp4', 'mov', 'webm'].map((format) => (
                        <button
                          key={format}
                          onClick={() => updateSettings({ outputFormat: format })}
                          className={`px-4 py-2 rounded-lg font-medium transition-all ${
                            settings.outputFormat === format
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                          }`}
                        >
                          {format.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Resolution
                    </label>
                    <select
                      value={settings.resolution}
                      onChange={(e) => updateSettings({ resolution: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="1080p">1080p (Full HD)</option>
                      <option value="720p">720p (HD)</option>
                      <option value="480p">480p (SD)</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Frame Rate
                    </label>
                    <select
                      value={settings.frameRate}
                      onChange={(e) => updateSetting('frameRate', parseInt(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value={24}>24 FPS (Cinematic)</option>
                      <option value={30}>30 FPS (Standard)</option>
                      <option value={60}>60 FPS (Smooth)</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Compression Level
                    </label>
                    <select
                      value={settings.compressionLevel}
                      onChange={(e) => updateSetting('compressionLevel', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="low">Low (Larger file, better quality)</option>
                      <option value="medium">Medium (Balanced)</option>
                      <option value="high">High (Smaller file, lower quality)</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Platforms Tab */}
            {activeTab === 'platforms' && (
              <div className="space-y-6">
                <p className="text-gray-600">Select the platforms you want to optimize your clips for:</p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(settings.platforms).map(([platform, enabled]) => (
                    <div key={platform} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          platform === 'tiktok' ? 'bg-black' :
                          platform === 'instagram' ? 'bg-gradient-to-r from-purple-500 to-pink-500' :
                          platform === 'youtube' ? 'bg-red-600' :
                          'bg-blue-500'
                        }`}>
                          <span className="text-white font-bold text-sm">
                            {platform === 'tiktok' ? 'TT' :
                             platform === 'instagram' ? 'IG' :
                             platform === 'youtube' ? 'YT' : 'TW'}
                          </span>
                        </div>
                        <div>
                          <h3 className="font-medium text-gray-900 capitalize">{platform}</h3>
                          <p className="text-sm text-gray-600">
                            {platform === 'tiktok' ? 'Vertical 9:16 format' :
                             platform === 'instagram' ? 'Stories & Reels' :
                             platform === 'youtube' ? 'Shorts format' :
                             'Square & vertical'}
                          </p>
                        </div>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(e) => updatePlatform(platform, e.target.checked)}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Notifications Tab */}
            {activeTab === 'notifications' && (
              <div className="space-y-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div>
                      <h3 className="font-medium text-gray-900">Email Notifications</h3>
                      <p className="text-sm text-gray-600">Receive notifications via email</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={settings.emailNotifications}
                        onChange={(e) => updateSettings({ emailNotifications: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>
                  
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div>
                      <h3 className="font-medium text-gray-900">Processing Updates</h3>
                      <p className="text-sm text-gray-600">Get notified when your videos are processed</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={settings.processingUpdates}
                        onChange={(e) => updateSettings({ processingUpdates: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>
                  
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div>
                      <h3 className="font-medium text-gray-900">Marketing Emails</h3>
                      <p className="text-sm text-gray-600">Receive tips and product updates</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={settings.marketingEmails}
                        onChange={(e) => updateSettings({ marketingEmails: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* Appearance Tab */}
            {activeTab === 'appearance' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Theme
                    </label>
                    <div className="flex gap-2">
                      {['light', 'dark', 'auto'].map((theme) => (
                        <button
                          key={theme}
                          onClick={() => updateSettings({ theme: theme as 'light' | 'dark' | 'auto' })}
                          className={`px-4 py-2 rounded-lg font-medium transition-all capitalize ${
                            settings.theme === theme
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                          }`}
                        >
                          {theme}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Language
                    </label>
                    <select
                      value={settings.language}
                      onChange={(e) => updateSettings({ language: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="en">English</option>
                      <option value="es">Español</option>
                      <option value="fr">Français</option>
                      <option value="de">Deutsch</option>
                      <option value="zh">中文</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Save Button */}
          <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
            {saveError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
                <AlertCircle className="h-4 w-4" />
                <span className="text-sm">{saveError}</span>
              </div>
            )}
            <div className="flex justify-end">
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-orange-500 text-white px-6 py-2 rounded-lg font-medium hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                {isSaving ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings