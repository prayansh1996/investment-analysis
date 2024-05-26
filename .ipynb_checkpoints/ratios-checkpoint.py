import pandas as pd
import re
import datetime
import yfinance as yf
import numpy as np
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from packages.mftool import Mftool

print("Loading schemes and eq_schemes")

schemes = pd.read_csv('./data/scheme_details.csv')
eq_schemes = pd.read_csv('./data/equity_schemes.csv')

mf = Mftool()

COLUMNS = ['schemeCode', 'schemeName', 'category', 'benchmark', 'symbol', 'shortName', 'longName']

YFINANCE_INDEX_CODES = {
    'NIFTY 50': '^NSEI',
    'NIFTY 100': '^CNX100',
    'S&P BSE 100': 'BSE-100.BO',
    'NIFTY Large Midcap 250': 'NIFTY_LARGEMID250.NS',
    'S&P BSE 250 Large MidCap': 'LMI250.BO',
}

class Measures:
    def __init__(self, fund):
        self.fund = fund
        self.scheme_details = SchemeDetails(fund)

    def rolling_returns(self, window, period = '15y', sampling_period = '1d'):
        days = convert_period_to_days(window)
        
        def absolute(x):
            x = x.reset_index()
            first = x.iloc[0]
            last = x.iloc[-1]
            # 1 is subtracted from days as window has one day less
            if first['date'] != subtract_days(last['date'], days-1):
                return np.nan

            # nav is in column 0
            return last[0]/first[0] - 1

        return self._rolling_returns(absolute, window, period, sampling_period)

    def cagr_rolling_returns(self, window, period = '15y', sampling_period = '1d'):
        days = convert_period_to_days(window)
        if days <= 365:
            return self.rolling_returns(self, window, period, sampling_period)

        years = int(days/365)
        
        def cagr(x):
            x = x.reset_index()
            first = x.iloc[0]
            last = x.iloc[-1]
            # 1 is subtracted from days as window has one day less
            if first['date'] != subtract_days(last['date'], days-1):
                return np.nan

            # nav is in column 0
            return (last[0]/first[0])**(1/years) - 1

        return self._rolling_returns(cagr, window, period, sampling_period)

    def _rolling_returns(self, lambda_func, window, period = '15y', sampling_period = '1d'):
        nav = self.scheme_details.get_nav(period)
        days = convert_period_to_days(window)

        if sampling_period == '1d':
            rolling = nav
        else:
            rolling = nav.resample(sampling_period, on='date').last()

        rolling['ratio'] = rolling.rolling(window=str(days)+'d', on='date')['nav'].apply(lambda x: lambda_func(x))
        rolling['percentage'] = rolling['ratio'].apply(lambda x: f'{x:.2%}')
        rolling = rolling.dropna()
        return self._populate_df_with_scheme_details(rolling)

    # To
    def _populate_df_with_scheme_details(self, df):
        scheme_detail = self.scheme_details.get_scheme_details()
        df.insert(0, 'symbol', scheme_detail['symbol'].iloc[0])
        df.insert(1, 'schemeName', scheme_detail['schemeName'].iloc[0])
        df.insert(2, 'category', scheme_detail['category'].iloc[0])
        # df.insert(4, 'benchmark', scheme_detail['benchmark'].iloc[0])
        return df
    
    def _market_capture_ratio(returns):
        """
        Function to calculate the upside and downside capture for a given set of returns.
        The function is set up so that the investment's returns are in the first column of the dataframe
        and the index returns are the second column.
        :param returns: pd.DataFrame of asset class returns
        :return: pd.DataFrame of market capture results
        """
    
        # initialize an empty dataframe to store the results
        df_mkt_capture = pd.DataFrame()
    
        # 1) Upside capture ratio
        # a) Isolate positive periods of the index
        up_market = returns[returns.iloc[:, -1] >= 0]
    
        # b) Geometrically link the returns
        up_linked_rets = ((1 + up_market).product(axis=0)) - 1
    
        # c) Calculate the ratio, multiply by 100 and round to 2 decimals to show in percent
        up_ratio = (up_linked_rets / up_linked_rets.iloc[-1] * 100).round(2)
    
        # 2) Downside capture ratio
        # a) Isolate negative periods of the index
        down_market = returns[returns.iloc[:, -1] < 0]
    
        # b) Geometrically link the returns
        down_linked_rets = ((1 + down_market).product(axis=0)) - 1
    
        # c) Calculate the ratio, multiply by 100 and round to 2 decimals to show in percent
        down_ratio = (down_linked_rets / down_linked_rets.iloc[-1] * 100).round(2)
    
        # 3) Combine to produce our final dataframe
        df_mkt_capture = pd.concat([up_ratio, down_ratio], axis=1)
    
        df_mkt_capture.columns = ['Upside Capture', 'Downside Capture']
    
        return df_mkt_capture


class SchemeDetails:
    def __init__(self, fund):
        self.fund = fund
        self.scheme_details = self._get_scheme_details()

    def get_scheme_details(self):
        return self.scheme_details

    def get_nav(self, period):
        return self._get_nav(period)

    def _get_scheme_details(self):
        if self.fund == 'NIFTY 50':
            return self._build_benchmark_details(self.fund)

        if self._is_benchmark():
            benchmark = eq_schemes['benchmark'][eq_schemes['benchmark'].str.startswith(self.fund, na=False)].iloc[0]
            benchmark = benchmark.replace('Total Return Index', '').strip()
            return self._build_benchmark_details(benchmark)

        scheme_name = None
        scheme_df = None
        if self._is_scheme_code():
            scheme_df = schemes[schemes['schemeCode'] == self.fund]
            scheme_name = scheme_df['shortName'].iloc[0]
        else:
            trunc = truncate_string(self.fund, 31)
            scheme_df = schemes[schemes['shortName'].str.startswith(trunc, na=False)]
            scheme_df = self._get_direct_growth_fund(scheme_df)
            scheme_name = self.fund
        assert len(scheme_df) == 1, f"DataFrame has {len(scheme_df)} rows, expected exactly 1 row."

        eq_scheme = eq_schemes[eq_schemes['scheme_name'].str.startswith(scheme_name, na=False)]
        scheme_df['benchmark'] = eq_scheme['benchmark'].iloc[0]
        scheme_df['schemeName'] = eq_scheme['scheme_name'].iloc[0]
        scheme_df['category'] = eq_scheme['category'].iloc[0]
        
        return scheme_df[COLUMNS]

    def _get_direct_growth_fund(self, scheme_df):
        dir_growth_df = scheme_df[scheme_df['longName'].str.contains('Dir Gr', na=False)]
        if len(dir_growth_df) > 0:
            return dir_growth_df

        non_idcw = scheme_df[~scheme_df['longName'].str.contains('IDCW', na=False)]
        if len(non_idcw) == 1:
            return non_idcw

        return scheme_df.head(1)

    def _is_benchmark(self):
        if self.fund == 'NIFTY 50':
            return True

        return len(eq_schemes[eq_schemes['benchmark'].str.startswith(self.fund, na=False)]) > 1

    def _build_benchmark_details(self, benchmark):
        benchmark_row = {}

        scheme_code = ''
        if benchmark in YFINANCE_INDEX_CODES:
            scheme_code = YFINANCE_INDEX_CODES[benchmark]
            
        benchmark_row['schemeCode'] = [scheme_code]
        benchmark_row['schemeName'] = [benchmark]
        benchmark_row['category'] = ['Index Fund']
        benchmark_row['benchmark'] = [benchmark]
        benchmark_row['symbol'] = [scheme_code]
        benchmark_row['shortName'] = [benchmark]
        benchmark_row['longName'] = [benchmark]

        return pd.DataFrame(benchmark_row)
    
    def _is_scheme_code(self):
        regex = re.compile('^[A-Z.0-9]+$')
        if (regex.match(self.fund)):
            return True
        return False

    def _get_nav(self, period):
        start_date = str(convert_period_to_date(period))

        end_date = str(datetime.date.today())
        symbol = self.scheme_details['symbol'].iloc[0]
        nav_df = yf.download(symbol, start_date, end_date)
        return nav_df.reset_index()[['Date', 'Adj Close']].rename(columns={'Date': 'date', 'Adj Close': 'nav'})


def convert_period_to_date(period):
    # Get the current date
    current_date = datetime.date.today()
    
    # Define regex patterns for years, months, and days
    year_pattern = re.compile(r'(\d+)y')
    month_pattern = re.compile(r'(\d+)m')
    day_pattern = re.compile(r'(\d+)d')
    
    # Find all matches in the period string
    years = year_pattern.findall(period)
    months = month_pattern.findall(period)
    days = day_pattern.findall(period)
    
    # Calculate the date difference
    years = int(years[0]) if years else 0
    months = int(months[0]) if months else 0
    days = int(days[0]) if days else 0
    
    # Subtract the time period from the current date
    new_date = current_date - relativedelta(years=years, months=months, days=days)
    
    return new_date

def convert_period_to_days(period):
    # Create a relativedelta object based on the date string
    start_date = convert_period_to_date(period)
    current_date = datetime.date.today()
    
    return (current_date-start_date).days

def subtract_days(date, days):
    return date - timedelta(days=days)
    
def truncate_string(s, max_length):
    return s[:max_length] if len(s) > max_length else s
