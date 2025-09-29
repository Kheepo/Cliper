import React from 'react'

function TestApp() {
  console.log('TestApp component rendered')
  
  return (
    <div style={{ padding: '20px', backgroundColor: 'lightblue' }}>
      <h1>Test App - React is Working!</h1>
      <p>If you can see this, React is rendering properly.</p>
    </div>
  )
}

export default TestApp