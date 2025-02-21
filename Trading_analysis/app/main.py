# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agents import NewsAnalyst, MarketAnalyst, StrategyAnalyst, EconomicDataAgent, InstitutionalDataAgent, PeerAnalysisAgent
from core import message_bus
from models import TradingRequest, AnalysisResponse
from core.trading_session import TradingSession
from config import Settings
import logging


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load settings
settings = Settings()

# Initialize FastAPI app
app = FastAPI(
    title="Trading Agent API",
    description="API for analyzing stocks using multiple specialized agents",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Trading Agent API is running"}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_stock(request: TradingRequest):
    try:
        logger.info(f"Analyzing {request.symbol} with {request.analysis_type} analysis")
        session1 = TradingSession(request.symbol, request.analysis_type)
        await session1.run()
        return session1.get_results()
    except Exception as e:
        logger.error(f"Error analyzing {request.symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}