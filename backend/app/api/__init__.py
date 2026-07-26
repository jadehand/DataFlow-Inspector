from .assistant import router as assistant_router
from .catalog import router as catalog_router
from .compare import router as compare_router
from .health import router as health_router
from .imports import router as imports_router
from .metadata import router as metadata_router
from .projects import router as projects_router

__all__ = [
    "assistant_router",
    "catalog_router",
    "compare_router",
    "health_router",
    "imports_router",
    "metadata_router",
    "projects_router",
]
