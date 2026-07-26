from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    data_dir: Path
    db_path: Path
    imports_dir: Path
    max_zip_bytes: int
    max_zip_files: int
    max_zip_uncompressed_bytes: int
    max_zip_file_bytes: int
    max_zip_compression_ratio: int
    worker_poll_interval_ms: int


def get_settings() -> Settings:
    root_dir = Path(__file__).resolve().parents[2]
    data_dir = Path(os.getenv("DFI_DATA_DIR", root_dir / "data"))
    return Settings(
        root_dir=root_dir,
        data_dir=data_dir,
        db_path=Path(os.getenv("DFI_DB_PATH", data_dir / "dataflow.db")),
        imports_dir=Path(os.getenv("DFI_IMPORT_DIR", data_dir / "imports")),
        max_zip_bytes=int(os.getenv("DFI_MAX_ZIP_BYTES", 50 * 1024 * 1024)),
        max_zip_files=int(os.getenv("DFI_MAX_ZIP_FILES", "5000")),
        max_zip_uncompressed_bytes=int(
            os.getenv("DFI_MAX_ZIP_UNCOMPRESSED_BYTES", str(500 * 1024 * 1024))
        ),
        max_zip_file_bytes=int(
            os.getenv("DFI_MAX_ZIP_FILE_BYTES", str(100 * 1024 * 1024))
        ),
        max_zip_compression_ratio=int(os.getenv("DFI_MAX_ZIP_COMPRESSION_RATIO", "200")),
        worker_poll_interval_ms=int(os.getenv("DFI_WORKER_POLL_MS", "100")),
    )
