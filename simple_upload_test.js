/**
 * Simple Upload Test - Verify basic upload functionality
 */

import axios from 'axios';
import fs from 'fs';
import FormData from 'form-data';

const API_BASE_URL = 'http://localhost:8000';

async function testServerConnection() {
  console.log('🔍 Testing server connection...');
  try {
    const response = await axios.get(`${API_BASE_URL}/health`, { timeout: 5000 });
    console.log('✅ Server is responding:', response.status);
    return true;
  } catch (error) {
    console.log('❌ Server connection failed:', error.message);
    return false;
  }
}

async function getTestToken() {
  console.log('🔑 Attempting to get test authentication token...');
  try {
    // Try to login with test credentials
    const loginResponse = await axios.post(`${API_BASE_URL}/api/auth/login`, {
      email: 'test@example.com',
      password: 'password123'
    }, { timeout: 10000 });
    
    if (loginResponse.data && loginResponse.data.session && loginResponse.data.session.access_token) {
      console.log('✅ Test token obtained successfully');
      return loginResponse.data.session.access_token;
    } else {
      console.log('⚠️ Login successful but no token in expected format');
      console.log('Response structure:', JSON.stringify(loginResponse.data, null, 2));
      return null;
    }
  } catch (error) {
    console.log('❌ Failed to get test token:', error.message);
    if (error.response) {
      console.log('Response status:', error.response.status);
      console.log('Response data:', JSON.stringify(error.response.data, null, 2));
    }
    return null;
  }
}

async function createTestFile() {
  console.log('📝 Creating test file...');
  const testContent = 'This is a test file for upload functionality testing.\n'.repeat(1000);
  const filePath = './test_upload.txt';
  
  fs.writeFileSync(filePath, testContent);
  console.log(`✅ Test file created: ${filePath} (${testContent.length} bytes)`);
  return filePath;
}

async function testBasicUpload(authToken) {
  console.log('\n🧪 Testing basic upload functionality...');
  
  try {
    const filePath = await createTestFile();
    const formData = new FormData();
    
    formData.append('file', fs.createReadStream(filePath));
    formData.append('niche', 'test');
    formData.append('quality', 'medium');
    
    console.log('📤 Uploading file...');
    const startTime = Date.now();
    
    const headers = {
      ...formData.getHeaders(),
    };
    
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    const response = await axios.post(`${API_BASE_URL}/api/videos/upload`, formData, {
      headers,
      timeout: 60000, // 1 minute timeout
      onUploadProgress: (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        process.stdout.write(`\r📊 Progress: ${percentCompleted}%`);
      }
    });
    
    const duration = Date.now() - startTime;
    console.log(`\n✅ Upload successful in ${duration}ms`);
    console.log('📋 Response:', JSON.stringify(response.data, null, 2));
    
    // Cleanup
    fs.unlinkSync(filePath);
    console.log('🧹 Test file cleaned up');
    
    return response.data;
    
  } catch (error) {
    console.log('\n❌ Upload failed:');
    
    if (error.code === 'ECONNABORTED') {
      console.log('⏰ Request timed out');
    } else if (error.response) {
      console.log(`🚫 HTTP ${error.response.status}: ${error.response.statusText}`);
      console.log('📄 Response data:', JSON.stringify(error.response.data, null, 2));
    } else if (error.request) {
      console.log('🌐 No response received from server');
    } else {
      console.log('🔥 Error:', error.message);
    }
    
    throw error;
  }
}

async function testChunkedUploadInit(authToken) {
  console.log('\n🧪 Testing chunked upload initialization...');
  
  try {
    const headers = {};
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    const response = await axios.post(`${API_BASE_URL}/api/videos/upload/init`, {
      filename: 'test_chunked.txt',
      fileSize: 1024000, // 1MB
      totalChunks: 10,
      niche: 'test',
      quality: 'medium'
    }, {
      headers,
      timeout: 30000
    });
    
    console.log('✅ Chunked upload init successful');
    console.log('📋 Response:', JSON.stringify(response.data, null, 2));
    
    return response.data;
    
  } catch (error) {
    console.log('❌ Chunked upload init failed:', error.message);
    if (error.response) {
      console.log('📄 Response data:', JSON.stringify(error.response.data, null, 2));
    }
    throw error;
  }
}

async function runSimpleTests() {
  console.log('🚀 Starting Simple Upload Tests');
  console.log('=' .repeat(40));
  
  try {
    // Test 1: Server connection
    const serverOk = await testServerConnection();
    if (!serverOk) {
      console.log('❌ Cannot proceed - server is not responding');
      return;
    }
    
    // Test 2: Get authentication token
    const authToken = await getTestToken();
    if (!authToken) {
      console.log('⚠️ No authentication token available - testing without auth');
    }
    
    // Test 3: Basic upload
    await testBasicUpload(authToken);
    
    // Test 4: Chunked upload initialization
    await testChunkedUploadInit(authToken);
    
    console.log('\n🎉 All tests completed successfully!');
    
  } catch (error) {
    console.log('\n💥 Test suite failed:', error.message);
  }
}

// Run the tests
runSimpleTests().catch(console.error);