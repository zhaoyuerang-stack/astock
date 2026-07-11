Quant Research OS 前端設計與開發要求文檔
文檔版本：V1.0
適用系統：Quant Research OS — A 股全市場因子量化研究平台
前端定位：Alpha 審計駕駛艙，而不是普通量化數據大屏
推薦技術棧：Next.js 14 + React 18 + TypeScript + Tailwind CSS + Zustand + FastAPI API

1. 產品定位
Quant Research OS 前端不是用來展示炫酷圖表，也不是用來做普通股票交易看板。它的核心任務是幫助使用者快速回答以下問題：
今天是否可以交易？
今天的信號是否可信？
信號為什麼是這樣？
當前組合暴露了哪些風險？
策略是否仍然有效？
數據、模型、回測和治理是否存在問題？
AI 助手是否能幫助使用者發現風險，而不是替代決策？
因此，前端應設計成：
交易操作台 + 風險駕駛艙 + 信號審計系統 + 策略病歷台帳 + 因子研究實驗室 + 數據治理控制台
前端必須保持只讀原則。所有量化計算、因子計算、回測、門禁判定、策略裁決、數據校驗都應由後端完成，前端只負責展示、下鑽、對比、篩選、標註與審計閱讀。

2. 設計總原則
2.1 先結論，後證據
每個頁面第一屏都必須先給出明確結論，例如：
今日是否可交易
信號是否正式發布
組合風險等級
策略是否可部署
數據是否健康
系統治理是否通過
結論必須可以下鑽到證據。不能只展示「通過 / 不通過」標籤，必須展示判定依據、時間、數據版本、Spec Hash、影響範圍和人工復核建議。
2.2 任何數字都要可追溯
所有核心數字必須具備來源：
數據日期
策略版本
Spec Hash
Data Fingerprint
回測區間
成本口徑
信號日期
門禁狀態
最後更新時間
不允許出現無來源的收益率、Sharpe、最大回撤、IC、DSR、容量、滑點等數字。
2.3 防自欺是核心 UI 語言
系統前端要把「防自欺」產品化。頁面不應只展示收益，而要持續提示：
是否存在未通過門禁
是否存在未完成審計
是否存在數據滯後
是否存在未處理異常
是否存在過擬合嫌疑
是否存在小盤 / 低流動性 / ST 暴露
是否存在回測口徑與真實執行口徑偏差
是否存在樣本外塌陷
是否存在策略冗餘
2.4 AI 是審計助手，不是交易員
右側 AI 面板的定位是：
解釋、質疑、提醒、總結，不裁決，不下單，不給投資建議。
AI 面板底部必須固定展示：
AI 僅供研究與審計參考，不替代有效性裁決，不構成交易建議。
AI 可以回答：
為什麼今天是 BULL？
為什麼選這 25 隻股票？
哪些風險需要人工確認？
這個策略最脆弱的假設是什麼？
是否存在過擬合嫌疑？
哪些數據可能影響信號？
AI 不得展示：
強烈買入
必買
穩賺
保證收益
明確替代人工交易決策的語言

3. 全局布局要求
3.1 整體三欄布局
前端採用固定三欄布局：
┌──────────────┬────────────────────────────────────┬────────────────────┐
│ 左側導航欄    │ 中央主工作區                         │ 右側 AI 審計助手     │
│ 220px-260px  │ 自適應寬度                           │ 300px-360px        │
└──────────────┴────────────────────────────────────┴────────────────────┘
3.2 左側導航欄
左側導航欄負責全局模塊切換。導航不應按照技術目錄組織，而應按照使用者任務組織。
推薦導航：
今日操作台
組合風控
信號審計
策略台帳
因子研究
回測實驗
數據健康
系統治理
底部展示當前運行身份：
當前用戶：researcher
當前策略：illiquidity v3.1
系統版本：v2.3.0
數據日期：2026-06-23
左側導航要求：
當前頁高亮
使用圖標 + 文本
支持收起為窄欄
收起後保留圖標
鼠標懸停顯示 tooltip
不允許在左側放太多二級菜單
3.3 頂部狀態欄
中央區域頂部應有全局狀態欄，所有頁面保持一致。
內容包括：
今日：2026-06-24（星期三）
最新數據：2026-06-23
數據狀態：已更新 / 滯後 / 異常
下一次調倉：還有 12 個交易日
策略切換
更多操作
要求：
數據狀態用顏色標識
已更新：綠色
滯後：黃色
異常：紅色
策略切換必須顯示當前策略版本
所有頁面都能看到最新數據日期
3.4 右側 AI 審計助手
右側 AI 面板固定存在，隨頁面上下文變化。
標準結構：
AI 審計助手
狀態：在線 / 離線

[本頁風險摘要]
根據當前頁面生成 3-5 條重點

[審計結論]
用簡短語言說明是否存在明顯風險

[關鍵問題檢視]
可展開問題列表

[輸入框]
向 AI 提問

[底部免責]
AI 僅供研究與審計參考，不替代有效性裁決，不構成交易建議。
AI 面板要求：
不要顯示過長回答
優先展示風險與疑點
回答要關聯當前頁上下文
支持快捷問題
支持「查看詳細分析」跳轉
不允許生成交易指令

4. 視覺設計規範
4.1 整體風格
推薦風格：
深色研究終端風格
高信息密度
低裝飾
強狀態識別
少動效
強數字層級
類似金融風控系統，而不是散戶交易 App
4.2 色彩規範
基礎色：
背景色：#06111F / #081827 / #0B1C2F
卡片背景：#0E2238 / #10263D
邊框色：#1F3550
主文字：#E6EDF7
次文字：#8FA3BF
弱文字：#5F728A
狀態色：
通過 / 正常 / 收益：#35D06E
警告 / 中風險：#F6B73C
失敗 / 高風險 / 回撤：#FF5C5C
信息 / 可點擊：#3D7BFF
參考 / 中性：#9AA8BD
要求：
綠色只表示通過、正常、收益、可執行
紅色只表示風險、失敗、回撤、阻塞
黃色表示需要人工注意
藍色表示導航、鏈接、選中狀態
不允許多彩圖表干擾風控判斷
4.3 字體規範
建議：
中文：Inter / PingFang SC / Microsoft YaHei
英文與數字：Inter / JetBrains Mono
代碼與 Hash：JetBrains Mono
數字展示：
核心數字使用 28px - 36px
二級指標使用 18px - 24px
表格數字使用 13px - 14px
Hash / ID 使用等寬字體
4.4 卡片規範
卡片結構：
[標題 + 信息圖標]
[核心數字 / 狀態]
[輔助說明]
[較昨日變化 / 查看詳情]
卡片要求：
所有卡片有明確標題
所有狀態有顏色
所有關鍵卡片可點擊下鑽
卡片不使用強陰影
用邊框、間距、色塊建立層級

5. 頁面一：今日操作台
5.1 頁面目標
今日操作台是首頁，回答：
今天能不能交易？應該做什麼？為什麼？
使用者打開系統後，10 秒內必須理解：
今日信號狀態
市場狀態
建議動作
目標倉位
生產門禁是否通過
是否需要人工確認
今日主要風險
5.2 頁面結構
今日操作台
├── 今日交易決策
├── 決策摘要
├── 生產就緒度門禁檢查
├── 今日信號詳情
├── 模擬盤狀態
├── 策略績效摘要
└── 數據健康摘要
5.3 今日交易決策卡
核心字段：
系統建議：建倉買入 / 持有 / 清倉 / 空倉觀望
可執行狀態：可執行 / 需人工確認 / 已阻塞
市場制度：BULL / BEAR
目標倉位：118%
當前倉位：96%
Band Exposure：1.18
下一次調倉：12 個交易日後
要求：
系統建議用最大字號展示
「可執行」狀態必須緊貼建議
若被阻塞，應直接顯示阻塞原因
BULL / BEAR 要有明確顏色區分
倉位超過 100% 時要標註是否涉及槓桿或融資
5.4 決策摘要卡
字段：
發布狀態：正式發布 / 草稿 / 阻塞
發布時間：2026-06-24 07:30
部署 ID：deploy_20250624_v1
策略版本：illiquidity v3.1
Spec Hash：a1b2c3d4e5f6
數據指紋：d4e5f6a7b8c9
要求：
Spec Hash 和數據指紋必須可複製
點擊可進入信號審計頁
若版本身份不匹配，卡片變紅並阻塞交易
5.5 生產就緒度門禁檢查
展示五項：
Governance
Decay
Paper
Data
Trading Day
每項卡片展示：
狀態：通過 / 警告 / 失敗
說明：已註冊策略 / 未檢測到衰減 / 模擬盤正常 / 數據已更新 / 今日為交易日
最後檢查時間
交互要求：
點擊單項進入對應治理詳情
任一項失敗時首頁總狀態變為阻塞
任一項警告時首頁總狀態變為需人工確認
5.6 今日信號詳情
分為四個 tab：
持倉與交易
Top-25 候選
否決器過濾
執行風險
持倉與交易字段：
當前持倉數
持倉市值
建議買入數
建議賣出數
預計交易金額
Top-25 表格字段：
代碼
名稱
行業
因子得分
成交額
ADV 占用率
ST 狀態
操作
否決器過濾字段：
原始候選數
治理過濾數
基本面否決數
流動性否決數
風險否決數
通過後候選數
執行風險字段：
預計滑點
沖擊成本
ADV 占用率
擁擠度
容量充足度
執行風險評級
5.7 底部摘要卡
三張卡：
模擬盤狀態
策略績效
數據健康度
模擬盤狀態：
今日盈虧
總資產
可用資金
查看模擬盤
策略績效：
年化收益
Sharpe
最大回撤
DSR p 值
策略狀態：ACTIVE / REFERENCE
數據健康度：
數據新鮮度
PIT 通過率
質量報告狀態
查看詳情

6. 頁面二：組合風控
6.1 頁面目標
組合風控頁回答：
目前組合暴露了哪些風險？這些風險是否可接受？
這是整個系統最重要的風險頁之一，不應藏在二級頁面。
6.2 頁面結構
組合風控
├── 組合風險總覽
├── 風險暴露總覽
├── 因子 / 風險暴露圖
├── 行業配置分布
├── 集中度趨勢
├── 持倉風險明細
├── 壓力測試
└── AI 風險審計
6.3 組合風險總覽
核心卡片：
總風險等級：低 / 中 / 高
當前淨值
風險預算使用率
容量使用率
預估滑點
要求：
風險等級必須明顯
風險預算使用率超過 80% 顯示黃色
超過 100% 顯示紅色
容量使用率必須與策略容量上限關聯
6.4 風險暴露總覽
卡片：
小盤暴露
流動性暴露
ST 暴露
行業集中度
單票集中度
換手壓力
每張卡片展示：
暴露值
風險等級
較昨日變化
要求：
小盤暴露和流動性暴露是核心
ST 暴露必須單獨展示
換手壓力應和交易成本聯動
6.5 持倉風險明細表
字段：
代碼
名稱
權重
ADV 使用率
是否 ST
流動性得分
預估滑點 bps
風險暴露
風險標籤示例：
流動性緊張
ST 標的
ADV 使用過高
行業集中
單票集中
要求：
高風險行用紅色或黃色標註
支持按風險等級排序
支持只看異常持倉
支持導出 CSV
6.6 壓力測試區
場景：
連續跌停
流動性凍結
風格反轉
行業沖擊
開盤跳空風險
利率上行 50bp
字段：
場景
情景描述
組合損益估算
最大回撤估算
風險等級
要求：
壓力測試不做成精確預測，而是風險提示
結果要明確標註「估算」
高風險場景置頂

7. 頁面三：信號審計
7.1 頁面目標
信號審計頁回答：
今天的信號為什麼可信？它經過了哪些檢查？哪些地方需要人工確認？
這是將「信號」變成「證據包」的頁面。
7.2 頁面結構
信號審計
├── 信號身份卡
├── 發布審計
├── 信號生成流水線
├── Top-25 執行清單
├── 執行風險與可行性
├── 元數據
└── 數據指紋
7.3 信號身份卡
字段：
信號日期
市場狀態
建議動作
Band Exposure
發布狀態
Spec Hash
要求：
一眼看到信號是否正式發布
Spec Hash 必須展示
信號日期與最新數據日期必須分離展示
若信號日期與數據日期不合理，直接提示
7.4 發布審計
門禁：
治理合規
Decay 檢查
Paper 帳戶檢查
數據新鮮度
交易日校驗
字段：
狀態
說明
最新檢查時間
阻塞原因
要求：
全部通過才顯示「正式發布」
任意失敗則顯示草稿或阻塞
點擊門禁可查看完整證據
7.5 信號生成流水線
展示流程：
候選池 325 隻
→ 否決過濾 67 隻
→ Top-25 25 隻
→ 執行清單 25 隻
要求：
每一步展示輸入數、輸出數、過濾原因
Top-25 節點高亮
支持查看被否決股票與否決原因
7.6 Top-25 執行清單
字段：
排名
代碼
名稱
因子綜合得分
建議買入金額
行業
ST 狀態
關鍵理由
關鍵理由應包含因子貢獻：
流動性改善
低波動
動量反轉
估值修復
風險溢價
要求：
表格支持展開每隻股票的因子分解
ST 股票必須顯著標記
建議買入金額必須顯示 RMB
不允許只展示股票代碼
7.7 執行風險與可行性
卡片：
漲停買不進
跌停賣不出
停牌
一字板
預期成交滑點
字段：
數量
占比
預估影響金額
要求：
執行風險不能只在回測頁展示，必須出現在信號審計頁
任何不可成交風險都應進入 AI 復核清單
7.8 元數據與數據指紋
字段：
部署 ID
策略版本
策略類型
創建時間
創建人
數據日期
Spec Hash
數據集版本
因子庫版本
代碼版本 / Git Commit
要求：
所有字段可複製
支持下載審計報告
支持查看完整指紋詳情

8. 頁面四：策略台帳
8.1 頁面目標
策略台帳頁回答：
系統裡有哪些策略？哪些可用？哪些只是參考？哪些已退役或證偽？每個策略的證據鏈是什麼？
策略台帳應該像策略病歷系統，而不是普通列表。
8.2 頁面結構
策略台帳
├── 策略統計
├── 策略列表
├── 策略詳情
├── 策略身份證
├── 核心假設
├── 適用市場
├── 失效信號
├── 生命週期
├── 九門禁
└── 審計與事件日誌
8.3 策略統計卡
字段：
總家族數
在冊策略
參考策略
退役策略
今日預警
要求：
數字大卡展示
支持點擊快速篩選
今日預警必須高亮
8.4 策略列表
字段：
收藏
策略名稱
家族
版本
狀態
年化收益
Sharpe
最大回撤
DSR
容量
相關性
最後評審
狀態枚舉：
ACTIVE
REFERENCE
CANDIDATE
FALSIFIED
RETIRED
要求：
ACTIVE 綠色
REFERENCE 藍色
CANDIDATE 灰色
FALSIFIED 紅色
RETIRED 紫色或灰色
支持狀態篩選、家族篩選、市場篩選、標籤篩選
支持只看我的策略
8.5 策略詳情
選中策略後，下方展示策略詳情。
策略身份證：
策略代碼
所屬家族
版本
創建人
創建日期
上次重大變更
負責人
策略標籤
投資方向
標的範圍
默認組合
文檔鏈接
核心假設：
為什麼這個 alpha 應該存在？
收益來自哪個市場結構？
它依賴什麼條件？
適用市場：
A 股全市場
中高流動性股票
牛市 / 震盪市 / 熊市
是否剔除 ST
是否支持港股或跨市場
失效信號：
動量因子 IC 連續 20 日 < -0.02
市場成交額低於 20 日均值 -30%
波動率 > 40 且趨勢指標反轉
8.6 生命週期
展示策略從構思到上線的時間線：
構思
研究
回測完成
上線試運行
正式上線
最近評審
下次評審
要求：
用 timeline 展示
已完成節點綠色
當前節點高亮
未完成節點灰色
8.7 九門禁
展示九道門：
1. 數據完整性
2. 因子有效性
3. 邏輯合理性
4. 回測穩健性
5. 交易可執行性
6. 風險可控性
7. 容量與沖擊
8. 經濟學意義
9. 文檔與可複現性
字段：
門禁名稱
狀態
最近檢查時間
證據鏈接
失敗原因
要求：
不應只展示 8/9
必須能看到哪一門沒過
沒過的門禁必須展示原因
支持查看門禁定義
8.8 審計與事件日誌
字段：
時間
事件類型
事件描述
觸發人
影響範圍
附件
操作
事件類型：
定期評審
參數變更
數據更新
模型變更
預警觸發
退役判定
治理審計
要求：
日誌不可刪除
支持查看附件
支持導出策略證據包

9. 頁面五：因子研究
9.1 頁面目標
因子研究頁回答：
某個因子是否真的有預測力？它是否穩定？是否只是暴露於其他風格？成本後還剩多少？
9.2 頁面結構
因子研究
├── 因子總覽指標
├── 因子庫
├── 當前因子詳情
├── IC 時序
├── 分組年化收益
├── 分組單調性
├── 中性化表現
├── 換手與成本敏感性
├── 風格相關性
└── 實驗隊列
9.3 因子總覽
卡片：
因子數量
今日實驗數
平均 IC
中性化 ICIR
數據覆蓋率
要求：
因子數量展示總庫規模
今日實驗數展示進行中與待處理
平均 IC 必須標註是否中性化
數據覆蓋率低於 95% 顯示警告
9.4 因子庫
左側因子庫按類型分組：
流動性
動量
價值
質量
否決器
每個因子展示：
因子名
IC
ICIR
要求：
支持搜索
支持中英文搜索
支持按 IC / ICIR 排序
當前選中因子高亮
否決器因子與選股因子要區分
9.5 當前因子詳情
字段：
因子名稱
因子 ID
作者
創建時間
數據起點
覆蓋範圍
適用市場
因子類型
Tab：
因子表現
分組收益
單調性
中性化表現
換手與成本
風格相關性
因子信息
9.6 IC 時序
字段：
IC
ICIR
年化 IC
t 統計
勝率
要求：
展示 IC 時序曲線
0 軸明顯
支持近 1 年 / 近 2 年 / 近 3 年 / 全部
必須標註是否 Newey-West 校正
9.7 分組收益
展示等權分組：
Top 10%
Top 30%
中性組
Bottom 30%
Bottom 10%
要求：
展示分組累計收益
展示多空組合
展示單調性表格
若單調性弱，AI 面板必須提示
9.8 換手與成本敏感性
字段：
年化換手
持有期
沖擊成本
年化 IR
成本矩陣：
成本 bps：0 / 5 / 10 / 15 / 20 / 25 / 30
對應年化 IR
要求：
成本後顯著衰減必須標黃或標紅
高換手因子必須顯示成本風險
9.9 風格相關性
展示矩陣：
市值
閃崩
動量
盈利
價值
波動率
槓桿率
流動性
要求：
高相關性用熱力圖展示
超過 0.7 標記為高相關
AI 面板提示可能只是風格暴露
9.10 實驗隊列
字段：
優先級
假設 / 因子
假設描述
影響因子
覆蓋範圍
信號類型
當前階段
狀態
創建人
創建時間
階段：
L0
L1
L2
L3
要求：
顯示每個實驗處於哪一級
支持查看實驗詳情
支持失敗原因展示
不允許只保留成功實驗

10. 頁面六：回測實驗
10.1 頁面目標
回測實驗頁回答：
策略在歷史上表現如何？是否穩健？樣本外是否塌陷？真實執行後收益剩多少？
10.2 頁面結構
回測實驗
├── 回測摘要
├── 淨值曲線
├── 回撤曲線
├── 回測口徑 vs 真實口徑
├── 樣本分段
├── 參數敏感性
├── 年度收益與壓力期
├── 交易統計與換手
└── AI 過擬合風險評估
10.3 回測摘要
卡片：
年化收益
Sharpe
最大回撤
Calmar
換手
成本後收益
要求：
必須展示成本後收益
必須展示最大回撤
不允許只突出年化收益
回測區間必須可見
10.4 淨值曲線
內容：
策略淨值
基準淨值
最大回撤區域
要求：
可切換全部 / 近 1 年 / 近 2 年 / 近 3 年 / 近 5 年
回撤區域用背景或面積圖展示
基準曲線不可省略
10.5 回測口徑 vs 真實口徑
字段：
回測口徑：T+1 收盤
真實口徑：T+1 開盤
年化收益
Sharpe
最大回撤
年化換手
成本後收益
差異
要求：
這是關鍵模塊，必須展示
差異為負時用紅色
必須解釋差異來源：隔夜跳空、不可成交、滑點、成本
10.6 參數敏感性
熱力圖字段：
持倉上限
信號閾值
目標指標：年化收益 / Sharpe / Calmar / 最大回撤
要求：
最優區域用標記展示
不允許只展示最優點
需要顯示參數平台區是否穩定
過於尖銳的最優點要提示過擬合嫌疑
10.7 樣本分段
Tab：
IS
OOS
Walk-Forward
壓力期
字段：
時間段
年化收益
Sharpe
最大回撤
勝率
要求：
OOS 表現不能藏起來
壓力期表現必須單獨展示
若 OOS 明顯低於 IS，顯示黃色或紅色警告
10.8 交易統計與換手
字段：
年化換手
平均持倉天數
勝率
平均盈虧比
平均單票收益
交易成本占比
要求：
高換手必須聯動成本風險
月度 / 年度換手可切換
成本占比超過閾值顯示警告

11. 頁面七：數據健康
11.1 頁面目標
數據健康頁回答：
今天的信號會不會被數據問題影響？
11.2 頁面結構
數據健康
├── 數據健康總覽
├── 數據管道狀態
├── 質量檢查報告
├── 數據源健康
├── 異常與問題
└── AI 數據影響評估
11.3 數據健康總覽
卡片：
最新交易日
覆蓋股票數
PIT 通過率
質量評分
更新延遲
數據源狀態
要求：
最新交易日必須明顯
T-1 / T-2 必須顯示
PIT 通過率低於閾值必須警告
更新延遲超過 30 分鐘標黃，超過 60 分鐘標紅
11.4 數據管道狀態
管道節點：
價格
日頻基礎
資金流向
財務數據
事件數據
指數數據
宏觀數據
每個節點字段：
狀態
完成時間
是否成功
是否延遲
是否失敗
要求：
成功綠色
運行中藍色
延遲黃色
失敗紅色
支持查看詳情
11.5 質量檢查報告
檢查項：
負價
OHLC 一致性
異常跳變
停牌缺失識別
科創板成交量歸一化
復權因子突變
字段：
狀態
異常數
異常比例
要求：
真問題與 A 股正常現象區分展示
異常數量必須可點擊查看明細
嚴重異常會影響今日信號
11.6 數據源健康
字段：
數據源
域
最新可用日
更新延遲
失敗率
狀態
數據源示例：
Wind
聚源
同花順
中證指數公司
國家統計局
財聯社
交易所接口
要求：
支持多源對比
單一數據源故障不應直接判定全局失敗
數據源狀態影響右側 AI 風險摘要
11.7 異常與問題
字段：
發現時間
域
異常類型
影響範圍
嚴重度
狀態
操作
要求：
支持查看
支持標記已修復
支持按嚴重度排序
最近 7 日問題默認展示

12. 頁面八：系統治理
12.1 頁面目標
系統治理頁回答：
系統本身是否可靠？架構、CI、Registry、Spec Hash、策略身份是否一致？
12.2 頁面結構
系統治理
├── 部署狀態
├── CI 守衛通過率
├── 當前策略身份
├── Registry 一致性
├── 今日告警
├── 架構與依賴拓撲
├── CI 守衛列表
├── 治理九宮格
├── Registry 完整性
├── Spec Hash 身份
└── 近期審計與事件日誌
12.3 部署狀態
卡片：
部署狀態：生產就緒 / 部分異常 / 阻塞
部署版本
部署時間
要求：
生產就緒用綠色
有阻塞項時整頁狀態變紅
部署版本必須可複製
12.4 CI 守衛通過率
字段：
CI 通過率
今日通過數
總守衛數
較昨日變化
要求：
顯示小趨勢線
不只展示百分比，還要展示失敗項
失敗項必須可下鑽
12.5 架構與依賴拓撲
展示：
data_lake → factors → core.engine → strategies/factory → registry → production
要求：
每一層顯示健康狀態
顯示版本
顯示延遲
顯示依賴關係
若發生反向依賴或非法 import，直接高亮
12.6 CI 守衛列表
字段：
守衛腳本
說明
狀態
上次運行時間
守衛示例：
check_layer_deps.py
check_lake_writers.py
check_no_force_promote.py
check_registry_evidence.py
holdout_compliance.py
control_exceptions.py
data_full_forbidden.py
要求：
通過綠色
失敗紅色
失敗項展示原因
支持查看全部守衛詳情
12.7 治理九宮格
展示 9 個治理項：
數據新鮮度
樣本外合規
依賴完整性
Spec Hash 鎖定
Registry 證據齊全
回滾可行性
風控閾值合規
影子運行一致性
發布審批閉環
要求：
每一項有狀態
全部通過才顯示 100%
點擊可查看定義與證據
12.8 近期審計與事件日誌
字段：
時間
級別
類別
事件
涉及範圍
觸發者
結果
級別：
P0
P1
P2
要求：
P0 紅色
P1 黃色
P2 藍色或灰色
支持查看全部日誌
不允許刪除日誌

13. 組件設計要求
13.1 核心組件列表
必須沉澱以下可復用組件：
AppShell
Sidebar
TopStatusBar
RightAuditPanel
StatusCard
MetricCard
GateCard
RiskBadge
HashCopy
EvidenceLink
DataFreshnessBadge
StrategyStatusBadge
PageHeader
SectionCard
AuditTimeline
RiskTable
FactorChart
BacktestChart
Heatmap
PipelineStepper
EmptyState
LoadingSkeleton
ErrorBoundary
13.2 StatusCard
用途：展示核心狀態。
Props：
type StatusCardProps = {
  title: string
  status: 'success' | 'warning' | 'danger' | 'neutral'
  value: string | number
  subtitle?: string
  delta?: string
  onClick?: () => void
}
13.3 MetricCard
用途：展示數值指標。
Props：
type MetricCardProps = {
  label: string
  value: string | number
  unit?: string
  delta?: number
  deltaLabel?: string
  intent?: 'positive' | 'negative' | 'neutral'
  precision?: number
}
13.4 GateCard
用途：展示門禁狀態。
Props：
type GateCardProps = {
  name: string
  status: 'passed' | 'warning' | 'failed' | 'pending'
  summary: string
  lastCheckedAt?: string
  evidenceUrl?: string
}
13.5 RiskBadge
用途：展示風險等級。
Props：
type RiskBadgeProps = {
  level: 'low' | 'medium' | 'high' | 'blocked'
  label?: string
}
13.6 HashCopy
用途：展示並複製 Spec Hash、Data Fingerprint、Git Commit。
Props：
type HashCopyProps = {
  value: string
  label?: string
  short?: boolean
}

14. API 數據要求
14.1 今日操作台 API
建議端點：
GET /api/dashboard/today
返回字段：
type TodayDashboardResponse = {
  date: string
  latestDataDate: string
  dataStatus: 'fresh' | 'stale' | 'error'
  strategy: {
    family: string
    version: string
    status: string
    specHash: string
  }
  decision: {
    action: 'buy' | 'hold' | 'sell' | 'cash'
    executable: boolean
    reason: string
    regime: 'bull' | 'bear'
    targetExposure: number
    currentExposure: number
    bandExposure: number
    nextRebalanceDays: number
  }
  readiness: GateStatus[]
  signal: {
    published: boolean
    publishTime?: string
    deploymentId: string
    dataFingerprint: string
  }
}
14.2 信號審計 API
GET /api/signals/:date/audit
返回：
type SignalAuditResponse = {
  signalDate: string
  marketRegime: string
  action: string
  bandExposure: number
  publishStatus: string
  specHash: string
  gates: GateStatus[]
  pipeline: {
    name: string
    inputCount: number
    outputCount: number
    rejectedCount?: number
  }[]
  top25: SignalCandidate[]
  executionRisk: ExecutionRisk
  metadata: SignalMetadata
}
14.3 組合風控 API
GET /api/portfolio/risk
返回：
type PortfolioRiskResponse = {
  riskLevel: 'low' | 'medium' | 'high'
  nav: number
  riskBudgetUsage: number
  capacityUsage: number
  estimatedSlippageBps: number
  exposures: {
    smallCap: number
    liquidity: number
    st: number
    industryConcentration: number
    singleNameConcentration: number
    turnoverPressure: number
  }
  holdings: HoldingRisk[]
  stressTests: StressTestResult[]
}
14.4 策略台帳 API
GET /api/strategies
GET /api/strategies/:id
策略列表字段：
type StrategyListItem = {
  id: string
  name: string
  family: string
  version: string
  status: 'ACTIVE' | 'REFERENCE' | 'CANDIDATE' | 'FALSIFIED' | 'RETIRED'
  annualReturn: number
  sharpe: number
  maxDrawdown: number
  dsrPValue: number
  capacity: number
  correlation: number
  lastReviewDate: string
}
策略詳情字段：
type StrategyDetail = {
  identity: StrategyIdentity
  thesis: string
  applicableMarket: string[]
  failureSignals: string[]
  lifecycle: LifecycleEvent[]
  nineGates: GateStatus[]
  auditLogs: AuditLog[]
}
14.5 因子研究 API
GET /api/factors
GET /api/factors/:id
字段：
type FactorDetail = {
  id: string
  name: string
  category: string
  ic: number
  icir: number
  neutralizedIcir: number
  coverage: number
  icSeries: TimeSeriesPoint[]
  groupReturns: GroupReturn[]
  monotonicity: MonotonicityTable
  costSensitivity: CostSensitivity
  styleCorrelation: CorrelationMatrix
}
14.6 回測實驗 API
GET /api/backtests/:id
字段：
type BacktestResponse = {
  summary: {
    annualReturn: number
    sharpe: number
    maxDrawdown: number
    calmar: number
    turnover: number
    netAfterCost: number
  }
  navSeries: TimeSeriesPoint[]
  drawdownSeries: TimeSeriesPoint[]
  theoreticalVsReal: {
    theoretical: PerformanceStats
    realExecution: PerformanceStats
    diff: PerformanceStats
  }
  segments: SegmentPerformance[]
  parameterSensitivity: HeatmapData
  yearlyReturns: YearlyReturn[]
  tradeStats: TradeStats
}
14.7 數據健康 API
GET /api/data/health
字段：
type DataHealthResponse = {
  latestTradeDate: string
  stockCoverage: number
  pitPassRate: number
  qualityScore: number
  updateDelayMinutes: number
  sourceStatus: string
  pipelines: PipelineStatus[]
  qualityChecks: QualityCheck[]
  sources: DataSourceHealth[]
  issues: DataIssue[]
}
14.8 系統治理 API
GET /api/system/governance
字段：
type GovernanceResponse = {
  deployStatus: string
  deployVersion: string
  deployTime: string
  ciPassRate: number
  currentStrategyIdentity: string
  registryConsistency: number
  alerts: Alert[]
  architectureLayers: ArchitectureLayer[]
  ciGuards: CIGuard[]
  governanceGrid: GateStatus[]
  auditLogs: AuditLog[]
}

15. 前端狀態管理要求
15.1 Zustand Store
建議 store 拆分：
useAppStore
useLayoutStore
useStrategyStore
useDashboardStore
useAuditStore
useRiskStore
useAIStore
15.2 useAppStore
字段：
type AppStore = {
  currentDate: string
  latestDataDate: string
  selectedStrategyId: string
  selectedStrategyVersion: string
  dataStatus: 'fresh' | 'stale' | 'error'
}
15.3 useLayoutStore
字段：
type LayoutStore = {
  sidebarCollapsed: boolean
  rightPanelWidth: number
  theme: 'dark' | 'light'
}
15.4 useAIStore
字段：
type AIStore = {
  currentPageContext: string
  suggestedQuestions: string[]
  messages: AIMessage[]
  isLoading: boolean
}
要求：
頁面切換時更新 AI context
AI 問題必須帶 pageContext
不允許 AI 自行讀取不在當前上下文的敏感操作數據

16. 數據刷新策略
16.1 全局刷新
默認：
今日操作台：30 秒
組合風控：60 秒
信號審計：60 秒
策略台帳：5 分鐘
因子研究：5 分鐘
回測實驗：不自動刷新
數據健康：30 秒
系統治理：30 秒
16.2 刷新要求
所有 API 請求要有 loading skeleton
刷新失敗不能清空舊數據
API 失敗時顯示上次成功時間
關鍵頁面支持手動刷新
刷新後若狀態變更，應有輕量提示
16.3 數據版本指紋
前端需要顯示並緩存：
dataFingerprint
specHash
deployId
gitCommit
lastUpdatedAt
若指紋變化：
今日操作台刷新
信號審計重新拉取
AI 面板重新生成摘要

17. 權限與安全要求
17.1 權限模型
初期可以簡化為三類：
viewer：只讀查看
researcher：查看研究與實驗
admin：系統治理與配置查看
17.2 操作限制
前端 V1 不允許：
實盤下單
直接修改策略狀態
直接註冊策略
直接改配置
直接刪除日誌
直接覆蓋證據包
可允許：
查看報告
下載報告
複製 Hash
篩選表格
導出 CSV
向 AI 提問
查看審計證據

18. 錯誤與空狀態設計
18.1 API 錯誤
展示：
數據暫時不可用
上次成功更新：2026-06-24 07:30
錯誤原因：API timeout
建議：稍後刷新或查看系統治理頁
18.2 無數據
展示：
暫無回測結果
可能原因：
1. 該策略尚未完成回測
2. 回測任務正在執行
3. 證據包尚未生成
18.3 阻塞狀態
展示：
今日信號已被阻塞
阻塞原因：
- Data 門禁失敗：最新價量日期滯後
- Registry 身份不匹配
要求：
阻塞狀態必須明確
不能只顯示錯誤碼
要給出下一步行動建議

19. 響應式設計要求
19.1 桌面優先
主要面向桌面端，推薦最小寬度：
1440px
最佳寬度：
1600px - 1920px
19.2 平板適配
寬度低於 1200px：
右側 AI 面板收起為抽屜
左側導航收起為圖標
表格支持水平滾動
19.3 手機端
手機端 V1 不做完整研究功能，只做只讀監控：
今日狀態
是否可交易
核心風險
數據健康
告警

20. 性能要求
20.1 首屏性能
要求：
首屏可用時間 < 2 秒
核心指標渲染 < 1 秒
頁面切換 < 500ms
表格 1000 行內不卡頓
20.2 圖表性能
要求：
大型時間序列使用降採樣
表格超過 500 行使用虛擬滾動
熱力圖不超過 100 x 100
圖表懶加載
回測頁大圖表按 tab 加載
20.3 API 性能
前端要求後端端點：
今日操作台 < 1s
組合風控 < 1s
信號審計 < 1s
策略台帳 < 1s
因子詳情 < 2s
回測詳情 < 2s
數據健康 < 1s
系統治理 < 1s

21. 開發目錄建議
frontend/
├── app/
│   ├── dashboard/
│   ├── portfolio-risk/
│   ├── signal-audit/
│   ├── strategy-registry/
│   ├── factor-research/
│   ├── backtest-lab/
│   ├── data-health/
│   └── system-governance/
├── components/
│   ├── layout/
│   ├── cards/
│   ├── charts/
│   ├── tables/
│   ├── badges/
│   ├── gates/
│   └── ai/
├── hooks/
├── stores/
├── services/
├── types/
├── utils/
└── styles/

22. 開發里程碑
22.1 Phase 1：操作台 MVP
必做頁面：
今日操作台
信號審計
數據健康
必做組件：
AppShell
Sidebar
TopStatusBar
RightAuditPanel
MetricCard
GateCard
StatusBadge
HashCopy
DataTable
完成標準：
能展示今日是否可交易
能展示五項生產門禁
能展示信號身份
能展示數據健康
AI 面板可根據頁面顯示摘要
22.2 Phase 2：風險與策略
新增頁面：
組合風控
策略台帳
完成標準：
能展示組合主要風險暴露
能展示 ST / 小盤 / 流動性風險
能展示策略狀態
能展示九門禁
能展示策略生命周期
22.3 Phase 3：研究與回測
新增頁面：
因子研究
回測實驗
完成標準：
能展示因子 IC / ICIR
能展示分組收益
能展示成本敏感性
能展示回測淨值與回撤
能比較回測口徑與真實口徑
能展示參數敏感性熱力圖
22.4 Phase 4：治理完整化
新增能力：
系統治理
CI 守衛
Registry 一致性
審計日誌
報告導出
完成標準：
能看到架構依賴拓撲
能看到 CI 守衛結果
能看到 Registry 完整性
能下載策略證據包
能追溯所有發布與阻塞事件

23. 驗收標準
23.1 今日操作台驗收
必須滿足：
使用者 10 秒內知道今天是否可交易
能看到市場狀態、建議動作、目標倉位
能看到五項生產門禁
能看到信號是否正式發布
能看到主要風險摘要
23.2 信號審計驗收
必須滿足：
能追溯信號日期、策略版本、Spec Hash、Data Fingerprint
能看到信號生成流水線
能看到 Top-25 候選與理由
能看到執行風險
能下載審計報告
23.3 組合風控驗收
必須滿足：
能看到小盤、流動性、ST、行業、單票、換手風險
能看到持倉風險明細
能看到壓力測試
AI 能指出最主要風險來源
23.4 策略台帳驗收
必須滿足：
能區分 ACTIVE / REFERENCE / FALSIFIED / RETIRED
能看到每個策略的九門禁狀態
能看到策略生命周期
能看到審計日誌
能打開證據包
23.5 因子研究驗收
必須滿足：
能看到 IC / ICIR / 中性化 ICIR
能看到分組收益
能看到成本敏感性
能看到風格相關性
能看到實驗隊列
23.6 回測實驗驗收
必須滿足：
能看到淨值、回撤、年度收益
能看到 IS / OOS / Walk-Forward
能看到參數敏感性
能看到回測口徑 vs 真實口徑
能看到交易統計與成本
23.7 數據健康驗收
必須滿足：
能看到最新交易日
能看到 PIT 通過率
能看到數據管道狀態
能看到質量檢查報告
能看到異常問題
23.8 系統治理驗收
必須滿足：
能看到部署狀態
能看到 CI 守衛通過率
能看到架構依賴拓撲
能看到 Registry 一致性
能看到審計事件日誌

24. 禁止事項
前端不得做以下事情：
不得在前端計算策略收益
不得在前端計算因子
不得在前端判定策略有效性
不得讓 AI 做最終裁決
不得顯示「穩賺」「必買」「強烈買入」
不得隱藏 DSR、OOS、最大回撤、成本後收益
不得只展示成功策略，不展示失敗策略
不得刪除審計日誌
不得覆蓋歷史策略版本
不得讓使用者在未審計狀態下誤以為策略已通過

25. 最終設計定位
Quant Research OS 前端的正確形態不是「股票看板」，而是：
Alpha 審計駕駛艙。
各頁分工：
今日操作台：今天能不能動
信號審計：為什麼這樣動
組合風控：動了會暴露什麼風險
策略台帳：這個策略歷史上是否可信
因子研究：這個因子是否真有預測力
回測實驗：歷史表現是否穩健
數據健康：信號是否被數據污染
系統治理：整個系統是否可靠
AI 助手：解釋與質疑，不拍板
整個前端最重要的產品氣質是：
克制、可追溯、可審計、可證偽。
不要讓使用者因為漂亮曲線而相信策略，要讓使用者因為完整證據鏈而理解策略。