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
import textwrap


##############################################
# Strategy Analyst Agent (Aggregator)
##############################################
class StrategyAnalyst(FinancialAgent):
    def __init__(self, bus, llm, analysis_type='short'):
        super().__init__("StrategyAnalyst", "Recommendation Engine", bus, llm)
        self.settings = get_settings()
        self.cache = CacheManager()
        self.analysis_type = analysis_type  # 'short' or 'long'

    def should_handle(self, topic, message):
        return topic in ["analysis_consolidation", "agent_discussion"]

    def process_message(self, topic, message, sender):
        if topic == "analysis_consolidation":
            symbol = message['symbol']
            print(f"\n💡 {self.name} is generating a final trading recommendation for {symbol}")
            cache_key = f"strategy_{symbol}_{self.analysis_type}"
            if cached := self.cache.get(cache_key):
                self.send("final_recommendation", {"symbol": symbol, "recommendation": cached})
                return
            try:
                recommendation = self._generate_recommendation(message)
                print(f"\n💡 {self.name} final recommendation:\n{textwrap.fill(recommendation, width=80)}")
                self.cache.set(cache_key, recommendation, 3600)  # 1 hour cache
                self.send("final_recommendation", {"symbol": symbol, "recommendation": recommendation})
            except Exception as e:
                error_msg = f"Recommendation failed: {str(e)}"
                print(error_msg)
                self.send("final_recommendation", {"symbol": symbol, "recommendation": error_msg})
        elif topic == "agent_discussion":
            if sender == "System":
                comment = (f"StrategyAnalyst: Signals are {'mixed' if self.analysis_type == 'short' else 'developing'}; "
                          f"recommend reviewing {'technical' if self.analysis_type == 'short' else 'fundamental'} factors.")
                self.send("agent_discussion", {"symbol": message.get("symbol", self.name), "comment": comment})

    def _generate_recommendation(self, data):
        # Create content string based on analysis type
        base_content = f"News Analysis:\n{data['news_analysis']}\n\nTechnical Analysis:\n{data['technical_analysis']}"
        if self.analysis_type == 'long':
            base_content += f"\n\nEconomic Analysis:\n{data['economic_analysis']}\nOwnership Analysis:\n{data['ownership_analysis']}\Peer Analysis:\n{data['peer_analysis']}"

        content_hash = hashlib.md5(base_content.encode()).hexdigest()
        cache_key = f"recommendation_{content_hash}"
        if cached := self.cache.get(cache_key):
            return cached

        try:
            # Different prompts for different analysis types
            analysis_points = (
                "• Technical patterns and recent price action\n"
                "• News sentiment impact\n"
                "• Short-term price targets (1-4 weeks)\n"
                "• Stop-loss levels"
                if self.analysis_type == "short"
                else
                "• Fundamental valuation metrics\n"
                "• Economic environment analysis\n"
                "• Institutional ownership trends\n"
                "• Long-term growth potential (6-12 months)"
            )

            system_prompt = SystemMessage(content=f"""Based on the following analyses, generate a {'short-term trading' if self.analysis_type == 'short' else 'long-term investment'} recommendation in bullet points. Include:
            {analysis_points}
            • Risk assessment
            • Clear action recommendation (Buy, Hold or Sell)""")

            response = self.llm.invoke([
                system_prompt,
                HumanMessage(content=base_content)
            ])

            self.cache.set(cache_key, response.content, 86400)
            return response.content
        except Exception as e:
            return f"Recommendation generation error: {str(e)}"