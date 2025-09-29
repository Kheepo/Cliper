require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Use service role key to bypass RLS for admin operations
const supabase = createClient(supabaseUrl, supabaseServiceKey);

async function checkUsersTable() {
  console.log('👥 Checking users table...');
  
  try {
    // Check all users
    const { data: users, error: usersError } = await supabase
      .from('users')
      .select('*');
    
    if (usersError) {
      console.error('❌ Error fetching users:', usersError);
      return;
    }
    
    console.log(`📊 Found ${users.length} users:`);
    users.forEach(user => {
      console.log(`  - ID: ${user.id}`);
      console.log(`    Email: ${user.email}`);
      console.log(`    Created: ${user.created_at}`);
      console.log('');
    });
    
    // Check if the test user exists in auth.users
    console.log('🔐 Checking auth users...');
    const { data: authUsers, error: authError } = await supabase.auth.admin.listUsers();
    
    if (authError) {
      console.error('❌ Error fetching auth users:', authError);
      return;
    }
    
    console.log(`🔑 Found ${authUsers.users.length} auth users:`);
    authUsers.users.forEach(user => {
      console.log(`  - ID: ${user.id}`);
      console.log(`    Email: ${user.email}`);
      console.log(`    Created: ${user.created_at}`);
      console.log('');
    });
    
    // Find the test@example.com user
    const testUser = authUsers.users.find(user => user.email === 'test@example.com');
    if (testUser) {
      console.log('✅ Found test@example.com user:');
      console.log(`  - Auth ID: ${testUser.id}`);
      
      // Check if this user exists in the users table
      const { data: userRecord, error: userRecordError } = await supabase
        .from('users')
        .select('*')
        .eq('id', testUser.id)
        .single();
      
      if (userRecordError) {
        console.log('⚠️  User not found in users table, creating...');
        
        // Create user record
        const { error: createError } = await supabase
          .from('users')
          .insert({
            id: testUser.id,
            email: testUser.email,
            created_at: testUser.created_at
          });
        
        if (createError) {
          console.error('❌ Failed to create user record:', createError);
        } else {
          console.log('✅ User record created successfully');
        }
      } else {
        console.log('✅ User record exists in users table');
      }
    } else {
      console.log('❌ test@example.com user not found in auth');
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

checkUsersTable();