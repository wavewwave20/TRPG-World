/**
 * Manual integration test for session creation flow
 * Run this in the browser console when the app is running
 */

// Test 1: Verify API service works
async function testApiService() {
  console.log('Testing API service...');
  
  try {
    const response = await fetch('http://localhost:8000/api/sessions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        host_user_id: 1,
        title: 'Integration Test Session',
        world_prompt: 'A test world for integration testing'
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('✓ API service works! Session ID:', data.session_id);
      return data.session_id;
    } else {
      console.error('✗ API service failed:', await response.text());
      return null;
    }
  } catch (error) {
    console.error('✗ API service error:', error);
    return null;
  }
}

// Test 2: Verify validation works
async function testValidation() {
  console.log('Testing validation...');
  
  // Test empty title
  try {
    const response = await fetch('http://localhost:8000/api/sessions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        host_user_id: 1,
        title: '',
        world_prompt: 'A test world'
      })
    });
    
    if (!response.ok) {
      console.log('✓ Empty title validation works');
    } else {
      console.error('✗ Empty title should be rejected');
    }
  } catch (error) {
    console.error('✗ Validation test error:', error);
  }
}

// Run all tests
async function runTests() {
  console.log('=== Session Creation Flow Integration Tests ===');
  await testApiService();
  await testValidation();
  console.log('=== Tests Complete ===');
}

// Export for use in console
if (typeof window !== 'undefined') {
  (window as any).testSessionFlow = runTests;
  console.log('Run testSessionFlow() in the console to test the session creation flow');
}
