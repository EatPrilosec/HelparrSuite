import React from 'react';
import { ShieldCheck, Sparkles, AlertTriangle, Clock, HelpCircle } from 'lucide-react';

interface StatusBadgeProps {
  status: string;
  confidence?: number;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, confidence }) => {
  const norm = (status || 'NOT_AUDITED').toUpperCase();

  switch (norm) {
    case 'VERIFIED':
    case 'PASSED':
    case 'EXACT_MATCH':
      return (
        <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Verified</span>
          {confidence !== undefined && confidence > 0 && (
            <span className="text-[10px] text-emerald-300 font-mono">({Math.round(confidence * 100)}%)</span>
          )}
        </span>
      );

    case 'AI_MATCHED':
      return (
        <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
          <Sparkles className="w-3.5 h-3.5" />
          <span>LLM Confirmed</span>
          {confidence !== undefined && confidence > 0 && (
            <span className="text-[10px] text-indigo-300 font-mono">({Math.round(confidence * 100)}%)</span>
          )}
        </span>
      );

    case 'FLAGGED_MISMATCH':
    case 'HAS_WARNINGS':
    case 'FAILED':
      return (
        <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>Flagged</span>
        </span>
      );

    case 'PENDING':
      return (
        <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-500/15 text-sky-400 border border-sky-500/30">
          <Clock className="w-3.5 h-3.5" />
          <span>Pending</span>
        </span>
      );

    default:
      return (
        <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/15 text-slate-400 border border-slate-600/30">
          <HelpCircle className="w-3.5 h-3.5" />
          <span>Not Audited</span>
        </span>
      );
  }
};
