import puppeteer from 'puppeteer';

// Configuration
const FRONTEND_URL = 'http://localhost:5173';
const TEST_EMAIL = 'test@example.com';
const TEST_PASSWORD = 'testpassword123';

async function testCompleteFlow() {
  let browser;
  let page;
  
  try {
    console.log('🚀 Starting Complete Flow Test with Browser Automation');
    
    // Launch browser
    browser = await puppeteer.launch({ 
      headless: false, // Set to true for headless mode
      devtools: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    page = await browser.newPage();
    
    // Enable console logging
    page.on('console', msg => {
      const type = msg.type();
      if (type === 'error' || type === 'warn') {
        console.log(`[Browser ${type.toUpperCase()}]:`, msg.text());
      }
    });
    
    // Enable request/response logging
    page.on('response', response => {
      const url = response.url();
      const status = response.status();
      if (url.includes('/api/') || status >= 400) {
        console.log(`[Network]: ${response.request().method()} ${url} - ${status}`);
      }
    });
    
    // Step 1: Navigate to home page
    console.log('\n📍 Step 1: Navigating to home page...');
    await page.goto(FRONTEND_URL, { waitUntil: 'networkidle0' });
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Step 2: Navigate to login page
    console.log('\n📍 Step 2: Navigating to login page...');
    await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'networkidle0' });
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Step 3: Login
    console.log('\n📍 Step 3: Attempting login...');
    
    // Wait for email input and fill it
    await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
    await page.type('input[type="email"], input[name="email"]', TEST_EMAIL);
    
    // Wait for password input and fill it
    await page.waitForSelector('input[type="password"], input[name="password"]', { timeout: 5000 });
    await page.type('input[type="password"], input[name="password"]', TEST_PASSWORD);
    
    // Click login button
    await page.waitForSelector('button[type="submit"]', { timeout: 5000 });
    await page.click('button[type="submit"]');
    
    // Wait for navigation after login
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    console.log('Current URL after login:', page.url());
    
    // Step 4: Navigate to upload page
    console.log('\n📍 Step 4: Navigating to upload page...');
    await page.goto(`${FRONTEND_URL}/upload`, { waitUntil: 'networkidle0' });
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    console.log('Current URL on upload page:', page.url());
    
    // Step 5: Test URL upload
    console.log('\n📍 Step 5: Testing URL upload...');
    
    // Look for URL input field
    const urlInput = await page.$('input[type="url"], input[placeholder*="URL"], input[placeholder*="url"]');
    if (urlInput) {
      console.log('✅ URL input field found');
      await urlInput.type('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
      
      // Look for submit button
      const submitButton = await page.evaluateHandle(() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        return buttons.find(button => button.textContent.includes('Start Processing'));
      });
      if (submitButton) {
        console.log('✅ Submit button found, clicking...');
        
        // Monitor network requests
        const responses = [];
        page.on('response', response => {
          responses.push({
            url: response.url(),
            status: response.status(),
            method: response.request().method()
          });
        });
        
        await submitButton.click();
        
        // Wait for processing
        await new Promise(resolve => setTimeout(resolve, 5000));
        
        console.log('\n📊 Network requests after submit:');
        responses.forEach(resp => {
          if (resp.url.includes('/api/')) {
            console.log(`  ${resp.method} ${resp.url} - ${resp.status}`);
          }
        });
        
        console.log('\nCurrent URL after submit:', page.url());
        
        // Check if we're on results page
        if (page.url().includes('/results/')) {
          console.log('✅ Successfully navigated to results page');
          
          // Wait for page content
          await new Promise(resolve => setTimeout(resolve, 3000));
          
          // Check for any content
          const bodyText = await page.evaluate(() => document.body.innerText);
          console.log('\n📄 Page content preview:');
          console.log(bodyText.substring(0, 500) + (bodyText.length > 500 ? '...' : ''));
          
        } else {
          console.log('❌ Did not navigate to results page');
        }
        
      } else {
        console.log('❌ Submit button not found');
      }
    } else {
      console.log('❌ URL input field not found');
    }
    
    // Step 6: Take screenshot for debugging
    console.log('\n📸 Taking screenshot...');
    await page.screenshot({ path: 'debug_screenshot.png', fullPage: true });
    console.log('Screenshot saved as debug_screenshot.png');
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    
    if (page) {
      // Take error screenshot
      try {
        await page.screenshot({ path: 'error_screenshot.png', fullPage: true });
        console.log('Error screenshot saved as error_screenshot.png');
      } catch (screenshotError) {
        console.error('Failed to take error screenshot:', screenshotError.message);
      }
    }
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

// Run the test
testCompleteFlow().then(() => {
  console.log('\n✅ Complete flow test finished');
}).catch(error => {
  console.error('\n❌ Test suite failed:', error.message);
});