import React, { useState } from 'react';
import { useAppState, type CVResultSection, type CVResultItem } from '../../contexts/AppStateContext';
import ScoreVisualization from '../scoring/ScoreVisualization';
import '../main/ResultsTab.css';

const ResultsTab: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [selectedSection, setSelectedSection] = useState<string | null>(null);

  if (!state.processingState?.result) {
    return (
      <div className="results-tab">
        <div className="no-results">
          <h2>No Results Yet</h2>
          <p>Process a job description to see scoring results here.</p>
          <div className="no-results-actions" style={{ marginTop: '24px' }}>
            <button 
              className="btn btn-secondary"
              onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'history' } })}
            >
              View History →
            </button>
          </div>
        </div>
      </div>
    );
  }

  const result = state.processingState.result;
  const metrics = result.summary_metrics;
  const experienceAnalysis = result.experience_analysis || [];

  return (
    <div className="results-tab">
      <div className="results-header">
        <h2>CV Analysis Results</h2>
        {metrics && (
          <div className="metrics-summary">
            <div className="metric-card">
              <div className="metric-value">{Number(metrics.mean_section_relevance)?.toFixed(1) || 'N/A'}</div>
              <div className="metric-label">Mean Relevance</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{Number(metrics.weighted_mean_section_relevance)?.toFixed(1) || 'N/A'}</div>
              <div className="metric-label">Weighted Relevance</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{Number(metrics.conciseness_relevance_metric)?.toFixed(1) || 'N/A'}</div>
              <div className="metric-label">Conciseness Metric</div>
            </div>
          </div>
        )}
      </div>

      <div className="results-content">
        <div className="sections-list">
          <h3>Experience Sections</h3>
          {experienceAnalysis.map((section: CVResultSection, index: number) => (
            <div 
              key={index} 
              className={`section-card ${selectedSection === (section.company || '') + (section.position || '') ? 'selected' : ''}`}
              onClick={() => setSelectedSection((section.company || '') + (section.position || ''))}
            >
              <div className="section-header">
                <h4>{section.company || '-'}</h4>
                <span className="position">{section.position || '-'}</span>
              </div>
              <div className="section-score">
                <ScoreVisualization score={section.section_score ?? 0} maxScore={10} />
              </div>
              <div className="items-count">
                {section.items?.length || 0} items
              </div>
            </div>
          ))}
        </div>

        {selectedSection && (
          <div className="section-details">
            <h3>Section Details</h3>
            {experienceAnalysis
              .filter((section: CVResultSection) => ((section.company || '') + (section.position || '')) === selectedSection)
              .map((section: CVResultSection, idx: number) => (
                <div key={idx} className="section-detail-content">
                  <h4>{section.company} - {section.position}</h4>
                  <p><strong>Section Score:</strong> {Number(section.section_score)?.toFixed(1)}/10</p>
                  <div className="items-list">
                    <h5>Experience Items:</h5>
                    {section.items?.map((item: CVResultItem, itemIdx: number) => (
                      <div key={itemIdx} className={`item-card ${item.kept ? 'kept' : 'removed'}`}>
                        <div className="item-text">{item.text}</div>
                        <div className="item-meta">
                          <span className="relevance-score">
                            Relevance: {Number(item.relevance_score)?.toFixed(1)}/10
                          </span>
                          <span className="explanation">{item.explanation}</span>
                        </div>
                        {item.posting_evidence && (
                          <div className="posting-evidence">
                            <strong>Evidence:</strong> {item.posting_evidence}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        )}

        <div className="actions-panel">
          <button 
            className="btn btn-primary"
            onClick={() => dispatch({ 
              type: 'SET_UI_STATE', 
              payload: { activeTab: 'editor' } 
            })}
          >
            Edit CV Sections →
          </button>
          <button 
            className="btn btn-secondary"
            onClick={() => dispatch({ 
              type: 'SET_UI_STATE', 
              payload: { showExportDialog: true } 
            })}
          >
            📦 Export CV
          </button>
        </div>
      </div>
    </div>
  );
};

export default ResultsTab;
