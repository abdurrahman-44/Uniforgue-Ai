"""API v1 Router Registry."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    auth,
    community,
    diagrams,
    documents,
    files,
    health,
    images,
    jobs,
    learning,
    notifications,
    presentations,
    projects,
    research,
    tasks,
    users,
    videos,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(workspaces.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(files.router)
api_router.include_router(ai.router)
api_router.include_router(documents.router)
api_router.include_router(presentations.router)
api_router.include_router(research.router)
api_router.include_router(diagrams.router)
api_router.include_router(images.router)
api_router.include_router(jobs.router)
api_router.include_router(videos.router)
api_router.include_router(learning.router)
api_router.include_router(community.router)
api_router.include_router(notifications.router)
api_router.include_router(admin.router)
