import React, { useState, useEffect } from 'react';
import { ArrowLeft, RefreshCw, FileText, ChevronDown, ChevronRight, Layers, Sparkles, X } from 'lucide-react';
import { api } from '../services/api';
import { Show, Transcript } from '../types';
import { StatusBadge } from '../components/StatusBadge';

interface ShowDetailProps {
  showId: number;
  onBack: () => void;
  onJobStarted: (jobIds: number[]) => void;
}

export const ShowDetail: React.FC<ShowDetailProps> = ({ showId, onBack, onJobStarted }) => {
  const [show, setShow] = useState<Show | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
  const [expandedEpisodeId, setExpandedEpisodeId] = useState<number | null>(null);
  const [transcriptModal, setTranscriptModal] = useState<Transcript | null>(null);

  useEffect(() => {
    loadShowDetail();
  }, [showId]);

  const loadShowDetail = async () => {
    setLoading(true);
    try {
      const data = await api.getShow(showId);
      setShow(data);
      if (data.episodes && data.episodes.length > 0 && selectedSeason === null) {
        // Default to first regular season or Season 1
        const seasons = Array.from(new Set(data.episodes.map(e => e.season_number)));
        const firstRegular = seasons.find(s => s > 0) ?? seasons[0];
        setSelectedSeason(firstRegular);
      }
    } catch (err) {
      console.error('Failed to load show detail:', err);
    } finally {
      setLoading(false);
    }
  };

  const [auditing, setAuditing] = useState(false);

  const handleAuditShow = async () => {
    if (!show) return;
    setAuditing(true);
    try {
      const res = await api.auditShow(show.id);
      onJobStarted([res.job_id]);
    } catch (err: any) {
      alert(err.message || 'Failed to start AI audit');
    } finally {
      setAuditing(false);
    }
  };

  const handleRescanShow = async () => {
    if (!show) return;
    try {
      const res = await api.importShow(show.sonarr_series_id);
      onJobStarted([res.job_id]);
    } catch (err: any) {
      alert(err.message || 'Failed to trigger rescan');
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="h-64 rounded-2xl bg-dark-800/40 border border-dark-700/40 animate-pulse mb-8" />
        <div className="space-y-4">
          {[1, 2, 3, 4].map(n => (
            <div key={n} className="h-16 rounded-xl bg-dark-800/30 border border-dark-700/30 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!show) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-16 text-center">
        <p className="text-slate-400 text-sm">Show not found.</p>
        <button
          onClick={onBack}
          className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold"
        >
          Back to Library
        </button>
      </div>
    );
  }

  // Strictly order seasons: 1, 2, ..., N, then Specials (0)
  const rawSeasons = Array.from(new Set(show.episodes?.map(e => e.season_number) || []));
  const sortedSeasons = rawSeasons.sort((a, b) => {
    const aOrder = a === 0 ? 999999 : a;
    const bOrder = b === 0 ? 999999 : b;
    return aOrder - bOrder;
  });

  const currentEpisodes = show.episodes?.filter(e => e.season_number === selectedSeason) || [];

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-fade-in">
      {/* Top Back Navigation */}
      <button
        onClick={onBack}
        className="flex items-center space-x-2 text-slate-400 hover:text-white transition-colors mb-6 text-xs font-semibold"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Library</span>
      </button>

      {/* Show Hero Banner */}
      <div className="glass-panel rounded-2xl p-6 sm:p-8 mb-8 border border-dark-700 shadow-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex items-start sm:items-center space-x-6">
          {show.poster_url ? (
            <img
              src={show.poster_url}
              alt={show.title}
              className="w-24 h-36 object-cover rounded-xl shadow-lg border border-dark-600 flex-shrink-0"
            />
          ) : (
            <div className="w-24 h-36 rounded-xl bg-dark-800 border border-dark-600 flex items-center justify-center text-slate-600 flex-shrink-0 text-xs">
              No Poster
            </div>
          )}

          <div>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white">{show.title}</h1>
              {show.year && <span className="text-base text-slate-400 font-mono">({show.year})</span>}
              <StatusBadge status={show.audit_status} />
              {show.original_language && (
                <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-mono font-semibold">
                  Native: {show.original_language}
                </span>
              )}
            </div>

            <p className="text-xs sm:text-sm text-slate-300 max-w-3xl leading-relaxed line-clamp-2">
              {show.overview || 'No overview provided.'}
            </p>

            <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-slate-400 font-mono">
              <span>Sonarr ID: <strong className="text-slate-200">{show.sonarr_series_id}</strong></span>
              {show.tvdb_id && <span>TVDB: <strong className="text-slate-200">{show.tvdb_id}</strong></span>}
              {show.tmdb_id && <span>TMDB: <strong className="text-slate-200">{show.tmdb_id}</strong></span>}
              {show.imdb_id && <span>IMDb: <strong className="text-slate-200">{show.imdb_id}</strong></span>}
              {show.tvmaze_id && <span>TVmaze: <strong className="text-slate-200">{show.tvmaze_id}</strong></span>}
            </div>
          </div>
        </div>

        {/* Actions: AI Audit & Rescan */}
        <div className="flex-shrink-0 flex items-center gap-3">
          <button
            onClick={handleAuditShow}
            disabled={auditing}
            className="flex items-center space-x-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white px-5 py-2.5 rounded-xl text-xs sm:text-sm font-bold shadow-lg shadow-purple-600/30 transition-all hover:scale-105 disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4 text-purple-200 animate-pulse" />
            <span>{auditing ? 'Starting Audit...' : 'Audit with AI'}</span>
          </button>
          <button
            onClick={handleRescanShow}
            className="flex items-center space-x-2 bg-dark-800 hover:bg-dark-700 text-slate-300 hover:text-white px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold border border-dark-600 transition-all"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Sync Sonarr</span>
          </button>
        </div>
      </div>

      {/* Season Tabs (Strict Order: S1..SN then Specials S0) */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-4 mb-4">
        {sortedSeasons.map(sNum => (
          <button
            key={sNum}
            onClick={() => setSelectedSeason(sNum)}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
              selectedSeason === sNum
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                : 'bg-dark-800 text-slate-400 hover:text-slate-200 hover:bg-dark-700 border border-dark-700'
            }`}
          >
            {sNum === 0 ? 'Specials (Season 0)' : `Season ${sNum}`}
          </button>
        ))}
      </div>

      {/* Episodes List Accordion */}
      <div className="space-y-3">
        {currentEpisodes.length === 0 ? (
          <div className="text-center py-12 text-slate-400 bg-dark-900/40 rounded-2xl border border-dark-700 text-xs">
            No episodes found for this season.
          </div>
        ) : (
          currentEpisodes.map(ep => {
            const isExpanded = expandedEpisodeId === ep.id;
            const primaryTranscript = ep.transcripts && ep.transcripts.length > 0 ? ep.transcripts[0] : null;

            return (
              <div
                key={ep.id}
                className={`rounded-2xl border transition-all overflow-hidden ${
                  isExpanded
                    ? 'bg-dark-850 border-indigo-500/50 shadow-xl'
                    : 'bg-dark-800/70 border-dark-700/80 hover:border-dark-600'
                }`}
              >
                {/* Row Header */}
                <div
                  onClick={() => setExpandedEpisodeId(isExpanded ? null : ep.id)}
                  className="p-4 flex items-center justify-between cursor-pointer select-none"
                >
                  <div className="flex items-center space-x-4">
                    <button className="text-slate-400">
                      {isExpanded ? <ChevronDown className="w-5 h-5 text-indigo-400" /> : <ChevronRight className="w-5 h-5" />}
                    </button>

                    <div className="flex items-center space-x-3">
                      <span className="font-mono text-xs font-bold px-2 py-1 rounded bg-dark-900 border border-dark-700 text-indigo-300">
                        S{String(ep.season_number).padStart(2, '0')}E{String(ep.episode_number).padStart(2, '0')}
                      </span>
                      <h3 className="text-xs sm:text-sm font-bold text-white hover:text-indigo-300 transition-colors">
                        {ep.title}
                      </h3>
                      {ep.air_date && <span className="text-xs text-slate-500 font-mono">{ep.air_date}</span>}
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    {/* Transcript Indicator */}
                    {primaryTranscript ? (
                      <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-semibold">
                        <FileText className="w-3 h-3" />
                        <span>Transcript Vaulted</span>
                      </span>
                    ) : (
                      <span className="text-[10px] text-slate-500 font-mono">
                        No Transcript
                      </span>
                    )}

                    <StatusBadge status={ep.ai_verification_status} confidence={ep.ai_confidence_score} />
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="p-6 border-t border-dark-700 bg-dark-900/60 space-y-6 animate-fade-in">
                    {/* Canonical Sonarr Synopsis */}
                    <div className="p-4 rounded-xl bg-dark-800 border border-dark-700/80">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center space-x-1.5">
                          <Layers className="w-3.5 h-3.5" />
                          <span>Sonarr Canonical Baseline</span>
                        </span>
                        <span className="text-[11px] font-mono text-slate-500">ID: {ep.sonarr_episode_id}</span>
                      </div>
                      <h4 className="text-xs font-bold text-white">{ep.title}</h4>
                      <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                        {ep.overview || 'No synopsis available in Sonarr.'}
                      </p>
                    </div>

                    {/* LLM Audit Notes */}
                    {ep.ai_audit_notes && (
                      <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex items-start space-x-3 text-xs text-indigo-200">
                        <Sparkles className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
                        <div>
                          <strong className="font-semibold block mb-0.5">Ollama LLM Verification Audit:</strong>
                          <span>{ep.ai_audit_notes}</span>
                        </div>
                      </div>
                    )}

                    {/* Transcript Vault Section */}
                    {primaryTranscript ? (
                      <div className="p-4 rounded-xl bg-dark-800 border border-dark-700/80">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center space-x-1.5">
                            <FileText className="w-3.5 h-3.5" />
                            <span>Canonical Spoken Dialogue Transcript</span>
                          </span>
                          <div className="flex items-center space-x-2">
                            <span className="px-2 py-0.5 rounded bg-dark-700 text-slate-300 text-[10px] font-mono">
                              Language: {primaryTranscript.language}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-dark-700 text-slate-300 text-[10px] font-mono">
                              Source: {primaryTranscript.source_provider}
                            </span>
                          </div>
                        </div>

                        <p className="text-xs text-slate-300 font-mono bg-dark-900/80 p-3 rounded-lg border border-dark-700 leading-relaxed mb-2">
                          &quot;{primaryTranscript.preview_text || primaryTranscript.raw_content?.slice(0, 400)}...&quot;
                        </p>

                        <button
                          onClick={() => setTranscriptModal(primaryTranscript)}
                          className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
                        >
                          View Full Dialogue Transcript →
                        </button>
                      </div>
                    ) : null}

                    {/* Source Variations Grid */}
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                        External Source Mappings ({ep.source_variations.length})
                      </h4>

                      {ep.source_variations.length === 0 ? (
                        <p className="text-xs text-slate-500 italic">
                          No external sources mapped yet. Will be ingested during Phase 3 verification.
                        </p>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                          {ep.source_variations.map(source => (
                            <div key={source.id} className="p-4 rounded-xl border bg-dark-800 border-dark-700 text-xs">
                              <div className="flex items-center justify-between mb-2">
                                <span className="px-2 py-0.5 rounded bg-dark-700 text-indigo-300 font-mono uppercase font-bold text-[10px]">
                                  {source.source_name}
                                </span>
                                <span className="text-slate-400 font-mono text-[10px]">
                                  S{source.source_season_number}E{source.source_episode_number}
                                </span>
                              </div>
                              <h5 className="font-bold text-white mb-1">{source.title || 'Untitled'}</h5>
                              <p className="text-slate-400 text-[11px] line-clamp-3 mb-2">{source.overview}</p>
                              {source.llm_reasoning && (
                                <p className="text-[10px] text-indigo-300 bg-indigo-950/40 p-2 rounded border border-indigo-500/20">
                                  {source.llm_reasoning}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Transcript Modal */}
      {transcriptModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="bg-dark-900 border border-dark-700 w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="px-6 py-4 border-b border-dark-700 flex items-center justify-between bg-dark-800">
              <div className="flex items-center space-x-2 text-white font-bold text-sm">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span>Full Spoken Dialogue Transcript</span>
              </div>
              <button
                onClick={() => setTranscriptModal(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 overflow-y-auto font-mono text-xs text-slate-300 leading-relaxed whitespace-pre-wrap bg-dark-950">
              {transcriptModal.raw_content}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
