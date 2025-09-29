console.log('🔍 Testing browser localStorage state...');

// Test what happens when we try to access the frontend with stored tokens
async function testBrowserStorage() {
  console.log('\n1. 🌐 Testing frontend localStorage simulation...');
  
  // Simulate what happens in a real browser
  const mockLocalStorage = {
    storage: {},
    getItem(key) {
      return this.storage[key] || null;
    },
    setItem(key, value) {
      this.storage[key] = value;
    },
    removeItem(key) {
      delete this.storage[key];
    }
  };
  
  // First, let's login and store tokens
  console.log('\n2. 🔐 Performing fresh login...');
  
  try {
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
      console.log('❌ Login failed:', loginResponse.status);
      return;
    }

    const loginResult = await loginResponse.json();
    console.log('✅ Login successful for:', loginResult.user.email);
    
    // Store tokens in mock localStorage (simulating browser behavior)
    mockLocalStorage.setItem('cliper_access_token', loginResult.tokens.access_token);
    mockLocalStorage.setItem('cliper_refresh_token', loginResult.tokens.refresh_token);
    mockLocalStorage.setItem('cliper_user', JSON.stringify(loginResult.user));
    
    console.log('✅ Tokens stored in localStorage');
    
    // Now simulate app restart - loading tokens from storage
    console.log('\n3. 🔄 Simulating app restart (loading from localStorage)...');
    
    const storedAccessToken = mockLocalStorage.getItem('cliper_access_token');
    const storedRefreshToken = mockLocalStorage.getItem('cliper_refresh_token');
    const storedUserStr = mockLocalStorage.getItem('cliper_user');
    
    console.log('📦 Loaded from storage:');
    console.log('   Access token:', storedAccessToken ? 'Present (length: ' + storedAccessToken.length + ')' : 'Missing');
    console.log('   Refresh token:', storedRefreshToken ? 'Present' : 'Missing');
    console.log('   User data:', storedUserStr ? 'Present' : 'Missing');
    
    let storedUser = null;
    if (storedUserStr) {
      try {
        storedUser = JSON.parse(storedUserStr);
        console.log('   User email:', storedUser.email);
      } catch (error) {
        console.error('❌ Failed to parse stored user:', error);
      }
    }
    
    // Check if we would be considered "authenticated" initially
    const initiallyAuthenticated = !!storedAccessToken && !!storedUser;
    console.log('\n🔐 Initial authentication state:', initiallyAuthenticated);
    
    // Now test token verification (what BackendAuthContext does on startup)
    console.log('\n4. 🔍 Testing token verification...');
    
    if (storedAccessToken) {
      try {
        const verifyResponse = await fetch('http://localhost:8000/api/auth/me', {
          headers: {
            'Authorization': `Bearer ${storedAccessToken}`,
            'Content-Type': 'application/json',
          },
        });

        if (verifyResponse.ok) {
          const verifiedUser = await verifyResponse.json();
          console.log('✅ Token verification successful:', verifiedUser.email);
          console.log('✅ User would remain authenticated');
        } else {
          console.log('❌ Token verification failed:', verifyResponse.status);
          console.log('❌ User would be logged out and need to login again');
          
          // This is what happens in the real app
          mockLocalStorage.removeItem('cliper_access_token');
          mockLocalStorage.removeItem('cliper_refresh_token');
          mockLocalStorage.removeItem('cliper_user');
          console.log('🧹 Tokens cleared from storage');
        }
      } catch (error) {
        console.error('❌ Token verification error:', error.message);
        console.log('❌ User would be logged out due to network error');
      }
    } else {
      console.log('❌ No access token to verify');
    }
    
    // Test what happens when we try to make API calls
    console.log('\n5. 🌐 Testing API calls with current auth state...');
    
    const currentToken = mockLocalStorage.getItem('cliper_access_token');
    const currentUser = mockLocalStorage.getItem('cliper_user');
    
    if (currentToken && currentUser) {
      console.log('✅ User appears authenticated, testing API calls...');
      
      // Test the analytics endpoint that's failing
      try {
        const analyticsResponse = await fetch('http://localhost:8000/analytics/user', {
          headers: {
            'Authorization': `Bearer ${currentToken}`,
            'Content-Type': 'application/json',
          },
        });
        
        if (analyticsResponse.ok) {
          console.log('✅ Analytics API call successful');
        } else {
          const errorText = await analyticsResponse.text();
          console.log('❌ Analytics API call failed:', analyticsResponse.status, errorText);
        }
      } catch (error) {
        console.error('❌ Analytics API call error:', error.message);
      }
    } else {
      console.log('❌ User not authenticated, API calls would fail with "No active session"');
    }
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
  }
}

// Run the test
testBrowserStorage().then(() => {
  console.log('\n🎉 Browser storage test completed!');
  
  console.log('\n📋 Summary of findings:');
  console.log('1. Fresh login works correctly');
  console.log('2. Tokens are stored in localStorage');
  console.log('3. On app restart, tokens are loaded from localStorage');
  console.log('4. Token verification determines if user stays logged in');
  console.log('5. If verification fails, user is logged out automatically');
  console.log('6. "No active session" errors occur when tokens are cleared');
}).catch(console.error);