from fastapi import FastAPI
from src.presentation.api.v1.controllers.order_controller import router as order_router_v1
from src.presentation.api.exceptions.handlers import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="iFactory API",
        version="1.0.0",
        description="Production-grade API for iFactory operations.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    register_exception_handlers(app)

    # API Versioning
    app.include_router(order_router_v1, prefix="/api/v1")

    return app


app = create_app()
