// Test authentication debugging
import { createClient } from '@supabase/supabase-js';
import fetch from 'node-fetch';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://your-project.supabase.co';
const supabaseAnonKey = process.env.VITE_SUPABASE_ANON_KEY || 'your-anon-key';

console.log('Supabase URL:', supabaseUrl);
console.log('Supabase Anon Key:', supabaseAnonKey ? 'Present' : 'Missing');

const supabase = createClient(supabaseUrl, supabaseAnonKey);

async function testAuth() {
  try {
    console.log('\n=== Testing Authentication ===');
    
    // Get current session
    const { data: { session }, error: sessionError } = await supabase.auth.getSession();
    
    if (sessionError) {
      console.error('Session error:', sessionError);
      return;
    }
    
    if (!session) {
      console.log('No active session found');
      return;
    }
    
    console.log('Session found:');
    console.log('- User ID:', session.user.id);
    console.log('- Email:', session.user.email);
    console.log('- Access Token:', session.access_token ? 'Present' : 'Missing');
    console.log('- Token expires at:', new Date(session.expires_at * 1000));
    
    // Test API call with auth header
    console.log('\n=== Testing API Call ===');
    
    const response = await fetch('http://localhost:8000/api/videos/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${session.access_token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ test: true })
    });
    
    console.log('API Response Status:', response.status);
    console.log('API Response Headers:', Object.fromEntries(response.headers));
    
    const responseText = await response.text();
    console.log('API Response Body:', responseText);
    
  } catch (error) {
    console.error('Test error:', error);
  }
}

testAuth();