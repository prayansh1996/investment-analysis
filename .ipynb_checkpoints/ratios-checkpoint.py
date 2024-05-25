import pandas as pd
import re
from packages.mftool import Mftool

schemes = pd.read_csv('./data/scheme_details.csv')
eq_schemes = pd.read_csv('./data/equity_schemes.csv')

mf = Mftool()

class Ratios:
    def Ratios(self, fund):
        self.fund = fund
    
    def market_capture_ratio(returns):
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
        self.scheme_details = self.get_scheme_details()

    def get_nav(self):
        pass
        
    def get_fund_type(self):
        pass

    def get_scheme_details(self):
        return self.scheme_details

    def _get_scheme_details(self):
        if self._is_benchmark():
            return None

        scheme_name = None
        scheme_df = None
        if self._is_scheme_code():
            scheme_df = schemes[schemes['schemeCode'] == self.fund]
            scheme_name = scheme_df['shortName'].iloc[0]
        else:
            trunc = truncate_string(self.fund, 32)
            scheme_df = schemes[schemes['shortName'].str.startswith(trunc, na=False)]
            scheme_df = scheme_df[schemes['longName'].str.contains('Dir Gr', na=False)]
            scheme_name = self.fund
        assert len(scheme_df) == 1, f"DataFrame has {len(scheme_df)} rows, expected exactly 1 row."

        print(scheme_name)
        benchmark = eq_schemes[eq_schemes['scheme_name'].str.startswith(scheme_name, na=False)]
        scheme_df['benchmark'] = benchmark['benchmark'].iloc[0]
        scheme_df['schemeName'] = benchmark['scheme_name'].iloc[0]
        
        return scheme_df[['schemeCode', 'symbol', 'schemeName', 'benchmark', 'shortName', 'longName']]

    def _is_scheme_code(self):
        regex = re.compile('^[A-Z.0-9]+$')
        if (regex.match(self.fund)):
            return True
        return False

    def _is_benchmark(self):
        return len(eq_schemes[eq_schemes['benchmark'].str.startswith(self.fund, na=False)]) > 1

    def _convert_period_to_date(period):
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
        new_date = current_date - datetime.timedelta(days=days)
        new_date = new_date.replace(year=new_date.year - years)
        
        # Handle month subtraction
        month_diff = new_date.month - months
        if month_diff <= 0:
            new_date = new_date.replace(year=new_date.year - 1)
            new_date = new_date.replace(month=month_diff + 12)
        else:
            new_date = new_date.replace(month=month_diff)
        
        return new_date

def truncate_string(s, max_length):
    return s[:max_length] if len(s) > max_length else s
