const puppeteer = require('puppeteer');

(async () => {
  console.log('🚀 Starting upload flow test...');
  
  const browser = await puppeteer.launch({ 
    headless: false, 
    defaultViewport: null,
    args: ['--start-maximized']
  });
  
  const page = await browser.newPage();
  
  try {
    // Navigate to the application
    console.log('📱 Navigating to application...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle0' });
    
    // Wait for the page to load
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Check current URL and page content
    const currentUrl = page.url();
    console.log(`📍 Current URL: ${currentUrl}`);
    
    // Try to navigate directly to upload page
    console.log('🔄 Navigating to upload page...');
    await page.goto('http://localhost:5173/upload', { waitUntil: 'networkidle0' });
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const uploadUrl = page.url();
    console.log(`📍 Upload page URL: ${uploadUrl}`);
    
    // Check if we're on the upload page
    if (uploadUrl.includes('/upload')) {
      console.log('✅ Successfully accessed upload page without authentication!');
      
      // Check for upload form elements
      const urlInput = await page.$('input[placeholder*="URL"], input[placeholder*="url"], input[type="url"]');
      const fileInput = await page.$('input[type="file"]');
      
      console.log(`🔍 URL input found: ${!!urlInput}`);
      console.log(`🔍 File input found: ${!!fileInput}`);
      
      // Check for upload form elements
      const uploadButtons = await page.$$('button');
      let foundUploadButton = false;
      
      for (const button of uploadButtons) {
        const text = await button.evaluate(el => el.textContent?.toLowerCase() || '');
        if (text.includes('process') || text.includes('upload') || text.includes('start')) {
          console.log(`✅ Upload button found: "${text}"`);
          foundUploadButton = true;
          break;
        }
      }
      
      if (!foundUploadButton) {
        console.log('❌ Upload button not found');
      }
      
      // Test URL input functionality
      if (urlInput) {
        console.log('🧪 Testing URL input...');
        await urlInput.click();
        await urlInput.type('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
        console.log('✅ URL input working');
        
        // Try to find and click submit button
        const buttons = await page.$$('button');
        console.log(`🔍 Found ${buttons.length} buttons on page`);
        
        for (let i = 0; i < buttons.length; i++) {
          const buttonText = await page.evaluate(el => el.textContent, buttons[i]);
          console.log(`🔘 Button ${i + 1}: "${buttonText}"`);
          
          if (buttonText && (buttonText.includes('Process') || buttonText.includes('Start') || buttonText.includes('Submit'))) {
            console.log(`🎯 Found processing button: "${buttonText}"`);
            
            // Click the button and monitor for navigation or errors
            console.log('🖱️ Clicking processing button...');
            await buttons[i].click();
            
            // Wait and check for any changes
            await new Promise(resolve => setTimeout(resolve, 3000));
            
            const newUrl = page.url();
            console.log(`📍 URL after clicking: ${newUrl}`);
            
            // Check if we got redirected to results or if there's a blank screen
            if (newUrl.includes('/results')) {
              console.log('✅ Successfully redirected to results page!');
            } else if (newUrl === uploadUrl) {
              console.log('⚠️ Stayed on upload page - checking for errors or loading states...');
              
              // Check for loading indicators
              const loadingElements = await page.$$('[class*="loading"], [class*="spinner"], [class*="progress"]');
              console.log(`🔄 Loading elements found: ${loadingElements.length}`);
              
              // Check for error messages
              const errorElements = await page.$$('[class*="error"], [class*="alert"]');
              console.log(`❌ Error elements found: ${errorElements.length}`);
            } else {
              console.log(`🔄 Redirected to: ${newUrl}`);
            }
            
            break;
          }
        }
      }
      
      // Check for blank screen issue
      const bodyText = await page.evaluate(() => document.body.innerText);
      if (bodyText.trim().length < 50) {
        console.log('⚠️ Potential blank screen detected - very little content on page');
        console.log(`Page content length: ${bodyText.trim().length}`);
      } else {
        console.log(`✅ Page has content (${bodyText.trim().length} characters)`);
      }
      
    } else {
      console.log('❌ Could not access upload page - redirected to:', uploadUrl);
    }
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
  }
  
  console.log('🏁 Test completed. Browser will remain open for manual inspection.');
  console.log('Press Ctrl+C to close the browser and exit.');
  
  // Keep browser open for manual inspection
  await new Promise(() => {});
})();