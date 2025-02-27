# app/agents/market.py
import pandas as pd
import pandas_ta as ta
import hashlib
from langchain.schema import SystemMessage, HumanMessage
from .base import FinancialAgent
from core.cache_manager import CacheManager
from datetime import datetime, timedelta
import pandas_datareader.data as web
import traceback
from config import get_settings
import yfinance as yf

##############################################
# InstitutionalDataAgent
##############################################

class InstitutionalDataAgent(FinancialAgent):
    def __init__(self, bus, llm):
        super().__init__("InstAgent", "Institutional Analysis", bus, llm)
        self.settings = get_settings()
        self.cache = CacheManager()

    def should_handle(self, topic, message):
        return topic == "ownership_request"

    def process_message(self, topic, message, sender):
        symbol = message['symbol']
        print(f"\n🏦 {self.name} fetching institutional data for {symbol}")
        cache_key = f"institutional_{symbol}"
        if cached := self.cache.get(cache_key):
            self.send("ownership_analysis", {"symbol": symbol, "analysis": cached})
            return
        try:
            ticker = yf.Ticker(symbol)
            ownership = {
                'institutional': ticker.institutional_holders,
                'mutual_fund': ticker.mutualfund_holders
            }

            analysis = self._analyze_ownership(symbol, ownership)
            self.cache.set(cache_key, analysis, 86400)
            self.send("ownership_analysis", {"symbol": symbol, "analysis": analysis})

        except Exception as e:
            error_msg = f"Ownership analysis failed: {str(e)}"
            self.send("ownership_analysis", {"symbol": symbol, "analysis": error_msg})

    def _analyze_ownership(self, symbol, data):
        formatted_data = ""
        for holder_type in data:
            if data[holder_type] is not None:
                formatted_data += f"{holder_type.replace('_', ' ').title()}:\n"
                formatted_data += data[holder_type].to_markdown(index=False) + "\n\n"

        prompt = f"""Analyze institutional ownership for {symbol}:
        {formatted_data}

        Identify:
        - Major position changes
        - Notable institutional investors
        - Ownership concentration risks
        - Recent buying/selling trends
        """

        response= self.llm.invoke([HumanMessage(content=prompt)]).content
        print(response)
        return response
