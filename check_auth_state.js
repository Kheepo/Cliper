// Comprehensive authentication test script
import { createClient } from '@supabase/supabase-js';

// Get Supabase configuration from environment
const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseAnonKey = process.env.VITE_SUPABASE_ANON_KEY;

console.log('🔧 Supabase Configuration Check:');
console.log('URL:', supabaseUrl ? '✅ Present' : '❌ Missing');
console.log('Anon Key:', supabaseAnonKey ? '✅ Present' : '❌ Missing');

if (!supabaseUrl || !supabaseAnonKey) {
  console.log('❌ Missing Supabase configuration. Please check your .env file.');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseAnonKey);

async function testAuthentication() {
  console.log('\n🔍 Testing Authentication System...');
  
  try {
    // 1. Check current session
    console.log('\n1️⃣ Checking current session...');
    const { data: { session }, error: sessionError } = await supabase.auth.getSession();
    
    if (sessionError) {
      console.log('❌ Session error:', sessionError.message);
    } else if (session) {
      console.log('✅ Active session found');
      console.log('   User ID:', session.user.id);
      console.log('   Email:', session.user.email);
      console.log('   Token expires:', new Date(session.expires_at * 1000).toISOString());
      
      // Check if token is expired
      const now = Math.floor(Date.now() / 1000);
      if (session.expires_at < now) {
        console.log('⚠️ Token is expired');
      } else {
        console.log('✅ Token is valid');
      }
    } else {
      console.log('❌ No active session');
    }
    
    // 2. Test Google OAuth configuration
    console.log('\n2️⃣ Testing Google OAuth configuration...');
    try {
      // This will fail if Google OAuth is not configured
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: 'http://localhost:3000/auth/callback',
          skipBrowserRedirect: true // Don't actually redirect
        }
      });
      
      if (error) {
        if (error.message.includes('Unsupported provider') || error.message.includes('provider is not enabled')) {
          console.log('❌ Google OAuth not configured in Supabase');
          console.log('   Fix: Enable Google provider in Supabase Dashboard > Authentication > Providers');
        } else {
          console.log('⚠️ Google OAuth error:', error.message);
        }
      } else {
        console.log('✅ Google OAuth is configured');
      }
    } catch (oauthError) {
      console.log('❌ Google OAuth test failed:', oauthError.message);
    }
    
    // 3. Test email/password authentication (without actually logging in)
    console.log('\n3️⃣ Testing email/password authentication setup...');
    try {
      // Try to sign in with invalid credentials to test if auth is working
      const { error } = await supabase.auth.signInWithPassword({
        email: 'test@invalid.com',
        password: 'invalid'
      });
      
      if (error) {
        if (error.message.includes('Invalid login credentials')) {
          console.log('✅ Email/password authentication is working (invalid credentials rejected)');
        } else if (error.message.includes('Email not confirmed')) {
          console.log('✅ Email/password authentication is working (email confirmation required)');
        } else {
          console.log('⚠️ Unexpected auth error:', error.message);
        }
      } else {
        console.log('⚠️ Unexpected: Login succeeded with invalid credentials');
      }
    } catch (authError) {
      console.log('❌ Email/password authentication test failed:', authError.message);
    }
    
    // 4. Test database connection
    console.log('\n4️⃣ Testing database connection...');
    try {
      const { data, error } = await supabase.from('user_profiles').select('count').limit(1);
      
      if (error) {
        if (error.message.includes('permission denied')) {
          console.log('⚠️ Database accessible but permission denied (expected for unauthenticated user)');
        } else {
          console.log('❌ Database error:', error.message);
        }
      } else {
        console.log('✅ Database connection working');
      }
    } catch (dbError) {
      console.log('❌ Database test failed:', dbError.message);
    }
    
    // 5. Summary and recommendations
    console.log('\n📋 Summary and Recommendations:');
    if (!session) {
      console.log('🎯 MAIN ISSUE: No active user session');
      console.log('   Solution: User needs to log in first');
      console.log('   1. Navigate to /login page');
      console.log('   2. Sign in with email/password or Google');
      console.log('   3. Ensure login is successful before uploading');
    }
    
    console.log('\n🔧 Next Steps:');
    console.log('   1. Test login functionality in the browser');
    console.log('   2. Check browser console for any JavaScript errors');
    console.log('   3. Verify Supabase project settings');
    console.log('   4. Test upload after successful authentication');
    
  } catch (error) {
    console.log('❌ Authentication test failed:', error.message);
  }
}

testAuthentication();