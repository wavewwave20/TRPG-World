import { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../stores/authStore';
import {
  getLLMSettings,
  setApiKey,
  deleteApiKey,
  addModel,
  removeModel,
  activateModel,
  deactivateModel,
  testModelConnection,
  type ApiKeyResponse,
  type ModelResponse,
} from '../services/api';

interface LLMSettingsPageProps {
  onBack: () => void;
}

const PROVIDERS = [
  { provider: 'openai', display: 'OpenAI', keyHint: 'sk-...', modelExample: 'gpt-4o' },
  { provider: 'gemini', display: 'Google Gemini', keyHint: 'AI...', modelExample: 'gemini/gemini-2.5-flash' },
  { provider: 'anthropic', display: 'Anthropic', keyHint: 'sk-ant-...', modelExample: 'anthropic/claude-sonnet-4-20250514' },
];

export default function LLMSettingsPage({ onBack }: LLMSettingsPageProps) {
  const userId = useAuthStore((s) => s.userId);

  // Data
  const [apiKeys, setApiKeys] = useState<ApiKeyResponse[]>([]);
  const [models, setModels] = useState<ModelResponse[]>([]);
  const [activeModel, setActiveModel] = useState<ModelResponse | null>(null);
  const [activeSource, setActiveSource] = useState('environment');
  const [envModel, setEnvModel] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // API Key edit state
  const [editingKeyProvider, setEditingKeyProvider] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState('');
  const [savingKey, setSavingKey] = useState(false);
  const [confirmDeleteKey, setConfirmDeleteKey] = useState<string | null>(null);

  // Model add form
  const [showAddModel, setShowAddModel] = useState(false);
  const [newModelProvider, setNewModelProvider] = useState('openai');
  const [newModelId, setNewModelId] = useState('');
  const [newModelDisplayName, setNewModelDisplayName] = useState('');
  const [addingModel, setAddingModel] = useState(false);

  // Model actions state
  const [testingModelId, setTestingModelId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{ id: number; success: boolean; message: string } | null>(null);
  const [confirmDeleteModelId, setConfirmDeleteModelId] = useState<number | null>(null);

  const fetchSettings = useCallback(async () => {
    if (!userId) return;
    try {
      setLoading(true);
      const data = await getLLMSettings(userId);
      setApiKeys(data.api_keys);
      setModels(data.models);
      setActiveModel(data.active_model);
      setActiveSource(data.active_source);
      setEnvModel(data.env_model);
      setError('');
    } catch (e: any) {
      setError(e.message || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // --- API Key Handlers ---

  const handleSaveKey = async (provider: string) => {
    if (!userId || !keyInput.trim()) return;
    setSavingKey(true);
    try {
      await setApiKey(userId, provider, keyInput.trim());
      setEditingKeyProvider(null);
      setKeyInput('');
      await fetchSettings();
    } catch (e: any) {
      setError(e.message || 'Failed to save API key');
    } finally {
      setSavingKey(false);
    }
  };

  const handleDeleteKey = async (provider: string) => {
    if (!userId) return;
    try {
      await deleteApiKey(userId, provider);
      setConfirmDeleteKey(null);
      await fetchSettings();
    } catch (e: any) {
      setError(e.message || 'Failed to delete API key');
    }
  };

  // --- Model Handlers ---

  const handleAddModel = async () => {
    if (!userId || !newModelId.trim() || !newModelDisplayName.trim()) return;
    setAddingModel(true);
    try {
      await addModel(userId, {
        provider: newModelProvider,
        model_id: newModelId.trim(),
        display_name: newModelDisplayName.trim(),
      });
      setNewModelId('');
      setNewModelDisplayName('');
      setShowAddModel(false);
      await fetchSettings();
    } catch (e: any) {
      setError(e.message || 'Failed to add model');
    } finally {
      setAddingModel(false);
    }
  };

  const handleRemoveModel = async (id: number) => {
    if (!userId) return;
    try {
      await removeModel(userId, id);
      setConfirmDeleteModelId(null);
      await fetchSettings();
    } catch (e: any) {
      setError(e.message || 'Failed to remove model');
    }
  };

  const handleActivate = async (id: number) => {
    if (!userId) return;
    try {
      await activateModel(userId, id);
      await fetchSettings();
    } catch (e: any) {
      setError(e.message || 'Failed to activate model');
    }
  };

  const handleDeactivate = async (id: number) => {
    if (!userId) return;
    try {
      await deactivateModel(userId, id);
      await fetchSettings();
    } catch (e: any) {
      setError(e.message || 'Failed to deactivate model');
    }
  };

  const handleTest = async (id: number) => {
    if (!userId) return;
    setTestingModelId(id);
    setTestResult(null);
    try {
      const result = await testModelConnection(userId, id);
      setTestResult({ id, success: result.success, message: result.message });
    } catch (e: any) {
      setTestResult({ id, success: false, message: e.message || 'Test failed' });
    } finally {
      setTestingModelId(null);
    }
  };

  // Helper: find API key info for a provider
  const getApiKeyForProvider = (provider: string) =>
    apiKeys.find((k) => k.provider === provider);

  // Auto-fill model example when provider changes in add form
  const selectedProviderInfo = PROVIDERS.find((p) => p.provider === newModelProvider);

  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={onBack}
          className="flex items-center justify-center w-10 h-10 rounded-lg hover:bg-slate-100 text-slate-500 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
          </svg>
        </button>
        <h1 className="text-xl font-bold text-slate-800">LLM Settings</h1>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-400 hover:text-red-600 ml-2">x</button>
        </div>
      )}

      {/* Current Active Status */}
      <div className="mb-6 p-4 bg-slate-50 border border-slate-200 rounded-xl">
        <div className="text-sm text-slate-500 mb-1">Current Active Model</div>
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2 h-2 rounded-full ${activeSource === 'database' ? 'bg-green-500' : 'bg-yellow-500'}`} />
          <span className="font-semibold text-slate-800">
            {activeModel ? `${activeModel.display_name} (${activeModel.model_id})` : envModel || 'gpt-4o'}
          </span>
          <span className="text-xs text-slate-400 ml-1">
            {activeSource === 'database' ? 'DB' : 'ENV'}
          </span>
        </div>
      </div>

      {loading && (
        <div className="text-center text-slate-400 py-8">Loading...</div>
      )}

      {!loading && (
        <>
          {/* ============================================================ */}
          {/* Section 1: API Keys */}
          {/* ============================================================ */}
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-slate-700 mb-3">API Keys</h2>
            <p className="text-xs text-slate-400 mb-4">
              Set API keys for each provider. Keys are encrypted and stored in the database.
            </p>

            <div className="space-y-3">
              {PROVIDERS.map((prov) => {
                const keyInfo = getApiKeyForProvider(prov.provider);
                const isEditing = editingKeyProvider === prov.provider;
                const isConfirmingDelete = confirmDeleteKey === prov.provider;

                return (
                  <div
                    key={prov.provider}
                    className={`p-4 bg-white border rounded-xl shadow-sm ${
                      keyInfo?.api_key_masked ? 'border-slate-200' : 'border-dashed border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-800">{prov.display}</span>
                        {keyInfo?.api_key_masked ? (
                          <span className="text-xs px-2 py-0.5 bg-green-50 text-green-600 rounded-full border border-green-200">Set</span>
                        ) : (
                          <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-400 rounded-full">Not set</span>
                        )}
                      </div>
                    </div>

                    {keyInfo?.api_key_masked && !isEditing && (
                      <div className="text-xs text-slate-400 font-mono mb-2">{keyInfo.api_key_masked}</div>
                    )}

                    {isEditing ? (
                      <div className="mt-2">
                        <input
                          type="password"
                          value={keyInput}
                          onChange={(e) => setKeyInput(e.target.value)}
                          placeholder={prov.keyHint}
                          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-300 mb-2"
                          autoFocus
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSaveKey(prov.provider)}
                            disabled={savingKey || !keyInput.trim()}
                            className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                          >
                            {savingKey ? 'Saving...' : 'Save'}
                          </button>
                          <button
                            onClick={() => { setEditingKeyProvider(null); setKeyInput(''); }}
                            className="px-4 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-xs font-medium hover:bg-slate-200 transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-2 mt-2">
                        <button
                          onClick={() => { setEditingKeyProvider(prov.provider); setKeyInput(''); }}
                          className="px-3 py-1.5 bg-slate-50 text-slate-600 border border-slate-200 rounded-lg text-xs font-medium hover:bg-slate-100 transition-colors"
                        >
                          {keyInfo?.api_key_masked ? 'Change Key' : 'Set Key'}
                        </button>
                        {keyInfo?.api_key_masked && (
                          isConfirmingDelete ? (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => handleDeleteKey(prov.provider)}
                                className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs font-medium hover:bg-red-700 transition-colors"
                              >
                                Confirm
                              </button>
                              <button
                                onClick={() => setConfirmDeleteKey(null)}
                                className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-xs font-medium hover:bg-slate-200 transition-colors"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setConfirmDeleteKey(prov.provider)}
                              className="px-3 py-1.5 bg-red-50 text-red-600 border border-red-200 rounded-lg text-xs font-medium hover:bg-red-100 transition-colors"
                            >
                              Delete Key
                            </button>
                          )
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* ============================================================ */}
          {/* Section 2: Models */}
          {/* ============================================================ */}
          <div>
            <h2 className="text-lg font-semibold text-slate-700 mb-3">Registered Models</h2>
            <p className="text-xs text-slate-400 mb-4">
              Register LLM models and activate one to use. Model IDs follow the LiteLLM format.
            </p>

            {/* Add Model Button */}
            {!showAddModel && (
              <button
                onClick={() => {
                  setShowAddModel(true);
                  setNewModelProvider('openai');
                  setNewModelId('');
                  setNewModelDisplayName('');
                }}
                className="mb-4 w-full py-3 border-2 border-dashed border-slate-300 rounded-xl text-slate-500 hover:border-blue-400 hover:text-blue-600 transition-colors text-sm font-medium"
              >
                + Register New Model
              </button>
            )}

            {/* Add Model Form */}
            {showAddModel && (
              <div className="mb-4 p-4 bg-white border border-slate-200 rounded-xl shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-slate-700">Register Model</h3>
                  <button onClick={() => setShowAddModel(false)} className="text-slate-400 hover:text-slate-600 text-sm">Cancel</button>
                </div>

                {/* Provider */}
                <div className="mb-3">
                  <label className="block text-xs text-slate-500 mb-1">Provider</label>
                  <div className="flex gap-2">
                    {PROVIDERS.map((prov) => (
                      <button
                        key={prov.provider}
                        onClick={() => {
                          setNewModelProvider(prov.provider);
                          setNewModelId('');
                          setNewModelDisplayName('');
                        }}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                          newModelProvider === prov.provider
                            ? 'bg-blue-100 text-blue-700 border border-blue-300'
                            : 'bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200'
                        }`}
                      >
                        {prov.display}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Model ID */}
                <div className="mb-3">
                  <label className="block text-xs text-slate-500 mb-1">Model ID (LiteLLM format)</label>
                  <input
                    type="text"
                    value={newModelId}
                    onChange={(e) => setNewModelId(e.target.value)}
                    placeholder={selectedProviderInfo?.modelExample || 'e.g. gpt-4o'}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                </div>

                {/* Display Name */}
                <div className="mb-4">
                  <label className="block text-xs text-slate-500 mb-1">Display Name</label>
                  <input
                    type="text"
                    value={newModelDisplayName}
                    onChange={(e) => setNewModelDisplayName(e.target.value)}
                    placeholder="e.g. GPT-4o"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                </div>

                <button
                  onClick={handleAddModel}
                  disabled={addingModel || !newModelId.trim() || !newModelDisplayName.trim()}
                  className="w-full py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {addingModel ? 'Adding...' : 'Register'}
                </button>
              </div>
            )}

            {/* Models List */}
            {models.length === 0 && !showAddModel && (
              <div className="text-center text-slate-400 py-8 text-sm">
                No models registered. Using environment variable ({envModel || 'gpt-4o'}).
              </div>
            )}

            <div className="space-y-3">
              {models.map((model) => (
                <div
                  key={model.id}
                  className={`p-4 bg-white border rounded-xl shadow-sm transition-colors ${
                    model.is_active ? 'border-green-300 bg-green-50/30' : 'border-slate-200'
                  }`}
                >
                  <div className="flex items-start justify-between mb-1">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-800">{model.display_name}</span>
                        <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full">
                          {PROVIDERS.find((p) => p.provider === model.provider)?.display || model.provider}
                        </span>
                        {model.is_active && (
                          <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full font-medium">Active</span>
                        )}
                        {!model.has_api_key && (
                          <span className="text-xs px-2 py-0.5 bg-yellow-50 text-yellow-600 rounded-full border border-yellow-200">No API Key</span>
                        )}
                      </div>
                      <div className="text-sm text-slate-500 font-mono mt-1">{model.model_id}</div>
                    </div>
                  </div>

                  {/* Test Result */}
                  {testResult && testResult.id === model.id && (
                    <div className={`mb-2 p-2 rounded-lg text-xs ${
                      testResult.success ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
                    }`}>
                      {testResult.message}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex flex-wrap gap-2 mt-3">
                    {model.is_active ? (
                      <button
                        onClick={() => handleDeactivate(model.id)}
                        className="px-3 py-1.5 bg-yellow-50 text-yellow-700 border border-yellow-200 rounded-lg text-xs font-medium hover:bg-yellow-100 transition-colors"
                      >
                        Deactivate
                      </button>
                    ) : (
                      <button
                        onClick={() => handleActivate(model.id)}
                        disabled={!model.has_api_key}
                        className="px-3 py-1.5 bg-green-50 text-green-700 border border-green-200 rounded-lg text-xs font-medium hover:bg-green-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title={!model.has_api_key ? 'Set an API key for this provider first' : ''}
                      >
                        Activate
                      </button>
                    )}
                    <button
                      onClick={() => handleTest(model.id)}
                      disabled={testingModelId === model.id || !model.has_api_key}
                      className="px-3 py-1.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg text-xs font-medium hover:bg-blue-100 disabled:opacity-50 transition-colors"
                      title={!model.has_api_key ? 'Set an API key for this provider first' : ''}
                    >
                      {testingModelId === model.id ? 'Testing...' : 'Test'}
                    </button>
                    {confirmDeleteModelId === model.id ? (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleRemoveModel(model.id)}
                          className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs font-medium hover:bg-red-700 transition-colors"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => setConfirmDeleteModelId(null)}
                          className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-xs font-medium hover:bg-slate-200 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDeleteModelId(model.id)}
                        disabled={model.is_active}
                        className="px-3 py-1.5 bg-red-50 text-red-600 border border-red-200 rounded-lg text-xs font-medium hover:bg-red-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        title={model.is_active ? 'Deactivate first to delete' : ''}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
