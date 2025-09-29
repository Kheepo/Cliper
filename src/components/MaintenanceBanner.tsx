import React from 'react';
import { AlertTriangle, Wrench } from 'lucide-react';

interface MaintenanceBannerProps {
  message?: string;
  type?: 'warning' | 'info';
}

const MaintenanceBanner: React.FC<MaintenanceBannerProps> = ({ 
  message = "Login services are temporarily unavailable for maintenance. Core video processing features remain fully operational.",
  type = 'warning'
}) => {
  const bgColor = type === 'warning' ? 'bg-yellow-50 border-yellow-200' : 'bg-blue-50 border-blue-200';
  const textColor = type === 'warning' ? 'text-yellow-800' : 'text-blue-800';
  const iconColor = type === 'warning' ? 'text-yellow-600' : 'text-blue-600';
  
  return (
    <div className={`${bgColor} border-l-4 p-4 mb-4`}>
      <div className="flex items-center">
        <div className="flex-shrink-0">
          {type === 'warning' ? (
            <AlertTriangle className={`h-5 w-5 ${iconColor}`} />
          ) : (
            <Wrench className={`h-5 w-5 ${iconColor}`} />
          )}
        </div>
        <div className="ml-3">
          <p className={`text-sm font-medium ${textColor}`}>
            {message}
          </p>
        </div>
      </div>
    </div>
  );
};

export default MaintenanceBanner;