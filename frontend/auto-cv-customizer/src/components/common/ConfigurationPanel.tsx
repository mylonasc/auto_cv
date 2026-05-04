import React, { useEffect, useState } from 'react';
import { useAppState } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import './ConfigurationPanel.css';

interface ConfigurationPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const ConfigurationPanel: React.FC<ConfigurationPanelProps> = ({ isOpen, onClose }) => {
  const { state, dispatch } = useAppState();
  const [config, setConfig] = useState(state.backendConfig);
  const [availableModels, setAvailableModels] = useState<{ ollama: string[]; google: string[] }>({
    ollama: [],
    google: [],
  });
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  useEffect(() => {
    setConfig(state.backendConfig);
  }, [state.backendConfig, isOpen]);

  useEffect(() => {
    const fetchModels = async () => {
      if (!isOpen) {
        return;
      }
      try {
        setIsLoadingModels(true);
        const models = await apiService.getAvailableModels();
        setAvailableModels({
          ollama: models.ollama || [],
          google: models.google || [],
        });
      } catch (error) {
        console.error('Failed to fetch available models:', error);
      } finally {
        setIsLoadingModels(false);
      }
    };

    fetchModels();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async () => {
    try {
      const updatedConfig = await apiService.updateConfig(config);
      dispatch({ type: 'SET_BACKEND_CONFIG', payload: updatedConfig });
    } catch (error) {
      console.error('Failed to persist backend config, using local state:', error);
      dispatch({ type: 'SET_BACKEND_CONFIG', payload: config });
    } finally {
      onClose();
    }
  };

  const updateModelConfig = (modelKey: 'analysisModel' | 'statementEditorModel' | 'coverLetterEditorModel', 
                           field: string, value: any) => {
    setConfig(prev => ({
      ...prev,
      [modelKey]: {
        ...prev[modelKey],
        [field]: value
      }
    }));
  };

  const updateRewritePolicy = (field: string, value: any) => {
    setConfig(prev => ({
      ...prev,
      rewritePolicy: {
        ...prev.rewritePolicy,
        [field]: value
      }
    }));
  };

  const updateOutputs = (field: string, value: boolean) => {
    setConfig(prev => ({
      ...prev,
      outputs: {
        ...prev.outputs,
        [field]: value
      }
    }));
  };

  const renderModelField = (modelKey: 'analysisModel' | 'statementEditorModel' | 'coverLetterEditorModel') => {
    const provider = config[modelKey].provider;
    const options = availableModels[provider] || [];
    const selectedModel = config[modelKey].model;
    const dropdownOptions = selectedModel && !options.includes(selectedModel)
      ? [selectedModel, ...options]
      : options;

    return (
      <>
        <label>
          Available Models:
          <select
            value={selectedModel}
            onChange={e => updateModelConfig(modelKey, 'model', e.target.value)}
            disabled={isLoadingModels || dropdownOptions.length === 0}
          >
            {dropdownOptions.length === 0 ? (
              <option value="">No models available</option>
            ) : (
              dropdownOptions.map(model => (
                <option key={`${modelKey}-${provider}-${model}`} value={model}>
                  {model}
                </option>
              ))
            )}
          </select>
        </label>
        <label>
          Custom Model:
          <input
            type="text"
            value={config[modelKey].model}
            onChange={e => updateModelConfig(modelKey, 'model', e.target.value)}
            placeholder={provider === 'ollama' ? 'e.g., gemma4:31b' : 'e.g., models/gemini-1.5-pro'}
          />
        </label>
        <p className="model-hint">
          {isLoadingModels
            ? 'Loading model list...'
            : `Provider reports ${dropdownOptions.length} available model(s).`}
        </p>
      </>
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Backend Configuration</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        
        <div className="modal-body">
          <div className="config-section">
            <h3>LLM Models</h3>
            
            <div className="model-config">
              <h4>Analysis Model</h4>
              <label>
                Provider:
                <select 
                  value={config.analysisModel.provider}
                  onChange={e => updateModelConfig('analysisModel', 'provider', e.target.value)}
                >
                  <option value="ollama">Ollama</option>
                  <option value="google">Google</option>
                </select>
              </label>
              {renderModelField('analysisModel')}
            </div>

            <div className="model-config">
              <h4>Statement Editor</h4>
              <label>
                Provider:
                <select 
                  value={config.statementEditorModel.provider}
                  onChange={e => updateModelConfig('statementEditorModel', 'provider', e.target.value)}
                >
                  <option value="ollama">Ollama</option>
                  <option value="google">Google</option>
                </select>
              </label>
              {renderModelField('statementEditorModel')}
            </div>

            <div className="model-config">
              <h4>Cover Letter Editor</h4>
              <label>
                Provider:
                <select 
                  value={config.coverLetterEditorModel.provider}
                  onChange={e => updateModelConfig('coverLetterEditorModel', 'provider', e.target.value)}
                >
                  <option value="ollama">Ollama</option>
                  <option value="google">Google</option>
                </select>
              </label>
              {renderModelField('coverLetterEditorModel')}
            </div>
          </div>

          <div className="config-section">
            <h3>Rewrite Policy</h3>
            <label>
              Max Section Items Keep:
              <input 
                type="number"
                value={config.rewritePolicy.maxSectionItemsKeep}
                onChange={e => updateRewritePolicy('maxSectionItemsKeep', parseInt(e.target.value))}
                min={1}
              />
            </label>
            <label>
              Min Section Items Keep:
              <input 
                type="number"
                value={config.rewritePolicy.minSectionItemsKeep}
                onChange={e => updateRewritePolicy('minSectionItemsKeep', parseInt(e.target.value))}
                min={0}
              />
            </label>
            <label>
              Min Relevance Score:
              <input 
                type="number"
                value={config.rewritePolicy.minRelevanceScore}
                onChange={e => updateRewritePolicy('minRelevanceScore', parseInt(e.target.value))}
                min={0}
                max={10}
              />
            </label>
          </div>

          <div className="config-section">
            <h3>Output Options</h3>
            <label>
              <input 
                type="checkbox"
                checked={config.outputs.includeCoverLetter}
                onChange={e => updateOutputs('includeCoverLetter', e.target.checked)}
              />
              Include Cover Letter
            </label>
            <label>
              <input 
                type="checkbox"
                checked={config.outputs.renderPDF}
                onChange={e => updateOutputs('renderPDF', e.target.checked)}
              />
              Render PDF
            </label>
            <label>
              <input 
                type="checkbox"
                checked={config.outputs.includeLaTeX}
                onChange={e => updateOutputs('includeLaTeX', e.target.checked)}
              />
              Include LaTeX
            </label>
            <label>
              <input 
                type="checkbox"
                checked={config.outputs.includeScoringComments}
                onChange={e => updateOutputs('includeScoringComments', e.target.checked)}
              />
              Include Scoring Comments
            </label>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave}>
            Save Configuration
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfigurationPanel;
