console.log('🔍 Testing authentication initialization flow...');

// Simulate the BackendAuthService initialization
class TestBackendAuthService {
  constructor() {
    this.accessToken = null;
    this.refreshToken = null;
    this.user = null;
    this.loadTokensFromStorage();
  }

  loadTokensFromStorage() {
    // Simulate localStorage.getItem calls
    console.log('📦 Loading tokens from storage...');
    
    // In a real browser, these would come from localStorage
    // For testing, let's simulate what happens when tokens exist
    this.accessToken = 'test_access_token_123';
    this.refreshToken = 'test_refresh_token_456';
    
    const userStr = JSON.stringify({
      id: 'test_user_id',
      email: 'testuser_1758806039@example.com',
      display_name: 'Test User'
    });
    
    if (userStr) {
      try {
        this.user = JSON.parse(userStr);
        console.log('✅ User loaded from storage:', this.user.email);
      } catch (error) {
        console.error('❌ Failed to parse user from storage:', error);
      }
    }
    
    console.log('🔑 Access token:', this.accessToken ? 'Present' : 'Missing');
    console.log('🔄 Refresh token:', this.refreshToken ? 'Present' : 'Missing');
    console.log('👤 User object:', this.user ? 'Present' : 'Missing');
  }

  isAuthenticated() {
    const result = !!this.accessToken && !!this.user;
    console.log('🔐 isAuthenticated():', result);
    console.log('   - accessToken check:', !!this.accessToken);
    console.log('   - user check:', !!this.user);
    return result;
  }

  async verifyToken() {
    console.log('🔍 Verifying token with backend...');
    
    if (!this.accessToken) {
      console.log('❌ No access token available for verification');
      return { success: false };
    }

    try {
      // Simulate API call to /auth/me
      const response = await fetch('http://localhost:8000/api/auth/me', {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        console.log('❌ Token verification failed:', response.status);
        this.clearTokensFromStorage();
        return { success: false };
      }

      const user = await response.json();
      console.log('✅ Token verification successful:', user.email);
      this.user = user;
      
      return { success: true, user };
    } catch (error) {
      console.error('❌ Token verification error:', error.message);
      this.clearTokensFromStorage();
      return { success: false };
    }
  }

  clearTokensFromStorage() {
    console.log('🧹 Clearing tokens from storage');
    this.accessToken = null;
    this.refreshToken = null;
    this.user = null;
  }
}

// Test the initialization flow
async function testInitialization() {
  console.log('\n1. 🚀 Simulating app startup...');
  
  const authService = new TestBackendAuthService();
  
  console.log('\n2. 🔍 Initial authentication state:');
  const initialAuth = authService.isAuthenticated();
  console.log('   Initial isAuthenticated:', initialAuth);
  
  console.log('\n3. 🔄 Simulating BackendAuthContext initialization...');
  console.log('   Calling verifyToken()...');
  
  const verifyResult = await authService.verifyToken();
  
  console.log('\n4. 📊 Final authentication state:');
  console.log('   verifyToken result:', verifyResult.success);
  const finalAuth = authService.isAuthenticated();
  console.log('   Final isAuthenticated:', finalAuth);
  
  console.log('\n🎯 Analysis:');
  if (initialAuth && finalAuth) {
    console.log('✅ Authentication flow working correctly');
  } else if (!initialAuth && finalAuth) {
    console.log('⚠️  Initial auth failed, but token verification succeeded');
    console.log('   This suggests tokens are loaded but user object might be missing initially');
  } else if (initialAuth && !finalAuth) {
    console.log('❌ Initial auth succeeded but token verification failed');
    console.log('   This suggests stored tokens are invalid');
  } else {
    console.log('❌ Authentication completely failed');
    console.log('   This suggests no valid tokens or user data');
  }
}

// Test with a real login first
async function testWithRealLogin() {
  console.log('\n🔐 Testing with real login first...');
  
  try {
    // Login first
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
    
    // Now test with real tokens
    class RealBackendAuthService extends TestBackendAuthService {
      constructor(tokens, user) {
        super();
        this.accessToken = tokens.access_token;
        this.refreshToken = tokens.refresh_token;
        this.user = user;
      }
    }
    
    console.log('\n🔄 Testing with real tokens...');
    const realAuthService = new RealBackendAuthService(loginResult.tokens, loginResult.user);
    
    console.log('Initial state with real tokens:');
    const realInitialAuth = realAuthService.isAuthenticated();
    console.log('   isAuthenticated:', realInitialAuth);
    
    const realVerifyResult = await realAuthService.verifyToken();
    console.log('   verifyToken result:', realVerifyResult.success);
    
    const realFinalAuth = realAuthService.isAuthenticated();
    console.log('   Final isAuthenticated:', realFinalAuth);
    
  } catch (error) {
    console.error('❌ Real login test failed:', error.message);
  }
}

// Run tests
async function runTests() {
  await testInitialization();
  await testWithRealLogin();
  
  console.log('\n🎉 Authentication initialization test completed!');
}

runTests().catch(console.error);