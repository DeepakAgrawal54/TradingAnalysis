import asyncio
from core.trading_session import TradingSession

async def test_trading_session():
    print("Initializing TradingSession...")
    session = TradingSession("AAPL", "short")

    print("\nRunning TradingSession...")
    await session.run()  # Run the session

    print("\nFetching results...")
    results = session.get_results()  # Get the results
    print(results)

# Run the test
asyncio.run(test_trading_session())
