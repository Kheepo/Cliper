require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(
  process.env.VITE_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY // Use service role for admin operations
);

async function createTestJob() {
  try {
    // First, get or create a test user
    const { data: users, error: userError } = await supabase
      .from('users')
      .select('*')
      .eq('email', 'test_e37d5d1a@example.com')
      .limit(1);
    
    if (userError) {
      console.error('Error fetching user:', userError);
      return;
    }
    
    if (!users || users.length === 0) {
      console.error('Test user not found. Please run create_test_user.js first.');
      return;
    }
    
    const userId = users[0].id;
    console.log('Found test user:', userId);
    
    // Create a test job
    const jobData = {
      user_id: userId,
      job_type: 'upload',
      title: 'Test Video Analysis',
      description: 'Test job for debugging Results page',
      video_filename: 'test_video.mp4',
      video_size: 1024000,
      video_duration: 120.5,
      status: 'completed',
      progress: 100
    };
    
    const { data: job, error: jobError } = await supabase
      .from('jobs')
      .insert(jobData)
      .select()
      .single();
    
    if (jobError) {
      console.error('Error creating job:', jobError);
      return;
    }
    
    console.log('Created test job:', job);
    
    // Create analysis results for the job
    const analysisData = {
      video_id: job.id,
      user_id: userId,
      analysis_type: 'emotion_analysis',
      analysis_data: {
        overall_virality_score: 85.5,
        emotion_analysis: {
          dominant_emotions: ['excitement', 'joy'],
          emotion_timeline: [{ time: 0, emotion: 'neutral' }, { time: 30, emotion: 'excitement' }]
        },
        face_detection_summary: {
          total_faces: 2,
          face_time_percentage: 75.5
        },
        scene_analysis: {
          scene_changes: 5,
          dominant_colors: ['blue', 'white']
        },
        transcript_summary: 'This is a test video with engaging content about technology.',
        key_moments: [
          { time: 15.5, description: 'Exciting product reveal', score: 90 },
          { time: 45.2, description: 'Emotional reaction', score: 85 }
        ]
      },
      confidence_score: 0.85,
      processing_time_ms: 45200
    };
    
    const { data: analysis, error: analysisError } = await supabase
      .from('analysis_results')
      .insert(analysisData)
      .select()
      .single();
    
    if (analysisError) {
      console.error('Error creating analysis:', analysisError);
      return;
    }
    
    console.log('Created analysis results:', analysis);
    
    // Skip analysis segments for now since we don't have that table structure
    
    // Create some generated clips
    const clips = [
      {
        original_video_id: job.id,
        user_id: userId,
        clip_name: 'Best Moment - Product Reveal',
        start_time: 15,
        end_time: 45,
        file_size: 5242880,
        resolution: '1920x1080',
        viral_score: 0.92,
        status: 'completed',
        platform: 'youtube',
        clip_type: 'highlight',
        quality: 'high',
        generation_settings: {
          target_duration: 30,
          include_captions: true,
          optimize_for_mobile: false
        },
        generation_metadata: {
          hashtags: ['#ProductReveal', '#TechDemo', '#Innovation'],
          posting_recommendations: {
            best_platforms: ['TikTok', 'Instagram'],
            optimal_time: '7-9 PM',
            suggested_caption: 'Mind-blowing product reveal! 🚀'
          }
        }
      },
      {
        original_video_id: job.id,
        user_id: userId,
        clip_name: 'Emotional Reaction',
        start_time: 40,
        end_time: 65,
        file_size: 4194304,
        resolution: '1920x1080',
        viral_score: 0.88,
        status: 'completed',
        platform: 'tiktok',
        clip_type: 'highlight',
        quality: 'high',
        generation_settings: {
          target_duration: 25,
          include_captions: true,
          optimize_for_mobile: true
        },
        generation_metadata: {
          hashtags: ['#Reaction', '#Authentic', '#Emotional'],
          posting_recommendations: {
            best_platforms: ['YouTube Shorts', 'TikTok'],
            optimal_time: '6-8 PM',
            suggested_caption: 'This reaction says it all! 😍'
          }
        }
      }
    ];
    
    const { data: clipResults, error: clipError } = await supabase
      .from('generated_clips')
      .insert(clips)
      .select();
    
    if (clipError) {
      console.error('Error creating clips:', clipError);
      return;
    }
    
    console.log('Created generated clips:', clipResults.length);
    
    console.log('\n✅ Test job created successfully!');
    console.log(`Job ID: ${job.id}`);
    console.log(`Analysis ID: ${analysis.id}`);
    console.log(`Clips: ${clipResults.length}`);
    console.log('\nYou can now test the Results page with this job data.');
    
  } catch (error) {
    console.error('Unexpected error:', error);
  }
}

createTestJob();