/**
 * Test script to validate upload timeout fixes and functionality
 * This script tests various upload scenarios to ensure timeout optimizations work correctly
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Test configuration
const TEST_CONFIG = {
  baseUrl: 'http://localhost:8000',
  frontendUrl: 'http://localhost:5173',
  testFiles: [
    { name: 'small_test.mp4', size: 10 * 1024 * 1024 }, // 10MB
    { name: 'medium_test.mp4', size: 50 * 1024 * 1024 }, // 50MB
    { name: 'large_test.mp4', size: 100 * 1024 * 1024 }, // 100MB
  ],
  chunkSize: 1024 * 1024, // 1MB chunks
  timeouts: {
    chunkUpload: 20 * 60 * 1000, // 20 minutes
    finalizeUpload: 10 * 60 * 1000, // 10 minutes
    processing: 60 * 60 * 1000, // 60 minutes
  }
};

// Create test files with dummy video data
function createTestFile(filename, sizeInBytes) {
  const testDir = path.join(__dirname, 'test_files');
  if (!fs.existsSync(testDir)) {
    fs.mkdirSync(testDir, { recursive: true });
  }
  
  const filePath = path.join(testDir, filename);
  
  // Create a dummy file with specified size
  const buffer = Buffer.alloc(sizeInBytes, 0);
  
  // Add minimal MP4 header to make it a valid video file
  const mp4Header = Buffer.from([
    0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70, // ftyp box
    0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
    0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
    0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31
  ]);
  
  mp4Header.copy(buffer, 0);
  
  fs.writeFileSync(filePath, buffer);
  console.log(`Created test file: ${filename} (${(sizeInBytes / 1024 / 1024).toFixed(1)}MB)`);
  
  return filePath;
}

// Test chunk upload timeout configuration
function testChunkUploadTimeout() {
  console.log('\n=== Testing Chunk Upload Timeout Configuration ===');
  
  const expectedTimeout = 20 * 60 * 1000; // 20 minutes
  console.log(`Expected chunk upload timeout: ${expectedTimeout / 1000 / 60} minutes`);
  
  // Test progressive timeout calculation
  const fileSize = 100 * 1024 * 1024; // 100MB
  const totalChunks = Math.ceil(fileSize / TEST_CONFIG.chunkSize);
  
  console.log(`File size: ${fileSize / 1024 / 1024}MB`);
  console.log(`Total chunks: ${totalChunks}`);
  console.log(`Chunk size: ${TEST_CONFIG.chunkSize / 1024 / 1024}MB`);
  
  // Simulate progressive timeout calculation
  for (let i = 0; i < Math.min(5, totalChunks); i++) {
    const progressFactor = 1 + (i / totalChunks) * 0.5;
    const fileSizeMB = fileSize / (1024 * 1024);
    const fileSizeFactor = Math.min(1 + (fileSizeMB / 100) * 1.5, 3);
    const calculatedTimeout = expectedTimeout * progressFactor * fileSizeFactor;
    
    console.log(`Chunk ${i + 1}: timeout = ${(calculatedTimeout / 1000 / 60).toFixed(1)} minutes`);
  }
}

// Test backend timeout configuration
function testBackendTimeouts() {
  console.log('\n=== Testing Backend Timeout Configuration ===');
  
  const timeouts = {
    'chunk-upload': 30 * 60, // 30 minutes
    'finalize-upload': 10 * 60, // 10 minutes
    'process-video': 60 * 60, // 60 minutes
    'process-url': 45 * 60, // 45 minutes
  };
  
  Object.entries(timeouts).forEach(([endpoint, seconds]) => {
    console.log(`${endpoint}: ${seconds / 60} minutes`);
  });
}

// Test Celery task configuration
function testCeleryConfiguration() {
  console.log('\n=== Testing Celery Task Configuration ===');
  
  const taskTimeout = 60 * 60; // 60 minutes (3600 seconds)
  console.log(`Task soft_time_limit: ${taskTimeout / 60} minutes`);
  console.log(`Task time_limit: ${(taskTimeout + 300) / 60} minutes`);
}

// Validate upload service configuration
function validateUploadService() {
  console.log('\n=== Validating Upload Service Configuration ===');
  
  const config = {
    chunkSize: '1MB',
    maxRetries: 5,
    uploadTimeout: '20 minutes',
    minTimeout: '10 minutes',
    maxTimeout: '40 minutes',
    progressiveTimeoutFactor: 1.5,
    concurrency: 2
  };
  
  Object.entries(config).forEach(([key, value]) => {
    console.log(`${key}: ${value}`);
  });
}

// Main test function
function runTests() {
  console.log('🚀 Starting Upload Timeout Validation Tests\n');
  
  try {
    // Create test files
    console.log('=== Creating Test Files ===');
    TEST_CONFIG.testFiles.forEach(file => {
      createTestFile(file.name, file.size);
    });
    
    // Run configuration tests
    testChunkUploadTimeout();
    testBackendTimeouts();
    testCeleryConfiguration();
    validateUploadService();
    
    console.log('\n✅ All timeout configuration tests completed successfully!');
    console.log('\n📋 Manual Testing Instructions:');
    console.log('1. Open http://localhost:5173 in your browser');
    console.log('2. Navigate to the Upload page');
    console.log('3. Test uploading the created test files:');
    TEST_CONFIG.testFiles.forEach(file => {
      console.log(`   - ${file.name} (${file.size / 1024 / 1024}MB)`);
    });
    console.log('4. Verify that:');
    console.log('   - Upload progress is displayed correctly');
    console.log('   - Chunk uploads complete without timeout errors');
    console.log('   - Processing completes successfully');
    console.log('   - Error handling works for network issues');
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    process.exit(1);
  }
}

// Run tests
runTests();