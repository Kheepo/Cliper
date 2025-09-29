// Debug authentication issue
import { auth } from './src/firebase/config.js';
import { apiService } from './src/services/api.js';

async function debugAuth() {
  console.log('Current user:', auth.currentUser);
  
  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      console.log('Token obtained:', token ? 'Yes' : 'No');
      console.log('Token length:', token?.length || 0);
      
      // Test API call
      const response = await fetch('http://localhost:8000/auth/verify', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      console.log('API Response status:', response.status);
      const data = await response.json();
      console.log('API Response data:', data);
      
    } catch (error) {
      console.error('Auth debug error:', error);
    }
  } else {
    console.log('No user authenticated');
  }
}

debugAuth();