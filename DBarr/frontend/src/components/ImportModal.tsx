import React, { useState, useEffect } from 'react';
import { X, Search, Loader2, AlertCircle, CheckSquare, Square, Check, Tv, Filter } from 'lucide-react';
import { api } from '../services/api';
import { SonarrShowLookup } from '../types';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportStarted: (jobIds: number[]) => void;
}

export const ImportModal: React.FC<ImportModalProps> = ({ isOpen, onClose, onImportStarted }) => {
  const [shows, setShows] = useState<SonarrShowLookup[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filterMonitoredOnly, setFilterMonitoredOnly] = useState(false);
  const [filterHideImported, setFilterHideImported] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadSonarrShows();
      setSelectedIds(new Set());
    }
  }, [isOpen]);

  const loadSonarrShows = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.lookupSonarrShows();
      setShows(data);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to Sonarr. Please check Settings.');
    } finally {
      setLoading(false);
    }
  };

  // Filter shows based on search and toggles
  const filteredShows = shows.filter(s => {
    const matchesSearch = s.title.toLowerCase().includes(search.toLowerCase());
    const matchesMonitored = !filterMonitoredOnly || s.monitored;
    const matchesImported = !filterHideImported || !s.already_imported;
    return matchesSearch && matchesMonitored && matchesImported;
  });

  const toggleSelectOne = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAllFiltered = () => {
    const unimportedFiltered = filteredShows.filter(s => !s.already_imported);
    setSelectedIds(new Set(unimportedFiltered.map(s => s.sonarr_series_id)));
  };

  const clearSelection = () => {
    setSelectedIds(new Set());
  };

  const handleSingleImport = async (id: number) => {
    setImporting(true);
    try {
      const res = await api.importShow(id);
      onImportStarted([res.job_id]);
      onClose();
    } catch (err: any) {
      alert(err.message || 'Failed to import show');
    } finally {
      setImporting(false);
    }
  };

  const handleBatchImport = async () => {
    if (selectedIds.size === 0) return;
    setImporting(true);
    try {
      const res = await api.importShowsBatch(Array.from(selectedIds));
      onImportStarted(res.job_ids);
      onClose();
    } catch (err: any) {
      alert(err.message || 'Failed to batch import shows');
    } finally {
      setImporting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
      <div className="bg-dark-900 border border-dark-700 w-full max-w-4xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-dark-700 flex items-center justify-between bg-dark-800/80">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Tv className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Import Shows From Sonarr</h2>
              <p className="text-xs text-slate-400">Select one or multiple shows to add to DBarr</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-dark-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search & Filter Toolbar */}
        <div className="p-4 border-b border-dark-700/80 bg-dark-850 space-y-3">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search series by title..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-dark-900 border border-dark-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            <button
              onClick={() => setFilterMonitoredOnly(!filterMonitoredOnly)}
              className={`flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-semibold border transition-colors ${
                filterMonitoredOnly
                  ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/40'
                  : 'bg-dark-800 text-slate-400 border-dark-700 hover:text-slate-200'
              }`}
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Monitored Only</span>
            </button>

            <button
              onClick={() => setFilterHideImported(!filterHideImported)}
              className={`flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-semibold border transition-colors ${
                filterHideImported
                  ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/40'
                  : 'bg-dark-800 text-slate-400 border-dark-700 hover:text-slate-200'
              }`}
            >
              <span>Hide Added</span>
            </button>
          </div>

          {/* Selection Actions */}
          <div className="flex items-center justify-between text-xs pt-1 text-slate-400">
            <div className="flex items-center space-x-3">
              <button
                onClick={selectAllFiltered}
                className="text-indigo-400 hover:text-indigo-300 font-semibold"
              >
                Select All Filtered ({filteredShows.filter(s => !s.already_imported).length})
              </button>
              <span>•</span>
              <button
                onClick={clearSelection}
                className="text-slate-400 hover:text-slate-300 font-semibold"
              >
                Clear Selection
              </button>
            </div>
            <div>
              <span className="font-semibold text-white">{selectedIds.size}</span> shows selected
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
              <p className="text-xs font-medium">Fetching library from Sonarr...</p>
            </div>
          ) : error ? (
            <div className="p-6 rounded-xl bg-amber-950/30 border border-amber-500/30 text-amber-300 flex items-start space-x-3 text-xs">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <div>
                <strong className="block font-semibold mb-1">Failed to Connect to Sonarr</strong>
                <span>{error}</span>
              </div>
            </div>
          ) : filteredShows.length === 0 ? (
            <div className="text-center py-16 text-slate-500 text-xs">
              No matching shows found in Sonarr library.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredShows.map(s => {
                const isSelected = selectedIds.has(s.sonarr_series_id);
                return (
                  <div
                    key={s.sonarr_series_id}
                    onClick={() => {
                      if (!s.already_imported) toggleSelectOne(s.sonarr_series_id);
                    }}
                    className={`p-3.5 rounded-xl border flex items-start space-x-3 transition-all cursor-pointer ${
                      s.already_imported
                        ? 'bg-dark-850/50 border-dark-800 opacity-60 cursor-not-allowed'
                        : isSelected
                        ? 'bg-indigo-950/30 border-indigo-500/50 shadow-md shadow-indigo-950/50'
                        : 'bg-dark-800/80 border-dark-700/70 hover:border-dark-600'
                    }`}
                  >
                    {/* Checkbox */}
                    <div className="pt-1 flex-shrink-0">
                      {s.already_imported ? (
                        <div className="w-4 h-4 rounded bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                          <Check className="w-3 h-3" />
                        </div>
                      ) : isSelected ? (
                        <CheckSquare className="w-4 h-4 text-indigo-400" />
                      ) : (
                        <Square className="w-4 h-4 text-slate-600 hover:text-slate-400" />
                      )}
                    </div>

                    {/* Poster */}
                    {s.poster_url ? (
                      <img
                        src={s.poster_url}
                        alt={s.title}
                        className="w-12 h-18 object-cover rounded-lg border border-dark-700 flex-shrink-0 bg-dark-900"
                      />
                    ) : (
                      <div className="w-12 h-18 rounded-lg bg-dark-900 border border-dark-700 flex items-center justify-center flex-shrink-0 text-slate-600 text-[10px]">
                        No Art
                      </div>
                    )}

                    {/* Show Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <h4 className="text-xs font-bold text-white truncate">{s.title}</h4>
                        {s.year && <span className="text-[11px] text-slate-400">({s.year})</span>}
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                        <span className="px-1.5 py-0.5 rounded bg-dark-700 text-slate-300 text-[10px] font-mono">
                          {s.season_count} Season{s.season_count === 1 ? '' : 's'}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-dark-700 text-slate-300 text-[10px] font-mono">
                          {s.episode_count} Eps
                        </span>
                        {s.original_language && (
                          <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-mono font-medium">
                            {s.original_language}
                          </span>
                        )}
                      </div>

                      {s.already_imported ? (
                        <span className="text-[10px] text-emerald-400 font-semibold block mt-2">
                          Already in DBarr Library
                        </span>
                      ) : (
                        <div className="mt-2 flex items-center justify-between">
                          <span className="text-[10px] text-slate-500 font-mono">ID: {s.sonarr_series_id}</span>
                          <button
                            onClick={e => {
                              e.stopPropagation();
                              handleSingleImport(s.sonarr_series_id);
                            }}
                            className="px-2 py-0.5 rounded bg-indigo-600/30 hover:bg-indigo-600 text-indigo-200 text-[10px] font-semibold border border-indigo-500/40 transition-colors"
                          >
                            Quick Import
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Modal Footer / Batch Action */}
        <div className="px-6 py-3.5 border-t border-dark-700 bg-dark-800/90 flex items-center justify-between">
          <div className="text-xs text-slate-400">
            {selectedIds.size > 0 ? (
              <span>
                Ready to queue <strong className="text-white">{selectedIds.size}</strong> shows for background processing.
              </span>
            ) : (
              <span>Select shows using checkboxes to import in bulk.</span>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-dark-700 transition-colors"
            >
              Cancel
            </button>
            <button
              disabled={selectedIds.size === 0 || importing}
              onClick={handleBatchImport}
              className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-2 rounded-xl text-xs font-bold shadow-lg shadow-indigo-600/30 transition-all"
            >
              {importing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              <span>Import Selected ({selectedIds.size})</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
