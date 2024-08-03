import pandas as pd
from bs4 import BeautifulSoup
import yfinance as yf
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
def make_graph(stock_data, revenue_data, stock):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("Historical Share Price", "Historical Revenue"), vertical_spacing = .3)
    stock_data_specific = stock_data[stock_data.Date <= '2021--06-14']
    revenue_data_specific = revenue_data[revenue_data.Date <= '2021-04-30']
    fig.add_trace(go.Scatter(x=pd.to_datetime(stock_data_specific.Date), y=stock_data_specific.Close.astype("float"), name="Share Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=pd.to_datetime(revenue_data_specific.Date), y=revenue_data_specific.Revenue.astype("float"), name="Revenue"), row=2, col=1)
    fig.update_xaxes(title_text="Date", row=1, col=1)
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Price ($US)", row=1, col=1)
    fig.update_yaxes(title_text="Revenue ($US Millions)", row=2, col=1)
    fig.update_layout(showlegend=False,
    height=900,
    title=stock,
    xaxis_rangeslider_visible=True)
    fig.show()
tesla = yf.Ticker("TSLA")
tesla_stock_data = tesla.history(period="max")
tesla_stock_data.reset_index(inplace=True)
url="https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/IBMDeveloperSkillsNetwork-PY0220EN-SkillsNetwork/labs/project/revenue.htm" 
data=requests.get(url).text
soup=BeautifulSoup(data,'html.parser')
tesla_revenue= pd.DataFrame(columns=["Date", "Revenue"])
for row in soup.find("tbody").find_all("tr"):
    col=row.find_all("td")
    date=col[0].text
    rev=col[1].text
    tesla_revenue=pd.concat([tesla_revenue,pd.DataFrame({"Date":[date],"Revenue":[rev]})],ignore_index= True)
tesla_revenue["Revenue"] = tesla_revenue['Revenue'].str.replace(',|\$',"", regex=True) #removes comma and dollar symbols in reveneue col
tesla_revenue.dropna(inplace=True) #to remove null or empty strings
tesla_revenue = tesla_revenue[tesla_revenue['Revenue'] != ""] #to remove null or empty strings
#print(tesla_revenue.tail())
make_graph(tesla_stock_data,tesla_revenue,'Tesla')

gamestop = yf.Ticker("GME")
gdata = gamestop.history(period="max")
gdata.reset_index(inplace=True)
url1="https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/IBMDeveloperSkillsNetwork-PY0220EN-SkillsNetwork/labs/project/stock.html"
data1=requests.get(url1).text
soup1=BeautifulSoup(data1,'html.parser')
game_revenue= pd.DataFrame(columns=["Date", "Revenue"])
for row in soup1.find("tbody").find_all("tr"):
    col=row.find_all("td")
    date=col[0].text
    rev=col[1].text
    game_revenue=pd.concat([tesla_revenue,pd.DataFrame({"Date":[date],"Revenue":[rev]})],ignore_index= True)
game_revenue["Revenue"] = game_revenue['Revenue'].str.replace(',|\$',"", regex=True) #removes comma and dollar symbols in reveneue col
game_revenue.dropna(inplace=True) #to remove null or empty strings
game_revenue = game_revenue[game_revenue['Revenue'] != ""] #to remove null or empty strings
make_graph(gdata,game_revenue,'GameStop')
