import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
import time
from retrying import retry
from requests_cache import CachedSession, SQLiteCache
from datetime import datetime
from tabulate import tabulate



class SECFinancialAnalyzer:
    def __init__(self):
        self.SYMBOL_LIST = ['AREB', 'TNON', 'BPTS', 'IBO', 'AEHL', "AAPL"]
        self.CIK_URL = "https://www.sec.gov/files/company_tickers.json"
        self.HEADERS = {
            'User-Agent': 'MyCompany Analytics/2.0 (analytics@mycompany.com)',
            'Accept-Encoding': 'gzip, deflate'
        }
        self.session = self._create_cached_session()
        self.INDUSTRY_BENCHMARKS = {
            'median_cash': 50_000_000,  # 行业现金中位数
            'cash_ratio_threshold': 0.25  # 现金/债务比率阈值
        }
        # 交易信号阈值
        self.TRADING_THRESHOLDS = {
            'high_cash_ratio': 1.5,      # 高现金比率阈值
            'medium_cash_ratio': 0.75,   # 中等现金比率阈值
            'low_cash_ratio': 0.25,      # 低现金比率阈值
            'safe_burn_rate': 12,        # 安全燃烧率(月)
            'warning_burn_rate': 6,      # 警告燃烧率(月)
            'critical_burn_rate': 3,     # 危急燃烧率(月)
            'small_cash': 10_000_000,    # 小型现金储备
            'micro_cash': 5_000_000      # 微型现金储备
        }
        
    def _create_cached_session(self):
        """创建带缓存的请求会话"""
        return CachedSession(
            cache_name='sec_cache',
            backend=SQLiteCache(),
            allowable_methods=('GET',),
            expire_after=3600,
            stale_if_error=True
        )
    
    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def load_cik_mapping(self):
        """加载CIK映射表"""
        try:
            response = self.session.get(self.CIK_URL, headers=self.HEADERS)
            response.raise_for_status()
            data = response.json()
            return {
                entry['ticker'].upper(): str(entry['cik_str']).zfill(10)
                for entry in data.values()
                if entry.get('ticker') and entry.get('cik_str')
            }
        except Exception as e:
            print(f"Error loading CIK mapping: {str(e)}")
            return {}

    def get_metric(self, facts, metric_names, unit='USD'):
        """获取财务指标"""
        for metric in metric_names:
            if metric in facts:
                entries = [e for e in facts[metric].get('units', {}).get(unit, []) 
                          if 'end' in e and 'val' in e]
                if entries:
                    return sorted(entries, key=lambda x: x['end'], reverse=True)[0]['val']
        return None

    def calculate_atm_risk(self, has_shelf, cash, debt, burn_rate=None):
        """专业ATM风险评估"""
        if not has_shelf:
            return "None", "No active shelf registration"
        
        cash_ratio = cash / debt if cash and debt else 0
        
        # 风险决策矩阵
        if not cash:
            return "Very High", "No cash reported"
        elif cash < 5_000_000:
            return "Very High", "Cash < $5M"
        elif cash < 10_000_000:
            return "High", "$5M ≤ Cash < $10M"
        elif cash_ratio < 0.1:
            return "High", f"Cash/Debt ratio < 10% ({cash_ratio:.1%})"
        elif cash_ratio < 0.25:
            return "Medium-High", f"10% ≤ Cash/Debt ratio < 25% ({cash_ratio:.1%})"
        elif burn_rate and burn_rate < 6:
            return "Medium-High", f"Burn rate < 6 months ({burn_rate:.1f} months)"
        else:
            return "Medium", "Adequate liquidity"

    def generate_trading_recommendations(self, data):
        """生成交易建议"""
        recommendations = {}
        
        # 获取关键指标
        symbol = data.get("Symbol")
        cash = data.get("Cash (USD)")
        debt = data.get("Debt (USD)")
        cash_ratio_str = data.get("Cash/Debt Ratio")
        burn_rate_str = data.get("Burn Rate (months)")
        risk_level = data.get("ATM Risk Level")
        has_shelf = data.get("Valid Shelf Filings", 0) > 0
        
        # 转换字符串到数值
        try:
            cash_ratio = float(cash_ratio_str.strip("%")) / 100 if cash_ratio_str and cash_ratio_str != "N/A" else None
        except (ValueError, AttributeError):
            cash_ratio = None
            
        try:
            burn_rate = float(burn_rate_str) if burn_rate_str and burn_rate_str != "N/A" else None
        except (ValueError, AttributeError):
            burn_rate = None
        
        # 默认建议
        recommendations["overall"] = "Hold - Insufficient data to make recommendation"
        recommendations["confidence"] = "Low"
        recommendations["reasons"] = []
        recommendations["strategy"] = "Monitor for more financial information"
        
        # 根据风险水平和财务状况生成建议
        if risk_level == "None" and cash and cash > self.TRADING_THRESHOLDS['small_cash']:
            recommendations["overall"] = "Hold/Accumulate"
            recommendations["confidence"] = "Medium"
            recommendations["reasons"].append("No dilution risk with adequate cash reserves")
            recommendations["strategy"] = "Conservative position sizing with tight stops"
            
        elif risk_level == "Very High":
            recommendations["overall"] = "Avoid/Sell"
            recommendations["confidence"] = "High"
            recommendations["reasons"].append(f"Very high ATM risk: {data.get('Risk Reason')}")
            recommendations["strategy"] = "Exit positions or avoid entry until financial situation improves"
            
        elif risk_level == "High":
            recommendations["overall"] = "Sell/Short-term only"
            recommendations["confidence"] = "Medium-High"
            recommendations["reasons"].append(f"High ATM risk: {data.get('Risk Reason')}")
            recommendations["strategy"] = "Day trading only with strict risk management, avoid swing positions"
            
        elif risk_level == "Medium-High":
            recommendations["overall"] = "Caution/Short-term"
            recommendations["confidence"] = "Medium"
            recommendations["reasons"].append(f"Medium-High ATM risk: {data.get('Risk Reason')}")
            recommendations["strategy"] = "Reduced position size, quick profit taking, tight stops"
            
        elif risk_level == "Medium":
            recommendations["overall"] = "Hold with caution"
            recommendations["confidence"] = "Medium"
            recommendations["reasons"].append("Moderate dilution risk")
            recommendations["strategy"] = "Normal position sizing with standard risk management"
        
        # 细分分析 - 现金/债务比率
        if cash_ratio is not None:
            if cash_ratio > self.TRADING_THRESHOLDS['high_cash_ratio']:
                recommendations["reasons"].append(f"Strong cash position relative to debt ({cash_ratio:.1%})")
                if recommendations["overall"] != "Avoid/Sell":
                    recommendations["overall"] = "Hold/Accumulate" 
            elif cash_ratio < self.TRADING_THRESHOLDS['low_cash_ratio']:
                recommendations["reasons"].append(f"Weak cash position relative to debt ({cash_ratio:.1%})")
                if "High" not in recommendations["overall"]:
                    recommendations["overall"] = "Reduce/Caution"
        
        # 细分分析 - 燃烧率
        if burn_rate is not None:
            if burn_rate < self.TRADING_THRESHOLDS['critical_burn_rate']:
                recommendations["reasons"].append(f"Critical burn rate of {burn_rate:.1f} months")
                if "Avoid" not in recommendations["overall"]:
                    recommendations["overall"] = "Reduce/Avoid"
            elif burn_rate < self.TRADING_THRESHOLDS['warning_burn_rate']:
                recommendations["reasons"].append(f"Concerning burn rate of {burn_rate:.1f} months")
                if "Caution" not in recommendations["overall"] and "Avoid" not in recommendations["overall"]:
                    recommendations["overall"] = "Caution/Reduce"
        
        # 分析货架注册情况
        if has_shelf:
            recommendations["reasons"].append("Active shelf registration increases dilution possibility")
            if "Avoid" not in recommendations["overall"] and "Sell" not in recommendations["overall"]:
                recommendations["strategy"] += "; Be prepared for potential offerings"
        
        # 分析现金绝对值
        if cash:
            if cash < self.TRADING_THRESHOLDS['micro_cash']:
                recommendations["reasons"].append(f"Extremely low cash reserves (${cash/1_000_000:.2f}M)")
                if "Avoid" not in recommendations["overall"]:
                    recommendations["overall"] = "Avoid/Sell"
            elif cash < self.TRADING_THRESHOLDS['small_cash']:
                recommendations["reasons"].append(f"Low cash reserves (${cash/1_000_000:.2f}M)")
                if "Caution" not in recommendations["overall"] and "Avoid" not in recommendations["overall"]:
                    recommendations["overall"] = "Caution/Reduce"
        
        # 短期挤压潜力分析
        if cash and cash < self.TRADING_THRESHOLDS['small_cash'] and has_shelf:
            squeeze_potential = "Low" if cash_ratio and cash_ratio > self.TRADING_THRESHOLDS['medium_cash_ratio'] else "High"
            if squeeze_potential == "High":
                recommendations["short_squeeze"] = "High short squeeze risk due to low cash and active shelf"
            else:
                recommendations["short_squeeze"] = "Moderate short squeeze risk despite active shelf"
        else:
            recommendations["short_squeeze"] = "Low short squeeze risk"
            
        return recommendations

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_company_data(self, symbol, cik_map):
        """获取公司完整数据"""
        try:
            cik = cik_map.get(symbol.upper())
            if not cik:
                return {"Symbol": symbol.upper(), "Error": "CIK not found"}

            # 获取申报文件
            filings = self.session.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=self.HEADERS
            ).json().get('filings', {}).get('recent', {})

            # Shelf文件分析
            shelf_filings = [
                {"form": form, "date": date, "accession": acc} 
                for form, date, acc in zip(
                    filings.get('form', []),
                    filings.get('filingDate', []),
                    filings.get('accessionNumber', [])
                )
                if form in {'S-3', 'S-3/A', 'S-3ASR', 'F-3', 'F-3ASR'}
            ]
            valid_shelf = [
                f for f in shelf_filings
                if pd.to_datetime(f['date']) > pd.Timestamp.now() - pd.DateOffset(years=3)
            ]

            # 获取财务数据
            facts = self.session.get(
                f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                headers=self.HEADERS
            ).json().get("facts", {}).get("us-gaap", {})

            cash = self.get_metric(facts, [
                'CashAndCashEquivalentsAtCarryingValue',
                'CashCashEquivalentsAndShortTermInvestments'
            ])
            
            debt = self.get_metric(facts, [
                'LongTermDebt',
                'LongTermDebtAndCapitalLeaseObligation'
            ])
            
            op_cash_flow = self.get_metric(facts, [
                'NetCashProvidedByUsedInOperatingActivities'
            ])
            
            # 计算关键指标
            cash_ratio = cash / debt if cash and debt else None
            burn_rate = (cash / abs(op_cash_flow)) * 3 if cash and op_cash_flow and op_cash_flow < 0 else None
            
            # 风险评估
            risk_level, risk_reason = self.calculate_atm_risk(
                has_shelf=bool(valid_shelf),
                cash=cash,
                debt=debt,
                burn_rate=burn_rate
            )

            result = {
                "Symbol": symbol.upper(),
                "CIK": cik,
                "Cash (USD)": cash,
                "Cash": f"${cash/1_000_000:.2f}M" if cash else "N/A",
                "Debt (USD)": debt,
                "Debt": f"${debt/1_000_000:.2f}M" if debt else "N/A",
                "Cash/Debt Ratio": f"{cash_ratio:.1%}" if cash_ratio else "N/A",
                "Burn Rate (months)": f"{burn_rate:.1f}" if burn_rate else "N/A",
                "Total Shelf Filings": len(shelf_filings),
                "Valid Shelf Filings": len(valid_shelf),
                "Last Shelf Date": max(f['date'] for f in valid_shelf) if valid_shelf else "None",
                "ATM Risk Level": risk_level,
                "Risk Reason": risk_reason,
                "Industry Cash Benchmark": "Above" if cash and cash > self.INDUSTRY_BENCHMARKS['median_cash'] else "Below",
                "Data Date": datetime.now().strftime("%Y-%m-%d")
            }
            
            # 生成交易建议
            trading_recs = self.generate_trading_recommendations(result)
            result.update({
                "Trading Recommendation": trading_recs["overall"],
                "Recommendation Confidence": trading_recs["confidence"],
                "Recommendation Reasons": trading_recs["reasons"],
                "Trading Strategy": trading_recs["strategy"],
                "Short Squeeze Risk": trading_recs["short_squeeze"] if "short_squeeze" in trading_recs else "Unknown"
            })
            
            return result
            
        except Exception as e:
            print(f"Error processing sec filings for {symbol}: {e}")
            return {
                "Symbol": symbol.upper(),
                "Error": str(e),
                "Data Date": datetime.now().strftime("%Y-%m-%d")
            }

    def print_results(self, results):
        """打印专业报表"""
        df = pd.DataFrame(results)
        
        # 选择要显示的列
        display_cols = [
            'Symbol', 'Cash', 'Debt', 'Cash/Debt Ratio', 
            'Total Shelf Filings', 'Valid Shelf Filings',
            'ATM Risk Level', 'Risk Reason'
        ]
        
        # 格式化打印
        print("\n" + "="*120)
        print("SEC ATM RISK ANALYSIS REPORT".center(120))
        print("="*120)
        print(tabulate(
            df[display_cols], 
            headers='keys', 
            tablefmt='grid',
            showindex=False,
            floatfmt=".2f"
        ))
        print("="*120)
        
        # 打印风险分布摘要
        risk_dist = df['ATM Risk Level'].value_counts()
        print("\nRISK DISTRIBUTION:")
        print(risk_dist.to_string())
        
        # 打印最高风险公司
        high_risk = df[df['ATM Risk Level'].isin(['Very High', 'High'])]
        if not high_risk.empty:
            print("\nHIGH RISK COMPANIES:")
            print(high_risk[['Symbol', 'ATM Risk Level', 'Risk Reason']].to_string(index=False))
        
        # 打印交易建议
        print("\n" + "="*120)
        print("TRADING RECOMMENDATIONS".center(120))
        print("="*120)
        for result in results:
            if "Error" in result:
                continue
            
            print(f"\n{result['Symbol']} - {result['Trading Recommendation']} (Confidence: {result['Recommendation Confidence']})")
            print(f"ATM Risk Level: {result['ATM Risk Level']}")
            
            print("Reasons:")
            for i, reason in enumerate(result['Recommendation Reasons'], 1):
                print(f"  {i}. {reason}")
                
            print(f"Trading Strategy: {result['Trading Strategy']}")
            print(f"Short Squeeze Risk: {result['Short Squeeze Risk']}")
            print("-" * 80)

    def generate_html_report(self, results):
        """生成专业HTML报告"""
        try:
            df = pd.DataFrame(results)
            
            # 基本HTML模板
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>SEC ATM Risk Analysis</title>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: sans-serif; margin: 20px; }}
                    table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                    th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                    th {{ background-color: #f8f9fa; position: sticky; top: 0; }}
                    tr:hover {{ background-color: #f5f5f5; }}
                    .very-high {{ background-color: #ffdddd; }}
                    .high {{ background-color: #ffe8d4; }}
                    .medium-high {{ background-color: #fff3cd; }}
                    .medium {{ background-color: #d4edda; }}
                    .section {{ margin-top: 40px; }}
                    .rec-avoid {{ color: #d9534f; }}
                    .rec-caution {{ color: #f0ad4e; }}
                    .rec-hold {{ color: #5bc0de; }}
                    .rec-buy {{ color: #5cb85c; }}
                </style>
            </head>
            <body>
                <h1>SEC ATM Risk Analysis Report</h1>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <div class="section">
                    <h2>Financial Risk Overview</h2>
                    {df[['Symbol', 'Cash', 'Debt', 'Cash/Debt Ratio', 'Burn Rate (months)', 'ATM Risk Level', 'Risk Reason']].to_html(classes='risk-table', index=False, escape=False)}
                </div>
                
                <div class="section">
                    <h2>Trading Recommendations</h2>
                    <table border="1" class="dataframe recommendation-table">
                        <thead>
                            <tr>
                                <th>Symbol</th>
                                <th>Recommendation</th>
                                <th>Confidence</th>
                                <th>Key Reasons</th>
                                <th>Strategy</th>
                                <th>Short Squeeze Risk</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            # 添加每只股票的交易建议
            for result in results:
                if "Error" in result:
                    continue
                
                # 确定推荐类别的颜色类
                rec_class = "rec-hold"
                if "Avoid" in result.get('Trading Recommendation', '') or "Sell" in result.get('Trading Recommendation', ''):
                    rec_class = "rec-avoid"
                elif "Caution" in result.get('Trading Recommendation', '') or "Reduce" in result.get('Trading Recommendation', ''):
                    rec_class = "rec-caution"
                elif "Buy" in result.get('Trading Recommendation', '') or "Accumulate" in result.get('Trading Recommendation', ''):
                    rec_class = "rec-buy"
                
                # 格式化原因列表
                reasons_html = "<ul>"
                for reason in result.get('Recommendation Reasons', []):
                    reasons_html += f"<li>{reason}</li>"
                reasons_html += "</ul>"
                
                html += f"""
                    <tr>
                        <td>{result.get('Symbol', '')}</td>
                        <td class="{rec_class}">{result.get('Trading Recommendation', '')}</td>
                        <td>{result.get('Recommendation Confidence', '')}</td>
                        <td>{reasons_html}</td>
                        <td>{result.get('Trading Strategy', '')}</td>
                        <td>{result.get('Short Squeeze Risk', '')}</td>
                    </tr>
                """
            
            # 完成HTML
            html += """
                        </tbody>
                    </table>
                </div>
            </body>
            </html>
            """
            
            # 添加风险高亮
            html = html.replace('>Very High<', ' class="very-high">Very High<')
            html = html.replace('>High<', ' class="high">High<')
            html = html.replace('>Medium-High<', ' class="medium-high">Medium-High<')
            html = html.replace('>Medium<', ' class="medium">Medium<')
            
            with open("output/sec_atm_risk_report.html", "w", encoding='utf-8') as f:
                f.write(html)
            print("\nProfessional HTML report generated: sec_atm_risk_report.html")
            
        except Exception as e:
            print(f"\nError generating HTML report: {str(e)}")

    def run_analysis(self):
        """执行完整分析流程"""
        print("Starting professional SEC ATM risk analysis...")
        start_time = time.time()
        
        cik_map = self.load_cik_mapping()
        if not cik_map:
            print("Failed to load CIK mappings. Exiting.")
            return None
        
        results = []
        for idx, symbol in enumerate(self.SYMBOL_LIST):
            print(f"\nProcessing {symbol} ({idx+1}/{len(self.SYMBOL_LIST)})...")
            result = self.get_company_data(symbol, cik_map)
            
            results.append(result)
            
            # 打印单公司结果
            print(f"\n{symbol} Analysis:")
            for k, v in result.items():
                if k not in ['CIK', 'Data Date', 'Recommendation Reasons']:
                    print(f"{k:>20}: {v}")
            
            # 特别打印建议原因列表
            if 'Recommendation Reasons' in result:
                print(f"{'Recommendation Reasons':>20}:")
                for i, reason in enumerate(result['Recommendation Reasons'], 1):
                    print(f"{' ':>22}{i}. {reason}")
            
            time.sleep(max(0.5, idx*0.1))  # 遵守SEC限速
        
        # 打印汇总结果
        self.print_results(results)
        
        # 生成HTML报告
        self.generate_html_report(results)
        
        print(f"\nAnalysis completed in {time.time()-start_time:.2f} seconds")
        if len(results) > 0:
            print(results)
        else: print("No SEC filings found for the provided symbols.")
        return results

if __name__ == "__main__":
    analyzer = SECFinancialAnalyzer()
    analyzer.SYMBOL_LIST = ['UPC']
    analysis_results = analyzer.run_analysis()