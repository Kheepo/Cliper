import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Download, Share2, Clock, Eye } from 'lucide-react';

interface VideoDetailProps {}

const VideoDetail: React.FC<VideoDetailProps> = () => {
  const { id } = useParams<{ id: string }>();

  // Mock data - in a real app, this would come from an API call
  const videoData = {
    id: id || '1',
    title: 'Sample Video Clip',
    description: 'AI-generated viral clip from your video',
    duration: '0:30',
    views: 1250,
    createdAt: '2024-01-15',
    thumbnailUrl: 'https://via.placeholder.com/640x360?text=Video+Thumbnail',
    videoUrl: '#',
    originalVideo: 'Original Video Name.mp4',
    status: 'completed'
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <Link 
            to="/dashboard" 
            className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">Video Details</h1>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Video Player Section */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-lg overflow-hidden">
              <div className="aspect-video bg-gray-900 flex items-center justify-center">
                <img 
                  src={videoData.thumbnailUrl} 
                  alt={videoData.title}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="p-6">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  {videoData.title}
                </h2>
                <p className="text-gray-600 mb-4">
                  {videoData.description}
                </p>
                <div className="flex items-center space-x-6 text-sm text-gray-500">
                  <div className="flex items-center">
                    <Clock className="w-4 h-4 mr-1" />
                    {videoData.duration}
                  </div>
                  <div className="flex items-center">
                    <Eye className="w-4 h-4 mr-1" />
                    {videoData.views.toLocaleString()} views
                  </div>
                  <div>
                    Created: {videoData.createdAt}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Actions */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Actions</h3>
              <div className="space-y-3">
                <button className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center">
                  <Download className="w-4 h-4 mr-2" />
                  Download Video
                </button>
                <button className="w-full bg-green-600 text-white py-2 px-4 rounded-lg hover:bg-green-700 transition-colors flex items-center justify-center">
                  <Share2 className="w-4 h-4 mr-2" />
                  Share Video
                </button>
              </div>
            </div>

            {/* Video Info */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Video Information</h3>
              <div className="space-y-3 text-sm">
                <div>
                  <span className="font-medium text-gray-700">Video ID:</span>
                  <span className="ml-2 text-gray-600">{videoData.id}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">Original File:</span>
                  <span className="ml-2 text-gray-600">{videoData.originalVideo}</span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">Status:</span>
                  <span className="ml-2">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      {videoData.status}
                    </span>
                  </span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">Duration:</span>
                  <span className="ml-2 text-gray-600">{videoData.duration}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoDetail;