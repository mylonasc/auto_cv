import React from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import './MainContent.css';

// Import tab components
import JobInputTab from '../main/JobInputTab';
import ProcessingTab from '../main/ProcessingTab';
import ResultsTab from '../main/ResultsTab';
import EditorTab from '../main/EditorTab';
import HistoryTab from '../main/HistoryTab';

const MainContent: React.FC = () => {
  const { state, dispatch } = useAppState();

  const renderTabContent = () => {
    switch (state.uiState.activeTab) {
      case 'jobInput':
        return <JobInputTab />;
      case 'processing':
        return <ProcessingTab />;
      case 'results':
        return <ResultsTab />;
      case 'editor':
        return <EditorTab />;
      case 'history':
        return <HistoryTab />;
      default:
        return <JobInputTab />;
    }
  };

  return (
    <main className="main-content">
      <div className="tab-bar">
        <button 
          className={state.uiState.activeTab === 'jobInput' ? 'active' : ''}
          onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'jobInput' } })}
        >
          Job Description
        </button>
        <button 
          className={state.uiState.activeTab === 'processing' ? 'active' : ''}
          onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'processing' } })}
        >
          Processing
        </button>
        <button 
          className={state.uiState.activeTab === 'results' ? 'active' : ''}
          onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'results' } })}
        >
          Results
        </button>
        <button 
          className={state.uiState.activeTab === 'editor' ? 'active' : ''}
          onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'editor' } })}
        >
          Editor
        </button>
        <button 
          className={state.uiState.activeTab === 'history' ? 'active' : ''}
          onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'history' } })}
        >
          History
        </button>
      </div>
      <div className="tab-content">
        {renderTabContent()}
      </div>
    </main>
  );
};

export default MainContent;
