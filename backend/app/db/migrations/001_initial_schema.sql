CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  dialect TEXT NOT NULL DEFAULT 'gaussdb_dws',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS imports(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  snapshot_json TEXT NOT NULL DEFAULT '{}',
  summary_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(project_id, version)
);

CREATE TABLE IF NOT EXISTS analysis_runs(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  mode TEXT NOT NULL DEFAULT 'zip',
  status TEXT NOT NULL,
  error TEXT NOT NULL DEFAULT '',
  requested_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS import_files(
  id INTEGER PRIMARY KEY,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  logical_name TEXT NOT NULL DEFAULT '',
  relative_path TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT '',
  content_sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE(import_id, relative_path)
);

CREATE TABLE IF NOT EXISTS tables(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  layer TEXT NOT NULL DEFAULT 'OTHER',
  ddl_file TEXT,
  description TEXT NOT NULL DEFAULT '',
  inferred INTEGER NOT NULL DEFAULT 0,
  confidence REAL NOT NULL DEFAULT 0,
  parse_source TEXT NOT NULL DEFAULT '',
  table_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(import_id, name)
);

CREATE TABLE IF NOT EXISTS columns(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  table_name TEXT NOT NULL,
  name TEXT NOT NULL,
  data_type TEXT NOT NULL DEFAULT '',
  column_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(import_id, table_name, name)
);

CREATE TABLE IF NOT EXISTS table_lineage_edges(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  source TEXT NOT NULL,
  target TEXT NOT NULL,
  file TEXT,
  line INTEGER,
  operation TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0,
  parse_source TEXT NOT NULL DEFAULT '',
  UNIQUE(import_id, source, target, file, line)
);

CREATE TABLE IF NOT EXISTS column_lineage_edges(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  source_table TEXT NOT NULL,
  source_column TEXT NOT NULL,
  target_table TEXT NOT NULL,
  target_column TEXT NOT NULL,
  file TEXT,
  line INTEGER,
  confidence REAL NOT NULL DEFAULT 0,
  parse_source TEXT NOT NULL DEFAULT '',
  edge_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(import_id, source_table, source_column, target_table, target_column, file, line)
);

CREATE TABLE IF NOT EXISTS metrics(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  table_name TEXT NOT NULL,
  formula TEXT NOT NULL DEFAULT '',
  grain_json TEXT NOT NULL DEFAULT '[]',
  filter_expr TEXT NOT NULL DEFAULT '',
  file TEXT,
  line INTEGER,
  confidence REAL NOT NULL DEFAULT 0,
  metric_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS quality_findings(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  code TEXT NOT NULL,
  severity TEXT NOT NULL,
  file TEXT,
  object_name TEXT NOT NULL DEFAULT '',
  message TEXT NOT NULL,
  finding_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  job_name TEXT NOT NULL,
  output_table TEXT NOT NULL DEFAULT '',
  schedule TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL DEFAULT '',
  script_path TEXT NOT NULL DEFAULT '',
  job_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(import_id, job_name)
);

CREATE TABLE IF NOT EXISTS job_edges(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  source TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'inferred',
  UNIQUE(import_id, source, target)
);

CREATE TABLE IF NOT EXISTS table_metadata(
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  table_name TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL DEFAULT '',
  update_frequency TEXT NOT NULL DEFAULT '',
  retention TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  modified_at TEXT NOT NULL,
  PRIMARY KEY(project_id, table_name)
);

CREATE TABLE IF NOT EXISTS column_metadata(
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  table_name TEXT NOT NULL,
  column_name TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  business_tag TEXT NOT NULL DEFAULT '',
  modified_at TEXT NOT NULL,
  PRIMARY KEY(project_id, table_name, column_name)
);

CREATE TABLE IF NOT EXISTS metadata_revisions(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  revision INTEGER NOT NULL,
  import_version INTEGER NOT NULL DEFAULT 0,
  summary_json TEXT NOT NULL DEFAULT '{}',
  source TEXT NOT NULL DEFAULT '',
  operator TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE(project_id, revision)
);

CREATE TABLE IF NOT EXISTS table_metadata_revisions(
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  revision_id INTEGER NOT NULL REFERENCES metadata_revisions(id) ON DELETE CASCADE,
  table_name TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT '',
  owner TEXT NOT NULL DEFAULT '',
  update_frequency TEXT NOT NULL DEFAULT '',
  retention TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(project_id, revision_id, table_name)
);

CREATE TABLE IF NOT EXISTS column_metadata_revisions(
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  revision_id INTEGER NOT NULL REFERENCES metadata_revisions(id) ON DELETE CASCADE,
  table_name TEXT NOT NULL,
  column_name TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  business_tag TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(project_id, revision_id, table_name, column_name)
);

CREATE TABLE IF NOT EXISTS project_members(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_tokens(
  id INTEGER PRIMARY KEY,
  subject TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs(
  id INTEGER PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  subject TEXT NOT NULL,
  action TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_name TEXT NOT NULL DEFAULT '',
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
