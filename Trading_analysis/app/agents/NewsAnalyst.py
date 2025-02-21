# app/agents/news.py
from datetime import datetime, timedelta
import yfinance as yf
import requests
from langchain.schema import SystemMessage, HumanMessage
import textwrap
import hashlib
from .base import FinancialAgent
from config import get_settings
from core.cache_manager import CacheManager

class NewsAnalyst(FinancialAgent):
    def __init__(self, bus, llm):
        super().__init__("NewsAnalyst", "News Analysis", bus, llm)
        self.settings = get_settings()
        self.cache = CacheManager()

    def should_handle(self, topic: str, message) -> bool:
        return topic in ["news_request", "agent_discussion"]

    def process_message(self, topic: str, message, sender: str) -> None:
        if topic == "news_request":
            symbol = message['symbol']
            print(f"\n📰 {self.name} is fetching news and market data for {symbol}")
            try:
                fetched_data = self._fetch_news_and_market_info(symbol)
                analysis = self._analyze_news(fetched_data)
                print(f"\n📰 {self.name} analysis result:\n{textwrap.fill(analysis, width=80)}")
                self.send("news_analysis", {"symbol": symbol, "analysis": analysis})
            except Exception as e:
                error_msg = f"News analysis failed: {str(e)}"
                self.send("news_analysis", {"symbol": symbol, "analysis": error_msg})
        
        elif topic == "agent_discussion" and sender == "System":
            comment = "NewsAnalyst: No major headlines; news data appears typical."
            self.send("agent_discussion", {"symbol": message.get("symbol", self.name), "comment": comment})

    def _fetch_news_and_market_info(self, symbol: str):
        cache_key = f"news_market_{symbol}"
        if cached := self.cache.get(cache_key):
            print(f"Using cached news/market data for {symbol}")
            return cached
        print("not in cache")
        ticker = yf.Ticker(symbol)
        company_name = ticker.info.get('longName', symbol)

        # Fetch Yahoo Finance News
        ten_days_ago = datetime.now() - timedelta(days=10)
        all_news = ticker.news or []
        yf_news = self._process_yf_news(all_news, ten_days_ago)

        # Fetch Alpha Vantage News
        av_news = self._fetch_alpha_vantage_news(symbol)
        
        # Combine and deduplicate news
        combined_news = self._combine_news(yf_news, av_news)

        # Fetch market data
        market_info = self._get_market_info(ticker)

        data = {
            "news": combined_news[:10],
            "market_info": market_info,
            "company_name": company_name
        }
        
        self.cache.set(cache_key, data, 3600)  # 1 hour cache
        return data

    def _process_yf_news(self, news_items, cutoff_date: datetime):
        processed_news = []
        for news in news_items:
            try:
                pub_date = datetime.fromisoformat(news["content"]["pubDate"].rstrip('Z'))
                if pub_date >= cutoff_date:
                    processed_news.append({
                        'title': news["content"]["title"],
                        'publisher': news["content"]['provider']["displayName"],
                        'link': news["content"]["canonicalUrl"]["url"],
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'summary': news["content"]['summary']
                    })
            except (KeyError, ValueError) as e:
                continue
        return processed_news

    def _fetch_alpha_vantage_news(self, symbol: str):
        try:
            response = requests.get(
                f"https://www.alphavantage.co/query",
                params={
                    "function": "NEWS_SENTIMENT",
                    "tickers": symbol,
                    "apikey": self.settings.alpha_vantage_key
                }
            )
            data = response.json()
            
            if 'feed' not in data:
                return []

            return [
                {
                    'title': item.get('title', 'No title'),
                    'publisher': item.get('source', 'Unknown'),
                    'link': item.get('url', '#'),
                    'date': datetime.strptime(item['time_published'], '%Y%m%dT%H%M%S').strftime('%Y-%m-%d'),
                    'summary': item.get('summary', '')
                }
                for item in data['feed']
                if self._is_valid_news_item(item)
            ]
        except Exception:
            return []

    def _is_valid_news_item(self, item) -> bool:
        required_fields = ['title', 'time_published']
        return all(field in item for field in required_fields)

    def _combine_news(self, yf_news, av_news):
        seen = set()
        unique_news = []
        
        for news in yf_news + av_news:
            if news['title'] not in seen:
                seen.add(news['title'])
                unique_news.append(news)
        
        return unique_news

    def _get_market_info(self, ticker: yf.Ticker):
        info = ticker.info
        return {
            "currentPrice": info.get("currentPrice"),
            "marketCap": info.get("marketCap"),
            "previousClose": info.get("regularMarketPreviousClose"),
            "open": info.get("regularMarketOpen"),
            "dayHigh": info.get("regularMarketDayHigh"),
            "dayLow": info.get("regularMarketDayLow"),
            "volume": info.get("volume")
        }

    def _analyze_news(self, fetched_data) -> str:
        news_text = []
        if fetched_data["news"]:
            news_text.append("Recent News:")
            for article in fetched_data["news"]:
                news_text.append(f"• {article['date']} | {article['publisher']}: {article['title']}: {article['summary']}")
        else:
            news_text.append("No news articles found in the last 10 days.")

        market_text = ["Market Data:"]
        for key, value in fetched_data["market_info"].items():
            market_text.append(f"• {key}: {value}")

        prompt = "\n".join(news_text + market_text)
        
        cache_key = "llm_" + hashlib.md5(prompt.encode()).hexdigest()
        if cached := self.cache.get(cache_key):
            return cached

        try:
            response = self.llm.invoke([
                SystemMessage(content=f"""Analyze the following news and market data for {fetched_data['company_name']}
Provide concise bullet points highlighting:
• Up to 3 positive points
• Up to 3 negative points
• Overall market sentiment (including key numbers like current price and market cap)
"""),
                HumanMessage(content=prompt)
            ])
            
            self.cache.set(cache_key, response.content, 86400)  # 24 hours
            return response.content
        except Exception as e:
            return f"News analysis error: {str(e)}"