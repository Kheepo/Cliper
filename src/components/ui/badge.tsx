import React from 'react';
import { cn } from '../../utils/cn';

/**
 * Badge variant types for different visual styles
 */
export type BadgeVariant = 'default' | 'destructive' | 'outline' | 'secondary';

/**
 * Props for the Badge component
 */
export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Visual variant of the badge */
  variant?: BadgeVariant;
  /** Content to display inside the badge */
  children: React.ReactNode;
}

/**
 * Tailwind CSS classes for each badge variant
 */
const badgeVariants: Record<BadgeVariant, string> = {
  default: 'bg-blue-600 text-white hover:bg-blue-700',
  destructive: 'bg-red-600 text-white hover:bg-red-700',
  outline: 'border border-gray-300 text-gray-700 hover:bg-gray-50',
  secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200'
};

/**
 * A versatile badge component for displaying status, labels, or categories.
 * 
 * @example
 * ```tsx
 * <Badge variant="default">New</Badge>
 * <Badge variant="destructive">Error</Badge>
 * <Badge variant="outline">Draft</Badge>
 * ```
 */
export const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = 'default', children, ...props }, ref) => {
    return (
      <div
        className={cn(
          'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
          badgeVariants[variant],
          className
        )}
        ref={ref}
        role="status"
        aria-label={typeof children === 'string' ? children : undefined}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Badge.displayName = 'Badge';