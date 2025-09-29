require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;

const supabase = createClient(supabaseUrl, supabaseKey);

async function checkJobsAndUser() {
  console.log('🔍 Checking jobs and user data...');
  
  try {
    // Sign in first
    const { data: authData, error: authError } = await supabase.auth.signInWithPassword({
      email: 'test@example.com',
      password: 'testpassword123'
    });
    
    if (authError) {
      console.error('❌ Authentication failed:', authError.message);
      return;
    }
    
    const userId = authData.user.id;
    console.log('✅ Signed in as:', authData.user.email);
    console.log('👤 User ID:', userId);
    
    // Check all jobs for this user
    console.log('\n📋 Checking jobs for this user...');
    const { data: jobs, error: jobsError } = await supabase
      .from('jobs')
      .select('*')
      .eq('user_id', userId);
    
    if (jobsError) {
      console.error('❌ Error fetching jobs:', jobsError);
    } else {
      console.log(`📊 Found ${jobs.length} jobs for user:`);
      jobs.forEach(job => {
        console.log(`  - Job ID: ${job.id}`);
        console.log(`    Status: ${job.status}`);
        console.log(`    Filename: ${job.video_filename}`);
        console.log(`    Created: ${job.created_at}`);
        console.log('');
      });
    }
    
    // Check the specific test job
    const testJobId = '80b0a4aa-8ee0-47f3-9d0a-8b8dc479632e';
    console.log(`🎯 Checking specific test job: ${testJobId}`);
    
    const { data: testJob, error: testJobError } = await supabase
      .from('jobs')
      .select('*')
      .eq('id', testJobId)
      .single();
    
    if (testJobError) {
      console.error('❌ Test job not found:', testJobError.message);
    } else {
      console.log('✅ Test job found:');
      console.log(`  - User ID: ${testJob.user_id}`);
      console.log(`  - Status: ${testJob.status}`);
      console.log(`  - Filename: ${testJob.video_filename}`);
      console.log(`  - Current user matches: ${testJob.user_id === userId}`);
    }
    
    // Check analysis results for the test job
    console.log('\n🔬 Checking analysis results...');
    const { data: analysisResults, error: analysisError } = await supabase
      .from('analysis_results')
      .select('*')
      .eq('video_id', testJobId);
    
    if (analysisError) {
      console.error('❌ Error fetching analysis results:', analysisError);
    } else {
      console.log(`📈 Found ${analysisResults.length} analysis results`);
      analysisResults.forEach(result => {
        console.log(`  - Analysis ID: ${result.id}`);
        console.log(`    Type: ${result.analysis_type}`);
        console.log(`    User ID: ${result.user_id}`);
        console.log(`    Confidence: ${result.confidence_score}`);
      });
    }
    
    // Check generated clips
    console.log('\n🎬 Checking generated clips...');
    const { data: clips, error: clipsError } = await supabase
      .from('generated_clips')
      .select('*')
      .eq('original_video_id', testJobId);
    
    if (clipsError) {
      console.error('❌ Error fetching clips:', clipsError);
    } else {
      console.log(`🎥 Found ${clips.length} clips`);
      clips.forEach(clip => {
        console.log(`  - Clip ID: ${clip.id}`);
        console.log(`    Name: ${clip.clip_name}`);
        console.log(`    User ID: ${clip.user_id}`);
        console.log(`    Status: ${clip.status}`);
        console.log(`    Viral Score: ${clip.viral_score}`);
      });
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

checkJobsAndUser();