import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentic_trader.api.routes.broker import router as broker_router
from agentic_trader.api.routes.control import router as control_router
from agentic_trader.api.routes.learning import router as learning_router
from agentic_trader.api.routes.trading import router as trading_router
from agentic_trader.config.logging import setup_logging
from agentic_trader.database.session import create_tables


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    load_dotenv(os.getenv("ENV_FILE"))
    create_tables()

    yield


app = FastAPI(
    title="Agentic Trader API",
    description="API for the Agentic Trader application",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(broker_router)
app.include_router(control_router)
app.include_router(learning_router)
app.include_router(trading_router)
