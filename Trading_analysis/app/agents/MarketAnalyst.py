# app/agents/market.py
import pandas as pd
import pandas_ta as ta
import hashlib
from langchain.schema import SystemMessage, HumanMessage
from .base import FinancialAgent
from core.cache_manager import CacheManager
import textwrap


class MarketAnalyst(FinancialAgent):
    def __init__(self, bus, llm):
        super().__init__("MarketAnalyst", "Technical Analysis", bus, llm)
        self.cache = CacheManager()
        self.price_change = None  # To store computed price change

    def should_handle(self, topic, message):
        return topic in ["price_data", "agent_discussion"]

    def process_message(self, topic, message, sender):
        if topic == "price_data":
            symbol = message['symbol']
            print(f"\n📈 {self.name} is analyzing price trends for {symbol}")
            cache_key = f"tech_analysis_{symbol}"
            if cached := self.cache.get(cache_key):
                self.send("technical_analysis", {"symbol": symbol, "analysis": cached})
                return
            data = message.get('data')
            if data is None or (hasattr(data, 'empty') and data.empty):
                analysis = "No price data available"
            else:
                analysis = self._analyze_trends(data)
            print(f"\n📈 {self.name} technical analysis result:\n{textwrap.fill(analysis, width=80)}")
            self.cache.set(cache_key, analysis, 1800)  # 30 min cache
            self.send("technical_analysis", {"symbol": symbol, "analysis": analysis})
        elif topic == "agent_discussion":
            if sender == "System":
                comment = ("MarketAnalyst: Over 10 days, price changed by {:.2f}%; volatility appears moderate.".format(
                    self.price_change if self.price_change is not None else 0))
                self.send("agent_discussion", {"symbol": message.get("symbol", self.name), "comment": comment})
            else:
                print(f"🗣 {self.name} observed discussion from {sender}: {message.get('comment', '')}")

    def _analyze_trends(self, data):
        summary_hash = hashlib.md5(str(data.tail(10)).encode()).hexdigest()
        cache_key = f"tech_llm_{summary_hash}"
        if cached := self.cache.get(cache_key): return cached
        try:

            # Calculate additional technical indicators
            data.ta.rsi(length=14, append=True)  # RSI (14-day)
            data.ta.ema(length=20, append=True)  # 20-day EMA
            data.ta.ema(length=50, append=True)  # 50-day EMA
            data.ta.macd(append=True)  # MACD

            # Add Bollinger Bands
            data.ta.bbands(length=20, std=2, append=True)  # 20-day Bollinger Bands with 2 standard deviations

            # Add Average True Range (ATR)
            data.ta.atr(length=14, append=True)  # 14-day ATR

            # Add Fibonacci Retracement Levels
            high = data['High'].max()
            low = data['Low'].min()
            diff = high - low
            fib_levels = {
                '23.6%': high - diff * 0.236,
                '38.2%': high - diff * 0.382,
                '50.0%': high - diff * 0.5,
                '61.8%': high - diff * 0.618,
                '78.6%': high - diff * 0.786
            }

            # Extract the latest values
            latest = data.iloc[-1]
            reference = data.iloc[0]

            # Calculate price and volume changes
            price_change = ((latest.Close - reference.Close) / reference.Close) * 100
            self.price_change = price_change
            volume_change = ((latest.Volume - reference.Volume) / reference.Volume) * 100

            # Prepare summary with advanced indicators
            summary = (
                f"10-Day Price Performance:\n"
                f"• Price Change: {price_change:.2f}%\n"
                f"• Volume Change: {volume_change:.2f}%\n"
                f"• Latest - Open: {latest.Open:.2f}, Close: {latest.Close:.2f}\n"
                f"• High/Low: {latest.High:.2f}/{latest.Low:.2f}\n"
                f"• Volume: {latest.Volume:,}\n"
                f"• RSI (14-day): {latest['RSI_14']:.2f}\n"
                f"• 20-day EMA: {latest['EMA_20']:.2f}\n"
                f"• 50-day EMA: {latest['EMA_50']:.2f}\n"
                f"• MACD: {latest['MACD_12_26_9']:.2f}\n"
                f"• MACD Histogram: {latest['MACDh_12_26_9']:.2f}\n"
                f"• MACD Signal Line: {latest['MACDs_12_26_9']:.2f}\n"
                f"• Bollinger Bands (20,2): Upper={latest['BBU_20_2.0']:.2f}, Middle={latest['BBM_20_2.0']:.2f}, Lower={latest['BBL_20_2.0']:.2f}\n"
                f"• ATR (14-day): {latest['ATRr_14']:.2f}\n"
                f"• Fibonacci Retracement Levels:\n"
                f"   - 23.6%: {fib_levels['23.6%']:.2f}\n"
                f"   - 38.2%: {fib_levels['38.2%']:.2f}\n"
                f"   - 50.0%: {fib_levels['50.0%']:.2f}\n"
                f"   - 61.8%: {fib_levels['61.8%']:.2f}\n"
                f"   - 78.6%: {fib_levels['78.6%']:.2f}"
            )

            # Analyze trends using LLM
            response = self.llm.invoke([
                SystemMessage(content="""Analyze the following 10-day price summary with advanced technical indicators.
Provide bullet point highlights including:
• Key technical indicators (e.g., price and volume changes, RSI, EMA, MACD, Bollinger Bands, ATR, Fibonacci levels)
• Notable support/resistance levels
• Short-term trend prediction (include main numbers)
"""),
                HumanMessage(content=summary)
            ])
            self.cache.set(cache_key, response.content, 86400)  # 24h cache
            return response.content
        except Exception as e:
            return f"Technical analysis error: {str(e)}"