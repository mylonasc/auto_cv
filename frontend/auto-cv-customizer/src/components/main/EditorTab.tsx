import React, { useState } from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import ScoreVisualization from '../scoring/ScoreVisualization';
import '../main/EditorTab.css';

const EditorTab: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [editingText, setEditingText] = useState('');
  const [selectedItem, setSelectedItem] = useState<{sectionIdx: number, itemIdx: number } | null>(null);
  const [liveScore, setLiveScore] = useState<number | null>(null);

  if (!state.processingState?.result?.experience_analysis) {
    return (
      <div className="editor-tab">
        <div className="no-results">
          <h2>No CV Data Available</h2>
          <p>Process a job description first to enable the editor.</p>
        </div>
      </div>
    );
  }

  const experienceData = state.processingState.result.experience_analysis;

  const handleItemClick = (sectionIdx: number, itemIdx: number, text: string) => {
    setSelectedItem({ sectionIdx, itemIdx });
    setEditingText(text);
    const mockScore = Math.random() * 10;
    setLiveScore(mockScore);
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = e.target.value;
    setEditingText(newText);
    const mockScore = 5 + Math.random() * 5;
    setLiveScore(mockScore);
  };

  const handleSaveEdit = () => {
    if (!selectedItem) return;
    alert('Changes saved! (Simulation)');
  };

  const handleCalculateScores = async () => {
    alert('Recalculating scores... (Simulation - would call API)');
  };

  return (
    <div className="editor-tab">
      <div className="editor-header">
        <h2>CV Section Editor</h2>
        <div className="editor-actions">
          <button 
            className="btn btn-secondary"
            onClick={handleCalculateScores}
          >
            🔄 Recalculate All Scores
          </button>
          <button 
            className="btn btn-primary"
            onClick={() => dispatch({ 
              type: 'SET_UI_STATE', 
              payload: { showExportDialog: true } 
            })}
          >
            📦 Export CV
          </button>
        </div>
      </div>

      <div className="editor-content">
        <div className="sections-panel">
          <h3>Experience Sections</h3>
          {experienceData.map((section: any, sectionIdx: number) => (
            <div key={sectionIdx} className="section-group">
              <div className="section-title">
                <strong>{section.company}</strong> - {section.position}
              </div>
              <div className="section-score-badge">
                <ScoreVisualization score={section.section_score} maxScore={10} size="small" />
              </div>
              <div className="items-list">
                {section.items?.map((item: any, itemIdx: number) => (
                  <div 
                    key={itemIdx}
                    className={`item-edit-card ${selectedItem?.sectionIdx === sectionIdx && selectedItem?.itemIdx === itemIdx ? 'selected' : ''} ${item.kept ? 'kept' : 'removed'}`}
                    onClick={() => handleItemClick(sectionIdx, itemIdx, item.text)}
                  >
                    <div className="item-text-review">
                      {item.text.substring(0, 60)}...
                    </div>
                    <div className="item-mini-score">
                      {item.relevance_score?.toFixed(1)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="edit-panel">
          {selectedItem ? (
            <>
              <div className="edit-header">
                <h3>Edit Experience Item</h3>
                {liveScore !== null && (
                  <div className="live-score">
                    <ScoreVisualization score={liveScore} maxScore={10} />
                    <span className="score-label">Live Score: {liveScore.toFixed(1)}/10</span>
                  </div>
                )}
              </div>
              <textarea
                className="edit-textarea"
                value={editingText}
                onChange={handleTextChange}
                rows={8}
                placeholder="Edit the experience item text..."
              />
              <div className="edit-actions">
                <button className="btn btn-secondary">Cancel</button>
                <button className="btn btn-primary" onClick={handleSaveEdit}>
                  Save Changes
                </button>
              </div>
              {selectedItem && experienceData[selectedItem.sectionIdx]?.items?.[selectedItem.itemIdx] && (
                <div className="explanation-panel">
                  <h4>Why this score?</h4>
                  <p>{experienceData[selectedItem.sectionIdx].items[selectedItem.itemIdx].explanation}</p>
                  <div className="evidence">
                    <strong>Evidence:</strong> {experienceData[selectedItem.sectionIdx].items[selectedItem.itemIdx].posting_evidence}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="no-selection">
              <p>Select an experience item from the left to edit it.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default EditorTab;