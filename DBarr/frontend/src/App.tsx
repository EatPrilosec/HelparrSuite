import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Dashboard } from './pages/Dashboard';
import { ShowDetail } from './pages/ShowDetail';
import { Activity } from './pages/Activity';
import { Settings } from './pages/Settings';
import { ImportModal } from './components/ImportModal';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'dashboard' | 'activity' | 'settings'>('dashboard');
  const [selectedShowId, setSelectedShowId] = useState<number | null>(null);
  const [isImportOpen, setIsImportOpen] = useState(false);

  const [activeJobId, setActiveJobId] = useState<number | null>(null);

  const handleSelectShow = (showId: number) => {
    setSelectedShowId(showId);
  };

  const handleBackToLibrary = () => {
    setSelectedShowId(null);
    setCurrentTab('dashboard');
  };

  const handleImportStarted = (jobIds: number[]) => {
    if (jobIds && jobIds.length > 0) {
      setActiveJobId(jobIds[0]);
    }
    // Navigate user to activity tab to view jobs in real-time
    setCurrentTab('activity');
  };

  return (
    <div className="min-h-screen bg-[#070a11] text-slate-100 flex flex-col font-sans">
      <Navbar
        currentTab={selectedShowId ? 'dashboard' : currentTab}
        onSelectTab={tab => {
          setSelectedShowId(null);
          setCurrentTab(tab);
        }}
        onOpenImport={() => setIsImportOpen(true)}
      />

      <main className="flex-1 pb-16">
        {selectedShowId ? (
          <ShowDetail
            showId={selectedShowId}
            onBack={handleBackToLibrary}
            onJobStarted={handleImportStarted}
          />
        ) : currentTab === 'dashboard' ? (
          <Dashboard
            onSelectShow={handleSelectShow}
            onOpenImport={() => setIsImportOpen(true)}
          />
        ) : currentTab === 'activity' ? (
          <Activity initialJobId={activeJobId} />
        ) : (
          <Settings />
        )}
      </main>

      <ImportModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onImportStarted={handleImportStarted}
      />
    </div>
  );
};
