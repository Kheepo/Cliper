from .auth import router as auth_router
from .users import router as users_router
from .jobs import router as jobs_router
from .results import router as results_router
from .health import router as health_router

__all__ = [
    "auth_router",
    "users_router", 
    "jobs_router",
    "results_router",
    "health_router"
]