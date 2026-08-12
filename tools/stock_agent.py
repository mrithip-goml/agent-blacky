import io
import json
import contextlib
from pathlib import Path

import yfinance as yf
from google import genai
from google.genai import types
from google.genai.errors import ClientError

from config.settings import GEMINI_API_KEY, GEMINI_MODEL


def load_prompt(filename: str) -> str:
    """Loads a system prompt template from the prompts/ directory."""
    prompt_path = Path(__file__).parent.parent / "prompts" / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file missing: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()


class StockAgent:
    def __init__(self, api_key: str = None, enable_widgets: bool = False):
        """
        :param api_key: Gemini API Key.
        :param enable_widgets: Set to True if your client parses <GenerateWidget> XML tags.
                              Set to False (default) to generate plain Markdown outputs.
        """
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing! Check your .env file.")

        self.client = genai.Client(api_key=self.api_key)
        self.model = GEMINI_MODEL
        self.enable_widgets = enable_widgets

    def _get_working_ticker(self, symbol: str):
        """Resolves raw tickers (e.g. TATASTEEL) to working yfinance Ticker objects (e.g. TATASTEEL.NS) without stderr spam."""
        clean_symbol = symbol.strip().upper()
        candidates = [clean_symbol]
        
        if "." not in clean_symbol:
            candidates.extend([f"{clean_symbol}.NS", f"{clean_symbol}.BO"])

        for sym in candidates:
            try:
                t = yf.Ticker(sym)
                # Suppress yfinance stderr noisy 404 prints during ticker checks
                with contextlib.redirect_stderr(io.StringIO()):
                    hist = t.history(period="5d", raise_errors=False)
                    if not hist.empty and "Close" in hist:
                        return t, sym
            except Exception:
                continue

        # Return None tuple consistently
        return None, clean_symbol

    def _format_market_cap(self, value) -> str:
        """Formats raw numerical market cap into readable strings ($B / $T / ₹ Cr)."""
        if not isinstance(value, (int, float)):
            return "N/A"
        if value >= 1e12:
            return f"${value / 1e12:.2f}T"
        if value >= 1e9:
            return f"${value / 1e9:.2f}B"
        if value >= 1e6:
            return f"${value / 1e6:.2f}M"
        return f"${value:,.2f}"

    def _format_percentage(self, value) -> str:
        """Formats decimals into percentage strings."""
        if not isinstance(value, (int, float)):
            return "N/A"
        return f"{value * 100:.2f}%"

    def fetch_stock_data(self, ticker_symbol: str) -> dict:
        """Fetches fundamental metrics and current price for a stock symbol."""
        try:
            ticker, working_symbol = self._get_working_ticker(ticker_symbol)
            if not ticker:
                return {"error": f"Could not retrieve stock data for '{ticker_symbol}'. Invalid symbol or missing exchange suffix."}

            try:
                info = ticker.info or {}
            except Exception:
                info = {}

            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            if current_price is None:
                hist = ticker.history(period="5d")
                if hist.empty or "Close" not in hist:
                    return {"error": f"No recent price data found for '{working_symbol}'."}
                current_price = float(hist["Close"].iloc[-1])

            currency = info.get("currency") or ("INR" if working_symbol.endswith((".NS", ".BO")) else "USD")

            return {
                "symbol": working_symbol,
                "name": info.get("longName") or info.get("shortName") or working_symbol,
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "price": round(float(current_price), 2),
                "currency": currency,
                "market_cap": self._format_market_cap(info.get("marketCap")),
                "pe_ratio": round(info.get("forwardPE") or info.get("trailingPE"), 2) if isinstance(info.get("forwardPE") or info.get("trailingPE"), (int, float)) else "N/A",
                "pb_ratio": round(info.get("priceToBook"), 2) if isinstance(info.get("priceToBook"), (int, float)) else "N/A",
                "ps_ratio": round(info.get("priceToSalesTrailing12Months"), 2) if isinstance(info.get("priceToSalesTrailing12Months"), (int, float)) else "N/A",
                "profit_margin": self._format_percentage(info.get("profitMargins")),
                "revenue_growth": self._format_percentage(info.get("revenueGrowth")),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow", "N/A"),
                "recommendation": str(info.get("recommendationKey", "N/A")).upper(),
            }
        except Exception as e:
            return {"error": f"Failed to fetch data for {ticker_symbol}: {str(e)}"}

    def fetch_historical_returns(self, tickers: list[str], period: str = "6mo") -> dict:
        """Fetches historical close prices and calculates relative percentage return over time."""
        history_data = {}
        for symbol in tickers:
            result = self._get_working_ticker(symbol)
            if not result or result[0] is None:
                continue
            
            ticker, working_symbol = result
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    hist = ticker.history(period=period, raise_errors=False)
                
                if not hist.empty and "Close" in hist:
                    start_price = float(hist["Close"].iloc[0])
                    series_points = []

                    for date, price in hist["Close"].items():
                        current_val = float(price)
                        return_pct = round(((current_val - start_price) / start_price) * 100, 2) if start_price > 0 else 0.0
                        series_points.append({
                            "date": str(date.strftime("%Y-%m-%d")),
                            "price": round(current_val, 2),
                            "return_pct": return_pct
                        })

                    history_data[working_symbol] = series_points
            except Exception:
                continue
        return history_data

    def _generate_markdown_returns_table(self, history_data: dict) -> str:
        """Generates a text-based Markdown table summary of relative return performance."""
        if not history_data:
            return ""

        table_md = "\n### Historical Return Summary (6-Month Performance)\n\n"
        table_md += "| Stock Symbol | Starting Price | Latest Price | 6-Month Total Return (%)\n"
        table_md += "| :--- | :--- | :--- | :--- |\n"

        for symbol, points in history_data.items():
            if not points:
                continue
            start = points[0]
            latest = points[-1]
            return_pct = latest['return_pct']
            sign = "+" if return_pct > 0 else ""
            table_md += f"| **{symbol}** | {start['price']} | {latest['price']} | `{sign}{return_pct}%` |\n"

        return table_md

    def analyze_single_stock(self, ticker: str) -> tuple[str, str]:
        """Generates single stock fundamentals and technical breakdown."""
        try:
            data = self.fetch_stock_data(ticker)
            if "error" in data:
                return data["error"], ""

            prompt = load_prompt("stock_analysis.txt").format(**data)
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            return response.text, ""
        except ClientError as e:
            return f"[ERROR] Gemini API Error: {str(e)}", ""
        except Exception as e:
            return f"[ERROR] Single stock analysis failed: {str(e)}", ""

    def compare_stocks(self, tickers: list[str]) -> tuple[str, str]:
        """Generates side-by-side comparative analysis and optional chart component/table."""
        try:
            if len(tickers) < 2:
                return "[ERROR] Please provide at least two stock tickers to compare (e.g. /stock compare ASHOKLEY TATASTEEL).", ""

            stock_datasets = []
            valid_symbols = []

            for t in tickers:
                d = self.fetch_stock_data(t)
                if "error" not in d:
                    stock_datasets.append(d)
                    valid_symbols.append(d['symbol'])

            if not stock_datasets:
                return "[ERROR] Could not fetch valid financial data for any of the specified tickers.", ""

            history_data = self.fetch_historical_returns(valid_symbols, period="6mo")
            comp_summary = json.dumps(stock_datasets, indent=2)

            prompt = load_prompt("stock_compare.txt").format(comp_summary=comp_summary)
            analysis_response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            analysis_text = analysis_response.text

            # Choose visual output format based on self.enable_widgets
            if self.enable_widgets:
                widget_data = {
                    "widgetSpec": {
                        "height": "600px",
                        "prompt": f"**Objective:** Build an interactive line chart comparing the 6-month normalized percentage return (%) of {', '.join(valid_symbols)}.\n **Data State:** {json.dumps(history_data)}\n **Inputs:** Checkboxes to toggle individual ticker visibility and timeframe control buttons (1M, 3M, 6M).\n **Behavior:** Render normalized % performance on the Y-axis (starting at 0% baseline) and dates on the X-axis with interactive hover tooltips."
                    }
                }
                visual_block = f"""
                <GenerateWidget height="600px">

                ```json
                {json.dumps(widget_data, indent=2)}
                ```
                </GenerateWidget>
                """
                return analysis_text, visual_block

            # Widgets disabled: return plain Markdown analysis with no widget block
            return analysis_text, ""

        except ClientError as e:
            return f"[ERROR] Gemini API Error: {str(e)}", ""
        except Exception as e:
            return f"[ERROR] Comparative analysis generation failed: {str(e)}", ""