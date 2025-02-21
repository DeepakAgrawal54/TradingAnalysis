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
import requests


##############################################
# Enhanced Peer Analysis Agent (FMP Version)
##############################################
class PeerAnalysisAgent(FinancialAgent):
    def __init__(self, bus, llm):
        super().__init__("PeerAnalyst", "Peer Comparison", bus, llm)
        self.settings = get_settings()
        self.cache = CacheManager()
        self.peer_data = {}

    def should_handle(self, topic, message):
        return topic in ["peer_request", "agent_discussion"]

    def process_message(self, topic, message, sender):
        if topic == "peer_request":
            symbol = message['symbol']
            print(f"\n🔗 {self.name} analyzing peers for {symbol}")
            cache_key = f"peer_analysis_{symbol}"
            if cached := self.cache.get(cache_key):
                self.send("peer_analysis", {"symbol": symbol, "analysis": cached})
                return

            try:
                # Step 1: Fetch peers from FMP
                peers_df = self._get_fmp_peers(symbol)
                print(peers_df)
                if len(peers_df)==0:
                    raise ValueError(f"No peers found for {symbol}")

                # Step 2: Enrich with fundamental data
                self._enrich_peer_data(symbol, peers_df)

                # Step 3: Generate analysis
                analysis = self._generate_comparison(symbol, peers_df)
                self.cache.set(cache_key, analysis, 86400)  # 24h cache
                self.send("peer_analysis", {"symbol": symbol, "analysis": analysis})

            except Exception as e:
                error_msg = f"Peer analysis failed: {str(e)}"
                self.send("peer_analysis", {"symbol": symbol, "analysis": error_msg})

    def _get_fmp_peers(self, symbol):
        """Retrieve peers from FMP API with error handling"""
        try:
            api_key=self.settings.financial_modeling_key
            url = f"https://financialmodelingprep.com/stable/stock-peers?symbol={symbol}&apikey={api_key}"

            response = requests.get(url,timeout=10)
            response.raise_for_status()

            data = response.json()
            if not data:
                return pd.DataFrame()

            data=pd.DataFrame(data)
            return list(data['symbol'])

        except Exception as e:
            print(f"FMP API error: {str(e)}")
            return pd.DataFrame()

    def _enrich_peer_data(self, target_symbol, peers_df):
        """Enrich data with Yahoo Finance fundamentals"""

        symbols = [target_symbol] + peers_df

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                self.peer_data[symbol] = {
                    'pe_ratio': info['forwardPE'],
                    'pb_ratio': info['priceToBook'],
                    'market_cap': info['marketCap'],
                    'beta': info['beta'],
                }
            except Exception as e:
                #self.peer_data[symbol] = {}
                continue

    def _generate_comparison(self, target_symbol, peers_df):
        """Generate comparative analysis using LLM"""
        target_data = self.peer_data.get(target_symbol, {})

        # Prepare peer comparison table
        comparison_table = [
            f"| Metric | Target ({target_symbol}) | Peer Average |",
            "|--------|--------------------------|--------------|"
        ]

        # Calculate averages
        metrics = ['pe_ratio', 'pb_ratio', 'market_cap', 'beta']
        for metric in metrics:
            peer_values = [v.get(metric, 0) for k,v in self.peer_data.items() if k != target_symbol]
            avg = sum(peer_values)/len(peer_values) if peer_values else 0
            comparison_table.append(
                f"| {metric.replace('_', ' ').title()} | {target_data.get(metric, 'N/A'):.2f} | {avg:.2f} |"
            )

        # Create LLM prompt
        prompt = f"""Analyze this peer comparison for {target_symbol}:

        {chr(10).join(comparison_table)}

        Provide insights on:
        - Valuation relative to peers
        - Risk profile (beta comparison)
        - Market position (market cap)
        - Key differentiators
        """

        return self.llm.invoke([
            SystemMessage(content="You are a financial peer comparison expert. Provide clear, concise analysis."),
            HumanMessage(content=prompt)
        ]).content
