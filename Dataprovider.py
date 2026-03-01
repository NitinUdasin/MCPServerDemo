
import pandas as pd
import os,os.path
import json
import time
from dotenv import load_dotenv

class Dataproviders:

    def __init__(self):              
        load_dotenv()
        self._dataFolderPath = os.getenv("dataFolderPath")        

    def get_financial_year(self): 
         return int(os.getenv("CurrentFyear"))
    
    def get_ticker_path(self, tickerName):
        return os.path.join(self._dataFolderPath, tickerName)

    def get_stockname(self, tickerName):
        path = os.path.join(self._dataFolderPath, "CompanyList.csv")        
        df = pd.read_csv(path)
        result = df[df['Symbol'] == tickerName]

        if not result.empty:
            stock_name = result.iloc[0]['Stock Name']
            return stock_name                
        else:
            print(f"Symbol '{tickerName}' not found in the dataset.")
    
    def get_balancesheet(self, tickerName)->pd.DataFrame: 
        path = self.get_ticker_path(tickerName)
        return pd.read_csv(os.path.join(path, "BalanceSheet.csv"))
    
    def get_cashFlows(self, tickerName) ->pd.DataFrame: 
        path = self.get_ticker_path(tickerName)
        return pd.read_csv(os.path.join(path, "CashFlows.csv"))
    
    def get_profitLoss(self, tickerName)->pd.DataFrame: 
        path = self.get_ticker_path(tickerName)
        return pd.read_csv(os.path.join(path, "ProfitLoss.csv"))
    
    def get_quarterlyresults(self, tickerName)->pd.DataFrame: 
        path = self.get_ticker_path(tickerName)
        return pd.read_csv(os.path.join(path, "quarterlyresults.csv"))
    
    def get_Ratio(self, tickerName): 
        path = self.get_ticker_path(tickerName)
        file_path = os.path.join(path, "stock_ratios.json")
        with open(file_path, "r") as file:
            stock_ratios = json.load(file)    
            stock_data = {item["name"]: item["value"] for item in stock_ratios["top_ratios"]} 
        return stock_data
    
    

    def clear_data(self,df)->pd.DataFrame : 
        #df.columns = df.columns.str.replace(u'\xa0', '', regex=False).str.strip()

    # Clean and normalize 'Metric' column
        df['Metric'] = (
            df['Metric']
            .str.replace(r'[%\-\+]', '', regex=True)
            .str.encode('ascii', 'ignore')  # remove non-ASCII characters
            .str.decode('utf-8')
            .str.strip()
            .str.lower()
        )

        # Clean percentage signs and commas from values
        df.replace('%', '', regex=True, inplace=True)
        df = df.apply(lambda col: col.map(lambda x: str(x).replace(',', '').strip() if isinstance(x, str) else x))
        # df.iloc[:, 2:] = df.iloc[:, 1:].apply(pd.to_numeric, errors='coerce')

        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

        # Set Metric column as index
        df.set_index('Metric', inplace=True)

        return df
    

if __name__ == "__main__": 
    # Start the MCP server    
    dataproviders=Dataproviders()
    dataproviders.get_Ratio("BEL")
    