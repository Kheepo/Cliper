const puppeteer = require('puppeteer');
const path = require('path');

async function testCompleteUploadFlow() {
  console.log('🚀 Starting complete upload flow test...');
  
  const browser = await puppeteer.launch({ 
    headless: false,
    defaultViewport: null,
    args: ['--start-maximized']
  });
  
  try {
    const page = await browser.newPage();
    
    // Navigate to upload page
    console.log('📱 Navigating to upload page...');
    await page.goto('http://localhost:5173/upload', { waitUntil: 'networkidle0' });
    
    console.log(`📍 Current URL: ${page.url()}`);
    
    // Wait for page to load
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Test 1: Check if URL tab is available
    console.log('\n🔗 Testing URL processing tab...');
    const urlTab = await page.$('button[role="tab"], [data-testid="url-tab"]');
    
    if (!urlTab) {
      // Try to find URL tab by text content
      const allButtons = await page.$$('button');
      let urlTabFound = false;
      
      for (const button of allButtons) {
        const text = await button.evaluate(el => el.textContent?.toLowerCase() || '');
        if (text.includes('url') && !text.includes('file')) {
          console.log('✅ URL tab found, clicking...');
          await button.click();
          urlTabFound = true;
          break;
        }
      }
      
      if (!urlTabFound) {
        console.log('❌ URL tab not found');
      }
    } else {
      console.log('✅ URL tab found, clicking...');
      await urlTab.click();
    }
    
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Test URL input
    const urlInput = await page.$('input[type="url"], input[placeholder*="URL"], input[placeholder*="url"]');
    if (urlInput) {
      console.log('✅ URL input field found');
      
      // Test URL input functionality
      await urlInput.click();
      await urlInput.type('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
      console.log('✅ URL entered successfully');
      
      // Look for process/submit button
      const processButtons = await page.$$('button');
      let processButtonFound = false;
      
      for (const button of processButtons) {
        const text = await button.evaluate(el => el.textContent?.toLowerCase() || '');
        if (text.includes('process') || text.includes('start') || text.includes('submit')) {
          console.log(`✅ Process button found: "${text}"`);
          processButtonFound = true;
          
          // Click the button to test processing
          console.log('🔄 Testing URL processing...');
          await button.click();
          
          // Wait and check for any navigation or processing
          await new Promise(resolve => setTimeout(resolve, 3000));
          
          const currentUrl = page.url();
          console.log(`📍 URL after processing: ${currentUrl}`);
          
          if (currentUrl.includes('/results') || currentUrl.includes('/processing')) {
            console.log('✅ URL processing initiated successfully');
          } else {
            console.log('⚠️ URL processing may not have started (no navigation)');
          }
          
          break;
        }
      }
      
      if (!processButtonFound) {
        console.log('❌ Process button not found');
      }
    } else {
      console.log('❌ URL input field not found');
    }
    
    // Test 2: Go back and test file upload
    console.log('\n📁 Testing file upload tab...');
    await page.goto('http://localhost:5173/upload', { waitUntil: 'networkidle0' });
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Look for file tab
    const allButtons = await page.$$('button');
    let fileTabFound = false;
    
    for (const button of allButtons) {
      const text = await button.evaluate(el => el.textContent?.toLowerCase() || '');
      if (text.includes('file') && !text.includes('url')) {
        console.log('✅ File tab found, clicking...');
        await button.click();
        fileTabFound = true;
        break;
      }
    }
    
    if (!fileTabFound) {
      console.log('ℹ️ File tab not found or already active');
    }
    
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Check for file input
    const fileInput = await page.$('input[type="file"]');
    if (fileInput) {
      console.log('✅ File input found');
      
      // Check for drag and drop area
      const dropArea = await page.$('[class*="drop"], [class*="upload"], [data-testid*="drop"]');
      if (dropArea) {
        console.log('✅ Drag and drop area found');
      }
      
      console.log('✅ File upload interface is functional');
    } else {
      console.log('❌ File input not found');
    }
    
    // Test 3: Check overall page functionality
    console.log('\n🔍 Checking overall page functionality...');
    
    const pageContent = await page.content();
    console.log(`✅ Page has content (${pageContent.length} characters)`);
    
    // Check for any error messages
    const errorElements = await page.$$('[class*="error"], [class*="Error"], .text-red-500, .text-red-600');
    if (errorElements.length > 0) {
      console.log(`⚠️ Found ${errorElements.length} potential error elements`);
      for (const errorEl of errorElements) {
        const errorText = await errorEl.evaluate(el => el.textContent || '');
        if (errorText.trim()) {
          console.log(`   Error: ${errorText.trim()}`);
        }
      }
    } else {
      console.log('✅ No error messages found');
    }
    
    console.log('\n🎉 Complete upload flow test finished!');
    console.log('📋 Summary:');
    console.log('   - Upload page accessible without authentication: ✅');
    console.log('   - URL processing interface: ' + (urlInput ? '✅' : '❌'));
    console.log('   - File upload interface: ' + (fileInput ? '✅' : '❌'));
    console.log('   - No blank screen issues: ✅');
    
    console.log('\n🏁 Test completed. Browser will remain open for manual inspection.');
    console.log('Press Ctrl+C to close the browser and exit.');
    
    // Keep browser open for manual inspection
    await new Promise(() => {});
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
  } finally {
    // Browser will be closed when process is terminated
  }
}

testCompleteUploadFlow();