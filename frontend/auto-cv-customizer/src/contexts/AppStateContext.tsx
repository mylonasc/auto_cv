import React, { createContext, useContext, useEffect, useReducer, type Dispatch } from 'react';

// Define the state shape
export interface AppState {
  // Job descriptions
  jobDescriptions: JobDescription[];
  currentJobDescriptionId: string | null;
  // CV Versions
  cvVersions: CVVersionInfo[];
  currentCVVersionId: string | null;
  // Backend configuration
  backendConfig: BackendConfig;
  // Processing state
  processingState: ProcessingState | null;
  // UI state
  uiState: UIState;
}

// Action types
type AppStateAction =
  | { type: 'SET_JOB_DESCRIPTIONS'; payload: JobDescription[] }
  | { type: 'SET_CURRENT_JOB_DESCRIPTION'; payload: string | null }
  | { type: 'SET_CV_VERSIONS'; payload: CVVersionInfo[] }
  | { type: 'SET_CURRENT_CV_VERSION'; payload: string | null }
  | { type: 'SET_BACKEND_CONFIG'; payload: BackendConfig }
  | { type: 'SET_PROCESSING_STATE'; payload: ProcessingState | null }
  | { type: 'SET_UI_STATE'; payload: Partial<UIState> }
  | { type: 'RESET_STATE' };

// Define sub-interfaces
export interface JobDescription {
  id: string;
  title: string;
  company: string;
  content: string;
  createdAt: string;
  updatedAt: string;
}

export interface CVVersionInfo {
  id: string;
  name: string;
  last_modified: number;
}

export interface CVData {
  personal_statement: string;
  alternative_statements: string[];
  experience_sections: ExperienceSection[];
}

export interface ExperienceSection {
  company: string;
  duration: string;
  position: string;
  text_items: string[];
}

export interface BackendConfig {
  // LLM settings
  analysisModel: ModelConfig;
  statementEditorModel: ModelConfig;
  coverLetterEditorModel: ModelConfig;
  // Processing policies
  rewritePolicy: RewritePolicy;
  analysisPolicy: AnalysisPolicy;
  // Outputs
  outputs: OutputsConfig;
  concurrency_limit: number;
}

export interface ModelConfig {
  provider: 'ollama' | 'google';
  model: string;
  config: Record<string, any>;
}

export interface RewritePolicy {
  maxSectionItemsKeep: number;
  minSectionItemsKeep: number;
  minRelevanceScore: number;
}

export interface AnalysisPolicy {
  maxSectionParseRetries: number;
}

export interface OutputsConfig {
  includeCoverLetter: boolean;
  renderPDF: boolean;
  includeLaTeX: boolean;
  includeScoringComments: boolean;
}

export interface ProcessingState {
  jobId: string | null;
  status: 'queued' | 'processing' | 'succeeded' | 'failed' | 'cancelled';
  progress: string | null;
  message: string | null;
  result: CVJobResult | null;
  jobAnalysis: any | null;
  error: string | null;
  lastSuccessfulJobId?: string | null;
}

export interface UIState {
  sidebarCollapsed: boolean;
  activeTab: 'jobInput' | 'processing' | 'results' | 'editor' | 'history';
  // Modals
  showJobDescriptionManager: boolean;
  showConfigurationPanel: boolean;
  showExportDialog: boolean;
  // Others
  isLoading: boolean;
}

export interface CVJobResult {
  job_id: string;
  status: string;
  summary_metrics: any;
  experience_analysis: any[];
  artifacts: any[];
}

const JOB_STORAGE_KEY = 'auto_cv_saved_jobs_v1';

const isValidJobDescription = (value: any): value is JobDescription => {
  return (
    value &&
    typeof value.id === 'string' &&
    typeof value.title === 'string' &&
    typeof value.company === 'string' &&
    typeof value.content === 'string' &&
    typeof value.createdAt === 'string' &&
    typeof value.updatedAt === 'string'
  );
};

// Initial state
const initialState: AppState = {
  jobDescriptions: [],
  currentJobDescriptionId: null,
  cvVersions: [],
  currentCVVersionId: 'master',
  backendConfig: {
    analysisModel: { provider: 'ollama', model: 'gemma4:31b', config: {} },
    statementEditorModel: { provider: 'google', model: 'models/gemini-2.5-flash-preview-05-20', config: {} },
    coverLetterEditorModel: { provider: 'google', model: 'models/gemini-2.5-flash-preview-05-20', config: {} },
    rewritePolicy: {
      maxSectionItemsKeep: 6,
      minSectionItemsKeep: 1,
      minRelevanceScore: 3
    },
    analysisPolicy: {
      maxSectionParseRetries: 3
    },
    outputs: {
      includeCoverLetter: true,
      renderPDF: true,
      includeLaTeX: true,
      includeScoringComments: true
    },
    concurrency_limit: 5
  },
  processingState: null,
  uiState: {
    sidebarCollapsed: false,
    activeTab: 'jobInput',
    showJobDescriptionManager: false,
    showConfigurationPanel: false,
    showExportDialog: false,
    isLoading: false
  }
};

const getInitialState = (): AppState => {
  if (typeof window === 'undefined') {
    return initialState;
  }

  try {
    const raw = window.localStorage.getItem(JOB_STORAGE_KEY);
    if (!raw) {
      return initialState;
    }

    const parsed = JSON.parse(raw);
    const savedJobs = Array.isArray(parsed?.jobDescriptions)
      ? parsed.jobDescriptions.filter(isValidJobDescription)
      : [];
    const savedCurrentId =
      typeof parsed?.currentJobDescriptionId === 'string'
        ? parsed.currentJobDescriptionId
        : null;

    const currentExists = savedCurrentId
      ? savedJobs.some((job: JobDescription) => job.id === savedCurrentId)
      : false;

    return {
      ...initialState,
      jobDescriptions: savedJobs,
      currentJobDescriptionId: currentExists ? savedCurrentId : null,
    };
  } catch (error) {
    console.error('Failed to load saved jobs from localStorage:', error);
    return initialState;
  }
};

// Reducer
function appStateReducer(state: AppState, action: AppStateAction): AppState {
  switch (action.type) {
    case 'SET_JOB_DESCRIPTIONS':
      return {
        ...state,
        jobDescriptions: action.payload,
        currentJobDescriptionId:
          state.currentJobDescriptionId && action.payload.some((job: JobDescription) => job.id === state.currentJobDescriptionId)
            ? state.currentJobDescriptionId
            : action.payload[0]?.id || null,
      };
    case 'SET_CURRENT_JOB_DESCRIPTION':
      return { ...state, currentJobDescriptionId: action.payload };
    case 'SET_CV_VERSIONS':
      return { ...state, cvVersions: action.payload };
    case 'SET_CURRENT_CV_VERSION':
      return { ...state, currentCVVersionId: action.payload };
    case 'SET_BACKEND_CONFIG':
      return { ...state, backendConfig: action.payload };
    case 'SET_PROCESSING_STATE': {
      const lastSuccessfulJobId = action.payload?.status === 'succeeded' 
        ? action.payload.jobId 
        : state.processingState?.lastSuccessfulJobId;
      
      return { 
        ...state, 
        processingState: action.payload ? {
          ...action.payload,
          lastSuccessfulJobId
        } : null 
      };
    }
    case 'SET_UI_STATE':
      return { ...state, uiState: { ...state.uiState, ...action.payload } };
    case 'RESET_STATE':
      return initialState;
    default:
      return state;
  }
}

// Context
const AppStateContext = createContext<{
  state: AppState;
  dispatch: Dispatch<AppStateAction>;
}>({
  state: initialState,
  dispatch: () => null
});

export const AppStateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(appStateReducer, undefined, getInitialState);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      const payload = {
        jobDescriptions: state.jobDescriptions,
        currentJobDescriptionId: state.currentJobDescriptionId,
      };
      window.localStorage.setItem(JOB_STORAGE_KEY, JSON.stringify(payload));
    } catch (error) {
      console.error('Failed to save jobs to localStorage:', error);
    }
  }, [state.jobDescriptions, state.currentJobDescriptionId]);

  return (
    <AppStateContext.Provider value={{ state, dispatch }}>
      {children}
    </AppStateContext.Provider>
  );
};

export const useAppState = () => {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error('useAppState must be used within an AppStateProvider');
  }
  return context;
};
