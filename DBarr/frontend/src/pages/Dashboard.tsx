import React, { useState, useEffect } from 'react';
import { Database, Plus, RefreshCw, Trash2, ArrowRight, Layers, Sparkles } from 'lucide-react';
import { api } from '../services/api';
import { ShowBrief } from '../types';
import { StatusBadge } from '../components/StatusBadge';

interface DashboardProps {
  onSelectShow: (showId: number) => void;
  onOpenImport: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onSelectShow, onOpenImport }) => {
  const [shows, setShows] = useState<ShowBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    loadShows();
  }, []);

  const loadShows = async () => {
    setLoading(true);
    try {
      const data = await api.getShows();
      setShows(data);
    } catch (err) {
      console.error('Failed to load shows:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, showId: number, title: string) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to remove '${title}' and its verified database entries from DBarr?`)) return;
    setDeletingId(showId);
    try {
      await api.deleteShow(showId);
      setShows(shows.filter(s => s.id !== showId));
    } catch (err: any) {
      alert(err.message || 'Failed to delete show');
    } finally {
      setDeletingId(null);
    }
  };

  const totalEpisodes = shows.reduce((acc, s) => acc + s.episode_count, 0);
  const verifiedEpisodes = shows.reduce((acc, s) => acc + s.verified_episode_count, 0);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-fade-in">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-950/70 via-dark-800 to-dark-900 border border-indigo-500/20 p-8 mb-8 shadow-xl">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-4">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Authoritative Ground-Truth Media Database</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            Episode Intelligence & Subtitle Vault
          </h1>
          <p className="text-slate-300 mt-2 text-xs sm:text-sm leading-relaxed">
            DBarr crawls Sonarr, internet subtitle repositories, and external metadata providers to build a 100% verified database of transcripts, alternate numberings, and identifiable dialogue anchors using local Ollama LLMs.
          </p>
          <div className="mt-6 flex items-center space-x-3">
            <button
              onClick={onOpenImport}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-xl text-xs font-bold shadow-lg shadow-indigo-600/30 transition-all hover:scale-105 flex items-center space-x-2"
            >
              <Plus className="w-4 h-4" />
              <span>Import From Sonarr</span>
            </button>
            <button
              onClick={loadShows}
              className="bg-dark-700/80 hover:bg-dark-700 text-slate-200 px-4 py-2.5 rounded-xl text-xs font-semibold border border-dark-600 transition-colors flex items-center space-x-2"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Quick Stats Overlay */}
        <div className="hidden lg:grid absolute right-8 top-1/2 -translate-y-1/2 grid-cols-2 gap-4 w-72">
          <div className="p-4 rounded-xl bg-dark-900/80 border border-dark-700/60 backdrop-blur-md">
            <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">Shows Ingested</span>
            <span className="text-2xl font-black text-white mt-1 block">{shows.length}</span>
          </div>
          <div className="p-4 rounded-xl bg-dark-900/80 border border-dark-700/60 backdrop-blur-md">
            <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">Verified / Total</span>
            <span className="text-2xl font-black text-indigo-400 mt-1 block">{verifiedEpisodes}/{totalEpisodes}</span>
          </div>
        </div>
      </div>

      {/* Shows Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-indigo-400" />
            <h2 className="text-base font-bold text-white">Ingested Media Library ({shows.length})</h2>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map(n => (
              <div key={n} className="h-72 rounded-2xl bg-dark-800/40 border border-dark-700/40 animate-pulse" />
            ))}
          </div>
        ) : shows.length === 0 ? (
          <div className="text-center py-20 rounded-2xl border border-dark-700/60 bg-dark-900/40 p-8 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center mx-auto">
              <Database className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">No Shows Added Yet</h3>
              <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                Connect your Sonarr instance in Settings, then click &quot;Import From Sonarr&quot; to begin building your verified episode database.
              </p>
            </div>
            <button
              onClick={onOpenImport}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2 rounded-xl text-xs font-bold shadow-lg shadow-indigo-600/30 transition-all inline-flex items-center space-x-2"
            >
              <Plus className="w-4 h-4" />
              <span>Import First Show</span>
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {shows.map(s => (
              <div
                key={s.id}
                onClick={() => onSelectShow(s.id)}
                className="glass-card rounded-2xl overflow-hidden border border-dark-700/80 hover:border-indigo-500/50 transition-all cursor-pointer group flex flex-col justify-between"
              >
                <div>
                  {/* Poster Art */}
                  <div className="relative aspect-[16/9] sm:aspect-[3/4] w-full overflow-hidden bg-dark-850">
                    {s.poster_url ? (
                      <img
                        src={s.poster_url}
                        alt={s.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-slate-600 text-xs font-semibold">
                        No Poster Art
                      </div>
                    )}

                    {/* Original Language Badge */}
                    {s.original_language && (
                      <div className="absolute top-3 left-3 px-2 py-0.5 rounded-md bg-dark-900/85 backdrop-blur-md border border-dark-700 text-indigo-300 text-[10px] font-mono font-bold">
                        {s.original_language}
                      </div>
                    )}

                    {/* Delete button */}
                    <button
                      onClick={e => handleDelete(e, s.id, s.title)}
                      disabled={deletingId === s.id}
                      className="absolute top-3 right-3 p-1.5 rounded-md bg-dark-900/80 hover:bg-red-600 text-slate-400 hover:text-white transition-colors opacity-0 group-hover:opacity-100"
                      title="Delete show"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Body info */}
                  <div className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-white truncate group-hover:text-indigo-400 transition-colors">
                        {s.title}
                      </h3>
                      {s.year && <span className="text-xs text-slate-400 font-mono">({s.year})</span>}
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <StatusBadge status={s.audit_status} />
                      <span className="text-[11px] text-slate-400 font-mono">
                        {s.episode_count} Episodes
                      </span>
                    </div>
                  </div>
                </div>

                {/* Footer link */}
                <div className="px-4 py-3 border-t border-dark-700/60 bg-dark-900/40 flex items-center justify-between text-xs text-slate-400 group-hover:text-indigo-300 transition-colors">
                  <span className="text-[11px] font-medium">Inspect Episodes & Vault</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
