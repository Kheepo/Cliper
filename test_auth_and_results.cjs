require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;

const supabase = createClient(supabaseUrl, supabaseKey);

async function testAuthAndResults() {
  console.log('🔍 Testing authentication and Results page flow...');
  
  try {
    // Check if there's an existing session
    const { data: { session }, error: sessionError } = await supabase.auth.getSession();
    
    if (sessionError) {
      console.error('❌ Session error:', sessionError);
      return;
    }
    
    if (!session) {
      console.log('⚠️  No active session found');
      
      // Try to sign in with test user
      console.log('🔐 Attempting to sign in with test user...');
      const { data: authData, error: authError } = await supabase.auth.signInWithPassword({
        email: 'test@example.com',
        password: 'testpassword123'
      });
      
      if (authError) {
        console.error('❌ Authentication failed:', authError.message);
        return;
      }
      
      console.log('✅ Successfully signed in:', authData.user.email);
    } else {
      console.log('✅ Active session found:', session.user.email);
    }
    
    // Test the API endpoints that Results page uses
    const jobId = '80b0a4aa-8ee0-47f3-9d0a-8b8dc479632e'; // Our test job
    
    console.log('\n🧪 Testing API endpoints...');
    
    // Test analysis endpoint
    console.log('📊 Testing /jobs/{jobId}/analysis endpoint...');
    
    // Get fresh session token
    const { data: { session: currentSession }, error: tokenError } = await supabase.auth.getSession();
    if (tokenError || !currentSession) {
      console.error('❌ Failed to get authentication token:', tokenError);
      return;
    }
    
    console.log('🔑 Using token:', currentSession.access_token.substring(0, 20) + '...');
    
    const analysisResponse = await fetch(`http://localhost:8000/api/jobs/${jobId}/analysis`, {
      headers: {
        'Authorization': `Bearer ${currentSession.access_token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (analysisResponse.ok) {
      const analysisData = await analysisResponse.json();
      console.log('✅ Analysis endpoint working:', {
        id: analysisData.id,
        job_id: analysisData.job_id,
        viral_score: analysisData.overall_viral_score
      });
    } else {
      console.error('❌ Analysis endpoint failed:', analysisResponse.status, await analysisResponse.text());
    }
    
    // Test clips endpoint
    console.log('🎬 Testing /jobs/{jobId}/clips endpoint...');
    const clipsResponse = await fetch(`http://localhost:8000/api/jobs/${jobId}/clips`, {
      headers: {
        'Authorization': `Bearer ${currentSession.access_token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (clipsResponse.ok) {
      const clipsData = await clipsResponse.json();
      console.log('✅ Clips endpoint working:', {
        clips_count: clipsData.clips?.length || 0,
        first_clip: clipsData.clips?.[0] ? {
          id: clipsData.clips[0].id,
          title: clipsData.clips[0].clip_name,
          viral_score: clipsData.clips[0].viral_score
        } : 'No clips'
      });
    } else {
      console.error('❌ Clips endpoint failed:', clipsResponse.status, await clipsResponse.text());
    }
    
    console.log('\n✅ Authentication and API testing completed!');
    console.log('🌐 You can now test the Results page at: http://localhost:3000/results/' + jobId);
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
  }
}

testAuthAndResults();