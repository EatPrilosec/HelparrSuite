import React, { useState, useEffect, useRef } from 'react';
import { Activity as ActivityIcon, RefreshCw, XCircle, Terminal, ArrowDown, Trash2, CheckCircle2, AlertCircle, Ban, RotateCcw, AlertTriangle } from 'lucide-react';
import { api } from '../services/api';
import { Job } from '../types';

interface ActivityProps {
  initialJobId?: number | null;
}

export const Activity: React.FC<ActivityProps> = ({ initialJobId }) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(initialJobId ?? null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [restartingId, setRestartingId] = useState<number | null>(null);
  const [clearing, setClearing] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isAutoScroll, setIsAutoScroll] = useState(true);

  const logContainerRef = useRef<HTMLDivElement>(null);
  const prevJobIdRef = useRef<number | null>(null);

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 2500);
    return () => clearInterval(interval);
  }, []);

  const loadJobs = async () => {
    try {
      const data = await api.getJobs();
      // Sort jobs strictly:
      // 1. RUNNING jobs at the very top (rank 0)
      // 2. PENDING jobs directly under running jobs (rank 1)
      // 3. Stopped / Finished / Interrupted / Cancelled / Failed jobs at the bottom (rank 2)
      const getStatusRank = (status: string) => {
        if (status === 'RUNNING') return 0;
        if (status === 'PENDING') return 1;
        return 2;
      };

      const sorted = [...data].sort((a, b) => {
        const rankA = getStatusRank(a.status);
        const rankB = getStatusRank(b.status);
        if (rankA !== rankB) return rankA - rankB;
        // Within PENDING: FIFO queue order (lowest ID first so next in line is at top of pending section)
        if (rankA === 1) return a.id - b.id;
        // Within RUNNING and completed/stopped: newest first
        return b.id - a.id;
      });
      setJobs(sorted);

      setSelectedJobId(prevId => {
        // If initialJobId was provided and exists, and prevId is null, use initialJobId
        if (prevId === null && initialJobId && sorted.some(j => j.id === initialJobId)) {
          return initialJobId;
        }
        // If user already has a selected job and it still exists in data, NEVER reset it!
        if (prevId !== null && sorted.some(j => j.id === prevId)) {
          return prevId;
        }
        // Otherwise default to the first available job (active job first)
        return sorted.length > 0 ? sorted[0].id : null;
      });
    } catch (err) {
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async (jobId: number) => {
    setCancellingId(jobId);
    try {
      await api.cancelJob(jobId);
      await loadJobs();
    } catch (err: any) {
      alert(err.message || 'Failed to cancel job');
    } finally {
      setCancellingId(null);
    }
  };

  const handleClearJobs = async (status?: string) => {
    setClearing(status || 'all');
    try {
      await api.clearJobs(status);
      await loadJobs();
    } catch (err: any) {
      alert(err.message || 'Failed to clear jobs');
    } finally {
      setClearing(null);
    }
  };

  const handleDeleteJob = async (jobId: number) => {
    setDeletingId(jobId);
    try {
      await api.deleteJob(jobId);
      if (selectedJobId === jobId) {
        setSelectedJobId(null);
      }
      await loadJobs();
    } catch (err: any) {
      alert(err.message || 'Failed to delete job');
    } finally {
      setDeletingId(null);
    }
  };

  const handleRestart = async (jobId: number) => {
    setRestartingId(jobId);
    try {
      await api.restartJob(jobId);
      await loadJobs();
    } catch (err: any) {
      alert(err.message || 'Failed to restart job');
    } finally {
      setRestartingId(null);
    }
  };

  const handleSelectJob = (jobId: number) => {
    setSelectedJobId(jobId);
    setIsAutoScroll(true);
  };

  const selectedJob = jobs.find(j => j.id === selectedJobId) || (jobs.length > 0 ? jobs[0] : null);

  // When selected job changes, scroll console to bottom and re-engage auto-scroll
  useEffect(() => {
    if (selectedJobId !== null && selectedJobId !== prevJobIdRef.current) {
      prevJobIdRef.current = selectedJobId;
      setIsAutoScroll(true);
      if (logContainerRef.current) {
        logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
      }
    }
  }, [selectedJobId]);

  // When logs update for selected job, only auto-scroll if user is pinned to the bottom
  useEffect(() => {
    if (isAutoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [selectedJob?.logs, isAutoScroll]);

  const handleConsoleScroll = () => {
    if (!logContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current;
    // User is considered at the bottom if within 60px
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 60;
    setIsAutoScroll(isAtBottom);
  };

  const scrollToBottom = () => {
    setIsAutoScroll(true);
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  };

  const completedCount = jobs.filter(j => j.status === 'COMPLETED').length;
  const failedCount = jobs.filter(j => j.status === 'FAILED').length;
  const cancelledCount = jobs.filter(j => j.status === 'CANCELLED').length;
  const interruptedCount = jobs.filter(j => j.status === 'INTERRUPTED').length;
  const totalInactiveCount = completedCount + failedCount + cancelledCount + interruptedCount;

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-fade-in flex flex-col h-[calc(100vh-80px)]">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6 flex-shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center">
            <ActivityIcon className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-white">Activity & Job Queue</h1>
            <p className="text-xs text-slate-400">Monitor background ingestion, transcript fetching, and LLM verification</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Clear Interrupted */}
          {interruptedCount > 0 && (
            <button
              onClick={() => handleClearJobs('interrupted')}
              disabled={clearing !== null}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-amber-950/50 hover:bg-amber-900/60 text-amber-300 border border-amber-800/60 text-xs font-semibold transition-all hover:scale-105 disabled:opacity-50"
              title="Clear all interrupted jobs"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              <span>Clear Interrupted ({interruptedCount})</span>
            </button>
          )}

          {/* Clear Cancelled */}
          {cancelledCount > 0 && (
            <button
              onClick={() => handleClearJobs('cancelled')}
              disabled={clearing !== null}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-semibold transition-all hover:scale-105 disabled:opacity-50"
              title="Clear all cancelled jobs"
            >
              <Ban className="w-3.5 h-3.5 text-slate-400" />
              <span>Clear Cancelled ({cancelledCount})</span>
            </button>
          )}

          {/* Clear Failed */}
          {failedCount > 0 && (
            <button
              onClick={() => handleClearJobs('failed')}
              disabled={clearing !== null}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-rose-950/50 hover:bg-rose-900/60 text-rose-300 border border-rose-800/60 text-xs font-semibold transition-all hover:scale-105 disabled:opacity-50"
              title="Clear all failed jobs"
            >
              <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
              <span>Clear Failed ({failedCount})</span>
            </button>
          )}

          {/* Clear Finished */}
          {completedCount > 0 && (
            <button
              onClick={() => handleClearJobs('completed')}
              disabled={clearing !== null}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-emerald-950/50 hover:bg-emerald-900/60 text-emerald-300 border border-emerald-800/60 text-xs font-semibold transition-all hover:scale-105 disabled:opacity-50"
              title="Clear all completed/finished jobs"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Clear Finished ({completedCount})</span>
            </button>
          )}

          {/* Clear All Inactive */}
          {totalInactiveCount > 1 && (
            <button
              onClick={() => handleClearJobs('all')}
              disabled={clearing !== null}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-dark-800 hover:bg-dark-750 text-slate-300 border border-dark-700 text-xs font-semibold transition-all hover:scale-105 disabled:opacity-50"
              title="Clear all finished, failed, cancelled, and interrupted jobs"
            >
              <Trash2 className="w-3.5 h-3.5 text-slate-400" />
              <span>Clear All ({totalInactiveCount})</span>
            </button>
          )}

          <button
            onClick={loadJobs}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-slate-300 border border-dark-700 text-xs font-semibold transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {loading && jobs.length === 0 ? (
        <div className="space-y-4">
          {[1, 2, 3].map(n => (
            <div key={n} className="h-20 rounded-2xl bg-dark-800/40 border border-dark-700/40 animate-pulse" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-20 rounded-2xl border border-dark-700/60 bg-dark-900/40 p-8 text-slate-400 text-xs">
          No background tasks have been queued yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
          {/* Job List: Independently scrollable container */}
          <div className="lg:col-span-1 flex flex-col h-full min-h-0 overflow-hidden glass-panel rounded-2xl border border-dark-700/80 p-4">
            <div className="flex items-center justify-between pb-3 px-1 text-[11px] font-semibold text-slate-400 flex-shrink-0 border-b border-dark-700/60 mb-3">
              <span>Job Queue ({jobs.length})</span>
              {jobs.some(j => ['RUNNING', 'PENDING'].includes(j.status)) && (
                <span className="flex items-center space-x-1.5 text-indigo-400 font-mono text-[10px]">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                  <span>Active Tasks</span>
                </span>
              )}
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {jobs.map(job => {
                const isSelected = selectedJob?.id === job.id;
                const isRunning = job.status === 'RUNNING';
                const isPending = job.status === 'PENDING';
                return (
                  <div
                    key={job.id}
                    onClick={() => handleSelectJob(job.id)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-dark-800 border-indigo-500 shadow-lg shadow-indigo-950/40 ring-1 ring-indigo-500/50'
                        : isRunning
                        ? 'bg-dark-850/90 border-indigo-500/50 hover:border-indigo-500/80 hover:bg-dark-800/60'
                        : isPending
                        ? 'bg-dark-850/90 border-amber-500/40 hover:border-amber-500/70 hover:bg-dark-800/60'
                        : 'bg-dark-850/80 border-dark-700/80 hover:border-dark-600 hover:bg-dark-800/50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-dark-900 text-indigo-300 border border-dark-700">
                          {job.job_type}
                        </span>
                        {isRunning && (
                          <span className="flex items-center space-x-1 text-[10px] text-indigo-400 font-mono">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                            <span>Running</span>
                          </span>
                        )}
                        {isPending && (
                          <span className="flex items-center space-x-1 text-[10px] text-amber-400 font-mono">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                            <span>Pending</span>
                          </span>
                        )}
                        {job.status === 'INTERRUPTED' && (
                          <span className="flex items-center space-x-1 text-[10px] text-amber-400 font-mono">
                            <AlertTriangle className="w-3 h-3 text-amber-400" />
                            <span>Interrupted</span>
                          </span>
                        )}
                        {job.status === 'CANCELLED' && (
                          <span className="flex items-center space-x-1 text-[10px] text-slate-400 font-mono">
                            <Ban className="w-3 h-3 text-slate-400" />
                            <span>Cancelled</span>
                          </span>
                        )}
                        {job.status === 'FAILED' && (
                          <span className="flex items-center space-x-1 text-[10px] text-rose-400 font-mono">
                            <AlertCircle className="w-3 h-3 text-rose-400" />
                            <span>Failed</span>
                          </span>
                        )}
                        {job.status === 'COMPLETED' && (
                          <span className="flex items-center space-x-1 text-[10px] text-emerald-400 font-mono">
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                            <span>Completed</span>
                          </span>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-[10px] text-slate-500 font-mono">
                          #{job.id}
                        </span>
                        {['COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED'].includes(job.status) && (
                          <div className="flex items-center space-x-1">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRestart(job.id);
                              }}
                              disabled={restartingId === job.id}
                              className="p-1 rounded text-slate-500 hover:text-indigo-300 hover:bg-indigo-500/10 transition-colors"
                              title="Restart this job"
                            >
                              <RotateCcw className={`w-3 h-3 ${restartingId === job.id ? 'animate-spin' : ''}`} />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteJob(job.id);
                              }}
                              disabled={deletingId === job.id}
                              className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                              title="Delete this job"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    <p className="text-xs font-semibold text-white truncate mb-2">
                      {job.message || 'Processing task...'}
                    </p>

                    {/* Progress bar */}
                    <div className="w-full bg-dark-950 rounded-full h-1.5 overflow-hidden mb-2">
                      <div
                        className={`h-full transition-all duration-300 ${
                          job.status === 'COMPLETED'
                            ? 'bg-emerald-500'
                            : job.status === 'FAILED'
                            ? 'bg-red-500'
                            : ['CANCELLED', 'INTERRUPTED'].includes(job.status)
                            ? 'bg-slate-500'
                            : 'bg-indigo-500'
                        }`}
                        style={{ width: `${job.progress}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-slate-400">
                      <span className="font-mono">{Math.round(job.progress)}%</span>
                      <span className="uppercase font-bold tracking-wider">
                        {job.status}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Job Details & Terminal Log Console */}
          <div className="lg:col-span-2 h-full min-h-0 overflow-hidden">
            {selectedJob ? (
              <div className="glass-panel rounded-2xl border border-dark-700 p-6 flex flex-col h-full min-h-0">
                <div className="flex items-center justify-between pb-4 border-b border-dark-700/80 mb-4 flex-shrink-0">
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="text-sm font-bold text-white">
                        Job #{selectedJob.id}: {selectedJob.job_type}
                      </h3>
                      <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${
                        selectedJob.status === 'COMPLETED'
                          ? 'bg-emerald-950/50 text-emerald-300 border-emerald-800/60'
                          : selectedJob.status === 'FAILED'
                          ? 'bg-rose-950/50 text-rose-300 border-rose-800/60'
                          : selectedJob.status === 'INTERRUPTED'
                          ? 'bg-amber-950/50 text-amber-300 border-amber-800/60'
                          : selectedJob.status === 'CANCELLED'
                          ? 'bg-slate-800 text-slate-300 border-slate-700'
                          : 'bg-indigo-950/50 text-indigo-300 border-indigo-800/60'
                      }`}>
                        {selectedJob.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">{selectedJob.message}</p>
                  </div>

                  <div className="flex items-center space-x-2">
                    {['PENDING', 'RUNNING'].includes(selectedJob.status) && (
                      <button
                        onClick={() => handleCancel(selectedJob.id)}
                        disabled={cancellingId === selectedJob.id}
                        className="px-3 py-1.5 rounded-xl bg-red-600/20 hover:bg-red-600 text-red-300 hover:text-white border border-red-500/30 text-xs font-semibold transition-colors flex items-center space-x-1.5"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Cancel Task</span>
                      </button>
                    )}

                    {['COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED'].includes(selectedJob.status) && (
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleRestart(selectedJob.id)}
                          disabled={restartingId === selectedJob.id}
                          className="px-3 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-xs font-semibold transition-colors flex items-center space-x-1.5"
                          title="Restart or resume this task"
                        >
                          <RotateCcw className={`w-3.5 h-3.5 ${restartingId === selectedJob.id ? 'animate-spin' : ''}`} />
                          <span>Restart Task</span>
                        </button>

                        <button
                          onClick={() => handleDeleteJob(selectedJob.id)}
                          disabled={deletingId === selectedJob.id}
                          className="px-3 py-1.5 rounded-xl bg-dark-800 hover:bg-rose-900/40 text-slate-300 hover:text-rose-200 border border-dark-700 hover:border-rose-700/50 text-xs font-semibold transition-colors flex items-center space-x-1.5"
                          title="Delete this job from history"
                        >
                          <Trash2 className="w-3.5 h-3.5 text-slate-400 hover:text-rose-400" />
                          <span>Delete Job</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Console */}
                <div
                  className="flex-1 bg-dark-950 rounded-xl border border-dark-800 p-4 font-mono text-xs overflow-y-auto flex flex-col min-h-0"
                  ref={logContainerRef}
                  onScroll={handleConsoleScroll}
                >
                  <div className="flex items-center justify-between text-slate-500 mb-2 pb-2 border-b border-dark-850 flex-shrink-0">
                    <div className="flex items-center space-x-2">
                      <Terminal className="w-3.5 h-3.5 text-slate-400" />
                      <span className="font-sans text-xs font-medium text-slate-400">Real-Time Execution Logs</span>
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        type="button"
                        onClick={scrollToBottom}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold flex items-center space-x-1.5 transition-colors ${
                          isAutoScroll
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            : 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600 hover:text-white cursor-pointer'
                        }`}
                        title={isAutoScroll ? 'Auto-scroll is active' : 'Click to jump to latest logs and resume auto-scroll'}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${isAutoScroll ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
                        <span>{isAutoScroll ? 'Live Auto-Scroll' : 'Jump to Latest (Paused)'}</span>
                        {!isAutoScroll && <ArrowDown className="w-3 h-3" />}
                      </button>
                    </div>
                  </div>

                  <div className="flex-1 text-slate-300 whitespace-pre-wrap leading-relaxed">
                    {selectedJob.logs || 'No logs recorded yet.'}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};
