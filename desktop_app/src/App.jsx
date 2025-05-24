import React, { useState } from 'react';
import PstProcessorView from './components/PstProcessorView';
import EmailSearchView from './components/EmailSearchView';
// Ensure the path to App.css is correct if main.jsx is in src and App.css is in src/styles
// If main.jsx is in src, and App.css is in src/styles, then './styles/App.css' is correct from main.jsx
// App.jsx is in src, so it would reference styles/App.css as './styles/App.css' too.
// However, main.jsx already imports App.css, so it might not be needed here unless App.jsx has specific styles not covered globally.
// For simplicity, assuming App.css in main.jsx covers general styles.

function App() {
  const [activeView, setActiveView] = useState('processor'); // 'processor' or 'search'

  return (
    <div className="app-container">
      <nav className="tabs">
        <button 
          onClick={() => setActiveView('processor')} 
          className={activeView === 'processor' ? 'active-tab' : ''}
        >
          PST Processor
        </button>
        <button 
          onClick={() => setActiveView('search')}
          className={activeView === 'search' ? 'active-tab' : ''}
        >
          Email Search
        </button>
      </nav>

      <main className="view-container">
        {activeView === 'processor' && <PstProcessorView />}
        {activeView === 'search' && <EmailSearchView />}
      </main>
    </div>
  );
}

export default App;
