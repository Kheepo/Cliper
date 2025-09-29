require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Use service role key to bypass RLS for admin operations
const supabase = createClient(supabaseUrl, supabaseServiceKey);

async function findCorrectUser() {
  console.log('🔍 Finding the correct user for test@example.com...');
  
  try {
    // Find the user with test@example.com email in the users table
    const { data: userRecord, error: userError } = await supabase
      .from('users')
      .select('*')
      .eq('email', 'test@example.com')
      .single();
    
    if (userError) {
      console.error('❌ User not found in users table:', userError.message);
      return;
    }
    
    console.log('✅ Found user in users table:');
    console.log(`  - ID: ${userRecord.id}`);
    console.log(`  - Email: ${userRecord.email}`);
    console.log(`  - Created: ${userRecord.created_at}`);
    
    // Now update the test job to use this correct user ID
    const testJobId = '80b0a4aa-8ee0-47f3-9d0a-8b8dc479632e';
    const correctUserId = userRecord.id;
    
    console.log(`\n🔄 Updating test job to use correct user ID: ${correctUserId}`);
    
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
    console.log(`🔑 Correct user ID: ${correctUserId}`);
    console.log('🌐 You can now test the Results page at: http://localhost:3000/results/' + testJobId);
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

findCorrectUser();