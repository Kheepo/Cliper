-- Create a test job and results for debugging the Results page
-- This will create a complete job with analysis results and clips

-- Insert a test job
INSERT INTO public.jobs (
  id,
  user_id,
  job_type,
  status,
  title,
  video_url,
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  (SELECT id FROM public.users WHERE email = 'test@example.com'),
  'url',
  'completed',
  'Test Video Analysis',
  'https://example.com/test-video.mp4',
  now(),
  now()
);

-- Insert test job results
INSERT INTO public.job_results (
  id,
  job_id,
  virality_score,
  engagement_metrics,
  hashtags,
  suggested_clips,
  analysis_summary,
  created_at,
  updated_at
) VALUES (
  gen_random_uuid(),
  (SELECT id FROM public.jobs WHERE title = 'Test Video Analysis' AND user_id = (SELECT id FROM public.users WHERE email = 'test@example.com')),
  8.7,
  '{"processing_time": 45.5, "engagement_rate": 0.85, "view_retention": 0.78}'::jsonb,
  ARRAY['viral', 'trending', 'amazing', 'mustwatch', 'epic'],
  '[
    {
      "id": "clip_1",
      "start_time": 10.5,
      "end_time": 25.3,
      "duration": 14.8,
      "score": 9.2,
      "title": "Epic Moment",
      "description": "The most engaging part of the video",
      "thumbnail_url": "https://example.com/thumb1.jpg",
      "clip_url": "https://example.com/clip1.mp4"
    },
    {
      "id": "clip_2",
      "start_time": 45.2,
      "end_time": 58.7,
      "duration": 13.5,
      "score": 8.8,
      "title": "Funny Reaction",
      "description": "Hilarious reaction that will go viral",
      "thumbnail_url": "https://example.com/thumb2.jpg",
      "clip_url": "https://example.com/clip2.mp4"
    },
    {
      "id": "clip_3",
      "start_time": 120.1,
      "end_time": 135.9,
      "duration": 15.8,
      "score": 8.5,
      "title": "Key Insight",
      "description": "Important information that viewers need",
      "thumbnail_url": "https://example.com/thumb3.jpg",
      "clip_url": "https://example.com/clip3.mp4"
    }
  ]'::jsonb,
  'This video shows high virality potential with engaging content and strong visual appeal. The analysis identified 3 key clips that are likely to perform well on social media platforms.',
  now(),
  now()
);

-- Insert test analysis results
INSERT INTO analysis_results (id, video_id, user_id, analysis_type, analysis_data, confidence_score, processing_time_ms, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    (SELECT id FROM jobs WHERE title = 'Test Video Analysis'),
    (SELECT id FROM users WHERE email = 'test@example.com'),
    'sentiment',
    '{"sentiment": "positive", "keywords": ["test", "video", "analysis"], "topics": ["technology", "demo"]}',
    0.85,
    5000,
    NOW(),
    NOW()
);

-- Insert test generated clips
INSERT INTO generated_clips (id, original_video_id, user_id, clip_name, start_time, end_time, viral_score, status, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    (SELECT id FROM jobs WHERE title = 'Test Video Analysis'),
    (SELECT id FROM users WHERE email = 'test@example.com'),
    'Test Highlight Clip 1',
    10.5,
    25.3,
    0.78,
    'completed',
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    (SELECT id FROM jobs WHERE title = 'Test Video Analysis'),
    (SELECT id FROM users WHERE email = 'test@example.com'),
    'Test Highlight Clip 2',
    45.2,
    62.1,
    0.82,
    'completed',
    NOW(),
    NOW()
);