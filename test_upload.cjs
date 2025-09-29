const fs = require('fs');
const FormData = require('form-data');
const fetch = require('node-fetch');

async function testUpload() {
    try {
        console.log('Testing upload to /api/v1/jobs/upload...');
        
        // Create a simple test file
        const testContent = 'This is a test file for upload';
        fs.writeFileSync('test_file.txt', testContent);
        
        // Create form data
        const form = new FormData();
        form.append('file', fs.createReadStream('test_file.txt'));
        form.append('job_type', 'test');
        
        // Make the request
        const response = await fetch('http://localhost:8000/api/v1/jobs/upload', {
            method: 'POST',
            body: form,
            headers: {
                ...form.getHeaders()
            }
        });
        
        console.log('Response status:', response.status);
        console.log('Response headers:', Object.fromEntries(response.headers));
        
        const responseText = await response.text();
        console.log('Response body:', responseText);
        
        // Clean up
        fs.unlinkSync('test_file.txt');
        
    } catch (error) {
        console.error('Upload test failed:', error.message);
        
        // Clean up on error
        try {
            fs.unlinkSync('test_file.txt');
        } catch (e) {
            // Ignore cleanup errors
        }
    }
}

testUpload();