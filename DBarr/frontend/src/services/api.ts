import { Show, ShowBrief, SonarrShowLookup, Job, AppSettings, ConnectionTestResponse } from '../types';

const API_BASE = '/api/v1';

export const api = {
  // Shows
  async getShows(): Promise<ShowBrief[]> {
    const res = await fetch(`${API_BASE}/shows`);
    if (!res.ok) throw new Error('Failed to fetch shows');
    return res.json();
  },

  async getShow(id: number): Promise<Show> {
    const res = await fetch(`${API_BASE}/shows/${id}`);
    if (!res.ok) throw new Error('Failed to fetch show details');
    return res.json();
  },

  async deleteShow(id: number): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/shows/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete show');
    return res.json();
  },

  async lookupSonarrShows(): Promise<SonarrShowLookup[]> {
    const res = await fetch(`${API_BASE}/shows/lookup/sonarr`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Sonarr lookup failed' }));
      throw new Error(err.detail || 'Failed to fetch series from Sonarr');
    }
    return res.json();
  },

  async importShow(sonarrSeriesId: number, scanMode: string = 'full'): Promise<{ success: boolean; job_id: number; message: string }> {
    const res = await fetch(`${API_BASE}/shows/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sonarr_series_id: sonarrSeriesId, scan_mode: scanMode }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Import failed' }));
      throw new Error(err.detail || 'Failed to import show');
    }
    return res.json();
  },

  async importShowsBatch(seriesIds: number[], scanMode: string = 'full'): Promise<{ success: boolean; job_ids: number[]; count: number; message: string }> {
    const res = await fetch(`${API_BASE}/shows/import-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ series_ids: seriesIds, scan_mode: scanMode }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Batch import failed' }));
      throw new Error(err.detail || 'Failed to batch import shows');
    }
    return res.json();
  },

  async auditShow(showId: number): Promise<{ success: boolean; job_id: number; message: string }> {
    const res = await fetch(`${API_BASE}/shows/${showId}/audit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to queue audit' }));
      throw new Error(err.detail || 'Failed to queue audit');
    }
    return res.json();
  },

  // Jobs
  async getJobs(): Promise<Job[]> {
    const res = await fetch(`${API_BASE}/jobs`);
    if (!res.ok) throw new Error('Failed to fetch jobs');
    return res.json();
  },

  async getJob(id: number): Promise<Job> {
    const res = await fetch(`${API_BASE}/jobs/${id}`);
    if (!res.ok) throw new Error('Failed to fetch job');
    return res.json();
  },

  async cancelJob(id: number): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/jobs/${id}/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to cancel job');
    return res.json();
  },

  // Settings
  async getSettings(): Promise<AppSettings> {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) throw new Error('Failed to fetch settings');
    return res.json();
  },

  async updateSettings(settings: Partial<AppSettings>): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings }),
    });
    if (!res.ok) throw new Error('Failed to update settings');
    return res.json();
  },

  async testConnection(service: string, config: any): Promise<ConnectionTestResponse> {
    const res = await fetch(`${API_BASE}/settings/test-connection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service, config }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Connection test failed' }));
      throw new Error(err.detail || 'Connection test failed');
    }
    return res.json();
  },
};
