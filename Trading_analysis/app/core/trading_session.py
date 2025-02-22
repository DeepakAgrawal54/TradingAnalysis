from typing import Dict, Optional
import asyncio
import pandas as pd
import yfinance as yf
from agents.NewsAnalyst import NewsAnalyst
from agents.MarketAnalyst import MarketAnalyst
from agents.StrategyAnalyst import StrategyAnalyst
from agents.EconomicDataAgent import EconomicDataAgent
from agents.InstitutionalDataAgent import InstitutionalDataAgent
from agents.PeerAnalysisAgent import PeerAnalysisAgent
from core.message_bus import MessageBus
from core.cache_manager import CacheManager
from config import get_settings
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq


class TradingSession:
    def __init__(self, symbol: str, analysis_type: str = 'short'):
        self.settings = get_settings()
        self.symbol = symbol.upper()
        self.analysis_type = analysis_type.lower()
        self.bus = MessageBus()
        self.cache = CacheManager()
        
        # Initialize LLM
        self.llm = ChatGroq(
            temperature=0.5,
            model="llama-3.1-8b-instant",
            groq_api_key=self.settings.groq_api_key
        )
        
        # Initialize agents
        self._init_agents()  # Initialize all the agents and assign them to self
        self._subscribe_agents()  # Subscribe agents after they are initialized

    def _init_agents(self) -> None:
        # Initialize core agents
        self.news_analyst = NewsAnalyst(self.bus, self.llm)
        self.market_analyst = MarketAnalyst(self.bus, self.llm)
        self.strategy_analyst = StrategyAnalyst(self.bus, self.llm, self.analysis_type)

        # Initialize long-term agents (if needed)
        if self.analysis_type == 'long':
            self.economy_analyst = EconomicDataAgent(self.bus, self.llm)
            self.institutional_analyst = InstitutionalDataAgent(self.bus, self.llm)
            self.peer_analyst = PeerAnalysisAgent(self.bus, self.llm)

    def _subscribe_agents(self) -> None:
        # Subscribe core agents to their respective topics
        self.bus.subscribe(self.news_analyst, "news_request")
        self.bus.subscribe(self.market_analyst, "price_data")
        self.bus.subscribe(self.strategy_analyst, "analysis_consolidation")

        # Subscribe core agents to 'agent_discussion'
        for agent in [self.news_analyst, self.market_analyst, self.strategy_analyst]:
            self.bus.subscribe(agent, "agent_discussion")

        # Subscribe long-term agents (if applicable) to their respective topics
        if self.analysis_type == 'long':
            self.bus.subscribe(self.economy_analyst, "economic_request")
            self.bus.subscribe(self.institutional_analyst, "ownership_request")
            self.bus.subscribe(self.peer_analyst, "peer_request")

            # Subscribe long-term agents to 'agent_discussion'
            for agent in [self.economy_analyst, self.institutional_analyst, self.peer_analyst]:
                self.bus.subscribe(agent, "agent_discussion")

    def _get_price_data(self):
        cache_key = f"price_data_{self.symbol}"
        print(f"🔍 Checking cache for {self.symbol} price data...")
        data = self.cache.get(cache_key)

        if data is not None and not data.empty:
            print(f"✅ Using cached price data for {self.symbol}")
            self.bus.publish("price_data", {"symbol": self.symbol, "data": data}, "System")
            return

        try:
            period = "60d" if self.analysis_type == 'short' else "5y"
            interval = "1d" if self.analysis_type == 'short' else "1wk"

            ticker = yf.Ticker(self.symbol)
            data = ticker.history(period=period, interval=interval)

            if not data.empty:
                self.cache.set(cache_key, data, 300)
                self.bus.publish("price_data", {"symbol": self.symbol, "data": data}, "System")
                print("✅ Price data published successfully!")

            else:
                print("⚠️ No historical price data available.")
                self.bus.publish("price_data", {"symbol": self.symbol, "data": pd.DataFrame()}, "System")

        except Exception as e:
            print(f"❌ Price data error: {str(e)}")

    async def run(self) -> None:
        requests = {
            'short': ["news_request", "price_data", "peer_request"],
            'long': ["news_request", "price_data", "peer_request", 
                     "economic_request", "ownership_request"]
        }

        # Publish initial requests
        for req in requests[self.analysis_type]:
            if req == "price_data":
                self._get_price_data()
            else:
                self.bus.publish(req, {"symbol": self.symbol}, "System")

        await asyncio.sleep(5)  # <-- Might be blocking

        print("\n💬 Initiating inter-agent discussion round...")
        self.bus.publish("agent_discussion", {"symbol": self.symbol, "prompt": "Review the analyses."}, "System")

        await asyncio.sleep(3)  # <-- Might be blocking

        print("\n📊 Consolidating analyses...")
        self._consolidate_analyses()
        print("✅ Trading Session completed.")

    def _consolidate_analyses(self) -> None:
        analyses = {
            "news_analysis": "No news analysis available",
            "technical_analysis": "No technical analysis available",
            "ownership_analysis": "No ownership analysis available",
            "economic_analysis": "No economic analysis available",
            "peer_analysis": "No peer analysis available"
        }

        # Collect results from messages
        for topic, msg, _ in self.bus.messages:
            if topic in analyses:
                analyses[topic] = msg.get("analysis", analyses[topic])

        # Generate final recommendation
        self.bus.publish("analysis_consolidation", {
            "symbol": self.symbol,
            **analyses
        }, "System")

    def get_results(self) -> Dict[str, str]:
        """Get final analysis results"""
        return {
            "symbol": self.symbol,
            "news_analysis": next((msg.get("analysis") for topic, msg, _ in self.bus.messages 
                                 if topic == "news_analysis"), "No news analysis"),
            "technical_analysis": next((msg.get("analysis") for topic, msg, _ in self.bus.messages 
                                     if topic == "technical_analysis"), "No technical analysis"),
            "recommendation": next((msg.get("recommendation") for topic, msg, _ in self.bus.messages 
                                 if topic == "final_recommendation"), "No recommendation"),
            "ownership_analysis": next((msg.get("analysis") for topic, msg, _ in self.bus.messages 
                                     if topic == "ownership_analysis"), None),
            "economic_analysis": next((msg.get("analysis") for topic, msg, _ in self.bus.messages 
                                    if topic == "economic_analysis"), None),
            "peer_analysis": next((msg.get("analysis") for topic, msg, _ in self.bus.messages 
                                 if topic == "peer_analysis"), None)
        }
