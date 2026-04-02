export interface RuntimeWindowWithConfig extends Window {
  __UDAKE_API_BASE__?: string;
  Capacitor?: {
    config?: {
      server?: {
        url?: string;
      };
      plugins?: {
        UDAKEConfig?: {
          apiBaseUrl?: string;
        };
      };
    };
  };
}

export interface RequestConfig {
  url: string;
  method?: string;
  body?: BodyInit | null;
  headers?: HeadersInit;
}

export interface HttpLikeError {
  response?: {
    status?: number;
    data?: Record<string, unknown>;
  };
  request?: unknown;
  message?: string;
}

export interface HistoryTimeSeriesRecord {
  timestamp: string;
  value: number;
  point_id?: string;
  x?: number;
  y?: number;
  metadata?: Record<string, unknown>;
}

export interface HistorySnapshotCreatePayload {
  dataset_id: string;
  version_label?: string;
  records: HistoryTimeSeriesRecord[];
  metadata?: Record<string, unknown>;
}

export interface HistorySnapshotMetadata {
  dataset_id: string;
  version: number;
  version_label?: string;
  created_at: string;
  record_count: number;
  compressed: boolean;
  file_name: string;
  metadata: Record<string, unknown>;
}

export interface HistorySnapshotListResponse {
  dataset_id: string;
  total_versions: number;
  versions: HistorySnapshotMetadata[];
}

export interface HistoryComparisonPayload {
  dataset_id: string;
  from_version: number;
  to_version: number;
  heatmap_grid_size?: number;
}

export interface HistoryTrendPayload {
  dataset_id: string;
  version?: number;
  alpha?: number;
  forecast_horizon?: number;
  seasonal_period?: number;
  anomaly_z_threshold?: number;
}

export interface HistoryReportPayload {
  dataset_id: string;
  from_version: number;
  to_version: number;
  forecast_horizon?: number;
}

export interface HistoryExportPayload {
  dataset_id: string;
  format?: 'json' | 'csv';
}

export interface HistoryImportPayload {
  dataset_id: string;
  format?: 'json' | 'csv';
  content: string;
  version_label?: string;
}

export interface HistoryArchivePayload {
  dataset_id: string;
  keep_latest?: number;
}
