console.log('🔍 Testing frontend login flow...');

// Test the actual frontend login process
async function testFrontendLogin() {
  console.log('\n1. 🔐 Testing login via frontend API...');
  
  try {
    // First, let's login using the frontend's expected format
    const loginResponse = await fetch('http://localhost:8000/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: 'testuser_1758806039@example.com',
        password: 'testpassword123'
      }),
    });

    if (!loginResponse.ok) {
      const errorData = await loginResponse.text();
      console.log('❌ Login failed:', loginResponse.status, errorData);
      return;
    }

    const loginResult = await loginResponse.json();
    console.log('✅ Login successful for:', loginResult.user.email);
    
    const accessToken = loginResult.tokens.access_token;
    
    // Now test all the endpoints that the frontend pages use
    console.log('\n2. 🧪 Testing all frontend API endpoints...');
    
    const endpoints = [
      { name: 'User Profile', url: '/user/profile', method: 'GET' },
      { name: 'User Settings', url: '/user/settings', method: 'GET' },
      { name: 'User Stats', url: '/users/stats', method: 'GET' },
      { name: 'Analytics User', url: '/analytics/user', method: 'GET' },
      { name: 'Analytics Jobs', url: '/analytics/jobs', method: 'GET' },
      { name: 'Job History', url: '/history', method: 'GET' },
      { name: 'Jobs List', url: '/jobs', method: 'GET' },
      { name: 'Auth Me', url: '/api/auth/me', method: 'GET' }
    ];
    
    const results = [];
    
    for (const endpoint of endpoints) {
      try {
        const response = await fetch(`http://localhost:8000${endpoint.url}`, {
          method: endpoint.method,
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
        });
        
        if (response.ok) {
          const data = await response.json();
          console.log(`✅ ${endpoint.name}: Success`);
          results.push({ endpoint: endpoint.name, status: 'success', code: response.status });
        } else {
          const errorText = await response.text();
          console.log(`❌ ${endpoint.name}: Failed (${response.status}) - ${errorText}`);
          results.push({ endpoint: endpoint.name, status: 'failed', code: response.status, error: errorText });
        }
      } catch (error) {
        console.log(`❌ ${endpoint.name}: Error - ${error.message}`);
        results.push({ endpoint: endpoint.name, status: 'error', error: error.message });
      }
    }
    
    console.log('\n📊 Summary of API endpoint tests:');
    const working = results.filter(r => r.status === 'success');
    const failing = results.filter(r => r.status !== 'success');
    
    console.log(`✅ Working endpoints (${working.length}):`);
    working.forEach(r => console.log(`   - ${r.endpoint}`));
    
    console.log(`❌ Failing endpoints (${failing.length}):`);
    failing.forEach(r => console.log(`   - ${r.endpoint}: ${r.code || 'Error'} - ${r.error || 'Unknown'}`));
    
    // Now let's test what happens when we simulate the frontend auth flow
    console.log('\n3. 🔄 Testing frontend authentication simulation...');
    
    // Simulate BackendAuthService behavior
    const mockBackendAuthService = {
      accessToken: accessToken,
      user: loginResult.user,
      
      isAuthenticated() {
        const result = !!this.accessToken && !!this.user;
        console.log(`   isAuthenticated(): ${result}`);
        return result;
      },
      
      async getAuthHeaders() {
        if (!this.accessToken) {
          throw new Error('No access token available');
        }
        return {
          'Authorization': `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json',
        };
      }
    };
    
    // Test the API service flow
    console.log('\n4. 🌐 Testing API service authentication flow...');
    
    try {
      // Check if authenticated
      if (!mockBackendAuthService.isAuthenticated()) {
        console.log('❌ Would throw: "No active session. Please log in again."');
        return;
      }
      
      console.log('✅ User is authenticated, proceeding with API calls...');
      
      // Get auth headers
      const headers = await mockBackendAuthService.getAuthHeaders();
      console.log('✅ Auth headers obtained successfully');
      
      // Test a failing endpoint to see the exact error
      console.log('\n5. 🔍 Testing specific failing endpoint (analytics/user)...');
      
      const analyticsResponse = await fetch('http://localhost:8000/analytics/user', {
        headers: headers
      });
      
      if (analyticsResponse.ok) {
        console.log('✅ Analytics endpoint working!');
      } else {
        const errorText = await analyticsResponse.text();
        console.log(`❌ Analytics endpoint failed: ${analyticsResponse.status}`);
        console.log(`   Error details: ${errorText}`);
        
        // This is what would cause the "No active session" error in the frontend
        console.log('\n💡 This explains the "No active session" errors!');
        console.log('   The frontend interprets API failures as authentication failures');
      }
      
    } catch (error) {
      console.log(`❌ Auth flow error: ${error.message}`);
    }
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
  }
}

// Run the test
testFrontendLogin().then(() => {
  console.log('\n🎉 Frontend login test completed!');
  
  console.log('\n🔧 Recommended fixes:');
  console.log('1. Fix the failing API endpoints (404/validation errors)');
  console.log('2. Improve error handling to distinguish between auth and API errors');
  console.log('3. Add better user feedback for API endpoint issues');
  console.log('4. Consider graceful degradation for non-critical endpoints');
}).catch(console.error);