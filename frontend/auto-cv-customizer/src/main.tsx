import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './components/MainApp';
import { AppStateProvider } from './contexts/AppStateContext';
import './styles/globals.css';
import { StudioProvider } from './contexts/StudioContext';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppStateProvider>
      <BrowserRouter>
        <StudioProvider><App /></StudioProvider>
      </BrowserRouter>
    </AppStateProvider>
  </StrictMode>,
)
