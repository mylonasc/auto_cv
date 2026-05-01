import React, { useState } from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import './JobInputTab.css';

const JobInputTab: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [jobText, setJobText] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setJobText(e.target.value);
  };

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setJobTitle(e.target.value);
  };

  const handleCompanyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCompanyName(e.target.value);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
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

    const newJob = {
      id: Date.now().toString(),
      title: jobTitle || 'Untitled Job',
      company: companyName || 'Unknown Company',
      content: jobText,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    const updatedJobs = [...state.jobDescriptions, newJob];
    dispatch({ type: 'SET_JOB_DESCRIPTIONS', payload: updatedJobs });
    dispatch({ type: 'SET_CURRENT_JOB_DESCRIPTION', payload: newJob.id });
    
    // Reset form
    setJobText('');
    setJobTitle('');
    setCompanyName('');
    setSelectedFile(null);
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

  return (
    <div className="job-input-tab">
      <div className="input-section">
        <h2>Job Description Input</h2>
        <p className="section-description">
          Paste a job description, upload a text file, or load an example.
        </p>

        <div className="form-group">
          <label htmlFor="jobTitle">Job Title</label>
          <input
            id="jobTitle"
            type="text"
            value={jobTitle}
            onChange={handleTitleChange}
            placeholder="e.g., Senior ML Engineer"
            className="form-input"
          />
        </div>

        <div className="form-group">
          <label htmlFor="companyName">Company Name</label>
          <input
            id="companyName"
            type="text"
            value={companyName}
            onChange={handleCompanyChange}
            placeholder="e.g., Google"
            className="form-input"
          />
        </div>

        <div className="form-group">
          <label htmlFor="jobText">Job Description</label>
          <textarea
            id="jobText"
            value={jobText}
            onChange={handleTextChange}
            placeholder="Paste the job description here..."
            className="job-textarea"
            rows={12}
          />
          <div className="char-count">
            {jobText.length} characters
          </div>
        </div>

        <div className="actions-row">
          <div className="file-upload">
            <label htmlFor="fileUpload" className="btn btn-secondary">
              📁 Upload File
              <input
                id="fileUpload"
                type="file"
                onChange={handleFileUpload}
                accept=".txt,.pdf,.doc,.docx"
                style={{ display: 'none' }}
              />
            </label>
            {selectedFile && (
              <span className="file-name">{selectedFile.name}</span>
            )}
          </div>

          <button className="btn btn-secondary" onClick={handleLoadExample}>
            Load Example
          </button>

          <button 
            className="btn btn-primary"
            onClick={handleSaveJob}
            disabled={!jobText.trim()}
          >
            Save Job Description
          </button>
        </div>
      </div>

      {state.currentJobDescriptionId && (
        <div className="current-job-info">
          <h3>Current Job Description</h3>
          <p>
            {state.jobDescriptions.find(j => j.id === state.currentJobDescriptionId)?.title}
          </p>
          <button 
            className="btn btn-primary"
            onClick={() => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'processing' } })}
          >
            Start Processing →
          </button>
        </div>
      )}
    </div>
  );
};

export default JobInputTab;