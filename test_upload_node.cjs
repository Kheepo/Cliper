const fs = require('fs');
const path = require('path');
const FormData = require('form-data');
const fetch = require('node-fetch');

const BASE_URL = 'http://localhost:8001';

// Create a simple test video file
function createTestVideoFile() {
    const testVideoPath = path.join(__dirname, 'test_video.mp4');
    
    // Create a minimal MP4 file (just header bytes for testing)
    const mp4Header = Buffer.from([
        0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70, // ftyp box
        0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
        0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
        0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31
    ]);
    
    fs.writeFileSync(testVideoPath, mp4Header);
    return testVideoPath;
}

async function registerUser() {
    console.log('1. Registering test user...');
    
    const uniqueEmail = `test${Date.now()}@example.com`;
    const userData = {
        email: uniqueEmail,
        password: 'testpass123',
        full_name: 'Test User'
    };
    
    try {
        const response = await fetch(`${BASE_URL}/api/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });
        
        if (response.ok) {
            const data = await response.json();
            const token = data.tokens?.access_token;
            console.log(`✓ User registered successfully, token: ${token?.substring(0, 20)}...`);
            return token;
        } else if (response.status === 400) {
            // Try to login with existing user
            console.log('User might exist, trying to login...');
            const loginResponse = await fetch(`${BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: 'test@example.com',
                    password: 'testpass123'
                })
            });
            
            if (loginResponse.ok) {
                const loginData = await loginResponse.json();
                const token = loginData.tokens?.access_token;
                console.log(`✓ User logged in successfully, token: ${token?.substring(0, 20)}...`);
                return token;
            }
        }
        
        const errorText = await response.text();
        console.log(`✗ Authentication failed: ${response.status} - ${errorText}`);
        return null;
    } catch (error) {
        console.log(`✗ Authentication error: ${error.message}`);
        return null;
    }
}

async function uploadVideo(token) {
    console.log('\n2. Testing video upload...');
    
    const testVideoPath = createTestVideoFile();
    
    try {
        const form = new FormData();
        form.append('file', fs.createReadStream(testVideoPath), {
            filename: 'test_video.mp4',
            contentType: 'video/mp4'
        });
        form.append('target_niche', 'entertainment');
        
        const response = await fetch(`${BASE_URL}/api/videos/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                ...form.getHeaders()
            },
            body: form
        });
        
        const responseText = await response.text();
        console.log(`Upload response status: ${response.status}`);
        console.log(`Upload response: ${responseText}`);
        
        if (response.ok) {
            const data = JSON.parse(responseText);
            console.log(`✓ Video uploaded successfully!`);
            console.log(`  Job ID: ${data.job_id}`);
            console.log(`  File URL: ${data.file_url}`);
            console.log(`  Task ID: ${data.task_id}`);
            return data.job_id;
        } else {
            console.log(`✗ Upload failed: ${response.status}`);
            return null;
        }
    } catch (error) {
        console.log(`✗ Upload error: ${error.message}`);
        return null;
    } finally {
        // Clean up test file
        try {
            fs.unlinkSync(testVideoPath);
        } catch (e) {
            // Ignore cleanup errors
        }
    }
}

async function checkJobStatus(token, jobId) {
    console.log('\n3. Checking job status...');
    
    try {
        const response = await fetch(`${BASE_URL}/api/videos/`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const videos = await response.json();
            console.log(`✓ Retrieved ${videos.length} videos`);
            
            const uploadedVideo = videos.find(v => v.id === jobId);
            if (uploadedVideo) {
                console.log(`  Video Status: ${uploadedVideo.status}`);
                console.log(`  Video Title: ${uploadedVideo.title}`);
                return uploadedVideo;
            } else {
                console.log(`✗ Uploaded video not found in list`);
                return null;
            }
        } else {
            console.log(`✗ Failed to get videos: ${response.status}`);
            return null;
        }
    } catch (error) {
        console.log(`✗ Status check error: ${error.message}`);
        return null;
    }
}

async function main() {
    console.log('=== VIDEO UPLOAD TEST ===');
    
    // Step 1: Register/login user
    const token = await registerUser();
    if (!token) {
        console.log('\n✗ TEST FAILED - No authentication token');
        return false;
    }
    
    // Step 2: Upload video
    const jobId = await uploadVideo(token);
    if (!jobId) {
        console.log('\n✗ TEST FAILED - Upload failed');
        return false;
    }
    
    // Step 3: Check job status
    const video = await checkJobStatus(token, jobId);
    
    // Summary
    console.log('\n=== TEST RESULTS ===');
    if (jobId && video) {
        console.log('✓ VIDEO UPLOAD TEST PASSED');
        console.log(`  Job ID: ${jobId}`);
        console.log(`  Video Status: ${video.status}`);
        return true;
    } else {
        console.log('✗ VIDEO UPLOAD TEST FAILED');
        return false;
    }
}

// Install required packages if not available
try {
    require('form-data');
    require('node-fetch');
} catch (e) {
    console.log('Installing required packages...');
    const { execSync } = require('child_process');
    try {
        execSync('npm install form-data node-fetch', { stdio: 'inherit' });
    } catch (installError) {
        console.log('Failed to install packages. Please run: npm install form-data node-fetch');
        process.exit(1);
    }
}

if (require.main === module) {
    main().then(success => {
        process.exit(success ? 0 : 1);
    }).catch(error => {
        console.error('Test failed with error:', error);
        process.exit(1);
    });
}

module.exports = { main };