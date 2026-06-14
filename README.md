# Stock Theme Scanner｜AI 主題台股 / 美股選股程式

這是一個 GitHub-ready 的 Python 選股掃描器，專門掃描你指定的主題：

- AI
- 散熱 / 液冷
- AI 基建 / Data Center
- 存儲 / HBM / NAND / SSD
- 無塵室 / 半導體廠務
- 玻璃基板 / TGV / 雷射加工
- 先進封裝 / CoWoS / ABF
- 太空 / 衛星 / 國防航太
- 機器人 / 自動化
- AI 應用
- 電力 / 核電 / 電網 / 儲能

它會結合：

1. 技術面：MA、EMA、RSI、MACD、成交量、ATR、布林通道、相對強弱。
2. 型態：均線多頭、20 日高突破、VCP/收斂、旗型、杯柄候選、底部反轉候選。
3. 基本面：營收成長、獲利成長、毛利率、營益率、自由現金流、負債權益比、Forward P/E。
4. 資金面：量能、流動性、相對強弱、機構持股欄位。
5. 新聞催化：yfinance news；可選 Finnhub API 補強。
6. 風控：進場區、加碼區、停損、目標價、上漲/下跌空間、RR、建議部位比例。

> 重要：這不是保證獲利，也不是自動下單程式。它是「候選交易清單 + 風控規劃工具」。

---

## 1. 安裝

```bash
git clone <你的 repo url>
cd stock-theme-scanner
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

打開 `.env` 填入 Telegram：

```env
TELEGRAM_BOT_TOKEN=你的bot_token
TELEGRAM_CHAT_ID=你的chat_id
FINNHUB_API_KEY=可不填
```

請不要把 `.env` commit 到 GitHub。

---

## 2. 執行一次掃描

全部市場：

```bash
python main.py --once
```

只掃台股：

```bash
python main.py --once --market TW
```

只掃美股：

```bash
python main.py --once --market US
```

不發 Telegram，只產出本地報告：

```bash
python main.py --once --no-send
```

報告會輸出在：

```text
reports/scanner_report_YYYYMMDD_HHMM.md
```

---

## 3. 持續巡邏

```bash
python main.py --loop
```

掃描間隔在 `config.yaml`：

```yaml
runtime:
  scan_interval_seconds: 300
```

你之前想要 15 分鐘級甚至 5 分鐘級，自己架在本機 / VPS / Railway / Render / Docker 比 ChatGPT 自動任務更適合。

---

## 4. GitHub Actions 自動跑

專案已附：

```text
.github/workflows/scan.yml
```

預設會在：

- 台股盤前：台灣 08:45
- 美股盤前夏令時間：台灣 21:15

自動跑一次，並用 Telegram 通知。

在 GitHub repo 的 Settings → Secrets and variables → Actions 新增：

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `FINNHUB_API_KEY`，可選

冬令時間時，美股盤前 cron 要改成台灣 22:15 對應 UTC 14:15：

```yaml
- cron: "15 14 * * 1-5"
```

---

## 5. 如何新增股票池

打開 `config.yaml`，找到：

```yaml
universe:
  US:
    ai_infra:
      - NVDA
      - AMD
  TW:
    cooling:
      - 3017.TW
      - 3324.TW
```

直接新增 ticker 即可。

台股格式：

- 上市：`2330.TW`
- 上櫃：`8299.TWO`

美股格式：

- `NVDA`
- `AMD`
- `PLTR`

---

## 6. 你的持股 / 觀察名單

在 `config.yaml` 的 `portfolio` 填：

```yaml
portfolio:
  - ticker: ONDS
    market: US
    shares: 300
    avg_cost: 9.08
    stop: 9.03
    target1: 10.23
    target2: 10.98
    theme: space
```

每天報告會檢查：

- 是否繼續持有
- 是否加碼
- 是否減碼
- 是否停利
- 是否停損
- 是否移動停利

---

## 7. 分數邏輯

總分 100：

- 技術面：45
- 基本面：25
- 資金面：15
- 催化劑：15

信心等級：

- S：總分高、RR ≥ 2、未過熱、波動可控
- A：條件佳，但可能需要等回測
- B：可觀察，小部位或等更清楚訊號
- Watch：只觀察，不進場

程式會避免：

- 追高
- RSI 過熱
- ATR 太大
- 流動性太差
- RR 不足
- 只有題材但沒量價支撐

---


---

## 8. Top 10 股票池 + Top 3 推薦候選

新版報告預設會：

- 全股票池排名前 10 名全部列出。
- 只有全股票池前 3 名會標示為「⭐ 推薦候選」。
- 第 4～10 名只列為觀察名單，不視為正式買進建議。
可在 `config.yaml` 調整：

```yaml
runtime:
  top_pool_count: 10
  recommended_count_per_market: 3
```

如果你想改成前 20 名、只推薦前 5 名，就改成：

```yaml
runtime:
  top_pool_count: 20
  recommended_count_per_market: 5
```

## 9. 免責聲明

本工具只做研究、篩選、風控輔助，不保證資料完整、即時或正確，也不構成投資建議。實際交易請自行判斷並控制風險。
