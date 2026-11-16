# Track 3B 研究總結報告：Bidirectional Grounded Hybrid 科學圖表與正文統計一致性自動稽核

**研究日期**：2026-11-15 至 2026-11-16  
**專案目錄**：`track3-ai4science`  
**相關圖表**：[fig1_ablation_comparison.png](file:///d:/_F/Side/_R/track3-ai4science/figures/fig1_ablation_comparison.png)｜[fig2_open_vs_commercial.png](file:///d:/_F/Side/_R/track3-ai4science/figures/fig2_open_vs_commercial.png)

---

## 1. 研究動機與問題定義
科學論文中常出現「圖表視覺呈現」與「圖說／正文統計宣稱」不一致的問題，例如：樣本數 `n` 與散點數量不符、顯著性星號（`*`/`**`/`***`）與 `p` 值衝突、長條圖 Y 軸截斷未標示、誤差棒未定義（SD/SEM/CI/IQR），或文字與圖表呈現完全相反的效應方向。

純粹依賴多模態視覺語言模型（Pure VLM）進行稽核時，實測會出現嚴重的**過度警報（Over-flagging）**——特別是在正常無誤的對照圖表（`C0_consistent`）上，VLM 常因散點重疊而誤判樣本數不足，導致對照組特異度（Specificity）極低。

---

## 2. 核心方法：Bidirectional Grounded Hybrid 架構
本專案提出**雙向事實錨定混合稽核（Bidirectional Grounded Hybrid）**兩階段管線：

1. **Track-1 確定性幾何與文本檢查（零 VLM 成本）**：
   * 直接解析向量 PDF 繪圖指令（`PyMuPDF`）與圖說／正文規則：
     * **負向違規偵測（Hard-error routing）**：若確切偵測到樣本數不符、星號與 `p` 值矛盾、Y 軸截斷或誤差棒定義缺失，直接判定異常並省去 VLM 呼叫。
     * **正向事實鎖定（Positive Fact Grounding）**：若通過檢查，提取 `VERIFIED_SAMPLE_SIZE`、`VERIFIED_Y_AXIS`、`VERIFIED_ERROR_BAR_DEF`、`VERIFIED_SIGNIFICANCE` 等不可違背的幾何事實。
2. **Track-2 多模態 VLM 語意複檢（僅針對剩餘邊界案例）**：
   * 將 Track-1 未能確定的案例連同 `VERIFIED_*` 事實鎖定送入 VLM，強制禁止模型推翻已驗證的幾何事實，使其專注於效應方向反轉、光柵圖視覺判讀與語意邊界消歧。

---

## 3. Benchmark v1 (N=60) 消融實驗結果（Exp-05A/05B/06）
Benchmark v1 包含 6 大類別（`C0_consistent`、`C1_sample_size_mismatch`、`C2_star_pvalue_conflict`、`C3_truncated_yaxis`、`C4_concealed_distribution`、`C5_direction_inversion`），每類 10 題共 60 題（含 47 件 Vector PDF 與 13 件 Raster PDF）。

| 稽核方法 | 模型 | VLM 呼叫數 | Accuracy | Precision | Recall | F1 | `C0` 特異度 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Track-1 Only** | —（純規則／向量） | **0** | 0.7000 | **1.0000** | 0.6400 | 0.7805 | **100.0%** (10/10) |
| **Pure VLM** | `gemini-3.5-flash-lite` | 60 | 0.8833 | 0.8772 | **1.0000** | 0.9346 | 30.0% (3/10) |
| **Hybrid v1**（僅傳負向證據） | `gemini-3.5-flash-lite` | 28 | 0.8833 | 0.8909 | 0.9800 | 0.9333 | 40.0% (4/10) |
| **Grounded Hybrid**（雙向事實錨定） | `gemini-3.5-flash-lite` | **28** | **0.9833** | **1.0000** | 0.9800 | **0.9899** | **100.0%** (10/10) |

* **關鍵結論**：單靠負向證據（Hybrid v1）仍無法抑制 VLM 誤報（`C0` 僅 40%）；唯有導入正向事實鎖定（Grounded Hybrid），才能在減少 **53.3%** VLM 呼叫量的同時，將整體準確率推升至 **98.33%**（F1 = **0.9899**）。
* 視覺比較圖：[fig1_ablation_comparison.png](file:///d:/_F/Side/_R/track3-ai4science/figures/fig1_ablation_comparison.png)

---

## 4. 開源本地 7B 模型 vs. 商業模型對照（Exp-13/14）
為確保研究可重現性與零邊際成本大規模掃描能力，我們在單張 **NVIDIA GeForce RTX 3080 (10 GB VRAM)** 上透過 Ollama 部署 4-bit 量化的開源視覺語言模型 **`qwen2.5vl:7b`**，並以完全相同的 Prompt 與 Benchmark v1 (N=60) 進行對照（[14_eval_local_vlm_benchmark.py](file:///d:/_F/Side/_R/track3-ai4science/src/14_eval_local_vlm_benchmark.py)）：

| 模式 | 模型 | VLM 呼叫數 | Accuracy | Precision | Recall | F1 | Vector PDF (N=47) | Raster PDF (N=13) | 本機總耗時 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Pure VLM** | `qwen2.5vl:7b` | 60 | 0.8333 | 0.8333 | 1.0000 | 0.9091 | 83.0% (39/47) | 84.6% (11/13) | 271.1s (4.52s/張) |
| **Pure VLM** | `gemini-3.5-flash-lite` | 60 | 0.8833 | 0.8772 | 1.0000 | 0.9346 | 85.1% (40/47) | 100.0% (13/13) | — |
| **Grounded Hybrid** | `qwen2.5vl:7b` | **28** | **0.9000** | 0.9583 | 0.9200 | **0.9388** | **100.0% (47/47)** | 53.8% (7/13) | **94.89s** (3.39s/張) |
| **Grounded Hybrid** | `gemini-3.5-flash-lite` | **28** | **0.9833** | 1.0000 | 0.9800 | **0.9899** | **100.0% (47/47)** | 92.3% (12/13) | — |

* **核心發現**：
  1. 在 **Vector PDF（N=47）** 上，**`qwen2.5vl:7b` + Grounded Hybrid 達到 100.0% (47/47)**，與商業大模型完全打平，且本機總推論時間縮短 65%（271.1s → 94.89s）。
  2. 開源 7B 與商業模型的差距幾乎全集中於**無向量線索的光柵化圖表（Raster PDF, N=13）**（如 `C1_sample_size_mismatch` 散點計數與小刻度辨識），為實務上的「Vector 本地優先、Raster 升級大模型」路由策略提供明確實證依據。
* 視覺比較圖：[fig2_open_vs_commercial.png](file:///d:/_F/Side/_R/track3-ai4science/figures/fig2_open_vs_commercial.png)

---

## 5. 真實開放取用論文大規模稽核（arXiv + bioRxiv，79 篇 / 314 圖）

| 批次 | 資料來源 | 解析論文數 | 萃取圖文對 | Track-1 觸發數 | Track-2 (`qwen2.5vl:7b`) 與人工複檢結果 |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Exp-11 / 12** | arXiv (`q-bio.QM`, `stat.AP`) | 24/25 | 113 | **2** (1.77%) | 1 件為真實**跨章節延遲定義**（`2611.13760v1` Fig 2 延遲至 `Appendix D.3`，耗時 10.46s）；1 件為**背景陰影假警報**（`2611.11796v1` Fig 2，VLM 成功排除為 `false_positive`，耗時 4.84s）。 |
| **Exp-15** | bioRxiv（細胞、神經、癌症、藥理等） | 54/60 | 201 | **3** (1.49%) | 1 件為真實 **error bar 區間未定義**（`10.64898/2026.09.30.754978` Fig 6，僅寫 `propagated uncertainty`，未寫 1-sigma 或 95% CI，耗時 13.3s）；另 2 件暴露 `SD_SEM_RE` 對 `95% C.I.` 與 `s.d.)` 的詞界正則缺陷，已於本次修復。 |
| **合計** | **arXiv + bioRxiv** | **78/85** | **314** | **5** (1.59%) | Track-1 初篩過濾掉 **98.4%** 正常圖文，大幅壓低 VLM 複檢成本。 |

---

## 6. 軟體品質與測試驗證
* 所有核心萃取、正則檢查與報告數據一致性均納入自動化單元測試：[test_audit_pipeline.py](file:///d:/_F/Side/_R/track3-ai4science/tests/test_audit_pipeline.py)。
* 最新測試結果：**5/5 全數通過**（`Ran 5 tests in 0.079s - OK`），涵蓋跨頁圖表定位、複數詞尾（`CIs`/`SDs`）、帶句點縮寫（`C.I.`/`s.d.`）及報告指標一致性檢核。

---

## 7. 限制與未來工作
1. **跨章節與附錄檢索（Cross-Section Resolution）**：如 `2611.13760v1` Fig 2 將誤差棒定義置於 `Appendix D.3`，未來可擴充全文章節索引以自動追蹤附錄與 Methods。
2. **光柵圖（Raster PDF）局部放大前處理**：針對本地 7B VLM 在光柵圖（53.8%）的短板，可加入座標軸區域與資料點群的自動裁切放大，或依 PDF 格式自動路由至高階 VLM。
3. **擴充真實世界異常基準庫**：以本次實測收集到的真實案例（跨章節延遲定義、未標示區間之 propagated uncertainty、背景陰影負樣本）建立更貼近真實審稿情境的 Real-World Benchmark v2。
