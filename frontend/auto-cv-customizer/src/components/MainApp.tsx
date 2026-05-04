import React, { useEffect } from 'react';
import Header from './layout/Header';
import Sidebar from './layout/Sidebar';
import MainContent from './layout/MainContent';
import Footer from './layout/Footer';
import ExportDialog from './common/ExportDialog';
import ConfigurationPanel from './common/ConfigurationPanel';
import { useAppState } from '../contexts/AppStateContext';
import apiService from '../services/api';
import './MainApp.css';

const MainApp: React.FC = () => {
  const { state, dispatch } = useAppState();

  useEffect(() => {
    const loadBackendConfig = async () => {
      try {
        const backendConfig = await apiService.getConfig();
        dispatch({ type: 'SET_BACKEND_CONFIG', payload: backendConfig });
      } catch (error) {
        console.error('Failed to load backend configuration:', error);
      }
    };

    loadBackendConfig();
  }, [dispatch]);

  const toggleSidebar = () => {
    dispatch({ type: 'SET_UI_STATE', payload: { sidebarCollapsed: !state.uiState.sidebarCollapsed } });
  };

  const handleCloseExportDialog = () => {
    dispatch({ type: 'SET_UI_STATE', payload: { showExportDialog: false } });
  };

  const handleCloseConfigPanel = () => {
    dispatch({ type: 'SET_UI_STATE', payload: { showConfigurationPanel: false } });
  };

  return (
    <div className="main-app">
      <Header onToggleSidebar={toggleSidebar} sidebarCollapsed={state.uiState.sidebarCollapsed} />
      <div className="app-body">
        <Sidebar 
          sidebarCollapsed={state.uiState.sidebarCollapsed} 
          onToggleSidebar={toggleSidebar} 
        />
        <MainContent />
      </div>
      <Footer />
      
      <ExportDialog 
        isOpen={state.uiState.showExportDialog} 
        onClose={handleCloseExportDialog} 
      />
      <ConfigurationPanel 
        isOpen={state.uiState.showConfigurationPanel} 
        onClose={handleCloseConfigPanel} 
      />
    </div>
  );
};

export default MainApp;
