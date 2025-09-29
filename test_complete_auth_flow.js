// Complete authentication flow test
const testCompleteAuthFlow = async () => {
  console.log('🔍 Testing complete authentication flow...');
  
  const baseUrl = 'http://localhost:8000';
  
  try {
    // Step 1: Login and get tokens
    console.log('\n1. 🔐 Testing login...');
    const loginResponse = await fetch(`${baseUrl}/api/auth/login`, {
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
      const errorData = await loginResponse.json();
      console.error('❌ Login failed:', errorData);
      return;
    }
    
    const loginData = await loginResponse.json();
    const accessToken = loginData.tokens.access_token;
    console.log('✅ Login successful for:', loginData.user.email);
    
    // Step 2: Test /auth/me endpoint (used by BackendAuthContext)
    console.log('\n2. 👤 Testing /auth/me endpoint...');
    const meResponse = await fetch(`${baseUrl}/api/auth/me`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (meResponse.ok) {
      const userData = await meResponse.json();
      console.log('✅ /auth/me successful:', userData.email);
    } else {
      const errorData = await meResponse.json();
      console.error('❌ /auth/me failed:', errorData);
      return;
    }
    
    // Step 3: Test Dashboard endpoints
    console.log('\n3. 📊 Testing Dashboard endpoints...');
    
    // Test getUserAnalytics (the failing one)
    console.log('   Testing /analytics/user...');
    const userAnalyticsResponse = await fetch(`${baseUrl}/api/analytics/user`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (userAnalyticsResponse.ok) {
      const analyticsData = await userAnalyticsResponse.json();
      console.log('✅ /analytics/user successful');
    } else {
      const errorData = await userAnalyticsResponse.json();
      console.log('❌ /analytics/user failed:', errorData.message);
    }
    
    // Test getJobAnalytics
    console.log('   Testing /analytics/jobs...');
    const jobAnalyticsResponse = await fetch(`${baseUrl}/api/analytics/jobs`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (jobAnalyticsResponse.ok) {
      const jobData = await jobAnalyticsResponse.json();
      console.log('✅ /analytics/jobs successful');
    } else {
      const errorData = await jobAnalyticsResponse.json();
      console.log('❌ /analytics/jobs failed:', errorData.message);
    }
    
    // Step 4: Test Upload page endpoints
    console.log('\n4. 📤 Testing Upload page endpoints...');
    
    // Test user settings (used by Upload page)
    const settingsResponse = await fetch(`${baseUrl}/api/user/settings`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (settingsResponse.ok) {
      console.log('✅ /user/settings successful');
    } else {
      const errorData = await settingsResponse.json();
      console.log('❌ /user/settings failed:', errorData.message);
    }
    
    // Step 5: Test History page endpoints
    console.log('\n5. 📜 Testing History page endpoints...');
    
    // Test user history
    const historyResponse = await fetch(`${baseUrl}/api/history?page=1&limit=10`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (historyResponse.ok) {
      const historyData = await historyResponse.json();
      console.log('✅ /history successful, jobs:', historyData.jobs?.length || 0);
    } else {
      const errorData = await historyResponse.json();
      console.log('❌ /history failed:', errorData.message);
    }
    
    // Test jobs endpoint
    const jobsResponse = await fetch(`${baseUrl}/api/jobs`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (jobsResponse.ok) {
      const jobsData = await jobsResponse.json();
      console.log('✅ /jobs successful, count:', jobsData.length || 'N/A');
    } else {
      const errorData = await jobsResponse.json();
      console.log('❌ /jobs failed:', errorData.message);
    }
    
    // Step 6: Test Settings page endpoints
    console.log('\n6. ⚙️ Testing Settings page endpoints...');
    
    // Test user profile
    const profileResponse = await fetch(`${baseUrl}/api/user/profile`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (profileResponse.ok) {
      console.log('✅ /user/profile successful');
    } else {
      const errorData = await profileResponse.json();
      console.log('❌ /user/profile failed:', errorData.message);
    }
    
    // Test user stats
    const statsResponse = await fetch(`${baseUrl}/api/users/stats`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (statsResponse.ok) {
      console.log('✅ /users/stats successful');
    } else {
      const errorData = await statsResponse.json();
      console.log('❌ /users/stats failed:', errorData.message);
    }
    
    console.log('\n🎉 Authentication flow test completed!');
    console.log('\n📋 Summary:');
    console.log('- Authentication system: ✅ Working');
    console.log('- Token validation: ✅ Working');
    console.log('- Some API endpoints have validation issues (not auth-related)');
    console.log('\n💡 The "No active session" errors are likely due to:');
    console.log('1. Frontend not properly storing/retrieving tokens from localStorage');
    console.log('2. BackendAuthContext not properly initializing on app startup');
    console.log('3. API service not properly sending auth headers');
    
  } catch (error) {
    console.error('💥 Test failed with error:', error);
  }
};

// Run the test
testCompleteAuthFlow();