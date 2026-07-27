# MSA 報告的繁體中文字型

正式 PDF 報告必須能正確呈現繁體中文。程式**不會**在找不到字型時
退回 Helvetica 輸出亂碼，而是回 `MSA_REPORT_FONT_MISSING`，讓部署
環境的缺漏在第一次產生報告時就被發現。

## 字型解析順序

`backend/services/msa_report.py` 的 `CJK_FONT_CANDIDATES` 依序尋找：

| 平台 | 路徑 |
|---|---|
| Windows | `C:/Windows/Fonts/msjh.ttc`（微軟正黑體） |
| Windows | `C:/Windows/Fonts/mingliu.ttc`（細明體） |
| Windows | `C:/Windows/Fonts/kaiu.ttf`（標楷體） |
| Linux | `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` |
| Linux | `/usr/share/fonts/truetype/wqy/wqy-microhei.ttc` |

## 為什麼這個目錄沒有字型檔

字型有各自的授權條款，不隨原始碼散布。Windows 開發機直接使用系統
內建字型；容器與 Linux 伺服器請自行安裝其中一種：

```bash
# Debian / Ubuntu
apt-get install -y fonts-noto-cjk

# 或
apt-get install -y fonts-wqy-microhei
```

## 驗證方式

```bash
venv/Scripts/python.exe -m pytest \
    backend/tests/test_services/test_msa_report.py -q -k pdf
```

`test_pdf_renders_traditional_chinese_extractably` 會確認產生的 PDF
可以抽取出繁體中文；`test_missing_cjk_font_refuses_to_produce_a_garbled_pdf`
則確認缺字型時是明確失敗而不是輸出亂碼。
