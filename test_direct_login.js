import axios from 'axios';
import { promises as fs } from 'fs';

const API_BASE_URL = 'http://localhost:8000';

async function testDirectLogin() {
    console.log('🔍 Testing direct login with existing users');
    console.log('==========================================');
    
    // List of users from database debug output
    const testUsers = [
        { email: 'test@example.com', authId: '8ab4c54d-7f8c-4625-a6a1-2d651bd1a8a5' },
        { email: 'test_e970102e@example.com', authId: 'a0466a10-1ad4-4e42-9bb9-af317200b14c' },
        { email: 'debug_e65d6db2@example.com', authId: 'b473ad2c-c100-4955-8801-7ac782d4d6da' }
    ];
    
    // Common test passwords to try
    const passwords = [
        'SecureP@ssw0rd123!',
        'password123',
        'testpassword',
        'Password123!',
        'test123'
    ];
    
    for (const user of testUsers) {
        console.log(`\n🧪 Testing user: ${user.email}`);
        
        for (const password of passwords) {
            try {
                console.log(`   🔑 Trying password: ${password.substring(0, 4)}...`);
                
                const response = await axios.post(`${API_BASE_URL}/api/auth/login`, {
                    email: user.email,
                    password: password
                });
                
                if (response.data && response.data.access_token) {
                    console.log(`   ✅ SUCCESS! Login worked for ${user.email}`);
                    console.log(`   🎯 Password: ${password}`);
                    console.log(`   🔐 Token: ${response.data.access_token.substring(0, 20)}...`);
                    
                    // Save working credentials
                    const credentials = {
                        email: user.email,
                        password: password,
                        access_token: response.data.access_token,
                        authId: user.authId
                    };
                    
                    await fs.writeFile('working_test_credentials.json', JSON.stringify(credentials, null, 2));
                    console.log(`   📝 Credentials saved to working_test_credentials.json`);
                    
                    return credentials;
                }
            } catch (error) {
                const status = error.response?.status || 'unknown';
                const message = error.response?.data?.detail || error.message;
                console.log(`   ❌ Failed (${status}): ${message}`);
            }
        }
    }
    
    console.log('\n❌ No working credentials found');
    return null;
}

// Check if this script is being run directly
const isMainModule = process.argv[1].endsWith('test_direct_login.js');

if (isMainModule) {
    testDirectLogin().catch(console.error);
}

export { testDirectLogin };