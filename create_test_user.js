#!/usr/bin/env node
/**
 * Create a test user for upload testing
 */

import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

const API_BASE_URL = 'http://localhost:8000';

async function createTestUser() {
    console.log('🚀 Creating test user for upload testing');
    console.log('========================================');
    
    // Test user credentials (matching test files)
    let testEmail = 'test@example.com';
    let testPassword = 'SecureP@ssw0rd123!';
    
    // Alternative test credentials to try
    const altTestEmail = 'testuser@example.com';
    const altTestPassword = 'SecureP@ssw0rd123!';
    
    console.log(`📧 Test email: ${testEmail}`);
    console.log(`🔑 Test password: ${testPassword}`);
    
    try {
        // Try login first
        console.log('\n🔸 Step 1: Trying login with existing test user...');
        const loginData = {
            email: testEmail,
            password: testPassword
        };
        
        try {
            const loginResponse = await axios.post(
                `${API_BASE_URL}/api/auth/login`,
                loginData,
                {
                    headers: { 'Content-Type': 'application/json' },
                    timeout: 30000
                }
            );
            
            if (loginResponse.status === 200) {
                console.log('✅ Login successful with existing user!');
                const loginResult = loginResponse.data;
                console.log(`   Access Token: ${loginResult.tokens.access_token.substring(0, 20)}...`);
                
                const credentials = {
                    email: testEmail,
                    password: testPassword,
                    access_token: loginResult.tokens.access_token,
                    user_id: loginResult.user.id
                };
                
                console.log('\n🎉 Test user login successful!');
                console.log('Use these credentials for upload testing:');
                console.log(`Email: ${testEmail}`);
                console.log(`Password: ${testPassword}`);
                console.log(`Token: ${loginResult.tokens.access_token.substring(0, 30)}...`);
                
                return credentials;
            }
        } catch (loginError) {
            console.log('❌ Login failed:', loginError.response?.status, loginError.response?.data);
            
            // Try alternative credentials
            console.log('\n🔸 Trying alternative credentials...');
            try {
                const altLoginResponse = await axios.post(`${API_BASE_URL}/api/auth/login`, {
                    email: altTestEmail,
                    password: altTestPassword
                });
                
                if (altLoginResponse.data && altLoginResponse.data.access_token) {
                    console.log('✅ Alternative login successful!');
                    console.log('📝 Credentials saved to test_credentials.json');
                    
                    // Save credentials for upload test
                    const credentials = {
                        email: altTestEmail,
                        password: altTestPassword,
                        access_token: altLoginResponse.data.access_token
                    };
                    
                    await fs.writeFile('test_credentials.json', JSON.stringify(credentials, null, 2));
                    return credentials;
                }
            } catch (altLoginError) {
                console.log('❌ Alternative login also failed:', altLoginError.response?.status, altLoginError.response?.data);
            }
            
            console.log('Will try registration...');
        }
        
        // If login failed, try registration with unique email
        testEmail = `test_${uuidv4().slice(0, 8)}@example.com`;
        console.log(`\n🔸 Step 2: Registering new test user: ${testEmail}`);
        const registrationData = {
            email: testEmail,
            password: testPassword,
            full_name: 'Upload Test User'
        };
        
        const registerResponse = await axios.post(
            `${API_BASE_URL}/api/auth/register`,
            registrationData,
            {
                headers: { 'Content-Type': 'application/json' },
                timeout: 30000
            }
        );
        
        if (registerResponse.status === 201) {
            console.log('✅ Registration successful!');
            const result = registerResponse.data;
            console.log(`   User ID: ${result.user.id}`);
            console.log(`   Email: ${result.user.email}`);
            console.log(`   Access Token: ${result.tokens.access_token.substring(0, 20)}...`);
            
            // Test login immediately
            console.log('\n🔸 Step 2: Testing login...');
            const loginData = {
                email: testEmail,
                password: testPassword
            };
            
            const loginResponse = await axios.post(
                `${API_BASE_URL}/api/auth/login`,
                loginData,
                {
                    headers: { 'Content-Type': 'application/json' },
                    timeout: 30000
                }
            );
            
            if (loginResponse.status === 200) {
                console.log('✅ Login successful!');
                const loginResult = loginResponse.data;
                console.log(`   Access Token: ${loginResult.tokens.access_token.substring(0, 20)}...`);
                
                // Save credentials for upload testing
                console.log('\n💾 Saving test credentials...');
                const credentials = {
                    email: testEmail,
                    password: testPassword,
                    access_token: loginResult.tokens.access_token,
                    user_id: loginResult.user.id
                };
                
                console.log('\n🎉 Test user created successfully!');
                console.log('Use these credentials for upload testing:');
                console.log(`Email: ${testEmail}`);
                console.log(`Password: ${testPassword}`);
                console.log(`Token: ${loginResult.tokens.access_token.substring(0, 30)}...`);
                
                return credentials;
            } else {
                console.log(`❌ Login failed: ${loginResponse.status}`);
                console.log(loginResponse.data);
            }
        } else {
            console.log(`❌ Registration failed: ${registerResponse.status}`);
            console.log(registerResponse.data);
        }
    } catch (error) {
        if (error.code === 'ECONNREFUSED') {
            console.log('❌ Connection refused - is the backend server running on port 8000?');
        } else if (error.response) {
            console.log(`❌ Request failed: ${error.response.status}`);
            console.log('Response data:', error.response.data);
        } else {
            console.log(`❌ Error: ${error.message}`);
        }
    }
}

// Debug output
console.log('Script loaded, checking execution context...');
console.log('process.argv[1]:', process.argv[1]);
console.log('import.meta.url:', import.meta.url);

// Run if this file is executed directly
const scriptPath = new URL(import.meta.url).pathname;
const isMainModule = process.argv[1].endsWith('create_test_user.js');
console.log('isMainModule:', isMainModule);

if (isMainModule) {
    console.log('Running createTestUser...');
    createTestUser();
} else {
    console.log('Script imported as module, not executing createTestUser');
}

export { createTestUser };