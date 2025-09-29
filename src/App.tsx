import React, { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { webSocketService } from './services/websocket'

// Components
import Navbar from './components/Navbar'
import LoadingSpinner from './components/LoadingSpinner'
import ErrorBoundary from './components/ErrorBoundary'
import CacheDebugger from './components/CacheDebugger'

// Pages
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Results from './pages/Results'
import History from './pages/History'
import Settings from './pages/Settings'
import Login from './pages/Login'
import Register from './pages/Register'
import AuthCallback from './pages/AuthCallback'

function AppContent() {
  const { user, loading, isAuthenticated, maintenanceMode } = useAuth()
  const [showCacheDebugger, setShowCacheDebugger] = useState(false)

  // Initialize WebSocket connection when user is authenticated
  useEffect(() => {
    if (isAuthenticated) {
      webSocketService.connect()
    } else {
      webSocketService.disconnect()
    }

    // Cleanup on unmount
    return () => {
      webSocketService.disconnect()
    }
  }, [isAuthenticated])

  // Add keyboard shortcut for cache debugger (Ctrl+Shift+C)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.key === 'C') {
        event.preventDefault()
        setShowCacheDebugger(true)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        {isAuthenticated && <Navbar />}
        
        <main className={isAuthenticated ? 'pt-16' : ''}>
          <ErrorBoundary>
            <Routes>
              {/* Public routes */}
              <Route 
                path="/login" 
                element={(isAuthenticated && !maintenanceMode) ? <Navigate to="/dashboard" replace /> : <Login />} 
              />
              <Route 
                path="/register" 
                element={(isAuthenticated && !maintenanceMode) ? <Navigate to="/dashboard" replace /> : <Register />} 
              />
              <Route path="/auth/callback" element={<AuthCallback />} />
              
              {/* Core Features - Always accessible during maintenance mode */}
              <Route path="/upload" element={<Upload />} />
              <Route path="/results" element={<Results />} />
              <Route path="/results/:jobId" element={<Results />} />
              
              {/* Protected Routes - Require authentication when not in maintenance mode */}
              <Route path="/dashboard" element={(isAuthenticated || maintenanceMode) ? <Dashboard /> : <Navigate to="/login" replace />} />
              <Route path="/settings" element={(isAuthenticated || maintenanceMode) ? <Settings /> : <Navigate to="/login" replace />} />
              <Route path="/history" element={(isAuthenticated || maintenanceMode) ? <History /> : <Navigate to="/login" replace />} />
              
              {/* Default routes */}
              <Route path="/" element={(isAuthenticated || maintenanceMode) ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />} />
              <Route path="*" element={(isAuthenticated || maintenanceMode) ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />} />
            </Routes>
          </ErrorBoundary>
        </main>
        
        {/* Global toast notifications */}
        <Toaster 
          position="top-right" 
          richColors 
          closeButton
          duration={4000}
        />
        
        {/* Cache Debugger - accessible via Ctrl+Shift+C */}
        <CacheDebugger 
          isOpen={showCacheDebugger} 
          onClose={() => setShowCacheDebugger(false)} 
        />
      </div>
    </Router>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ErrorBoundary>
  )
}

export default App