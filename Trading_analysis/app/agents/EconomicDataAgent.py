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


##############################################
# EconomicDataAgent
##############################################

class EconomicDataAgent(FinancialAgent):
    def __init__(self, bus, llm):
        super().__init__("EconAgent", "Economic Analysis", bus, llm)
        self.settings = get_settings()
        self.cache = CacheManager()
        self.indicators = {
            'GDP': 'GDP',
            'FEDFUNDS': 'Federal Funds Rate',
            'UNRATE': 'Unemployment Rate',
            'CPIAUCSL': 'CPI Inflation'
        }

    def should_handle(self, topic, message):
        return topic == "economic_request"

    def process_message(self, topic, message, sender):
        symbol = message['symbol']
        print(f"\n📊 {self.name} fetching economic indicators")
        cache_key = f"economic_data_{symbol}"
        cached = self.cache.get(cache_key)
        if cached:
          self.send("economic_analysis", {"symbol": symbol, "analysis": cached})
          return

        try:
            econ_data = {}
            for code, name in self.indicators.items():
                # Get FRED API key from environment
                fred_key = self.settings.FRED_API_KEY
                if not fred_key:
                    raise ValueError("FRED_API_KEY not found in environment variables")

                # Get data with error handling
                series = web.DataReader(
                    code,
                    'fred',
                    start=datetime.now() - timedelta(days=365),
                    end=datetime.now(),
                    api_key=fred_key
                )

                # Check for valid data
                if series.empty:
                    econ_data[name] = {'error': 'No data available'}
                    continue

                # Handle potential NaN values
                current_value = series.iloc[-1].values[0] if not pd.isna(series.iloc[-1].values[0]) else 0
                initial_value = series.iloc[0].values[0] if not pd.isna(series.iloc[0].values[0]) else 0

                # Calculate percentage change safely
                try:
                    pct_change = ((current_value - initial_value) / initial_value) * 100
                except ZeroDivisionError:
                    pct_change = 0

                econ_data[name] = {
                    'current': round(current_value, 2),
                    '1y_change': round(pct_change, 2)
                }

            analysis = self._analyze_economy(econ_data)
            self.cache.set(cache_key, analysis, 86400)  # 24 hours
            self.send("economic_analysis", {"symbol": symbol, "analysis": analysis})



        except Exception as e:
            error_msg = f"Economic analysis failed: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            self.send("economic_analysis", {"symbol": symbol, "analysis": error_msg})

    def _analyze_economy(self, data):
        try:
            # Create formatted table for LLM
            table = ["Indicator | Current Value | 1-Year Change",
                    "--- | --- | ---"]
            for indicator, values in data.items():
                if 'error' in values:
                    table.append(f"{indicator} | ERROR | {values['error']}")
                else:
                    table.append(f"{indicator} | {values['current']} | {values['1y_change']}%")

            prompt = f"""Analyze these economic indicators:
            {chr(10).join(table)}

            Provide insights on:
            - Overall economic health
            - Implications for equity markets
            - Sector-specific impacts

            Format your response with clear bullet points.
            """

            return self.llm.invoke([
                SystemMessage(content="You are a senior economic analyst. Provide clear, concise analysis."),
                HumanMessage(content=prompt)
            ]).content

        except Exception as e:
            return f"Economic analysis error: {str(e)}"