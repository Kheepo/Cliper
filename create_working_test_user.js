import axios from 'axios';
import { promises as fs } from 'fs';

const API_BASE_URL = 'http://localhost:8000';

async function createWorkingTestUser() {
    console.log('🔧 Creating a working test user for upload testing');
    console.log('================================================');
    
    // Generate a unique email for this test
    const timestamp = Date.now();
    const testEmail = `upload_test_${timestamp}@example.com`;
    const testPassword = 'UploadTest123!';
    
    console.log(`📧 Creating user: ${testEmail}`);
    console.log(`🔑 Password: ${testPassword}`);
    
    try {
        // Step 1: Register the user
        console.log('\n🔸 Step 1: Registering new user...');
        const registerResponse = await axios.post(`${API_BASE_URL}/api/auth/register`, {
            email: testEmail,
            password: testPassword,
            confirm_password: testPassword
        });
        
        if (registerResponse.status === 201 || registerResponse.status === 200) {
            console.log('✅ Registration successful!');
            
            // Check if we got tokens directly from registration
            if (registerResponse.data && registerResponse.data.tokens && registerResponse.data.tokens.access_token) {
                console.log('✅ Got access token from registration!');
                
                const credentials = {
                    email: testEmail,
                    password: testPassword,
                    access_token: registerResponse.data.tokens.access_token,
                    user_id: registerResponse.data.user?.id
                };
                
                await fs.writeFile('upload_test_credentials.json', JSON.stringify(credentials, null, 2));
                console.log('📝 Credentials saved to upload_test_credentials.json');
                
                return credentials;
            }
        }
        
        // Step 2: If no tokens from registration, try login
        console.log('\n🔸 Step 2: Logging in with new user...');
        const loginResponse = await axios.post(`${API_BASE_URL}/api/auth/login`, {
            email: testEmail,
            password: testPassword
        });
        
        if (loginResponse.data && loginResponse.data.tokens && loginResponse.data.tokens.access_token) {
            console.log('✅ Login successful!');
            
            const credentials = {
                email: testEmail,
                password: testPassword,
                access_token: loginResponse.data.tokens.access_token,
                user_id: loginResponse.data.user?.id
            };
            
            await fs.writeFile('upload_test_credentials.json', JSON.stringify(credentials, null, 2));
            console.log('📝 Credentials saved to upload_test_credentials.json');
            
            return credentials;
        } else {
            console.log('❌ Login response missing tokens:', loginResponse.data);
            return null;
        }
        
    } catch (error) {
        console.log('❌ Error:', error.response?.status, error.response?.data || error.message);
        
        // If user already exists, try to login
        if (error.response?.status === 400 && error.response?.data?.detail?.includes('already registered')) {
            console.log('\n🔸 User already exists, trying login...');
            try {
                const loginResponse = await axios.post(`${API_BASE_URL}/api/auth/login`, {
                    email: testEmail,
                    password: testPassword
                });
                
                if (loginResponse.data && loginResponse.data.tokens && loginResponse.data.tokens.access_token) {
                    console.log('✅ Login with existing user successful!');
                    
                    const credentials = {
                        email: testEmail,
                        password: testPassword,
                        access_token: loginResponse.data.tokens.access_token,
                        user_id: loginResponse.data.user?.id
                    };
                    
                    await fs.writeFile('upload_test_credentials.json', JSON.stringify(credentials, null, 2));
                    console.log('📝 Credentials saved to upload_test_credentials.json');
                    
                    return credentials;
                }
            } catch (loginError) {
                console.log('❌ Login with existing user failed:', loginError.response?.status, loginError.response?.data);
            }
        }
        
        return null;
    }
}

// Check if this script is being run directly
const isMainModule = process.argv[1].endsWith('create_working_test_user.js');

if (isMainModule) {
    createWorkingTestUser().then(result => {
        if (result) {
            console.log('\n🎉 Success! Test user created and credentials saved.');
            console.log('You can now run upload tests with these credentials.');
        } else {
            console.log('\n❌ Failed to create working test user.');
            process.exit(1);
        }
    }).catch(console.error);
}

export { createWorkingTestUser };