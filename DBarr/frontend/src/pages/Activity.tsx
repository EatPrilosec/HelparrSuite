import React, { useState, useEffect, useRef } from 'react';
import { Activity as ActivityIcon, RefreshCw, XCircle, Terminal, ArrowDown } from 'lucide-react';
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
      setJobs(data);

      setSelectedJobId(prevId => {
        // If initialJobId was provided and exists, and prevId is null, use initialJobId
        if (prevId === null && initialJobId && data.some(j => j.id === initialJobId)) {
          return initialJobId;
        }
        // If user already has a selected job and it still exists in data, NEVER reset it!
        if (prevId !== null && data.some(j => j.id === prevId)) {
          return prevId;
        }
        // Otherwise default to the first available job
        return data.length > 0 ? data[0].id : null;
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

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-fade-in">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center">
            <ActivityIcon className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-white">Activity & Job Queue</h1>
            <p className="text-xs text-slate-400">Monitor background ingestion, transcript fetching, and LLM verification</p>
          </div>
        </div>

        <button
          onClick={loadJobs}
          className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-slate-300 border border-dark-700 text-xs font-semibold transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {loading ? (
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Job List */}
          <div className="lg:col-span-1 space-y-3">
            {jobs.map(job => {
              const isSelected = selectedJob?.id === job.id;
              return (
                <div
                  key={job.id}
                  onClick={() => handleSelectJob(job.id)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-dark-800 border-indigo-500 shadow-lg shadow-indigo-950/40 ring-1 ring-indigo-500/50'
                      : 'bg-dark-850/80 border-dark-700/80 hover:border-dark-600 hover:bg-dark-800/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-dark-900 text-indigo-300 border border-dark-700">
                      {job.job_type}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      #{job.id}
                    </span>
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
                          : job.status === 'CANCELLED'
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

          {/* Job Details & Terminal Log Console */}
          <div className="lg:col-span-2">
            {selectedJob ? (
              <div className="glass-panel rounded-2xl border border-dark-700 p-6 flex flex-col h-[600px]">
                <div className="flex items-center justify-between pb-4 border-b border-dark-700/80 mb-4">
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="text-sm font-bold text-white">
                        Job #{selectedJob.id}: {selectedJob.job_type}
                      </h3>
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-dark-800 text-slate-300">
                        {selectedJob.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">{selectedJob.message}</p>
                  </div>

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
                </div>

                {/* Console */}
                <div
                  className="flex-1 bg-dark-950 rounded-xl border border-dark-800 p-4 font-mono text-xs overflow-y-auto flex flex-col"
                  ref={logContainerRef}
                  onScroll={handleConsoleScroll}
                >
                  <div className="flex items-center justify-between text-slate-500 mb-2 pb-2 border-b border-dark-850">
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
