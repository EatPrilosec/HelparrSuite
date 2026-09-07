import React from 'react';
import { Database, Activity, Settings, Plus, Layers } from 'lucide-react';

interface NavbarProps {
  currentTab: 'dashboard' | 'activity' | 'settings';
  onSelectTab: (tab: 'dashboard' | 'activity' | 'settings') => void;
  onOpenImport: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentTab, onSelectTab, onOpenImport }) => {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-dark-700/80 bg-dark-900/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-6">
          <div
            onClick={() => onSelectTab('dashboard')}
            className="flex items-center space-x-3 cursor-pointer group select-none"
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shadow-lg shadow-indigo-600/30 group-hover:scale-105 transition-transform">
              <Database className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-white text-lg tracking-tight">DBarr</span>
                <span className="text-[10px] uppercase font-bold tracking-widest px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Port 6781
                </span>
              </div>
              <span className="text-[11px] text-slate-400 font-medium block -mt-0.5">
                HelparrSuite Ground-Truth DB
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center space-x-1 pl-4 border-l border-dark-700/60">
            <button
              onClick={() => onSelectTab('dashboard')}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors ${
                currentTab === 'dashboard'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                  : 'text-slate-300 hover:text-white hover:bg-dark-800/60'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>Library</span>
            </button>

            <button
              onClick={() => onSelectTab('activity')}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors ${
                currentTab === 'activity'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                  : 'text-slate-300 hover:text-white hover:bg-dark-800/60'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Activity</span>
            </button>

            <button
              onClick={() => onSelectTab('settings')}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors ${
                currentTab === 'settings'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                  : 'text-slate-300 hover:text-white hover:bg-dark-800/60'
              }`}
            >
              <Settings className="w-4 h-4" />
              <span>Settings</span>
            </button>
          </nav>
        </div>

        {/* Right Action: Import Button */}
        <div className="flex items-center space-x-3">
          <button
            onClick={onOpenImport}
            className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-bold shadow-lg shadow-indigo-600/30 transition-all hover:scale-105"
          >
            <Plus className="w-4 h-4" />
            <span>Import From Sonarr</span>
          </button>
        </div>
      </div>
    </header>
  );
};
