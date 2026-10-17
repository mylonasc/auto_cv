import React, { useState, useEffect, useCallback } from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import type { CVData, ExperienceSection, CVTemplateMeta, MotivationLetterTemplateMeta } from '../../types/cv';
import { useCVVersion } from '../../hooks/useCVVersion';
import { editText, editSection, addBullet, removeBullet, parseCVJSON } from '../../domain/cvEditing';
import apiService from '../../services/api';
import type { TemplateRegistryResponse, CVVersionInfo } from '../../services/api';
import '../main/EditorTab.css';

const EditorTab: React.FC = () => {
  const { state, dispatch } = useAppState();
  const versionsChanged = useCallback((versions: CVVersionInfo[]) => dispatch({ type: 'SET_CV_VERSIONS', payload: versions }), [dispatch]);
  const source = useCVVersion(state.currentCVVersionId || 'master', versionsChanged);
  const { data: cvData, setData: setCvData, isLoading } = source;
  const [editingText, setEditingText] = useState('');
  const [selectedItem, setSelectedItem] = useState<{ type: 'experience' | 'alternative' | 'personal', sectionIdx?: number, itemIdx?: number } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [newVersionName, setNewVersionName] = useState('');
  const [showNewVersionInput, setShowNewVersionInput] = useState(false);
  const [isJsonMode, setIsJsonMode] = useState(false);
  const [jsonContent, setJsonContent] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [templateRegistry, setTemplateRegistry] = useState<TemplateRegistryResponse>({
    cv_templates: {},
    motivation_letter_templates: {},
  });

  const fetchTemplateRegistry = useCallback(async () => {
    try {
      const registry = await apiService.getTemplateRegistry();
      setTemplateRegistry(registry);
    } catch (error) {
      console.error('Failed to fetch template registry:', error);
    }
  }, []);

  useEffect(() => {
    fetchTemplateRegistry();
  }, [fetchTemplateRegistry]);

  useEffect(() => {
    setSelectedItem(null);
    setIsDirty(false);
    setIsJsonMode(false);
  }, [state.currentCVVersionId]);

  useEffect(() => { if (cvData) setJsonContent(JSON.stringify(cvData, null, 4)); }, [cvData]);

  const handleVersionChange = (versionId: string) => {
    if (isSaving) return;
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
      await source.create(versionId, isJsonMode ? parseCVJSON(jsonContent) : cvData);
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
      await source.remove(versionId);
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
      const dataToSave = isJsonMode ? parseCVJSON(jsonContent) : cvData;
      await source.save(dataToSave);
      setIsDirty(false);
      setJsonError(null);
      alert('Version saved successfully!');
    } catch (error) {
      console.error('Failed to save CV data:', error);
      setJsonError(String(error));
      alert('Failed to save changes.');
    } finally {
      setIsSaving(false);
    }
  };

  const updateCvData = (updater: (prev: CVData) => CVData) => {
    if (isSaving) return;
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

  const toggleJsonMode = () => {
    if (isSaving) return;
    try {
      if (isJsonMode) setCvData(parseCVJSON(jsonContent));
      else if (cvData) setJsonContent(JSON.stringify(cvData, null, 4));
      setJsonError(null);
      setSelectedItem(null);
      setIsJsonMode(!isJsonMode);
    } catch (error) { setJsonError(String(error)); }
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

    updateCvData(prev => editText(prev, selectedItem, editingText));

    setSelectedItem(null);
    setEditingText('');
  };

  const handleAddSection = () => {
    setSelectedItem(null);
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
    setSelectedItem(null);
    updateCvData(prev => addBullet(prev, sectionIdx));
  };

  const handleDeleteItem = (sectionIdx: number, itemIdx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    updateCvData(prev => removeBullet(prev, sectionIdx, itemIdx));
    setSelectedItem(null);
  };

  const handleAddAlternative = () => {
    setSelectedItem(null);
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
    setSelectedItem(null);
  };

  const updateCVTemplate = (field: keyof CVTemplateMeta, value: string) => {
    updateCvData(prev => ({
      ...prev,
      cv_template: {
        ...prev.cv_template,
        [field]: value,
      },
    }));
  };

  const updateMotivationTemplate = (field: keyof MotivationLetterTemplateMeta, value: string) => {
    updateCvData(prev => ({
      ...prev,
      motivation_letter_template: {
        ...prev.motivation_letter_template,
        [field]: value,
      },
    }));
  };

  if (isLoading) {
    return <div className="editor-tab"><div className="loading">Loading CV data...</div></div>;
  }

  return (
    <div className="editor-tab">
      {source.error && <p role="alert">{source.error}</p>}
      {jsonError && <p role="alert">{jsonError}</p>}
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
            <p>Source CV version — saving here changes inputs for future analyses, not a result working copy.</p>
            {isDirty && <span className="dirty-indicator">• Unsaved Changes</span>}
          </div>
          <div className="editor-actions">
            <button className={`btn ${isJsonMode ? 'btn-primary' : 'btn-secondary'}`} onClick={toggleJsonMode} disabled={isSaving}>
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
              aria-label="Source CV JSON"
              disabled={isSaving}
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
                  <h3>Template Selection</h3>
                </div>
                <div className="section-group">
                  <div className="subtitle-row" style={{ marginBottom: '8px' }}>
                    <select
                      className="inline-input"
                      value={cvData?.cv_template?.template_id || 'default_cv'}
                      onChange={(e) => {
                        const selectedId = e.target.value;
                        updateCvData(prev => ({
                          ...prev,
                          cv_template: {
                            template_id: selectedId,
                             template_path: templateRegistry.cv_templates[selectedId] || null,
                            experience_section_title: prev.cv_template?.experience_section_title || 'Work Experience',
                          },
                        }));
                      }}
                    >
                      {Object.keys(templateRegistry.cv_templates).map((templateId) => (
                        <option key={templateId} value={templateId}>{templateId}</option>
                      ))}
                    </select>
                    <input
                      className="inline-input-right"
                      value={cvData?.cv_template?.template_path || 'assets/latex_cv_template_v0.tex'}
                      onChange={(e) => updateCVTemplate('template_path', e.target.value)}
                      placeholder="CV template path"
                    />
                  </div>
                  <input
                    className="inline-input"
                    value={cvData?.cv_template?.experience_section_title || 'Work Experience'}
                    onChange={(e) => updateCVTemplate('experience_section_title', e.target.value)}
                    placeholder="Experience section title"
                  />

                  <div className="subtitle-row" style={{ marginTop: '12px' }}>
                    <select
                      className="inline-input"
                      value={cvData?.motivation_letter_template?.template_id || 'default_motivation_letter'}
                      onChange={(e) => {
                        const selectedId = e.target.value;
                        updateCvData(prev => ({
                          ...prev,
                          motivation_letter_template: {
                            template_id: selectedId,
                             template_path: templateRegistry.motivation_letter_templates[selectedId] || null,
                          },
                        }));
                      }}
                    >
                      {Object.keys(templateRegistry.motivation_letter_templates).map((templateId) => (
                        <option key={templateId} value={templateId}>{templateId}</option>
                      ))}
                    </select>
                    <input
                      className="inline-input-right"
                      value={cvData?.motivation_letter_template?.template_path || 'assets/cover_letter/CoverLetter_Template.tex'}
                      onChange={(e) => updateMotivationTemplate('template_path', e.target.value)}
                      placeholder="Motivation template path"
                    />
                  </div>
                </div>
              </div>

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
                            updateCvData(prev => editSection(prev, sectionIdx, { company: e.target.value }));
                          }}
                        />
                        <button className="btn-delete-sm" onClick={(e) => handleDeleteSection(sectionIdx, e)}>✕</button>
                      </div>
                      <div className="subtitle-row">
                        <input 
                          className="inline-input"
                          value={section.position} 
                          onChange={(e) => {
                            updateCvData(prev => editSection(prev, sectionIdx, { position: e.target.value }));
                          }}
                        />
                        <input 
                          className="inline-input-right"
                          value={section.duration} 
                          onChange={(e) => {
                            updateCvData(prev => editSection(prev, sectionIdx, { duration: e.target.value }));
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
                    <button className="btn btn-primary" onClick={handleApplyEdit} disabled={isSaving}>
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
