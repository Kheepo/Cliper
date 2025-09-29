/**
 * Test script to debug the frontend upload flow and blank screen issue
 */

const API_BASE_URL = 'http://localhost:8000';
const FRONTEND_BASE_URL = 'http://localhost:5173';
const TEST_EMAIL = 'test@example.com';
const TEST_PASSWORD = 'testpassword123';

async function testAuthFlow() {
  console.log('🔐 Testing Authentication Flow...');
  
  try {
    // First, try to register a test user
    console.log('\n=== Testing Registration Endpoint ===');
    const registerResponse = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: TEST_EMAIL,
        password: TEST_PASSWORD,
        full_name: 'Test User'
      })
    });
    
    console.log('Register response status:', registerResponse.status);
    if (registerResponse.ok) {
      const registerData = await registerResponse.json();
      console.log('✅ Registration successful');
      console.log('User created:', registerData.user?.email);
    } else {
      const errorData = await registerResponse.text();
      console.log('⚠️ Registration failed (user might already exist):', errorData);
    }
    
    // Test login endpoint
    console.log('\n=== Testing Login Endpoint ===');
    const loginResponse = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: TEST_EMAIL,
        password: TEST_PASSWORD
      })
    });
    
    console.log('Login response status:', loginResponse.status);
        
        if (loginResponse.ok) {
            const loginData = await loginResponse.json();
            console.log('✅ Login successful');
            console.log('Login response structure:', Object.keys(loginData));
            console.log('Access token received:', !!(loginData.tokens && loginData.tokens.access_token));
            if (loginData.tokens) {
                console.log('Token type:', loginData.tokens.token_type);
                console.log('Expires in:', loginData.tokens.expires_in);
            }
            if (loginData.user) {
                console.log('User email:', loginData.user.email);
                console.log('User active:', loginData.user.is_active);
            }
        } else {
            const errorData = await loginResponse.text();
            console.log('❌ Login failed:', errorData);
        }
  } catch (error) {
    console.error('❌ Login error:', error.message);
    return null;
  }
}

async function testJobsEndpoint(accessToken) {
  console.log('\n📋 Testing Jobs Endpoint...');
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/jobs`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      }
    });
    
    console.log('Jobs endpoint status:', response.status);
    
    if (response.ok) {
      const jobs = await response.json();
      console.log('✅ Jobs endpoint working');
      console.log('Number of jobs:', jobs.length || 0);
      
      if (jobs.length > 0) {
        console.log('Sample job ID:', jobs[0].id);
        return jobs[0].id;
      }
    } else {
      const errorData = await response.text();
      console.log('❌ Jobs endpoint failed:', errorData);
    }
  } catch (error) {
    console.error('❌ Jobs endpoint error:', error.message);
  }
  
  return null;
}

async function testResultsEndpoint(accessToken, jobId) {
  console.log('\n📊 Testing Results Endpoint...');
  
  if (!jobId) {
    console.log('⚠️  No job ID available, creating test job ID');
    jobId = 'test-job-id-123';
  }
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/results`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      }
    });
    
    console.log('Results endpoint status:', response.status);
    
    if (response.ok) {
      const results = await response.json();
      console.log('✅ Results endpoint working');
      console.log('Results data:', !!results);
      return results;
    } else {
      const errorData = await response.text();
      console.log('❌ Results endpoint failed:', errorData);
    }
  } catch (error) {
    console.error('❌ Results endpoint error:', error.message);
  }
  
  return null;
}

async function testFrontendPages() {
  console.log('\n🌐 Testing Frontend Pages...');
  
  const pages = [
    { path: '/', name: 'Home' },
    { path: '/login', name: 'Login' },
    { path: '/register', name: 'Register' },
    { path: '/dashboard', name: 'Dashboard' },
    { path: '/upload', name: 'Upload' },
    { path: '/results/test-job-id', name: 'Results' }
  ];
  
  for (const page of pages) {
    try {
      const response = await fetch(`${FRONTEND_BASE_URL}${page.path}`);
      console.log(`${page.name} (${page.path}): ${response.status}`);
      
      if (response.ok) {
        const html = await response.text();
        const hasReactApp = html.includes('React App') || html.includes('root');
        console.log(`  - React app detected: ${hasReactApp}`);
      }
    } catch (error) {
      console.log(`${page.name} (${page.path}): Error - ${error.message}`);
    }
  }
}

async function main() {
  console.log('🚀 Starting Frontend Flow Debug Test\n');
  
  // Test frontend pages accessibility
  await testFrontendPages();
  
  // Test authentication
  const accessToken = await testAuthFlow();
  
  if (accessToken) {
    // Test jobs endpoint
    const jobId = await testJobsEndpoint(accessToken);
    
    // Test results endpoint
    await testResultsEndpoint(accessToken, jobId);
  }
  
  console.log('\n✅ Frontend flow debug test completed');
}

// Run the test
main().catch(console.error);