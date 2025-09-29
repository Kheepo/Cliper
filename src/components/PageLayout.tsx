import React from 'react'
import { LucideIcon } from 'lucide-react'

interface PageLayoutProps {
  title: string
  subtitle?: string
  icon?: LucideIcon
  children: React.ReactNode
  headerActions?: React.ReactNode
  className?: string
  containerClassName?: string
  showBackButton?: boolean
  onBack?: () => void
}

const PageLayout: React.FC<PageLayoutProps> = ({
  title,
  subtitle,
  icon: Icon,
  children,
  headerActions,
  className = '',
  containerClassName = '',
  showBackButton = false,
  onBack
}) => {
  return (
    <div className={`min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 ${className}`}>
      <div className={`container-padding section-spacing max-w-7xl mx-auto ${containerClassName}`}>
        {/* Page Header */}
        <div className="text-center mb-8 sm:mb-12">
          {showBackButton && onBack && (
            <button
              onClick={onBack}
              className="btn btn-secondary btn-sm mb-4 inline-flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>
          )}
          
          {Icon && (
            <div className="flex items-center justify-center mb-4">
              <div className="bg-gradient-to-r from-blue-600 to-orange-500 p-3 rounded-full scale-in">
                <Icon className="h-8 w-8 text-white" />
              </div>
            </div>
          )}
          
          <h1 className="text-heading mb-2 fade-in">
            {title}
          </h1>
          
          {subtitle && (
            <p className="text-body max-w-2xl mx-auto fade-in">
              {subtitle}
            </p>
          )}
          
          {headerActions && (
            <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center items-center fade-in">
              {headerActions}
            </div>
          )}
        </div>
        
        {/* Page Content */}
        <div className="slide-in">
          {children}
        </div>
      </div>
    </div>
  )
}

export default PageLayout