import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Save, CheckCircle2, AlertCircle, Loader2, Sparkles, Tv, FileText, Globe } from 'lucide-react';
import { api } from '../services/api';
import { AppSettings } from '../types';

export const Settings: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Test states
  const [testingSonarr, setTestingSonarr] = useState(false);
  const [sonarrResult, setSonarrResult] = useState<{ success: boolean; message: string } | null>(null);

  const [testingOllama, setTestingOllama] = useState(false);
  const [ollamaResult, setOllamaResult] = useState<{ success: boolean; message: string; models?: string[] } | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await api.getSettings();
      setSettings(data);
    } catch (err) {
      console.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setSaveSuccess(false);
    try {
      await api.updateSettings(settings);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      alert(err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const testSonarr = async () => {
    if (!settings) return;
    setTestingSonarr(true);
    setSonarrResult(null);
    try {
      const res = await api.testConnection({
        service: 'sonarr',
        url: settings.sonarr_url,
        api_key: settings.sonarr_api_key,
      });
      setSonarrResult({ success: res.success, message: res.message });
    } catch (err: any) {
      setSonarrResult({ success: false, message: err.message || 'Connection failed' });
    } finally {
      setTestingSonarr(false);
    }
  };

  const testOllama = async () => {
    if (!settings) return;
    setTestingOllama(true);
    setOllamaResult(null);
    try {
      const res = await api.testConnection({
        service: 'ollama',
        url: settings.ollama_url,
      });
      setOllamaResult({ success: res.success, message: res.message, models: res.available_models });
    } catch (err: any) {
      setOllamaResult({ success: false, message: err.message || 'Connection failed' });
    } finally {
      setTestingOllama(false);
    }
  };

  if (loading || !settings) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-12">
        <div className="h-64 rounded-2xl bg-dark-800/40 border border-dark-700/40 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 animate-fade-in">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center">
            <SettingsIcon className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-white">System Settings</h1>
            <p className="text-xs text-slate-400">Configure Sonarr connection, local Ollama AI models, and external APIs</p>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl text-xs font-bold shadow-lg shadow-indigo-600/30 transition-all hover:scale-105"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          <span>{saveSuccess ? 'Saved!' : 'Save Settings'}</span>
        </button>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Sonarr Card */}
        <div className="glass-panel rounded-2xl border border-dark-700 p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-dark-700/80">
            <div className="flex items-center space-x-3">
              <Tv className="w-5 h-5 text-indigo-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Sonarr Integration</h3>
                <p className="text-xs text-slate-400">Canonical series and episode baseline source</p>
              </div>
            </div>

            <button
              type="button"
              onClick={testSonarr}
              disabled={testingSonarr}
              className="px-3 py-1.5 rounded-xl bg-dark-800 hover:bg-dark-700 border border-dark-600 text-xs font-semibold text-slate-300 transition-colors flex items-center space-x-1.5"
            >
              {testingSonarr && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Test Connection</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Sonarr URL</label>
              <input
                type="text"
                value={settings.sonarr_url}
                onChange={e => setSettings({ ...settings, sonarr_url: e.target.value })}
                placeholder="http://localhost:8989"
                className="w-full px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-700 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Sonarr API Key</label>
              <input
                type="password"
                value={settings.sonarr_api_key}
                onChange={e => setSettings({ ...settings, sonarr_api_key: e.target.value })}
                placeholder="Enter API key"
                className="w-full px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-700 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>
          </div>

          {sonarrResult && (
            <div className={`p-3 rounded-xl border text-xs flex items-center space-x-2 ${
              sonarrResult.success
                ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                : 'bg-red-950/30 border-red-500/30 text-red-300'
            }`}>
              {sonarrResult.success ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
              <span>{sonarrResult.message}</span>
            </div>
          )}
        </div>

        {/* Ollama Card */}
        <div className="glass-panel rounded-2xl border border-dark-700 p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-dark-700/80">
            <div className="flex items-center space-x-3">
              <Sparkles className="w-5 h-5 text-indigo-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Local Ollama AI</h3>
                <p className="text-xs text-slate-400">Authoritative LLM decision maker for episode & transcript matching</p>
              </div>
            </div>

            <button
              type="button"
              onClick={testOllama}
              disabled={testingOllama}
              className="px-3 py-1.5 rounded-xl bg-dark-800 hover:bg-dark-700 border border-dark-600 text-xs font-semibold text-slate-300 transition-colors flex items-center space-x-1.5"
            >
              {testingOllama && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Test Ollama</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Ollama Base URL</label>
              <input
                type="text"
                value={settings.ollama_url}
                onChange={e => setSettings({ ...settings, ollama_url: e.target.value })}
                placeholder="http://localhost:11434"
                className="w-full px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-700 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Primary Decision Model</label>
              <input
                type="text"
                value={settings.ollama_primary_model}
                onChange={e => setSettings({ ...settings, ollama_primary_model: e.target.value })}
                placeholder="llama3.1:8b"
                className="w-full px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-700 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>
          </div>

          {ollamaResult && (
            <div className={`p-3 rounded-xl border text-xs space-y-2 ${
              ollamaResult.success
                ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                : 'bg-red-950/30 border-red-500/30 text-red-300'
            }`}>
              <div className="flex items-center space-x-2 font-semibold">
                {ollamaResult.success ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                <span>{ollamaResult.message}</span>
              </div>
              {ollamaResult.models && ollamaResult.models.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {ollamaResult.models.map(m => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setSettings({ ...settings, ollama_primary_model: m })}
                      className="px-2 py-0.5 rounded bg-dark-900 text-slate-200 border border-dark-700 text-[10px] font-mono hover:border-indigo-500 transition-colors"
                    >
                      {m}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Subtitle Sources Card */}
        <div className="glass-panel rounded-2xl border border-dark-700 p-6 space-y-4">
          <div className="pb-3 border-b border-dark-700/80 flex items-center space-x-3">
            <FileText className="w-5 h-5 text-indigo-400" />
            <div>
              <h3 className="text-sm font-bold text-white">Internet Subtitle & Transcript Providers</h3>
              <p className="text-xs text-slate-400">Used for native-language dialogue transcript acquisition</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">OpenSubtitles.com API Key</label>
              <input
                type="password"
                value={settings.opensubtitles_api_key}
                onChange={e => setSettings({ ...settings, opensubtitles_api_key: e.target.value })}
                placeholder="Enter OpenSubtitles API key"
                className="w-full px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-700 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">SubDL API Key</label>
              <input
                type="password"
                value={settings.subdl_api_key}
                onChange={e => setSettings({ ...settings, subdl_api_key: e.target.value })}
                placeholder="Enter SubDL API key"
                className="w-full px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-700 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>
          </div>
        </div>

        {/* External Metadata Sources Card */}
        <div className="glass-panel rounded-2xl border border-dark-700 p-6 space-y-4">
          <div className="pb-3 border-b border-dark-700/80 flex items-center space-x-3">
            <Globe className="w-5 h-5 text-indigo-400" />
            <div>
              <h3 className="text-sm font-bold text-white">External Metadata Providers</h3>
              <p className="text-xs text-slate-400">TMDB, TVmaze (open REST), and OMDb</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">TMDB API Key / Read Token</label>
              <input
                type="password"
                value={settings.tmdb_api_key}
                onChange={e => setSettings({ ...settings, tmdb_api_key: e.target.value })}
                placeholder="Enter TMDB key"
                className="w-full px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-700 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">OMDb (IMDb) API Key</label>
              <input
                type="password"
                value={settings.omdb_api_key}
                onChange={e => setSettings({ ...settings, omdb_api_key: e.target.value })}
                placeholder="Enter OMDb key"
                className="w-full px-3.5 py-2 rounded-xl bg-dark-900 border border-dark-700 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
              />
            </div>
          </div>
        </div>
      </form>
    </div>
  );
};
