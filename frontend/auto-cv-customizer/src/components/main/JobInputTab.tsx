import React, { useState, useEffect, useRef } from 'react';
import { useAppState, type CVData, type ExperienceSection } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import './JobInputTab.css';

const JobInputTab: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [jobText, setJobText] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [editingJobId, setEditingJobId] = useState<string | null>(null);
  
  // Experience preview state
  const [cvData, setCvData] = useState<CVData | null>(null);
  const [editingItemId, setEditingItemId] = useState<{type: 'experience' | 'personal', sectionIdx?: number, itemIdx?: number} | null>(null);
  const [editingText, setEditingText] = useState('');
  const [isSavingCV, setIsSavingCV] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const versions = await apiService.listCVVersions();
        dispatch({ type: 'SET_CV_VERSIONS', payload: versions });
        
        // Fetch current version data
        const versionId = state.currentCVVersionId || 'master';
        const data = await apiService.getCVVersion(versionId);
        setCvData(data);
      } catch (error) {
        console.error('Failed to fetch initial data:', error);
      }
    };
    fetchInitialData();
  }, [dispatch, state.currentCVVersionId]);

  useEffect(() => {
    const selectedJob = state.jobDescriptions.find((job) => job.id === state.currentJobDescriptionId);
    if (!selectedJob) {
      return;
    }

    setEditingJobId(selectedJob.id);
    setJobTitle(selectedJob.title || '');
    setCompanyName(selectedJob.company || '');
    setJobText(selectedJob.content || '');
  }, [state.currentJobDescriptionId, state.jobDescriptions]);

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setJobText(e.target.value);
  };

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setJobTitle(e.target.value);
  };

  const handleCompanyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCompanyName(e.target.value);
  };

  const handleVersionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    dispatch({ type: 'SET_CURRENT_CV_VERSION', payload: e.target.value });
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        setJobText(text);
        if (!jobTitle) {
          setJobTitle(file.name.replace(/\.[^/.]+$/, ''));
        }
      };
      reader.readAsText(file);
    }
  };

  const handleSaveJob = () => {
    if (!jobText.trim()) {
      alert('Please enter or upload a job description');
      return;
    }

    const now = new Date().toISOString();

    if (editingJobId) {
      const updatedJobs = state.jobDescriptions.map((job) =>
        job.id === editingJobId
          ? {
              ...job,
              title: jobTitle || 'Untitled Job',
              company: companyName || 'Unknown Company',
              content: jobText,
              updatedAt: now,
            }
          : job
      );
      dispatch({ type: 'SET_JOB_DESCRIPTIONS', payload: updatedJobs });
      dispatch({ type: 'SET_CURRENT_JOB_DESCRIPTION', payload: editingJobId });
      return;
    }

    const newJob = {
      id: Date.now().toString(),
      title: jobTitle || 'Untitled Job',
      company: companyName || 'Unknown Company',
      content: jobText,
      createdAt: now,
      updatedAt: now,
    };

    const updatedJobs = [...state.jobDescriptions, newJob];
    dispatch({ type: 'SET_JOB_DESCRIPTIONS', payload: updatedJobs });
    dispatch({ type: 'SET_CURRENT_JOB_DESCRIPTION', payload: newJob.id });
    setEditingJobId(newJob.id);
  };

  const resetJobForm = () => {
    setEditingJobId(null);
    setJobText('');
    setJobTitle('');
    setCompanyName('');
    dispatch({ type: 'SET_CURRENT_JOB_DESCRIPTION', payload: null });
  };

  const handleDeleteJob = () => {
    if (!editingJobId) {
      return;
    }

    const confirmed = window.confirm('Delete this saved job posting?');
    if (!confirmed) {
      return;
    }

    const updatedJobs = state.jobDescriptions.filter((job) => job.id !== editingJobId);
    dispatch({ type: 'SET_JOB_DESCRIPTIONS', payload: updatedJobs });
    setEditingJobId(null);
    setJobText('');
    setJobTitle('');
    setCompanyName('');
  };

  const handleLoadExample = () => {
    const exampleJob = `We are looking for a Senior Machine Learning Engineer to join our AI team. 
    
Responsibilities:
- Design and implement machine learning models for production use
- Work with cross-functional teams to identify ML opportunities
- Optimize existing models for performance and scalability
- Mentor junior engineers and review code

Requirements:
- MSc or PhD in Computer Science, Machine Learning, or related field
- 5+ years of experience in machine learning engineering
- Strong Python programming skills
- Experience with TensorFlow, PyTorch, or similar frameworks
- Knowledge of cloud platforms (GCP, AWS, or Azure)
- Excellent communication skills in English

Nice to have:
- Experience with transformer models and LLMs
- Background in GNNs or graph-based ML
- Experience with MLOps practices`;

    setJobText(exampleJob);
    setJobTitle('Senior ML Engineer Example');
    setCompanyName('TechCorp AI');
  };

  // Editing handlers
  const handleEditPersonal = () => {
    if (!cvData) return;
    setEditingItemId({ type: 'personal' });
    setEditingText(cvData.personal_statement);
  };

  const handleEditItem = (sectionIdx: number, itemIdx: number, text: string) => {
    setEditingItemId({ type: 'experience', sectionIdx, itemIdx });
    setEditingText(text);
  };

  const handleSaveCVEdit = async () => {
    if (!editingItemId || !cvData) return;
    
    const updated = JSON.parse(JSON.stringify(cvData));
    if (editingItemId.type === 'personal') {
      updated.personal_statement = editingText;
    } else {
      updated.experience_sections[editingItemId.sectionIdx!].text_items[editingItemId.itemIdx!] = editingText;
    }
    
    try {
      setIsSavingCV(true);
      await apiService.updateCVVersion(state.currentCVVersionId || 'master', updated);
      setCvData(updated);
      setEditingItemId(null);
    } catch (error) {
      console.error('Failed to save CV edit:', error);
      alert('Failed to save CV changes.');
    } finally {
      setIsSavingCV(false);
    }
  };

  return (
    <div className="job-input-tab">
      <div className="input-grid">
        <div className="input-section">
          <h2>1. Job Description</h2>
          {editingJobId && (
            <div className="editing-banner">Editing saved job posting</div>
          )}
          <div className="form-group">
            <label htmlFor="jobTitle">Job Title</label>
            <input id="jobTitle" type="text" value={jobTitle} onChange={handleTitleChange} placeholder="e.g., Senior ML Engineer" className="form-input" />
          </div>

          <div className="form-group">
            <label htmlFor="companyName">Company Name</label>
            <input id="companyName" type="text" value={companyName} onChange={handleCompanyChange} placeholder="e.g., Google" className="form-input" />
          </div>

          <div className="form-group">
            <label htmlFor="jobText">Job Description</label>
            <textarea id="jobText" value={jobText} onChange={handleTextChange} placeholder="Paste the job description here..." className="job-textarea" rows={10} />
          </div>

          <div className="actions-row">
            <button className="btn btn-secondary" type="button" onClick={() => fileInputRef.current?.click()}>📁 Upload</button>
            <input ref={fileInputRef} id="fileUpload" type="file" onChange={handleFileUpload} accept=".txt,.md,text/plain" style={{ display: 'none' }} />
            <button className="btn btn-secondary" onClick={handleLoadExample}>Example</button>
            <button className="btn btn-primary" onClick={handleSaveJob} disabled={!jobText.trim()}>{editingJobId ? 'Update Job' : 'Save Job'}</button>
            <button className="btn btn-secondary" onClick={resetJobForm}>New</button>
            {editingJobId && <button className="btn btn-danger" onClick={handleDeleteJob}>Delete</button>}
          </div>
        </div>

        <div className="cv-preview-section">
          <h2>2. Review CV Draft</h2>
          <div className="form-group">
            <label htmlFor="cvVersion">Using CV Version:</label>
            <select id="cvVersion" className="form-input" value={state.currentCVVersionId || 'master'} onChange={handleVersionChange}>
              {state.cvVersions.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </div>

          <div className="cv-items-preview">
            {/* Personal Statement Preview */}
            <div className="preview-block">
               <div className="preview-section-header"><strong>Master Personal Statement</strong></div>
               <div className="preview-item">
                  {editingItemId?.type === 'personal' ? (
                    <div className="inline-edit">
                      <textarea value={editingText} onChange={(e) => setEditingText(e.target.value)} rows={4} />
                      <div className="inline-actions">
                        <button className="btn btn-xs" onClick={() => setEditingItemId(null)}>Cancel</button>
                        <button className="btn btn-xs btn-primary" onClick={handleSaveCVEdit} disabled={isSavingCV}>Save</button>
                      </div>
                    </div>
                  ) : (
                    <div className="item-text" onClick={handleEditPersonal}>
                      {cvData?.personal_statement}
                      <span className="edit-hint">✎</span>
                    </div>
                  )}
               </div>
            </div>

            {/* Experience Sections Preview */}
            {cvData?.experience_sections.map((section: ExperienceSection, sIdx: number) => (
              <div key={sIdx} className="preview-section">
                <div className="preview-section-header">
                  <strong>{section.company}</strong> ({section.duration})
                </div>
                {section.text_items.map((item: string, iIdx: number) => (
                  <div key={iIdx} className="preview-item">
                    {editingItemId?.type === 'experience' && editingItemId?.sectionIdx === sIdx && editingItemId?.itemIdx === iIdx ? (
                      <div className="inline-edit">
                        <textarea value={editingText} onChange={(e) => setEditingText(e.target.value)} rows={3} />
                        <div className="inline-actions">
                          <button className="btn btn-xs" onClick={() => setEditingItemId(null)}>Cancel</button>
                          <button className="btn btn-xs btn-primary" onClick={handleSaveCVEdit} disabled={isSavingCV}>Save</button>
                        </div>
                      </div>
                    ) : (
                      <div className="item-text" onClick={() => handleEditItem(sIdx, iIdx, item)}>
                        {item}
                        <span className="edit-hint">✎</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {state.currentJobDescriptionId && (
        <div className="start-banner">
          <div className="banner-content">
            <span className="banner-text">
              Ready to process <strong>{state.jobDescriptions.find(j => j.id === state.currentJobDescriptionId)?.title}</strong> 
              using <strong>{state.cvVersions.find(v => v.id === state.currentCVVersionId)?.name || state.currentCVVersionId}</strong>
            </span>
            <button className="btn btn-lg btn-primary" onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'processing' } })}>
              Start AI Analysis →
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default JobInputTab;
