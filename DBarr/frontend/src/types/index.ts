export interface Transcript {
  id: number;
  episode_id: number;
  language: string;
  is_native_language: boolean;
  source_provider: string;
  preview_text?: string;
  raw_content?: string;
  dialogue_anchors?: string;
  created_at: string;
}

export interface EpisodeSourceMetadata {
  id: number;
  episode_id: number;
  show_id: number;
  source_name: string;
  source_season_number?: number;
  source_episode_number?: number;
  source_absolute_number?: number;
  title?: string;
  alternate_titles?: string;
  overview?: string;
  air_date?: string;
  runtime_mins?: number;
  match_method: string;
  match_confidence: number;
  llm_reasoning?: string;
}

export interface Episode {
  id: number;
  show_id: number;
  sonarr_episode_id: number;
  season_number: number;
  episode_number: number;
  absolute_episode_number?: number;
  title: string;
  overview?: string;
  air_date?: string;
  runtime_mins?: number;
  has_file: boolean;
  monitored: boolean;
  ai_verification_status: string;
  ai_confidence_score: number;
  ai_audit_notes?: string;
  transcripts: Transcript[];
  source_variations: EpisodeSourceMetadata[];
  created_at: string;
  updated_at: string;
}

export interface Show {
  id: number;
  sonarr_series_id: number;
  title: string;
  clean_title?: string;
  sort_title?: string;
  original_title?: string;
  year?: number;
  status?: string;
  overview?: string;
  poster_url?: string;
  original_language?: string;
  path?: string;
  monitored: boolean;
  tvdb_id?: number;
  tmdb_id?: number;
  imdb_id?: string;
  tvmaze_id?: number;
  audit_status: string;
  last_audited_at?: string;
  created_at: string;
  updated_at: string;
  episodes?: Episode[];
}

export interface ShowBrief {
  id: number;
  sonarr_series_id: number;
  title: string;
  year?: number;
  status?: string;
  poster_url?: string;
  original_language?: string;
  audit_status: string;
  monitored: boolean;
  tvdb_id?: number;
  tmdb_id?: number;
  imdb_id?: string;
  tvmaze_id?: number;
  episode_count: number;
  verified_episode_count: number;
  created_at: string;
  updated_at: string;
}

export interface SonarrShowLookup {
  sonarr_series_id: number;
  title: string;
  sort_title?: string;
  year?: number;
  status?: string;
  overview?: string;
  poster_url?: string;
  original_language?: string;
  season_count: number;
  episode_count: number;
  monitored: boolean;
  tvdb_id?: number;
  tmdb_id?: number;
  imdb_id?: string;
  path?: string;
  already_imported: boolean;
}

export interface Job {
  id: number;
  show_id?: number;
  job_type: string;
  status: string;
  progress: number;
  message?: string;
  logs?: string;
  created_at: string;
  updated_at: string;
  finished_at?: string;
}

export interface AppSettings {
  ollama_url: string;
  ollama_primary_model: string;
  ollama_fallback_models: string[];
  ollama_fallback_model: string;
  ai_batch_size: number;
  sonarr_url: string;
  sonarr_api_key: string;
  tmdb_api_key: string;
  tvmaze_api_key: string;
  omdb_api_key: string;
  subdl_api_key: string;
  opensubtitles_api_key: string;
  opensubtitles_user_agent: string;
  max_concurrent_jobs: number;
  max_concurrent_ollama_requests: number;
  default_language: string;
}

export interface ConnectionTestResponse {
  service: string;
  success: boolean;
  message: string;
  available_models?: string[];
  details?: any;
}
