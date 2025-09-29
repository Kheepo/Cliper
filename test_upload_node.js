import fs from 'fs';
import path from 'path';
import FormData from 'form-data';
import fetch from 'node-fetch';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BASE_URL = 'http://localhost:8001';

// Create a simple test video file
function createTestVideoFile() {
    const testVideoPath = path.join(__dirname, 'node_test_video.mp4');
    
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
        const response = await fetch(`${BASE_URL}/api/v1/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });
        
        if (response.ok) {
            const data = await response.json();
            const token = data.tokens?.access_token || data.access_token;
            console.log(`✓ User registered successfully, token: ${token?.substring(0, 20)}...`);
            return token;
        } else {
            const errorData = await response.text();
            console.log(`✗ Registration failed: ${response.status} - ${errorData}`);
            return null;
        }
    } catch (error) {
        console.log(`✗ Authentication error: ${error.message}`);
        return null;
    }
}

async function uploadVideo(token) {
    console.log('\n2. Testing video upload...');
    
    const videoPath = createTestVideoFile();
    
    try {
        const form = new FormData();
        form.append('file', fs.createReadStream(videoPath));
        form.append('title', 'Node.js Test Video');
        form.append('description', 'Test video uploaded via Node.js');
        
        const response = await fetch(`${BASE_URL}/api/videos/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                ...form.getHeaders()
            },
            body: form
        });
        
        console.log(`Upload response status: ${response.status}`);
        
        if (response.ok) {
            const data = await response.json();
            console.log(`Upload response: ${JSON.stringify(data)}`);
            console.log('✓ Video uploaded successfully!');
            console.log(`  Job ID: ${data.job_id}`);
            console.log(`  File URL: ${data.file_url}`);
            console.log(`  Task ID: ${data.task_id}`);
            
            // Clean up test file
            fs.unlinkSync(videoPath);
            
            return data.job_id;
        } else {
            const errorData = await response.text();
            console.log(`✗ Upload failed: ${response.status} - ${errorData}`);
            return null;
        }
    } catch (error) {
        console.log(`✗ Upload error: ${error.message}`);
        return null;
    }
}

async function checkVideoStatus(token, jobId) {
    console.log('\n3. Checking video status...');
    
    try {
        const response = await fetch(`${BASE_URL}/api/videos/`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const videos = await response.json();
            console.log(`✓ Retrieved ${videos.length} videos`);
            
            const uploadedVideo = videos.find(v => v.id === jobId);
            if (uploadedVideo) {
                console.log(`  Video Status: ${uploadedVideo.status}`);
                console.log(`  Video Title: ${uploadedVideo.title || 'None'}`);
                console.log(`  Video ID: ${uploadedVideo.id}`);
                return uploadedVideo;
            } else {
                console.log('✗ Uploaded video not found in list');
                console.log('Available videos:');
                videos.forEach(v => {
                    console.log(`  - ${v.id}: ${v.title || 'None'} (${v.status})`);
                });
                return null;
            }
        } else {
            const errorData = await response.text();
            console.log(`✗ Status check failed: ${response.status} - ${errorData}`);
            return null;
        }
    } catch (error) {
        console.log(`✗ Status check error: ${error.message}`);
        return null;
    }
}

async function generateClips(token, videoId) {
    console.log('\n4. Testing clip generation...');
    
    const clipData = {
        platforms: ['youtube', 'tiktok'],
        max_clips: 3,
        min_duration: 30,
        max_duration: 60
    };
    
    try {
        const response = await fetch(`${BASE_URL}/api/videos/${videoId}/clips`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(clipData)
        });
        
        console.log(`Clip generation status: ${response.status}`);
        
        if (response.ok) {
            const data = await response.json();
            console.log(`Clip generation response: ${JSON.stringify(data)}`);
            console.log('✓ Clip generation request successful!');
            return true;
        } else {
            const errorData = await response.text();
            console.log(`✗ Clip generation failed: ${response.status} - ${errorData}`);
            return false;
        }
    } catch (error) {
        console.log(`✗ Clip generation error: ${error.message}`);
        return false;
    }
}

async function runTest() {
    console.log('=== NODE.JS VIDEO UPLOAD TEST ===');
    
    // Step 1: Register user
    const token = await registerUser();
    if (!token) {
        console.log('\n=== TEST RESULTS ===');
        console.log('✗ NODE.JS TEST FAILED - No authentication token');
        return;
    }
    
    // Step 2: Upload video
    const jobId = await uploadVideo(token);
    if (!jobId) {
        console.log('\n=== TEST RESULTS ===');
        console.log('✗ NODE.JS TEST FAILED - Upload failed');
        return;
    }
    
    // Step 3: Check video status
    const video = await checkVideoStatus(token, jobId);
    if (!video) {
        console.log('\n=== TEST RESULTS ===');
        console.log('✗ NODE.JS TEST FAILED - Video status check failed');
        return;
    }
    
    // Step 4: Generate clips
    const clipsGenerated = await generateClips(token, jobId);
    
    // Results
    console.log('\n=== TEST RESULTS ===');
    if (clipsGenerated) {
        console.log('✓ NODE.JS VIDEO UPLOAD TEST PASSED');
        console.log(`  Job ID: ${jobId}`);
        console.log(`  Video Status: ${video.status}`);
        console.log('✓ CLIP GENERATION TEST PASSED');
    } else {
        console.log('✗ NODE.JS TEST PARTIALLY FAILED - Clip generation failed');
        console.log(`  Job ID: ${jobId}`);
        console.log(`  Video Status: ${video.status}`);
    }
}

// Run the test
runTest().catch(console.error);