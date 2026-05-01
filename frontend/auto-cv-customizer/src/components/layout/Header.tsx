import React from 'react';
import './Header.css';

interface HeaderProps {
  onToggleSidebar: () => void;
  sidebarCollapsed: boolean;
}

const Header: React.FC<HeaderProps> = ({ onToggleSidebar, sidebarCollapsed }) => {
  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-left">
          <button className="sidebar-toggle" onClick={onToggleSidebar} aria-label="Toggle sidebar">
            <span className="hamburger-icon">
              {sidebarCollapsed ? '☰' : '✕'}
            </span>
          </button>
          <h1 className="app-title">AutoCV Customizer</h1>
        </div>
        <div className="header-right">
          <div className="user-info">
            <span className="user-name">Charilaos Mylonas</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;