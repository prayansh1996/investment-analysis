import pandas as pd
import matplotlib.pyplot as plt

def rolling_returns(dfs, period='1m', figsize=(10, 6)):
    joined = pd.concat(dfs)
    joined.set_index('date', inplace=True)
    
    joined['percentage'] = joined['percentage'].str.rstrip('%').astype(float)
    joined = joined[['schemeName', 'percentage']].groupby('schemeName').resample(period).mean().reset_index()
    
    plt.figure(figsize=figsize)
    for scheme in joined['schemeName'].unique():
        subset = joined[joined['schemeName'] == scheme]
        plt.plot(subset['date'], subset['percentage'], label=scheme)
    
    # Customize plot
    plt.xlabel('Date')
    plt.ylabel('Percentage')
    plt.title('Rolling Returns')
    plt.legend()
    plt.grid(True)
    plt.show()