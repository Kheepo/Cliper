// Comprehensive Google OAuth Diagnostic Script
// This script will help identify the exact cause of the OAuth error

import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
dotenv.config();

// Initialize Supabase client
const supabaseUrl = process.env.SUPABASE_URL || 'https://stzdywhbdovjojtqxmsd.supabase.co';
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0emR5d2hiZG92am9qdHF4bXNkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc1NDA1NjgsImV4cCI6MjA3MzExNjU2OH0.R7GzJ18oGs4JQMBqdoq8h3jH_FQr4W8d0xJ_Wf9Hzm8';

const supabase = createClient(supabaseUrl, supabaseAnonKey);

console.log('🔍 GOOGLE OAUTH DIAGNOSTIC REPORT');
console.log('================================\n');

async function runDiagnostics() {
  try {
    // 1. Check environment variables
    console.log('1. ENVIRONMENT VARIABLES CHECK:');
    console.log('   ✓ SUPABASE_URL:', supabaseUrl);
    console.log('   ✓ SUPABASE_ANON_KEY:', supabaseAnonKey ? 'Present' : 'Missing');
    console.log('   ✓ GOOGLE_CLIENT_ID:', process.env.GOOGLE_CLIENT_ID ? 'Present' : 'Missing');
    console.log('   ✓ GOOGLE_CLIENT_SECRET:', process.env.GOOGLE_CLIENT_SECRET ? 'Present' : 'Missing');
    console.log('');

    // 2. Test Supabase client initialization
    console.log('2. SUPABASE CLIENT TEST:');
    const { data: { user }, error: userError } = await supabase.auth.getUser();
    if (userError) {
      console.log('   ⚠️  Auth client error:', userError.message);
    } else {
      console.log('   ✓ Supabase client initialized successfully');
      console.log('   ✓ Current user:', user ? user.email : 'Not logged in');
    }
    console.log('');

    // 3. Test Google OAuth provider availability
    console.log('3. GOOGLE OAUTH PROVIDER TEST:');
    try {
      // Attempt to get OAuth URL (this will fail if provider is not enabled)
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: 'http://localhost:5173/auth/callback',
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      });

      if (error) {
        console.log('   ❌ Google OAuth Error:', error.message);
        console.log('   📋 Error Code:', error.status || 'Unknown');
        
        // Analyze specific error types
        if (error.message.includes('Unsupported provider') || error.message.includes('provider is not enabled')) {
          console.log('\n   🔧 DIAGNOSIS: Google OAuth provider is NOT ENABLED in Supabase');
          console.log('   📝 SOLUTION:');
          console.log('      1. Go to your Supabase Dashboard: https://supabase.com/dashboard');
          console.log('      2. Select your project: stzdywhbdovjojtqxmsd');
          console.log('      3. Navigate to Authentication > Providers');
          console.log('      4. Find "Google" in the list and click "Enable"');
          console.log('      5. Enter your Google OAuth credentials:');
          console.log('         - Client ID:', process.env.GOOGLE_CLIENT_ID || 'NOT SET');
          console.log('         - Client Secret:', process.env.GOOGLE_CLIENT_SECRET || 'NOT SET');
          console.log('      6. Set the redirect URL to: https://stzdywhbdovjojtqxmsd.supabase.co/auth/v1/callback');
          console.log('      7. Save the configuration');
        } else if (error.message.includes('invalid_request')) {
          console.log('\n   🔧 DIAGNOSIS: Google OAuth configuration mismatch');
          console.log('   📝 SOLUTION: Check Google Cloud Console settings');
        }
      } else {
        console.log('   ✓ Google OAuth provider is enabled and configured');
        console.log('   ✓ OAuth URL generated successfully');
      }
    } catch (err) {
      console.log('   ❌ Unexpected error:', err.message);
    }
    console.log('');

    // 4. Check Google Cloud Console configuration
    console.log('4. GOOGLE CLOUD CONSOLE VERIFICATION:');
    console.log('   📋 Required settings in Google Cloud Console:');
    console.log('      - Authorized JavaScript origins: http://localhost:5173, https://stzdywhbdovjojtqxmsd.supabase.co');
    console.log('      - Authorized redirect URIs: https://stzdywhbdovjojtqxmsd.supabase.co/auth/v1/callback');
    console.log('      - OAuth consent screen must be configured');
    console.log('      - Client ID and Secret must match environment variables');
    console.log('');

    // 5. Test with different provider names (common mistake)
    console.log('5. PROVIDER NAME VALIDATION:');
    const providerVariants = ['google', 'Google', 'GOOGLE'];
    
    for (const provider of providerVariants) {
      try {
        const { error } = await supabase.auth.signInWithOAuth({
          provider: provider,
          options: { redirectTo: 'http://localhost:5173/auth/callback' },
        });
        
        if (!error) {
          console.log(`   ✓ Provider "${provider}" works`);
        } else {
          console.log(`   ❌ Provider "${provider}" failed:`, error.message);
        }
      } catch (err) {
        console.log(`   ❌ Provider "${provider}" error:`, err.message);
      }
    }
    console.log('');

    // 6. Final recommendations
    console.log('6. FINAL RECOMMENDATIONS:');
    console.log('   📋 Based on the error "Unsupported provider: provider is not enabled":');
    console.log('      1. The most likely cause is that Google OAuth is disabled in Supabase Dashboard');
    console.log('      2. Even if you have Google credentials in .env, they need to be configured in Supabase');
    console.log('      3. Check the screenshots provided to ensure the provider is enabled');
    console.log('      4. Verify the redirect URL matches exactly');
    console.log('      5. After enabling, wait 1-2 minutes for changes to propagate');
    console.log('');

  } catch (error) {
    console.error('❌ Diagnostic script failed:', error.message);
  }
}

// Run diagnostics
runDiagnostics().then(() => {
  console.log('🏁 Diagnostic complete. Check the results above for next steps.');
}).catch((error) => {
  console.error('❌ Failed to run diagnostics:', error.message);
});