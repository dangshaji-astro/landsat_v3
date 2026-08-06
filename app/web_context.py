"""
Web Context Fetcher for Expert Agent
Provides historical landslide data (DuckDuckGo search) and 
recent news (Google News RSS / NewsAPI.org, switchable)
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote_plus


# =============================================
#  HISTORICAL LANDSLIDE DATA (DuckDuckGo)
# =============================================

def fetch_historical_data(location_name: str, max_results: int = 8) -> str:
    """
    Search for historical landslide events near a location
    using DuckDuckGo (aggregates Wikipedia, NDMA, news archives, etc.)
    """
    try:
        from duckduckgo_search import DDGS

        query = f"landslide history {location_name} Kerala India"
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region="in-en"))

        if not results:
            return "No historical landslide data found for this location."

        formatted = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            source = r.get("href", "")
            # Extract domain name for source attribution
            domain = source.split("/")[2] if "/" in source else source
            formatted.append(f"- [{domain}] {title}: {body[:200]}")

        return "\n".join(formatted)

    except ImportError:
        return "[duckduckgo-search not installed. Run: pip install duckduckgo-search]"
    except Exception as e:
        return f"[Historical search failed: {str(e)}]"


# =============================================
#  RECENT NEWS - Google News RSS (Free)
# =============================================

def fetch_news_google_rss(location_name: str, max_results: int = 5) -> str:
    """
    Fetch recent landslide news from Google News RSS feed
    Free, no API key needed
    """
    try:
        query = quote_plus(f"landslide {location_name} Kerala")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0"
        })

        if resp.status_code != 200:
            return f"[Google News RSS returned status {resp.status_code}]"

        root = ET.fromstring(resp.content)
        items = root.findall(".//item")

        if not items:
            return "No recent landslide news found."

        formatted = []
        for item in items[:max_results]:
            title = item.findtext("title", "")
            pub_date = item.findtext("pubDate", "")
            source = item.findtext("source", "")
            # Clean up date
            if pub_date:
                try:
                    dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                    pub_date = dt.strftime("%Y-%m-%d")
                except:
                    pub_date = pub_date[:16]

            formatted.append(f"- [{pub_date}] {title} ({source})")

        return "\n".join(formatted)

    except Exception as e:
        return f"[Google News RSS failed: {str(e)}]"


# =============================================
#  RECENT NEWS - NewsAPI.org (Richer, needs key)
# =============================================

def fetch_news_newsapi(location_name: str, api_key: str, max_results: int = 5) -> str:
    """
    Fetch recent landslide news from NewsAPI.org
    Requires API key (free tier: 100 requests/day)
    """
    if not api_key:
        return "[NewsAPI key not configured. Add it in Settings.]"

    try:
        # Search last 30 days
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f"landslide {location_name} Kerala",
            "from": from_date,
            "sortBy": "relevancy",
            "language": "en",
            "pageSize": max_results,
            "apiKey": api_key
        }

        resp = requests.get(url, params=params, timeout=10)

        if resp.status_code == 401:
            return "[NewsAPI: Invalid API key]"
        if resp.status_code != 200:
            return f"[NewsAPI returned status {resp.status_code}]"

        data = resp.json()
        articles = data.get("articles", [])

        if not articles:
            return "No recent landslide news found."

        formatted = []
        for article in articles:
            title = article.get("title", "")
            source = article.get("source", {}).get("name", "")
            pub_date = article.get("publishedAt", "")[:10]
            desc = article.get("description", "")
            formatted.append(f"- [{pub_date}] {title} ({source}): {desc[:150]}")

        return "\n".join(formatted)

    except Exception as e:
        return f"[NewsAPI failed: {str(e)}]"


# =============================================
#  MAIN FUNCTION
# =============================================

def get_web_context(
    location_name: str,
    news_provider: str = "google_rss",
    news_api_key: str = ""
) -> Dict[str, str]:
    """
    Fetch all web context for the expert agent.
    
    Args:
        location_name: Name of the taluk/location (e.g., "Wayanad")
        news_provider: "google_rss" or "newsapi"
        news_api_key: API key for NewsAPI.org (only needed if provider is "newsapi")
    
    Returns:
        Dict with 'historical' and 'recent_news' strings
    """
    print(f"  🌐 Fetching web context for '{location_name}'...")

    # 1. Historical data (always DuckDuckGo)
    print(f"    📜 Searching historical landslide data...")
    historical = fetch_historical_data(location_name)

    # 2. Recent news (switchable provider)
    print(f"    📰 Fetching recent news ({news_provider})...")
    if news_provider == "newsapi":
        recent_news = fetch_news_newsapi(location_name, news_api_key)
    else:
        recent_news = fetch_news_google_rss(location_name)

    return {
        "historical": historical,
        "recent_news": recent_news,
        "provider": news_provider
    }


def format_for_prompt(web_context: Dict[str, str]) -> str:
    """Format web context for injection into LLM prompt"""
    return f"""
HISTORICAL LANDSLIDE DATA (from web search):
{web_context['historical']}

RECENT NEWS ({web_context['provider']}):
{web_context['recent_news']}
"""


# Quick test
if __name__ == "__main__":
    print("=" * 60)
    print("Testing Web Context Fetcher")
    print("=" * 60)

    ctx = get_web_context("Wayanad", "google_rss")
    print("\n📜 HISTORICAL:")
    print(ctx["historical"])
    print("\n📰 RECENT NEWS:")
    print(ctx["recent_news"])
