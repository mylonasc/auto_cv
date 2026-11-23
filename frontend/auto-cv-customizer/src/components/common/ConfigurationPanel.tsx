import React, { useEffect, useState } from 'react';
import { useAppState, type BackendConfig, type ModelConfig, type RewritePolicy, type OutputsConfig } from '../../contexts/AppStateContext';
import apiService from '../../services/api';
import type { ModelCatalogResponse, ProviderModelList } from '../../types/api.generated';
import { resolveModelOptions } from '../../domain/modelCatalog';
import { Button, Modal } from './Primitives';
import './ConfigurationPanel.css';

interface ConfigurationPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const emptyProvider: ProviderModelList = { models: [], error: null, live: false };

const ConfigurationPanel: React.FC<ConfigurationPanelProps> = ({ isOpen, onClose }) => {
  const { state, dispatch } = useAppState();
  const [config, setConfig] = useState<BackendConfig>(state.backendConfig);
  const [catalog, setCatalog] = useState<ModelCatalogResponse>({ ollama: emptyProvider, google: emptyProvider });
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    setConfig(state.backendConfig);
  }, [state.backendConfig, isOpen]);

  const fetchModels = async (refresh = false) => {
    setIsLoadingModels(true);
    setCatalogError(null);
    try {
      setCatalog(await apiService.getAvailableModels(refresh));
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsLoadingModels(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      void fetchModels(false);
    }
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

  const updateModelConfig = (
    modelKey: 'analysisModel' | 'statementEditorModel' | 'coverLetterEditorModel',
    field: keyof ModelConfig,
    value: ModelConfig[keyof ModelConfig],
  ) => {
    setConfig(prev => ({
      ...prev,
      [modelKey]: {
        ...prev[modelKey],
        [field]: value
      }
    }));
  };

  const updateRewritePolicy = (field: keyof RewritePolicy, value: number) => {
    setConfig(prev => ({
      ...prev,
      rewritePolicy: {
        ...prev.rewritePolicy,
        [field]: value
      }
    }));
  };

  const updateOutputs = (field: keyof OutputsConfig, value: boolean) => {
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
    const reported = catalog[provider] ?? emptyProvider;
    const selectedModel = config[modelKey].model;
    const { options: dropdownOptions, stale } = resolveModelOptions(reported.models, selectedModel);

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
            placeholder={provider === 'ollama' ? 'e.g., gemma4:31b' : 'e.g., models/gemini-3.8-flash'}
          />
        </label>
        <p className="model-hint">
          {isLoadingModels
            ? 'Loading model list...'
            : reported.error
              ? `Provider list unavailable: ${reported.error}`
              : reported.live
                ? `Provider reports ${dropdownOptions.length} available model(s) — live list.`
                : `Provider reports ${dropdownOptions.length} available model(s).`}
          {stale && !isLoadingModels && ' This saved model is not in the provider list and may be retired.'}
        </p>
      </>
    );
  };

  return (
    <Modal title="Backend Configuration" onClose={onClose} className="configuration-panel">
        <div className="cv-modal-body">
          <div className="config-section">
            <h3>LLM Models</h3>
            <p>
              <Button onClick={() => fetchModels(true)} disabled={isLoadingModels}>
                {isLoadingModels ? 'Refreshing…' : 'Refresh model lists'}
              </Button>
            </p>
            {catalogError && <p role="alert">Could not load provider model lists: {catalogError}</p>}
            
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
              <h4>Cover Letter Editor (CLI only)</h4>
              <p>Configure this existing CLI workflow with --cover-letter-provider and --cover-letter-model. HTTP jobs do not generate cover letters.</p>
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
                disabled={!config.outputs.includeCoverLetter}
                onChange={e => updateOutputs('includeCoverLetter', e.target.checked)}
              />
              Include Cover Letter (CLI only; disable for HTTP jobs)
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

        <div className="cv-modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave}>
            Save Configuration
          </button>
        </div>
    </Modal>
  );
};

export default ConfigurationPanel;
