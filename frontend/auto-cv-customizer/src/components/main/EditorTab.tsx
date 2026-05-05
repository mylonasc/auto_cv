import React, { useState, useEffect, useCallback } from 'react';
import { useAppState, type CVData, type ExperienceSection } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import '../main/EditorTab.css';

const EditorTab: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [cvData, setCvData] = useState<CVData | null>(null);
  const [editingText, setEditingText] = useState('');
  const [selectedItem, setSelectedItem] = useState<{ type: 'experience' | 'alternative' | 'personal', sectionIdx?: number, itemIdx?: number } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [newVersionName, setNewVersionName] = useState('');
  const [showNewVersionInput, setShowNewVersionInput] = useState(false);
  const [isJsonMode, setIsJsonMode] = useState(false);
  const [jsonContent, setJsonContent] = useState('');

  const fetchVersions = useCallback(async () => {
    try {
      const versions = await apiService.listCVVersions();
      dispatch({ type: 'SET_CV_VERSIONS', payload: versions });
    } catch (error) {
      console.error('Failed to fetch CV versions:', error);
    }
  }, [dispatch]);

  const fetchCVData = useCallback(async (versionId: string) => {
    try {
      setIsLoading(true);
      const data = await apiService.getCVVersion(versionId);
      // Ensure alternative_statements exists
      if (!data.alternative_statements) {
        data.alternative_statements = [];
      }
      setCvData(data);
      setJsonContent(JSON.stringify(data, null, 4));
      setIsDirty(false);
    } catch (error) {
      console.error(`Failed to fetch CV data for version ${versionId}:`, error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVersions();
    fetchCVData(state.currentCVVersionId || 'master');
  }, [fetchCVData, fetchVersions, state.currentCVVersionId]);

  const handleVersionChange = (versionId: string) => {
    if (isDirty && !window.confirm('You have unsaved changes. Discard them?')) {
      return;
    }
    dispatch({ type: 'SET_CURRENT_CV_VERSION', payload: versionId });
  };

  const handleCreateVersion = async () => {
    if (!newVersionName || !cvData) return;
    const versionId = newVersionName.toLowerCase().replace(/\s+/g, '_');
    try {
      setIsSaving(true);
      await apiService.createCVVersion(versionId, cvData);
      await fetchVersions();
      dispatch({ type: 'SET_CURRENT_CV_VERSION', payload: versionId });
      setNewVersionName('');
      setShowNewVersionInput(false);
    } catch (error) {
      console.error('Failed to create version:', error);
      alert('Failed to create new version.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteVersion = async (versionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (versionId === 'master') return;
    if (!window.confirm(`Are you sure you want to delete version "${versionId}"?`)) return;
    
    try {
      await apiService.deleteCVVersion(versionId);
      await fetchVersions();
      if (state.currentCVVersionId === versionId) {
        dispatch({ type: 'SET_CURRENT_CV_VERSION', payload: 'master' });
      }
    } catch (error) {
      console.error('Failed to delete version:', error);
    }
  };

  const handleSaveVersion = async () => {
    if (!cvData || !state.currentCVVersionId) return;
    try {
      setIsSaving(true);
      const dataToSave = isJsonMode ? JSON.parse(jsonContent) : cvData;
      await apiService.updateCVVersion(state.currentCVVersionId, dataToSave);
      setCvData(dataToSave);
      setIsDirty(false);
      alert('Version saved successfully!');
    } catch (error) {
      console.error('Failed to save CV data:', error);
      alert('Failed to save changes.');
    } finally {
      setIsSaving(false);
    }
  };

  const updateCvData = (updater: (prev: CVData) => CVData) => {
    setCvData((prev) => {
      if (!prev) {
        return prev;
      }
      const next = updater(prev);
      setJsonContent(JSON.stringify(next, null, 4));
      return next;
    });
    setIsDirty(true);
  };

  // Experience handlers
  const handleExperienceClick = (sectionIdx: number, itemIdx: number, text: string) => {
    setSelectedItem({ type: 'experience', sectionIdx, itemIdx });
    setEditingText(text);
  };

  const handlePersonalStatementClick = () => {
    if (!cvData) return;
    setSelectedItem({ type: 'personal' });
    setEditingText(cvData.personal_statement);
  };

  const handleAlternativeClick = (itemIdx: number, text: string) => {
    setSelectedItem({ type: 'alternative', itemIdx });
    setEditingText(text);
  };

  const handleApplyEdit = () => {
    if (!selectedItem || !cvData) return;

    if (selectedItem.type === 'experience') {
      const next = { ...cvData };
      next.experience_sections[selectedItem.sectionIdx!].text_items[selectedItem.itemIdx!] = editingText;
      updateCvData(() => next);
    } else if (selectedItem.type === 'personal') {
      updateCvData(prev => ({ ...prev, personal_statement: editingText }));
    } else if (selectedItem.type === 'alternative') {
      const next = { ...cvData };
      next.alternative_statements[selectedItem.itemIdx!] = editingText;
      updateCvData(() => next);
    }

    setSelectedItem(null);
    setEditingText('');
  };

  const handleAddSection = () => {
    const newSection = {
      company: "New Company",
      duration: "Duration",
      position: "Position",
      text_items: ["New experience bullet..."]
    };
    updateCvData(prev => ({
      ...prev,
      experience_sections: [newSection, ...prev.experience_sections]
    }));
  };

  const handleDeleteSection = (idx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Delete this entire section?")) return;
    updateCvData(prev => {
      const sections = [...prev.experience_sections];
      sections.splice(idx, 1);
      return { ...prev, experience_sections: sections };
    });
    setSelectedItem(null);
  };

  const handleAddItem = (sectionIdx: number) => {
    updateCvData(prev => {
      const sections = [...prev.experience_sections];
      sections[sectionIdx].text_items.push("New experience bullet...");
      return { ...prev, experience_sections: sections };
    });
  };

  const handleDeleteItem = (sectionIdx: number, itemIdx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    updateCvData(prev => {
      const sections = [...prev.experience_sections];
      sections[sectionIdx].text_items.splice(itemIdx, 1);
      return { ...prev, experience_sections: sections };
    });
    if (selectedItem?.type === 'experience' && selectedItem.sectionIdx === sectionIdx && selectedItem.itemIdx === itemIdx) {
      setSelectedItem(null);
    }
  };

  const handleAddAlternative = () => {
    updateCvData(prev => ({
      ...prev,
      alternative_statements: ["New alternative personal statement...", ...prev.alternative_statements]
    }));
  };

  const handleDeleteAlternative = (idx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    updateCvData(prev => {
      const alts = [...prev.alternative_statements];
      alts.splice(idx, 1);
      return { ...prev, alternative_statements: alts };
    });
    if (selectedItem?.type === 'alternative' && selectedItem.itemIdx === idx) {
      setSelectedItem(null);
    }
  };

  if (isLoading) {
    return <div className="editor-tab"><div className="loading">Loading CV data...</div></div>;
  }

  return (
    <div className="editor-tab">
      <div className="editor-sidebar">
        <div className="sidebar-header">
          <h3>CV Versions</h3>
          <button className="btn-icon" onClick={() => setShowNewVersionInput(!showNewVersionInput)} title="New Version">
            ➕
          </button>
        </div>
        
        {showNewVersionInput && (
          <div className="new-version-input">
            <input 
              type="text" 
              placeholder="Version name..." 
              value={newVersionName}
              onChange={(e) => setNewVersionName(e.target.value)}
            />
            <button className="btn btn-primary btn-sm" onClick={handleCreateVersion} disabled={isSaving}>
              Create
            </button>
          </div>
        )}

        <div className="version-list">
          {state.cvVersions.map(v => (
            <div 
              key={v.id} 
              className={`version-item ${state.currentCVVersionId === v.id ? 'active' : ''}`}
              onClick={() => handleVersionChange(v.id)}
            >
              <div className="version-info">
                <span className="version-name">{v.name}</span>
                <span className="version-date">{new Date(v.last_modified * 1000).toLocaleDateString()}</span>
              </div>
              {v.id !== 'master' && (
                <button className="btn-delete" onClick={(e) => handleDeleteVersion(v.id, e)}>✕</button>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="editor-main">
        <div className="editor-header">
          <div className="header-title">
            <h2>Editing: {state.cvVersions.find(v => v.id === state.currentCVVersionId)?.name || state.currentCVVersionId}</h2>
            {isDirty && <span className="dirty-indicator">• Unsaved Changes</span>}
          </div>
          <div className="editor-actions">
            <button className={`btn ${isJsonMode ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setIsJsonMode(!isJsonMode)}>
              {isJsonMode ? 'Visual Mode' : '{ } JSON Mode'}
            </button>
            <button className="btn btn-success" onClick={handleSaveVersion} disabled={!isDirty || isSaving}>
              {isSaving ? 'Saving...' : '💾 Save Version'}
            </button>
            <button className="btn btn-secondary" onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'jobInput' } })}>
              🔄 Run Analysis
            </button>
          </div>
        </div>

        {isJsonMode ? (
          <div className="json-editor-container">
            <textarea 
              className="json-textarea"
              value={jsonContent}
              onChange={(e) => {
                setJsonContent(e.target.value);
                setIsDirty(true);
              }}
              spellCheck={false}
            />
          </div>
        ) : (
          <div className="editor-content">
            <div className="sections-panel">
              {/* Personal Statements Section */}
              <div className="editor-section-block">
                <div className="panel-header">
                  <h3>Personal Statements</h3>
                </div>
                <div className="personal-statement-group">
                  <div className="group-label">Master Statement</div>
                  <div 
                    className={`item-edit-card ${selectedItem?.type === 'personal' ? 'selected' : ''}`}
                    onClick={handlePersonalStatementClick}
                  >
                    <div className="item-text-review">{cvData?.personal_statement?.substring(0, 100) || ''}...</div>
                  </div>

                  <div className="group-label-row">
                    <span>Alternative Statements (for AI rewriting)</span>
                    <button className="btn btn-xs btn-secondary" onClick={handleAddAlternative}>+ Add Alternative</button>
                  </div>
                  <div className="alternatives-list">
                    {cvData?.alternative_statements?.map((alt: string, idx: number) => (
                      <div 
                        key={idx}
                        className={`item-edit-card ${selectedItem?.type === 'alternative' && selectedItem.itemIdx === idx ? 'selected' : ''}`}
                        onClick={() => handleAlternativeClick(idx, alt)}
                      >
                        <div className="item-text-review">{alt.substring(0, 80)}...</div>
                        <button className="btn-delete-item" onClick={(e) => handleDeleteAlternative(idx, e)}>✕</button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Experience Sections */}
              <div className="editor-section-block">
                <div className="panel-header">
                  <h3>Experience Sections</h3>
                  <button className="btn btn-xs btn-secondary" onClick={handleAddSection}>+ Add Section</button>
                </div>
                {cvData?.experience_sections.map((section: ExperienceSection, sectionIdx: number) => (
                  <div key={sectionIdx} className="section-group">
                    <div className="section-title">
                      <div className="title-row">
                        <input 
                          className="inline-input-bold"
                          value={section.company} 
                          onChange={(e) => {
                            const next = {...cvData};
                            next.experience_sections[sectionIdx].company = e.target.value;
                            updateCvData(() => next);
                          }}
                        />
                        <button className="btn-delete-sm" onClick={(e) => handleDeleteSection(sectionIdx, e)}>✕</button>
                      </div>
                      <div className="subtitle-row">
                        <input 
                          className="inline-input"
                          value={section.position} 
                          onChange={(e) => {
                            const next = {...cvData};
                            next.experience_sections[sectionIdx].position = e.target.value;
                            updateCvData(() => next);
                          }}
                        />
                        <input 
                          className="inline-input-right"
                          value={section.duration} 
                          onChange={(e) => {
                            const next = {...cvData};
                            next.experience_sections[sectionIdx].duration = e.target.value;
                            updateCvData(() => next);
                          }}
                        />
                      </div>
                    </div>
                    <div className="items-list">
                      {section.text_items?.map((itemText: string, itemIdx: number) => (
                        <div 
                          key={itemIdx}
                          className={`item-edit-card ${selectedItem?.type === 'experience' && selectedItem.sectionIdx === sectionIdx && selectedItem.itemIdx === itemIdx ? 'selected' : ''}`}
                          onClick={() => handleExperienceClick(sectionIdx, itemIdx, itemText)}
                        >
                          <div className="item-text-review">
                            {itemText.substring(0, 100)}...
                          </div>
                          <button className="btn-delete-item" onClick={(e) => handleDeleteItem(sectionIdx, itemIdx, e)}>✕</button>
                        </div>
                      ))}
                      <button className="btn btn-xs btn-dashed" onClick={() => handleAddItem(sectionIdx)}>+ Add Bullet</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="edit-panel">
              {selectedItem ? (
                <>
                  <div className="edit-header">
                    <h3>
                      {selectedItem.type === 'personal' && 'Edit Master Personal Statement'}
                      {selectedItem.type === 'alternative' && 'Edit Alternative Statement'}
                      {selectedItem.type === 'experience' && 'Edit Experience Item'}
                    </h3>
                  </div>
                  <textarea
                    className="edit-textarea"
                    value={editingText}
                    onChange={(e) => setEditingText(e.target.value)}
                    rows={12}
                    placeholder="Enter text..."
                  />
                  <div className="edit-actions">
                    <button className="btn btn-secondary" onClick={() => setSelectedItem(null)}>
                      Cancel
                    </button>
                    <button className="btn btn-primary" onClick={handleApplyEdit}>
                      Apply Edit
                    </button>
                  </div>
                </>
              ) : (
                <div className="no-selection">
                  <p>Select an item from the left to edit it.</p>
                  <p className="hint">Remember to click <strong>Save Version</strong> to persist your changes to the server.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EditorTab;
