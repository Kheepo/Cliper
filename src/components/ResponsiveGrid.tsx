import React from 'react'

interface ResponsiveGridProps {
  children: React.ReactNode
  columns?: {
    sm?: number
    md?: number
    lg?: number
    xl?: number
  }
  gap?: 'sm' | 'md' | 'lg'
  className?: string
}

const ResponsiveGrid: React.FC<ResponsiveGridProps> = ({
  children,
  columns = { sm: 1, md: 2, lg: 3, xl: 4 },
  gap = 'md',
  className = ''
}) => {
  const getGridClasses = () => {
    const baseClasses = 'grid'
    
    const columnClasses = [
      'grid-cols-1', // Default mobile
      columns.sm && `sm:grid-cols-${columns.sm}`,
      columns.md && `md:grid-cols-${columns.md}`,
      columns.lg && `lg:grid-cols-${columns.lg}`,
      columns.xl && `xl:grid-cols-${columns.xl}`
    ].filter(Boolean).join(' ')
    
    const gapClasses = {
      sm: 'gap-3 sm:gap-4',
      md: 'gap-4 sm:gap-6',
      lg: 'gap-6 sm:gap-8'
    }[gap]
    
    return `${baseClasses} ${columnClasses} ${gapClasses} ${className}`
  }

  return (
    <div className={getGridClasses()}>
      {children}
    </div>
  )
}

export default ResponsiveGrid