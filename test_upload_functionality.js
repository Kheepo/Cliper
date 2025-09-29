/**
 * Comprehensive Upload Functionality Test
 * Tests timeout configurations, progress tracking, and error handling
 */

import fs from 'fs';
import path from 'path';
import FormData from 'form-data';
import axios from 'axios';

// Test configuration
const API_BASE_URL = 'http://localhost:8000';
const TEST_FILES_DIR = './test_files';

// Create test directory if it doesn't exist
if (!fs.existsSync(TEST_FILES_DIR)) {
  fs.mkdirSync(TEST_FILES_DIR, { recursive: true });
}

/**
 * Generate test video file of specified size
 */
function generateTestFile(sizeInMB, filename) {
  const filePath = path.join(TEST_FILES_DIR, filename);
  const sizeInBytes = sizeInMB * 1024 * 1024;
  
  // Create a simple test file with repeated content
  const chunkSize = 1024 * 1024; // 1MB chunks
  const content = Buffer.alloc(chunkSize, 'A'); // Fill with 'A' characters
  
  const writeStream = fs.createWriteStream(filePath);
  
  return new Promise((resolve, reject) => {
    let written = 0;
    
    function writeChunk() {
      if (written >= sizeInBytes) {
        writeStream.end();
        resolve(filePath);
        return;
      }
      
      const remainingBytes = sizeInBytes - written;
      const chunkToWrite = remainingBytes < chunkSize ? 
        content.slice(0, remainingBytes) : content;
      
      writeStream.write(chunkToWrite);
      written += chunkToWrite.length;
      
      // Use setImmediate to avoid blocking
      setImmediate(writeChunk);
    }
    
    writeStream.on('error', reject);
    writeChunk();
  });
}

/**
 * Test upload with timeout monitoring
 */
async function testUpload(filePath, testName) {
  console.log(`\n🧪 Testing: ${testName}`);
  console.log(`📁 File: ${filePath}`);
  
  const startTime = Date.now();
  
  try {
    const formData = new FormData();
    formData.append('file', fs.createReadStream(filePath));
    formData.append('niche', 'test');
    formData.append('quality', 'medium');
    
    const response = await axios.post(`${API_BASE_URL}/api/videos/upload`, formData, {
      headers: {
        ...formData.getHeaders(),
        'Authorization': 'Bearer test-token' // Add if auth is required
      },
      timeout: 30 * 60 * 1000, // 30 minutes timeout
      onUploadProgress: (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        process.stdout.write(`\r📤 Upload Progress: ${percentCompleted}%`);
      }
    });
    
    const duration = Date.now() - startTime;
    console.log(`\n✅ Upload successful in ${duration}ms`);
    console.log(`📋 Job ID: ${response.data.job_id}`);
    
    return {
      success: true,
      jobId: response.data.job_id,
      duration,
      testName
    };
    
  } catch (error) {
    const duration = Date.now() - startTime;
    console.log(`\n❌ Upload failed after ${duration}ms`);
    
    if (error.code === 'ECONNABORTED') {
      console.log(`⏰ Timeout Error: Request timed out`);
    } else if (error.response) {
      console.log(`🚫 HTTP Error: ${error.response.status} - ${error.response.statusText}`);
      console.log(`📄 Response: ${JSON.stringify(error.response.data, null, 2)}`);
    } else {
      console.log(`🔥 Network Error: ${error.message}`);
    }
    
    return {
      success: false,
      error: error.message,
      duration,
      testName
    };
  }
}

/**
 * Test chunked upload functionality
 */
async function testChunkedUpload(filePath, testName) {
  console.log(`\n🧪 Testing Chunked Upload: ${testName}`);
  
  const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks
  const fileStats = fs.statSync(filePath);
  const totalChunks = Math.ceil(fileStats.size / CHUNK_SIZE);
  
  console.log(`📊 File size: ${(fileStats.size / (1024 * 1024)).toFixed(2)}MB`);
  console.log(`🔢 Total chunks: ${totalChunks}`);
  
  const startTime = Date.now();
  
  try {
    // Initialize upload session
    const initResponse = await axios.post(`${API_BASE_URL}/api/videos/upload/init`, {
      filename: path.basename(filePath),
      fileSize: fileStats.size,
      totalChunks,
      niche: 'test',
      quality: 'medium'
    });
    
    const sessionId = initResponse.data.session_id;
    console.log(`🆔 Session ID: ${sessionId}`);
    
    // Upload chunks
    for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
      const start = chunkIndex * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, fileStats.size);
      const chunkBuffer = Buffer.alloc(end - start);
      
      const fd = fs.openSync(filePath, 'r');
      fs.readSync(fd, chunkBuffer, 0, end - start, start);
      fs.closeSync(fd);
      
      const formData = new FormData();
      formData.append('chunk', chunkBuffer, {
        filename: `chunk_${chunkIndex}`,
        contentType: 'application/octet-stream'
      });
      formData.append('chunkIndex', chunkIndex.toString());
      formData.append('sessionId', sessionId);
      
      const chunkStartTime = Date.now();
      
      await axios.post(`${API_BASE_URL}/api/videos/upload/chunk`, formData, {
        headers: formData.getHeaders(),
        timeout: 5 * 60 * 1000 // 5 minutes per chunk
      });
      
      const chunkDuration = Date.now() - chunkStartTime;
      const progress = Math.round(((chunkIndex + 1) / totalChunks) * 100);
      
      console.log(`✅ Chunk ${chunkIndex + 1}/${totalChunks} uploaded in ${chunkDuration}ms (${progress}%)`);
    }
    
    // Finalize upload
    const finalizeResponse = await axios.post(`${API_BASE_URL}/api/videos/upload/finalize`, {
      sessionId,
      niche: 'test',
      quality: 'medium'
    }, {
      timeout: 3 * 60 * 1000 // 3 minutes for finalization
    });
    
    const duration = Date.now() - startTime;
    console.log(`\n✅ Chunked upload successful in ${duration}ms`);
    console.log(`📋 Job ID: ${finalizeResponse.data.job_id}`);
    
    return {
      success: true,
      jobId: finalizeResponse.data.job_id,
      duration,
      testName: `${testName} (Chunked)`
    };
    
  } catch (error) {
    const duration = Date.now() - startTime;
    console.log(`\n❌ Chunked upload failed after ${duration}ms`);
    console.log(`🔥 Error: ${error.message}`);
    
    return {
      success: false,
      error: error.message,
      duration,
      testName: `${testName} (Chunked)`
    };
  }
}

/**
 * Main test runner
 */
async function runUploadTests() {
  console.log('🚀 Starting Upload Functionality Tests\n');
  console.log('=' .repeat(50));
  
  const testResults = [];
  
  try {
    // Test 1: Small file (10MB) - should use regular upload
    console.log('\n📝 Generating test files...');
    const smallFile = await generateTestFile(10, 'test_small_10mb.dat');
    const result1 = await testUpload(smallFile, 'Small File (10MB)');
    testResults.push(result1);
    
    // Test 2: Medium file (100MB) - should use chunked upload
    const mediumFile = await generateTestFile(100, 'test_medium_100mb.dat');
    const result2 = await testChunkedUpload(mediumFile, 'Medium File (100MB)');
    testResults.push(result2);
    
    // Test 3: Large file (500MB) - stress test chunked upload
    const largeFile = await generateTestFile(500, 'test_large_500mb.dat');
    const result3 = await testChunkedUpload(largeFile, 'Large File (500MB)');
    testResults.push(result3);
    
    // Test 4: Very large file (1GB) - ultimate stress test
    const veryLargeFile = await generateTestFile(1024, 'test_very_large_1gb.dat');
    const result4 = await testChunkedUpload(veryLargeFile, 'Very Large File (1GB)');
    testResults.push(result4);
    
  } catch (error) {
    console.error('❌ Test setup failed:', error.message);
    return;
  }
  
  // Print test summary
  console.log('\n' + '=' .repeat(50));
  console.log('📊 TEST SUMMARY');
  console.log('=' .repeat(50));
  
  const successful = testResults.filter(r => r.success);
  const failed = testResults.filter(r => !r.success);
  
  console.log(`✅ Successful: ${successful.length}/${testResults.length}`);
  console.log(`❌ Failed: ${failed.length}/${testResults.length}`);
  
  if (successful.length > 0) {
    console.log('\n🎉 Successful Tests:');
    successful.forEach(result => {
      console.log(`  ✅ ${result.testName} - ${result.duration}ms`);
    });
  }
  
  if (failed.length > 0) {
    console.log('\n💥 Failed Tests:');
    failed.forEach(result => {
      console.log(`  ❌ ${result.testName} - ${result.error}`);
    });
  }
  
  // Cleanup test files
  console.log('\n🧹 Cleaning up test files...');
  try {
    fs.rmSync(TEST_FILES_DIR, { recursive: true, force: true });
    console.log('✅ Cleanup completed');
  } catch (error) {
    console.log('⚠️  Cleanup warning:', error.message);
  }
  
  console.log('\n🏁 Upload functionality tests completed!');
}

// Run tests if this script is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runUploadTests().catch(console.error);
}

export {
  runUploadTests,
  testUpload,
  testChunkedUpload,
  generateTestFile
};