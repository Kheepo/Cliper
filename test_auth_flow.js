import puppeteer from 'puppeteer';

(async () => {
  console.log('🔐 Testing Authentication Flow');
  
  const browser = await puppeteer.launch({ 
    headless: false,
    defaultViewport: null,
    args: ['--start-maximized']
  });
  
  const page = await browser.newPage();
  
  try {
    // Navigate to login
    console.log('📍 Step 1: Navigating to login page...');
    await page.goto('http://localhost:5173/login');
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Fill login form
    console.log('📍 Step 2: Filling login form...');
    await page.type('input[type="email"]', 'test@example.com');
    await page.type('input[type="password"]', 'password123');
    
    // Submit login
    console.log('📍 Step 3: Submitting login...');
    await page.click('button[type="submit"]');
    
    // Wait for navigation and check URL
    console.log('📍 Step 4: Waiting for authentication...');
    await new Promise(resolve => setTimeout(resolve, 5000));
    
    const currentUrl = page.url();
    console.log('Current URL after login:', currentUrl);
    
    if (currentUrl.includes('/dashboard')) {
      console.log('✅ Login successful - redirected to dashboard');
      
      // Try to navigate to upload
      console.log('📍 Step 5: Navigating to upload page...');
      await page.goto('http://localhost:5173/upload');
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      const uploadUrl = page.url();
      console.log('Current URL on upload page:', uploadUrl);
      
      if (uploadUrl.includes('/upload')) {
        console.log('✅ Upload page accessible - authentication working!');
        
        // Check if upload form is visible
        const urlInput = await page.$('input[placeholder*="URL"], input[placeholder*="url"], input[type="url"]');
        if (urlInput) {
          console.log('✅ URL input field found - upload form is working!');
        } else {
          console.log('❌ URL input field not found');
        }
      } else {
        console.log('❌ Redirected away from upload page - authentication issue persists');
      }
    } else {
      console.log('❌ Login failed or redirected incorrectly');
    }
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
  } finally {
    console.log('📸 Keeping browser open for manual inspection...');
    console.log('Press Ctrl+C to close when done.');
    
    // Keep browser open for manual inspection
    await new Promise(() => {});
  }
})();