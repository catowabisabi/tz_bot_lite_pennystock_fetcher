import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime




class ShortSqueezeScanner:
    """
    A comprehensive scanner for identifying short squeeze risks and opportunities in stocks.
    
    This class analyzes various factors that influence short squeeze potential including:
    - Float size and characteristics
    - Cash reserves relative to market capitalization
    - At-The-Money (ATM) offering risks
    - Short interest metrics
    - Technical resistance levels
    - Market sentiment indicators
    
    The scanner loads stock data dynamically, performs multi-factor risk analysis,
    generates signals for potential short positions, and provides human-readable
    analysis reports. It's designed to help traders identify both high-risk
    short squeeze scenarios to avoid and potential shorting opportunities.
    
    Attributes:
        data: DataFrame or None, stores the stock data for analysis
        current_price: float or None, the current market price of the stock
    """
    def __init__(self):
        """Initialize without binding data, which will be updated dynamically via setup_data"""
        self.data = None
        self.current_price = None  # Can be updated real-time from external API
    
    def setup_data(self, new_data: dict or pd.DataFrame):
        """
        Dynamically load new data (supports Dict or DataFrame input)
        
        Args:
            new_data: Dictionary or DataFrame containing stock data
        """
        if isinstance(new_data, dict):
            self.data = pd.DataFrame([new_data])  # Convert single stock data to DataFrame
        elif isinstance(new_data, pd.DataFrame):
            self.data = new_data.copy()  # Avoid modifying original data
        else:
            raise TypeError("Input must be dict or DataFrame")
        
        # Force type conversion (prevent JSON parsing errors)
        self._clean_data_types()
    
    def _clean_data_types(self):
        """Ensure numeric/date formats are correct"""
        # Handle numeric fields (including burn rate)
        numeric_cols = ['float', 'outstandingshares', 'cash (usd)', 'averagevolume3m', 
                    'debt (usd)', 'burn rate (months)']
        
        # Only process columns that actually exist
        existing_numeric_cols = [col for col in numeric_cols if col in self.data.columns]
        self.data[existing_numeric_cols] = self.data[existing_numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        # Handle dates (e.g., data date)
        if 'data date' in self.data.columns:
            self.data['data_date'] = pd.to_datetime(self.data['data date'], errors='coerce')
        
        # Handle "None" strings
        if 'last shelf date' in self.data.columns:
            self.data['last shelf date'] = self.data['last shelf date'].replace('None', pd.NaT)
    
    def update_price(self, current_price: float):
        """
        Update stock price in real-time (used for market cap/resistance calculations)
        
        Args:
            current_price: Current stock price
        """
        self.current_price = current_price
    
    def calculate_squeeze_risk(self, short_interest: float = None):
        """
        Calculate short squeeze risk score (requires external short interest data)
        
        This method evaluates multiple risk factors:
        1. Float liquidity risk (based on size of float)
        2. Float ratio risk (float as percentage of outstanding shares)
        3. Cash crisis indicator (low cash relative to market cap)
        4. Short interest density (if data available)
        
        Args:
            short_interest: Number of shares sold short (skips this factor if None)
        """
        # 1. Float liquidity risk
        if 'float' in self.data:
            self.data['float_risk'] = np.select(
                [self.data['float'] < 1e6, self.data['float'].between(1e6, 5e6, inclusive='left')],
                ['Extreme Risk (Float <1M)', 'High Risk (1M≤Float<5M)'],
                default='Acceptable'
            )
        
        # 2. New: Float/OutstandingShares ratio risk
        if 'float' in self.data and 'outstandingshares' in self.data:
            self.data['float_ratio'] = self.data['float'] / self.data['outstandingshares']
            self.data['float_ratio_risk'] = np.where(
                self.data['float_ratio'] < 0.4,
                'Warning (Float/Outstanding <40%)',
                'Normal'
            )
        
        # 3. Cash crisis indicator
        if self.current_price is not None and 'outstandingshares' in self.data and 'cash (usd)' in self.data:
            self.data['market_cap'] = self.data['outstandingshares'] * self.current_price
            self.data['cash/mcap'] = self.data['cash (usd)'] / self.data['market_cap']
            self.data['cash_crisis'] = (self.data['cash/mcap'] < 0.1).astype(int)
        
        # 4. Short interest crowding (if data available)
        if short_interest is not None and 'float' in self.data:
            self.data['short_ratio'] = short_interest / self.data['float']
            short_risk = (self.data['short_ratio'] > 0.3).astype(float)
        else:
            short_risk = 0  # Ignore this factor when data unavailable
        
        # Composite squeeze score (weights can be adjusted)
        squeeze_score_components = []
        weights = []
        
        if 'float_risk' in self.data:
            squeeze_score_components.append(0.5 * (self.data['float_risk'].str.contains('Extreme Risk').astype(float)))
            weights.append(0.5)
        
        if 'float_ratio_risk' in self.data:
            squeeze_score_components.append(0.2 * (self.data['float_ratio_risk'] == 'Warning (Float/Outstanding <40%)').astype(float))
            weights.append(0.2)
        
        squeeze_score_components.append(0.2 * short_risk)
        weights.append(0.2)
        
        if 'cash_crisis' in self.data:
            squeeze_score_components.append(0.1 * self.data['cash_crisis'])
            weights.append(0.1)
        
        if squeeze_score_components:
            total_weight = sum(weights)
            self.data['squeeze_score'] = sum(comp * (weight/total_weight) for comp, weight in zip(squeeze_score_components, weights))
        else:
            self.data['squeeze_score'] = 0
    
    def calculate_atm_risk(self):
        """
        Calculate ATM offering urgency
        
        Evaluates the risk of imminent At-The-Money stock offerings based on
        shelf registration dates and burn rate (how quickly company is depleting cash)
        """
        if 'last shelf date' in self.data.columns and not self.data['last shelf date'].isna().all():
            try:
                shelf_days_left = (pd.to_datetime(self.data['last shelf date']) - datetime.now()).dt.days
                # Ensure burn rate is numeric
                if pd.api.types.is_numeric_dtype(self.data['burn rate (months)']):
                    self.data['atm_urgency'] = (
                        self.data['burn rate (months)'] < (shelf_days_left / 30)
                    ).astype(int)
                else:
                    self.data['atm_urgency'] = 0
            except Exception as e:
                print(f"Error calculating ATM risk: {e}")
                self.data['atm_urgency'] = 0
        else:
            self.data['atm_urgency'] = 0
    
    def generate_short_signals(self, intraday_high: float = None):
        """
        Generate short selling signals (requires intraday high price)
        
        Combines multiple factors to identify potential shorting opportunities:
        1. Technical resistance strength
        2. Market sentiment overheating
        3. Low squeeze risk
        4. Imminent ATM offering
        
        Args:
            intraday_high: Day's highest price (for resistance level assessment)
        """
        # 1. Technical resistance strength
        if intraday_high is not None and self.current_price is not None:
            self.data['distance_to_high'] = (intraday_high - self.current_price) / intraday_high
            self.data['resistance_ok'] = (self.data['distance_to_high'] < 0.03)  # <3% from high
        else:
            self.data['resistance_ok'] = False  # Not satisfied without price data
        
        # 2. Market sentiment overheating (simple keyword matching)
        keywords = ['breakthrough', 'surge', 'milestone', 'bullish', 'buy rating']
        if 'suggestion' in self.data.columns:
            self.data['hype_score'] = self.data['suggestion'].str.count('|'.join(keywords))
        else:
            self.data['hype_score'] = 0
        
        # 3. Composite short signal (all conditions must be satisfied)
        self.data['short_signal'] = (
            (self.data['squeeze_score'] < 0.4) &     # Low squeeze risk
            (self.data['atm_urgency'] == 1) &        # ATM offering imminent
            (self.data['resistance_ok']) &           # Price near resistance
            (self.data['hype_score'] >= 3)           # Excessively optimistic news
        )
    
    def get_results(self, as_json: bool = False) -> pd.DataFrame or dict:
        """
        Return processed data (optional DataFrame or JSON format)
        
        Args:
            as_json: Whether to return JSON format
            
        Returns:
            DataFrame or dictionary containing analysis results
        """
        if self.data is None:
            return {} if as_json else pd.DataFrame()
        
        # Show only relevant columns
        display_cols = ['symbol', 'float_risk', 'float_ratio', 'float_ratio_risk', 'squeeze_score', 
                    'short_signal', 'cash/mcap', 'atm_urgency', 'hype_score']
        display_cols = [col for col in display_cols if col in self.data.columns]
        
        results = self.data[display_cols]
        
        if as_json:
            # Convert to dictionary and handle special types (like numpy types)
            json_results = results.to_dict(orient='records')[0]  # Assume single record
            
            # Convert numpy types to native Python types
            for k, v in json_results.items():
                if pd.api.types.is_float_dtype(type(v)):
                    json_results[k] = float(v)
                elif pd.api.types.is_integer_dtype(type(v)):
                    json_results[k] = int(v)
                elif pd.api.types.is_bool_dtype(type(v)):
                    json_results[k] = bool(v)
            
            return json_results
        else:
            return results
    
    def print_readable_analysis(self):
        """Generate human-readable analysis report"""
        if self.data is None or len(self.data) == 0:
            print("No data available for analysis")
            return
        
        stock = self.data.iloc[0]  # Get first stock record
        
        # Basic information
        print(f"\n[Stock Analysis Report] {stock['symbol']} - {stock.get('name', 'N/A')}")
        print("="*50)
        
        # Liquidity analysis
        print("\n[Liquidity Analysis]")
        print(f"- Float: {stock.get('float', 'N/A'):,} shares")
        print(f"- Float Ratio: {stock.get('float_ratio', 0)*100:.1f}% (of total outstanding shares)")
        print(f"- Risk Assessment: {stock.get('float_risk', 'N/A')}")
        if stock.get('float_ratio_risk', '') == 'Warning (Float/Outstanding <40%)':
            print("  ⚠️ Warning: Float ratio below 40%, may be susceptible to major shareholder manipulation")
        
        # Financial health
        print("\n[Financial Health]")
        if 'cash/mcap' in stock:
            print(f"- Cash/Market Cap Ratio: {stock['cash/mcap']*100:.1f}%", end=" ")
            if stock['cash/mcap'] < 0.1:
                print("⚠️ (Insufficient cash reserves)")
            else:
                print("(Adequate cash reserves)")
        
        # Short squeeze risk
        print("\n[Short Squeeze Risk Assessment]")
        print(f"- Composite Squeeze Risk Score: {stock.get('squeeze_score', 0)*100:.0f}/100")
        if stock.get('squeeze_score', 0) > 0.7:
            print("  🚨 High Risk: This stock has high short squeeze potential")
        elif stock.get('squeeze_score', 0) > 0.4:
            print("  ⚠️ Medium Risk: Monitor short squeeze potential")
        else:
            print("  ✅ Low Risk: Short squeeze potential is low")
        
        # Short signal analysis
        print("\n[Short Opportunity Assessment]")
        if stock.get('short_signal', False):
            print("  🔻 Strong Short Signal: Satisfies the following conditions:")
            reasons = []
            if stock.get('squeeze_score', 0) < 0.4:
                reasons.append("Low short squeeze risk")
            if stock.get('atm_urgency', 0) == 1:
                reasons.append("Potential imminent stock offering")
            if stock.get('resistance_ok', False):
                reasons.append("Price near resistance level")
            if stock.get('hype_score', 0) >= 3:
                reasons.append("Excessive market optimism")
            print("    - " + "\n    - ".join(reasons))
        else:
            print("  🔍 No clear short signal")
        
        # Market sentiment
        print("\n[Market Sentiment]")
        print(f"- News Hype Score: {stock.get('hype_score', 0)}/5")
        if stock.get('hype_score', 0) >= 3:
            print("  📢 Market sentiment is elevated, be cautious of excessive optimism")
        
        # Technical analysis
        if 'distance_to_high' in stock:
            print("\n[Technical Analysis]")
            print(f"- Distance to Day High: {stock['distance_to_high']*100:.1f}%")
        
        # Investment recommendation
        print("\n[Overall Recommendation]")
        if stock.get('short_signal', False):
            print("  🎯 Consider short opportunity, but set strict stop losses")
        elif stock.get('squeeze_score', 0) > 0.6:
            print("  ⚠️ Trade with caution, this stock has short squeeze risk")
        else:
            print("  📊 Neutral outlook, no clear trading signal")
        
        print("="*50)
    
    def run(self, new_stock_data, current_price=None, intraday_high=None, short_interest=None, as_json=False):
        """
        Execute complete analysis workflow
        
        This is the main entry point that runs the entire analysis pipeline:
        1. Setup data and current price
        2. Calculate all risk metrics
        3. Generate trading signals
        4. Return formatted results
        
        Args:
            new_stock_data: Dictionary or DataFrame with stock data
            current_price: Current stock price
            intraday_high: Day's highest price
            short_interest: Number of shares sold short (optional)
            as_json: Whether to return results as JSON
            
        Returns:
            DataFrame or dictionary with analysis results
        """
        self.setup_data(new_stock_data)
        self.update_price(current_price=current_price)
        
        # Calculate risk metrics
        self.calculate_squeeze_risk(short_interest=short_interest)
        self.calculate_atm_risk()
        
        # Generate short signals
        self.generate_short_signals(intraday_high=intraday_high)
        
        # Get results
        results = self.get_results(as_json=as_json)
        
        # Only show relevant columns
       # display_cols = ['symbol', 'float_risk', 'float_ratio', 'float_ratio_risk', 'squeeze_score', 
         #              'short_signal', 'cash/mcap', 'atm_urgency', 'hype_score']
        #display_cols = [col for col in display_cols if col in results.columns]
        
        #return results[display_cols]

        # Check if results are empty
        if (isinstance(results, dict) and not results) or \
        (hasattr(results, 'empty') and results.empty):
            return {'msg': 'no analysis or analysis already done and saved in database'}
        

        
        print(f"\n\n\n\nShort Squeeze Scanner Results: {results}\n")
        results.pop('_id', None)


        return results
    

if __name__ == "__main__":
    


    new_stock_data = {
    "symbol": "KTTA",
    "name": "Pasithea Therapeutics Corp",
    "listingexchange": "US",
    "securitytype": "Common Stock",
    "countrydomicile": "US",
    "countryincorporation": "US",
    "isin": "US70261F1030",
    "sector": "\"Consumer, Non-cyclical\"",
    "industry": "Biotechnology",
    "lastsplitinfo": "1 for 20",
    "lastsplitdate": "2021-06-08T00:00:00",
    "lotsize": None,
    "optionable": False,
    "earningspershare": None,
    "earningspersharettm": None,
    "forwardearningspershare": None,
    "nextearnings": None,
    "annualdividend": 0.0,
    "last12monthdividend": 0.0,
    "lastdividend": 0.0,
    "exdividend": None,
    "dividendfrequency": "None",
    "beta": None,
    "averagevolume3m": None,
    "turnoverpercentage": None,
    "bookvalue": None,
    "sales": None,
    "outstandingshares": 26143407,
    "float": 18037356,
    "suggestion": "Based on the news summaries provided, the market sentiment for Pasithea Therapeutics (NASDAQ: KTTA) shows clearly positive momentum, driven by several key factors:\n\n1. **Positive clinical trial results for new drug**: The company's drug PAS-004 has shown positive efficacy and good safety profile in treating advanced pancreatic cancer patients. A single case showed 9.8% tumor reduction, and the related clinical research has received approval from the safety review committee to accelerate progress. The high pERK inhibition rate is also viewed favorably by the market.\n2. **Clinical data release for Parkinson's disease**: The Phase 1 clinical trial released interim positive data, causing an immediate stock price increase.\n3. **Strong price volatility and significant upward movement**: The company's stock price rose over 20% following the news cycle, briefly triggering a circuit breaker, but quickly rebounded and continued upward after trading resumed.\n4. **Public offering financing information**: The company announced issuing new shares and warrants at $1.40, raising $5 million, indicating new capital inflow, but the offering may put pressure on the stock price. Attention should be paid to subsequent capital flows and selling pressure.\n\n### Risk Assessment & Trading Recommendations\nThe market currently has high expectations for the prospective drug efficacy, with the stock price clearly driven by positive news. In situations with extremely elevated sentiment and increased liquidity:\n\n- **Strongly advise against shorting** KTTA at this time. Attempting to short against the trend could lead to a squeeze and violent short-term increases. Even with fund financing or offering news, negative catalysts are unlikely to suppress the optimistic sentiment in the short term.\n- **Potential risks**: If subsequent clinical progress falls short of expectations or offering funds are quickly liquidated, market sentiment may rapidly deteriorate. If significant reversal signals appear, reassess shorting opportunities at that time.\n\n**Summary**: Currently, KTTA is experiencing a surge driven by positive catalysts and capital inflow. Shorting is not recommended; instead, wait for news digestion and market fever to cool before seeking potential shorting opportunities based on price action.\n\nPlease let me know if you'd like information about pressure levels or sentiment reversal points!",
    "cik": "0001841330",
    "cash (usd)": 6922729,
    "cash": "$6.92M",
    "debt (usd)": None,
    "debt": "N/A",
    "cash/debt ratio": "N/A",
    "burn rate (months)": "1.4",
    "total shelf filings": 3,
    "valid shelf filings": 3,
    "last shelf date": "2024-10-07",
    "atm risk level": "High",
    "risk reason": "$5M ≤ Cash < $10M",
    "industry cash benchmark": "Below",
    "data date": "2025-05-07",
    "trading recommendation": "Reduce/Avoid",
    "recommendation confidence": "Medium-High",
    "recommendation reasons": [
      "High ATM risk: $5M ≤ Cash < $10M",
      "Critical burn rate of 1.4 months",
      "Active shelf registration increases dilution possibility",
      "Low cash reserves ($6.92M)"
    ],
    "trading strategy": "Day trading only with strict risk management, avoid swing positions",
    "short squeeze risk": "High short squeeze risk due to low cash and active shelf"
  }

    # Create scanner instance
    scanner = ShortSqueezeScanner()

    """ analyzer = ChartAnalyzer(symbol)
    result = analyzer.run() """
    
    # Run analysis (assuming current price $1.2, day high $1.5, short interest 500k)
    results = scanner.run(
        new_stock_data=new_stock_data,
        current_price=1.2,
        intraday_high=1.5,
        short_interest=None,
        as_json=True
    )
    
    print(results)
    scanner.print_readable_analysis()