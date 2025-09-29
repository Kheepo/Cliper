// Test script to verify Google OAuth configuration
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
dotenv.config();

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ Missing Supabase environment variables');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function testGoogleOAuthConfig() {
  console.log('🔍 Testing Google OAuth Configuration...');
  console.log('📍 Supabase URL:', supabaseUrl);
  console.log('🔑 Google Client ID:', process.env.GOOGLE_CLIENT_ID ? '✅ Set' : '❌ Missing');
  console.log('🔐 Google Client Secret:', process.env.GOOGLE_CLIENT_SECRET ? '✅ Set' : '❌ Missing');
  
  try {
    // Test if we can get auth providers
    const { data, error } = await supabase.auth.getSession();
    
    if (error) {
      console.error('❌ Supabase auth error:', error.message);
      return false;
    }
    
    console.log('✅ Supabase connection successful');
    console.log('📋 Next steps:');
    console.log('   1. Go to Supabase Dashboard → Authentication → Providers');
    console.log('   2. Enable Google provider');
    console.log('   3. Add Client ID:', process.env.GOOGLE_CLIENT_ID);
    console.log('   4. Add Client Secret:', process.env.GOOGLE_CLIENT_SECRET);
    console.log('   5. Save configuration');
    console.log('   6. Test login at http://localhost:3001');
    
    return true;
  } catch (err) {
    console.error('❌ Test failed:', err.message);
    return false;
  }
}

testGoogleOAuthConfig().then(success => {
  if (success) {
    console.log('\n🎉 Configuration test completed successfully!');
    console.log('🔗 Redirect URI for Google Cloud Console:');
    console.log('   https://stzdywhbdovjojtqxmsd.supabase.co/auth/v1/callback');
  } else {
    console.log('\n❌ Configuration test failed. Please check the errors above.');
  }
  process.exit(success ? 0 : 1);
});