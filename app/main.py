from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.urls import api_router
from app.core.config import settings

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url="/openapi.json",
    )

    # CORS enabled origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], 
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    
    return app

app = create_app()
