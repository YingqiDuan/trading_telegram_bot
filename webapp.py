# webapp.py
import plotly.graph_objs as go
from flask import Flask, render_template_string
import yfinance as yf
import pandas as pd
import requests

app = Flask(__name__)

# 获取股票数据的路由保持不变
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <!-- 引入 plotly.js -->
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
  <h3>{{ title }}</h3>
  <div id="chart"></div>
  <script>
    var trace = {
      x: {{ dates|safe }},
      open: {{ opens|safe }},
      high: {{ highs|safe }},
      low: {{ lows|safe }},
      close: {{ closes|safe }},
      type: 'candlestick',
      increasing: {line: {color: 'green'}},
      decreasing: {line: {color: 'red'}}
    };

    var data = [trace];

    var layout = {
      dragmode: 'zoom',
      title: '{{ title }}',
      xaxis: { title: 'Date' },
      yaxis: { title: 'Price' },
      margin: {l: 50, r: 50, t: 50, b: 50}  // 可根据需要调整边距
    };

    Plotly.newPlot('chart', data, layout);
  </script>
</body>
</html>
"""


@app.route("/chart/stock/<symbol>")
def stock_chart(symbol):
    """获取股票K线（示例使用 yfinance 获取1个月数据）"""
    data = yf.download(symbol, period="6mo", interval="1d")
    if data.empty:
        return "Invalid stock symbol!", 400

    data.reset_index(inplace=True)
    data.dropna(inplace=True)

    dates = data["Date"].dt.strftime("%Y-%m-%d").tolist()
    opens = data["Open"].squeeze().tolist()
    highs = data["High"].squeeze().tolist()
    lows = data["Low"].squeeze().tolist()
    closes = data["Close"].squeeze().tolist()

    return render_template_string(
        HTML_TEMPLATE,
        title=f"{symbol} Candlestick Chart",
        dates=dates,
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
    )


@app.route("/chart/crypto/<coin_id>")
def crypto_chart(coin_id):
    """获取加密货币K线（聚合为日线，数据来源 CoinGecko）"""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": 90}  # 获取90天数据
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return "Invalid crypto symbol!", 400
    data = r.json()

    # 使用价格数据生成DataFrame
    df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)

    # 按天重采样生成OHLC
    ohlc = df["price"].resample("1D").ohlc().dropna()
    ohlc.reset_index(inplace=True)

    dates = ohlc["timestamp"].dt.strftime("%Y-%m-%d").tolist()
    opens = ohlc["open"].tolist()
    highs = ohlc["high"].tolist()
    lows = ohlc["low"].tolist()
    closes = ohlc["close"].tolist()

    return render_template_string(
        HTML_TEMPLATE,
        title=f"{coin_id.capitalize()} Candlestick Chart",
        dates=dates,
        opens=opens,
        highs=highs,
        lows=lows,
        closes=closes,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
