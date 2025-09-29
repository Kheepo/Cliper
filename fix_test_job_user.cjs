require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Use service role key to bypass RLS for admin operations
const supabase = createClient(supabaseUrl, supabaseServiceKey);

async function fixTestJobUser() {
  console.log('🔧 Fixing test job user assignment...');
  
  try {
    // First, let's see what user ID the test job currently has
    const testJobId = '80b0a4aa-8ee0-47f3-9d0a-8b8dc479632e';
    
    console.log(`🔍 Checking current test job: ${testJobId}`);
    const { data: currentJob, error: currentJobError } = await supabase
      .from('jobs')
      .select('*')
      .eq('id', testJobId)
      .single();
    
    if (currentJobError) {
      console.error('❌ Test job not found:', currentJobError.message);
      return;
    }
    
    console.log('📋 Current job details:');
    console.log(`  - Current User ID: ${currentJob.user_id}`);
    console.log(`  - Status: ${currentJob.status}`);
    console.log(`  - Filename: ${currentJob.video_filename}`);
    
    // The correct user ID for test@example.com
    const correctUserId = '8ab4c54d-7f8c-4625-a6a1-2d651bd1a8a5';
    
    if (currentJob.user_id === correctUserId) {
      console.log('✅ Job already has correct user ID');
      return;
    }
    
    console.log(`🔄 Updating job user_id from ${currentJob.user_id} to ${correctUserId}`);
    
    // Update the job user_id
    const { error: updateJobError } = await supabase
      .from('jobs')
      .update({ user_id: correctUserId })
      .eq('id', testJobId);
    
    if (updateJobError) {
      console.error('❌ Failed to update job:', updateJobError);
      return;
    }
    
    console.log('✅ Job user_id updated successfully');
    
    // Update analysis results user_id
    console.log('🔬 Updating analysis results user_id...');
    const { error: updateAnalysisError } = await supabase
      .from('analysis_results')
      .update({ user_id: correctUserId })
      .eq('video_id', testJobId);
    
    if (updateAnalysisError) {
      console.error('❌ Failed to update analysis results:', updateAnalysisError);
    } else {
      console.log('✅ Analysis results user_id updated');
    }
    
    // Update generated clips user_id
    console.log('🎬 Updating generated clips user_id...');
    const { error: updateClipsError } = await supabase
      .from('generated_clips')
      .update({ user_id: correctUserId })
      .eq('original_video_id', testJobId);
    
    if (updateClipsError) {
      console.error('❌ Failed to update clips:', updateClipsError);
    } else {
      console.log('✅ Generated clips user_id updated');
    }
    
    console.log('\n🎉 Test job data successfully updated!');
    console.log('🌐 You can now test the Results page at: http://localhost:3000/results/' + testJobId);
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

fixTestJobUser();