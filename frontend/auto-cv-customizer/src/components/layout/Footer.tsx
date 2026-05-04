import React from 'react';
import './Footer.css';

const Footer: React.FC = () => {
  return (
    <footer className="app-footer">
      <div className="footer-content">
        <div className="footer-left">
          <span>AutoCV Customizer</span>
          <span className="version">v0.1.0</span>
        </div>
        <div className="footer-center">
          <span>© 2026 Charilaos Mylonas</span>
        </div>
        <div className="footer-right">
          <span className="status-dot"></span>
          <span>Connected to API</span>
        </div>
      </div>
    </footer>
  );
};

export default Footer;