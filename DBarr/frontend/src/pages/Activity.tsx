import React, { useState, useEffect, useRef } from 'react';
import { Activity as ActivityIcon, RefreshCw, XCircle, Terminal } from 'lucide-react';
import { api } from '../services/api';
import { Job } from '../types';

export const Activity: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 2500);
    return () => clearInterval(interval);
  }, []);

  const loadJobs = async () => {
    try {
      const data = await api.getJobs();
      setJobs(data);
      if (data.length > 0 && selectedJobId === null) {
        setSelectedJobId(data[0].id);
      }
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
      loadJobs();
    } catch (err: any) {
      alert(err.message || 'Failed to cancel job');
    } finally {
      setCancellingId(null);
    }
  };

  const selectedJob = jobs.find(j => j.id === selectedJobId) || jobs[0];

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [selectedJob?.logs]);

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
                  onClick={() => setSelectedJobId(job.id)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-dark-800 border-indigo-500 shadow-lg shadow-indigo-950/40'
                      : 'bg-dark-850/80 border-dark-700/80 hover:border-dark-600'
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
                <div className="flex-1 bg-dark-950 rounded-xl border border-dark-800 p-4 font-mono text-xs overflow-y-auto flex flex-col" ref={logContainerRef}>
                  <div className="flex items-center space-x-2 text-slate-500 mb-2 pb-2 border-b border-dark-850">
                    <Terminal className="w-3.5 h-3.5" />
                    <span>Real-Time Execution Logs</span>
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
