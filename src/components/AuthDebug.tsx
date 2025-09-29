import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../lib/supabase';

const AuthDebug: React.FC = () => {
  const { user, session, isAuthenticated } = useAuth();
  const [sessionInfo, setSessionInfo] = useState<any>(null);
  const [testResult, setTestResult] = useState<string>('');

  useEffect(() => {
    const checkSession = async () => {
      const { data: { session }, error } = await supabase.auth.getSession();
      setSessionInfo({ session, error });
    };
    checkSession();
  }, []);

  const testApiCall = async () => {
    try {
      setTestResult('Testing...');
      
      const { data: { session }, error } = await supabase.auth.getSession();
      
      if (error) {
        setTestResult(`Session Error: ${error.message}`);
        return;
      }
      
      if (!session) {
        setTestResult('No session found');
        return;
      }
      
      // Test API call
      const response = await fetch('http://localhost:8001/api/auth/me', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        }
      });
      
      const responseText = await response.text();
      setTestResult(`API Response: ${response.status} - ${responseText}`);
      
    } catch (error: any) {
      setTestResult(`Error: ${error.message}`);
    }
  };

  return (
    <div className="p-4 bg-gray-100 rounded-lg">
      <h3 className="text-lg font-bold mb-4">Authentication Debug</h3>
      
      <div className="space-y-2 text-sm">
        <div><strong>Is Authenticated:</strong> {isAuthenticated ? 'Yes' : 'No'}</div>
        <div><strong>Current User:</strong> {user?.email || 'None'}</div>
        <div><strong>User ID:</strong> {user?.id || 'None'}</div>
        <div><strong>Session:</strong> {session ? 'Present' : 'None'}</div>
        <div><strong>Access Token:</strong> {session?.access_token ? 'Present' : 'None'}</div>
        
        {sessionInfo && (
          <div>
            <strong>Session Info:</strong>
            <pre className="text-xs bg-white p-2 rounded mt-1">
              {JSON.stringify({
                hasSession: !!sessionInfo.session,
                userId: sessionInfo.session?.user?.id,
                email: sessionInfo.session?.user?.email,
                expiresAt: sessionInfo.session?.expires_at ? new Date(sessionInfo.session.expires_at * 1000).toISOString() : null,
                error: sessionInfo.error
              }, null, 2)}
            </pre>
          </div>
        )}
        
        <button 
          onClick={testApiCall}
          className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
        >
          Test API Call
        </button>
        
        {testResult && (
          <div className="mt-2">
            <strong>Test Result:</strong>
            <pre className="text-xs bg-white p-2 rounded mt-1">{testResult}</pre>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuthDebug;