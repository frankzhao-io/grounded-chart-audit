# 實驗與研究進度日誌（Experiment Log）

> 記錄方向 3B「科學圖表與統計一致性自動審計」自啟動以來的所有實驗設計、程式執行結果與觀察結論。

---

## Exp-01｜MVP 可控矛盾基準資料集生成（2026-11-14）
* **腳本**：`src/01_mvp_benchmark_generator.py`
* **輸出目錄**：`data/mvp_samples/`
* **目的**：針對 5 類圖文統計矛盾（`C1–C5`）與 1 類完全一致對照組（`C0`），生成具標準答案（Ground Truth）的向量 `.pdf` + 300dpi `.png` + `.json` 配對樣本。
* **生成結果**（共 6 組 × 3 檔 = 18 個檔案）：
  * `C0_consistent_control`：對照組（$n=10$、`p=0.0021` 對應 `**`、Y 軸從 `0` 開始）
  * `C1_sample_size_mismatch`：正文聲稱 $n=12$，圖中實際只繪製 7 個散點
  * `C2_star_pvalue_conflict`：圖中標註 `***`（隱含 $p<0.001$），正文卻報告 $p=0.042$
  * `C3_truncated_yaxis`：柱狀圖 Y 軸自 `0.78` 截斷，將 `0.80` vs. `0.83` 誇大為 2.5 倍視覺差距
  * `C4_concealed_distribution`：以純柱狀圖掩蓋雙峰分佈，且圖注未定義誤差線為 SD 或 SEM
  * `C5_direction_inversion`：正文聲稱 Group B 顯著高於 Group A，圖中數值完全相反

---

## Exp-02｜arXiv 真實開放論文結構探勘（2026-11-15）
* **腳本**：`src/02_real_paper_probe.py`
* **輸出**：`data/real_papers/probe_summary.json`（及 5 篇原文 PDF）
* **目的**：從 arXiv `q-bio.QM` 抽取 5 篇最新定量論文，觀察真實論文的圖表儲存型態（純向量 vs. 內嵌點陣圖）與統計宣告密度。
* **實測數據**：

| arXiv ID | 頁數 | 內嵌點陣圖 | $p$ 值出現次數 | $n=$ 樣本數 | SD/SEM 提及 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `2611.15743v1` | 7 | 3 | 0 | 2 | 2 |
| `2611.14511v1` | 32 | 1 | 2 | 4 | 4 |
| `2611.14184v1` | 26 | **0** | 3 | 0 | 5 |
| `2611.12855v1` | 20 | **42** | **45** | **28** | 6 |
| `2611.12228v1` | 13 | 46 | 0 | 5 | 0 |

* **核心觀察**：真實論文同時存在「純向量圖表 PDF（`2611.14184v1`）」與「大量內嵌點陣圖（`2611.12855v1`，含 45 處 $p$ 值）」，驗證單靠純向量規則或單靠 VLM 看圖皆有盲區，支持「雙軌混合審計」的必要性。

---

## Exp-03｜Track-1 純文字與座標規則審計原型（2026-11-15）
* **腳本**：`src/03_mvp_auditor.py`
* **輸出**：`data/mvp_audit_results.json`
* **目的**：測試僅依賴 `pypdf` 文字/刻度抽取與正則規則（不使用幾何形狀解析或 VLM）在 `C0–C5` 上的檢出極限。
* **實測結果（準確率：4 / 6）**：
  * ✅ `C0_consistent_control`：PASS（無誤報）
  * ❌ `C1_sample_size_mismatch`：MISS（無法數出圖內散點數量）
  * ✅ `C2_star_pvalue_conflict`：PASS（抓出 `pdf_star='***'` 與 `p=0.042` 衝突）
  * ✅ `C3_truncated_yaxis`：PASS（抓出 `min_tick=0.78` 截斷）
  * ✅ `C4_concealed_distribution`：PASS（抓出未定義 SD/SEM/CI）
  * ❌ `C5_direction_inversion`：MISS（無法比對圖中柱體高度與正文方向敘述）
* **真實論文快測（`2611.12855v1.pdf`）**：成功抽取 45 處 $p$ 值、28 處 $n$ 值與 6 處 SD/SEM 提及，未檢出 `p=0.000` 或 `p>1` 異常。

---

## Exp-04｜Track-1 + PyMuPDF 向量幾何審計器（2026-11-15）
* **環境準備**：安裝 `pymupdf` (`fitz`) 用於解析 PDF 向量繪圖路徑與文字座標。
* **腳本**：`src/04_vector_geometry_auditor.py`
* **輸出**：`data/mvp_vector_audit_results.json`
* **目的**：在 Exp-03 基礎上補齊向量幾何抽取——自動配對柱狀圖矩形高度與 X 軸標籤（抓 `C5`），並統計每個柱體區域內的向量散點數（抓 `C1`）。
* **實測結果（準確率由 4/6 提升至 6/6）**：
  * ✅ `C0_consistent_control`：PASS（無誤報）
  * ✅ `C1_sample_size_mismatch`：PASS（`bar='Vehicle' has 7 vector dots, prose claims n=12`）
  * ✅ `C2_star_pvalue_conflict`：PASS（`pdf_star='***' implies p<0.001, prose says p=0.042`）
  * ✅ `C3_truncated_yaxis`：PASS（`min_tick=0.78`）
  * ✅ `C4_concealed_distribution`：PASS（`SD/SEM/CI not specified`）
  * ✅ `C5_direction_inversion`：PASS（`prose claims 'Group B' > 'Group A', but bar heights are 76.4 vs 117.9`）
* **下一步重點**：可控模擬集已達 `6/6`；接下來需面對真實世界的兩大挑戰：(1) 非標準寫法與跨段語意（需引入 VLM 軌道 2 判讀比較句與點陣圖），(2) 在擴展測試集（50–100 題＋真實 arXiv/PMC 論文）上跑「純 VLM vs. 混合審計」的消融對比。

---

## Exp-05A｜60 題多樣化基準（Benchmark v1）與純規則／向量 Baseline 正式評測（2026-11-15）
* **生成腳本**：`src/05_benchmark_v1_generator.py`（產出 `data/benchmark_v1/` 共 60 題：`C0–C5` 各 10 題，含約 22% 內嵌點陣圖 PDF 以模擬 Exp-02 觀察到的真實論文分佈）
* **評測腳本**：`src/06_eval_rule_baseline.py`
* **輸出報告**：`data/benchmark_v1_rule_baseline.json`
* **總體成績單（$N = 60$）**：
  * **Accuracy**：`0.700`（70.0%）
  * **Precision**：`1.000`（零誤報）
  * **Recall**：`0.640`
  * **F1**：`0.780`
* **各類別細項準確率**：
  * `C0_consistent`：`10/10`（100.0%）
  * `C1_sample_size_mismatch`：`7/10`（70.0%）
  * `C2_star_pvalue_conflict`：`6/10`（60.0%）
  * `C3_truncated_yaxis`：`8/10`（80.0%）
  * `C4_concealed_distribution`：`10/10`（100.0%）
  * `C5_direction_inversion`：**`1/10`（10.0%）**
* **PDF 格式對比（關鍵動機證據）**：
  * `vector_pdf`：`38/47`（**80.8%**）
  * `raster_pdf`：`4/13`（**30.8%**）
* **核心結論**：純規則＋向量幾何雖能維持 `1.000` 精確率，但在 **點陣圖 PDF（30.8%）** 與 **多變自然語言比較句（`C5` 僅 10.0%）** 上全面失守。此實驗直接量化了「必須引入 Track-2 VLM（看圖＋語意理解）與 Track-1 結合」的必要性。

---

## Exp-05B｜60 題基準上「純 VLM vs. 初版混合審計」正面對決（2026-11-15）
* **評測腳本**：`src/07_eval_vlm_and_hybrid.py`（模型：`gemini-3.5-flash-lite`）
* **輸出報告**：`data/benchmark_v1_vlm_hybrid_results.json`
* **三方總體成績對比（$N = 60$）**：

| 方法 | Accuracy | Precision | Recall | F1 | `C0` 正常對照組正確率（誤報率） |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Track-1 Only**（純規則＋向量） | 70.0% | **1.000** | 64.0% | 0.7805 | **10/10 (100%)**（0% 誤報） |
| **Pure VLM**（純看圖 AI） | 88.3% | 0.877 | **100.0%** | 0.9346 | **3/10 (30%)**（**70% 誤報！**） |
| **Hybrid v1**（無正向驗證回饋） | 88.3% | 0.891 | 98.0% | 0.9333 | 4/10 (40%)（60% 誤報） |

* **關鍵突破性發現（7/7 假警報全來自 VLM 數錯散點）**：
  * 檢查 `Pure VLM` 在 `C0_00–C0_09` 誤報的 7 題原因後，發現 **100%（7/7）全部都是因為 VLM 數錯重疊散點數量**（例如實際 8 點數成 7 點、12 點數成 10 點、6 點數成 7 點）。
  * 這完美揭示了 **Pure VLM 的致命缺陷**：它雖然召回率高（100%），但因為缺乏精確幾何計數能力，會在正常論文上製造高達 **70% 的假警報**；而初版 Hybrid v1 只傳入「未檢出錯誤」，未把 Track-1 的**正向幾何驗證事實（如「向量計數確認每組確有 8 點 = $n=8$」）**傳給 VLM 當作否決機制（Veto）。
* **下一步（Exp-06）**：實作 **Bidirectional Grounded Hybrid（雙向證據錨定混合審計）**——不僅將 Track-1 的負向錯誤傳給 VLM，更將 Track-1 的「正向驗證通過證據」作為硬性否決（Veto）傳給 VLM，預期能把 `C0` 誤報率從 70% 大幅壓低，同時維持 `C1–C5` 高檢出率。

---

## Exp-06｜雙向證據錨定混合審計（Bidirectional Grounded Hybrid）消融實驗（2026-11-15）
* **評測腳本**：`src/08_eval_grounded_hybrid.py`（模型：`gemini-3.5-flash-lite`）
* **輸出報告**：`data/benchmark_v1_grounded_hybrid_results.json`
* **四組消融對比（$N = 60$）**：

| 方法 | Accuracy | Precision | Recall | F1 | `C0` 正常組正確率（誤報率） | VLM API 呼叫次數 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Track-1 Only**（純規則＋向量） | 70.0% | **1.000** | 64.0% | 0.7805 | **10/10 (100%)**（0%） | 0 |
| **Pure VLM**（純看圖 AI） | 88.3% | 0.877 | **100.0%** | 0.9346 | **3/10 (30%)**（**70% 誤報**） | 60 |
| **Hybrid v1**（僅傳負向錯誤） | 88.3% | 0.891 | 98.0% | 0.9333 | 4/10 (40%)（60% 誤報） | 28 |
| **Grounded Hybrid（本方法）** | **98.3%** | **1.000** | **98.0%** | **0.9899** | **10/10 (100%)**（**0% 誤報**） | **28（省 53%）** |

* **核心結論**：
  * 引入 Track-1 **正向幾何驗證事實（`VERIFIED_SAMPLE_SIZE`、`VERIFIED_Y_AXIS` 等）** 作為 VLM 的防幻覺否決錨點後，`C0` 正常對照組誤報率直接從 **70% 歸零（10/10 全對）**，整體準確率躍升至 **98.3%（59/60，F1 = 0.9899）**，且 VLM 呼叫成本降低 53%。
  * 僅失誤 1 題（`C3_03` 或 `C3_07` 某一點陣圖版 Y 軸截斷）。
* **下一階段（Phase 3｜真實論文測試）**：可控基準已驗證架構有效；接下來須將系統移師到**真實開放獲取論文（arXiv / PubMed Central）**上，建立真實論文圖文對抽樣集並測試真實世界檢出率與誤報率。

---

## Exp-07｜Phase 1–2 實驗結果圖表化與總結報告（2026-11-15）
* **腳本**：`src/09_plot_ablation_results.py`
* **產出**：
  * `figures/fig1_ablation_comparison.pdf` 與 `figures/fig1_ablation_comparison.png`（Panel A：整體 Accuracy / F1 / C0 Specificity 對比；Panel B：C0–C5 各類別準確率對比）
  * `notes/phase1-2-results-summary.md`（Phase 1–2 總結報告）

---

## Exp-08｜真實論文圖文對抽取（Phase 3 Step 1，2026-11-15）
* **腳本**：`src/10_real_paper_figure_extractor.py`
* **輸出**：`data/real_paper_pairs/real_pairs_manifest.json`（及 23 張 180dpi 截圖 PNG）
* **成果**：從 5 篇真實 arXiv `q-bio.QM` 論文共切出 **23 組「圖表截圖＋圖注＋正文引用段落」**：
  * `2611.12228v1.pdf`：5 組
  * `2611.12855v1.pdf`：4 組
  * `2611.14184v1.pdf`：5 組
  * `2611.14511v1.pdf`：5 組
  * `2611.15743v1.pdf`：4 組

---

## Exp-09｜真實論文 23 組圖文對審計試跑 ＋ Subagent 獨立覆核（2026-11-15）
* **審計腳本**：`src/11_audit_real_papers.py`（輸出 `data/real_paper_audit_results.json`）
* **初步結果**：23 組真實圖文對共標記 `1/23`（`2611.14511v1__fig3`）。
* **獨立 `research` Subagent 覆核結果（重大工程除錯收穫）**：
  1. **抓出 `1/23` 為假警報（False Positive）**：人工／Subagent 檢視 `2611.14511v1_fig3_p8.png` 確認圖注已明確寫出 *"Error bars are 95% CIs."*；誤報原因是 Track-1 正則 `95%\s*CI\b` 漏掉複數型 **`CIs`**（且 VLM 本身判斷為無問題，卻被外層聯集條件強制標記）。
  2. **抓出真實論文跨頁圖表切圖 Bug**：
     * `2611.12855v1__fig1`（p.16）與 `fig3`（p.19）的圖注在當頁，但**實際圖片位於前一頁（p.15 / p.18）**，導致 `10_real_paper_figure_extractor.py` 只切出空白頁與圖注。
     * `2611.12855v1__fig4`（p.20）因 `crop_top=20.0` 切掉了最上方的面板字母 `A, B, C`。
     * `2611.12855v1__fig2`（p.17）與 `fig4`（p.20）經 Subagent 人工核對圖中相關係數與 KM log-rank $p$ 值（如 `0.156`、`0.00355`→`0.0036`、`0.00104`→`0.0010`），確認與正文完全一致（True Negative）。
  3. **實驗數據紀錄核對（Exact Match）**：Subagent 比對 `experiment-log.md`、`phase1-2-results-summary.md` 與所有 JSON 原始輸出檔，確認所有核心數據完全一致（僅 Exp-05A 紀錄 `0.780` 與 `80.8%` 採截斷顯示，其餘皆四捨五入至小數點後四位）。
* **下一步修正（Exp-10）**：修復 `10_real_paper_figure_extractor.py` 的跨頁圖表偵測與頂部邊距問題，並修正 Track-1 `CIs` 複數型與 VLM 否決邏輯後重跑真實論文審計。

---

## Exp-10｜工程 Bug 修復、單元測試建立與真實論文複驗（2026-11-15）
* **單元測試套件**：新增 `tests/test_audit_pipeline.py`（4 項回歸測試：`test_plural_error_bar_definitions_not_flagged`、`test_missing_error_bar_definition_still_flagged`、`test_cross_page_figure_and_no_top_clip`、`test_summary_metrics_match_json`），執行 `python -m unittest discover` 結果 **`Ran 4 tests in 0.097s — OK`**。
* **修復項目**：
  1. `src/10_real_paper_figure_extractor.py`：`crop_top` 改為 `0.0` 避免裁切面板字母；新增 `_has_visual_content_above()` 自動回退前一頁擷取跨頁圖表（`2611.12855v1` Fig 1 成功改抓 p.15、Fig 3 成功改抓 p.18）。
  2. `src/11_audit_real_papers.py`：`SD_SEM_RE` 補齊複數型 `CIs / SDs / SEMs`，並修正 `missing_error_bar_definition` 軟規則不強制蓋過 VLM 正常判定。
* **複驗結果**：重跑 23 組真實 arXiv 圖文對後，假警報歸零（**`Flagged: 0/23`**）。

---

### Exp-11：25 篇真實開放取用論文之零成本 Track-1 大規模初篩 (2026-11-15)
* **實驗腳本**：[12_scale_real_paper_triage.py](file:///d:/_F/Side/_R/track3-ai4science/src/12_scale_real_paper_triage.py)
* **輸出報告**：[real_paper_scale_triage.json](file:///d:/_F/Side/_R/track3-ai4science/data/real_paper_scale_triage.json)
* **掃描規模**：從 arXiv 擷取 25 篇定量論文（`q-bio.QM` / `stat.AP` 類別），共萃取出 **113 組真實圖文對**（25 篇中有 24 篇成功萃取 1–6 張圖）。
* **初篩結果**：**`Flagged: 2/113`**（假警報率已極低，僅 1.77% 觸發人工/VLM 複檢門檻）。
* **人工視覺複檢（2 件觸發案例）**：
  1. `2611.13760v1` Fig 2（[2611.13760v1_fig2_p18.png](file:///d:/_F/Side/_R/track3-ai4science/data/real_paper_pairs_scale/2611.13760v1_fig2_p18.png)）：Panel (c) 確實繪有 error bars，且圖說僅寫 `"Appendix D.3 gives the design and the error bars."`，未在圖說與鄰近正文說明其代表 SD/SEM/CI。此為真實存在的**「跨章節延遲定義（cross-section deferral）」**案例，適合納入後續多頁/附錄檢索能力評估。
  2. `2611.11796v1` Fig 2（[2611.11796v1_fig2_p7.png](file:///d:/_F/Side/_R/track3-ai4science/data/real_paper_pairs_scale/2611.11796v1_fig2_p7.png)）：Panel (d) 圖說提及 `"basic-prompt agent runs (colored circles; shaded region)"`，其中 `shaded region` 實際上是標示執行時間區間的灰色背景區塊而非誤差帶，導致 Track-1 規則誤觸發（假警報）。此案例可作為後續 Track-2 VLM 語意過濾與正則微調的負樣本。

---

### Exp-12：本機開源 VLM（Ollama `qwen2.5vl:7b` / RTX 3080）Track-2 語意複檢驗證 (2026-11-16)
* **實驗腳本**：[13_track2_local_vlm_audit.py](file:///d:/_F/Side/_R/track3-ai4science/src/13_track2_local_vlm_audit.py)
* **輸出報告**：[track2_local_vlm_audit.json](file:///d:/_F/Side/_R/track3-ai4science/data/track2_local_vlm_audit.json)
* **硬體與推論設定**：NVIDIA GeForce RTX 3080 (10 GB VRAM)、Ollama `qwen2.5vl:7b` (4-bit)、圖片最長邊縮放至 `<=1280px`、`temperature=0.0`、JSON 格式輸出。
* **問題修正歷程**：
  * **初版問題**：[12_scale_real_paper_triage.py](file:///d:/_F/Side/_R/track3-ai4science/src/12_scale_real_paper_triage.py) 僅儲存 `caption[:240]`，加上 `SYSTEM_PROMPT` 缺乏判決一致性規則，導致模型雖正確看出 `2611.11796v1` Fig 2 `has_error_bars_or_bands: false`，仍將 `track1_verdict` 誤輸出為 `confirmed_issue`（耗時 `11.47s` / `5.1s`）。
  * **修正措施**：改為保留完整圖說（`2611.13760v1` 503 字元、`2611.11796v1` 1413 字元），並在 `SYSTEM_PROMPT` 明訂 `deferred_to_other_section` 與 `false_positive` 的邏輯邊界。
* **修正後複檢結果（2/2 與人工複檢完全一致）**：
  1. `2611.13760v1` Fig 2：`has_error_bars_or_bands=true`、`definition_deferred_to_appendix=true` → **`track1_verdict="deferred_to_other_section"`**（耗時 **10.46 秒**）。
  2. `2611.11796v1` Fig 2：`has_error_bars_or_bands=false`、`definition_deferred_to_appendix=false` → **`track1_verdict="false_positive"`**（耗時 **4.84 秒**）。
* **結論**：Track-1 初篩（113→2）搭配本機 7B 開源 VLM 複檢可在 **15 秒內**完成全數邊界案例過濾，並將 Exp-11 的唯一純規則假警報成功消弭。

---

### Exp-13：Benchmark v1 (N=60) 開源本地模型 (`qwen2.5vl:7b`) vs. Gemini (`gemini-3.5-flash-lite`) 完整對照 (2026-11-16)
* **實驗腳本**：[14_eval_local_vlm_benchmark.py](file:///d:/_F/Side/_R/track3-ai4science/src/14_eval_local_vlm_benchmark.py)
* **輸出報告**：[benchmark_v1_local_vlm_results.json](file:///d:/_F/Side/_R/track3-ai4science/data/benchmark_v1_local_vlm_results.json)（對照 [benchmark_v1_grounded_hybrid_results.json](file:///d:/_F/Side/_R/track3-ai4science/data/benchmark_v1_grounded_hybrid_results.json)）
* **整體指標對照**：
  * **Pure VLM（60 次 VLM 呼叫）**：
    * `qwen2.5vl:7b` (RTX 3080)：Acc = **`0.8333`**、Prec = `0.8333`、Rec = `1.0000`、F1 = **`0.9091`**（總耗時 **271.1 秒**，平均 **4.52 秒/張**；`C0_consistent` = **`0/10 (0.0%)`**）
    * `gemini-3.5-flash-lite`：Acc = **`0.8833`**、Prec = `0.8772`、Rec = `1.0000`、F1 = **`0.9346`**（`C0_consistent` = **`3/10 (30.0%)`**）
  * **Grounded Hybrid（Track-1 + 僅 28 次 VLM 呼叫）**：
    * `qwen2.5vl:7b` (RTX 3080)：Acc = **`0.9000`**、Prec = `0.9583`、Rec = `0.9200`、F1 = **`0.9388`**（總耗時 **94.89 秒**，平均 **3.39 秒/張**；`C0_consistent` = **`8/10 (80.0%)`**）
    * `gemini-3.5-flash-lite`：Acc = **`0.9833`**、Prec = `1.0000`、Rec = `0.9800`、F1 = **`0.9899`**（`C0_consistent` = **`10/10 (100.0%)`**）
* **關鍵格式拆解（Vector PDF vs. Raster PDF）**：
  * **Vector PDF（47 件）**：`qwen2.5vl:7b` Grounded Hybrid 達到 **`47/47 (100.0%)`**，與 `gemini-3.5-flash-lite`（`47/47`）**完全打平**。
  * **Raster PDF（13 件）**：`qwen2.5vl:7b` Grounded Hybrid 為 **`7/13 (53.8%)`**，低於 `gemini-3.5-flash-lite` 的 **`12/13 (92.3%)`**（失分集中於光柵化圖表的 `C1_sample_size_mismatch` 3 件、`C0_consistent` 2 件、`C3_truncated_yaxis` 1 件）。
* **核心研究結論**：
  1. 在 **向量 PDF** 場景下，**Track-1 雙向事實錨定 + 本機 7B 開源 VLM** 即能達到與商業大模型相同的 **100% 滿分**，且 VLM 推論時間縮短 65%（271.1s → 94.89s）。
  2. 開源 7B 與商業模型的能力落差幾乎完全集中在**無向量資訊的光柵化圖片（Raster PDF）**之細粒度散點計數與軸刻度辨識，為後續導入「影像級幾何前處理 / 放大裁切」指明明確方向。

---

### Exp-14：開源本地 7B vs. 商業 VLM 發表級比較圖生成 (2026-11-16)
* **繪圖腳本**：[15_plot_open_vs_commercial.py](file:///d:/_F/Side/_R/track3-ai4science/src/15_plot_open_vs_commercial.py)
* **輸出圖表**：[fig2_open_vs_commercial.pdf](file:///d:/_F/Side/_R/track3-ai4science/figures/fig2_open_vs_commercial.pdf)、[fig2_open_vs_commercial.png](file:///d:/_F/Side/_R/track3-ai4science/figures/fig2_open_vs_commercial.png)
* **圖表內容與視覺檢查**：
  * **Panel a**：比較 `Qwen2.5-VL-7B Pure`、`Gemini Flash-Lite Pure`、`Qwen2.5-VL-7B Hybrid`、`Gemini Flash-Lite Hybrid` 的 Accuracy、F1 Score 與 C0 Specificity（清楚呈現 Grounded Hybrid 將開源 7B 的 C0 Specificity 由 `0%` 拉升至 `80%`）。
  * **Panel b**：比較兩者在 `Vector PDF (N=47)`（雙雙 **100.0%**）與 `Raster PDF (N=13)`（**53.8%** vs. **92.3%**）的準確率落差。
  * 已透過視覺檢查確認版面、圖例與數值標籤皆無重疊或裁切。

---

### Exp-15：54 篇 bioRxiv 實驗生物醫學論文兩階段稽核與規則邊界修正 (2026-11-16)
* **實驗腳本**：[16_biorxiv_biomed_audit.py](file:///d:/_F/Side/_R/track3-ai4science/src/16_biorxiv_biomed_audit.py)
* **輸出報告**：[biorxiv_biomed_audit.json](file:///d:/_F/Side/_R/track3-ai4science/data/biorxiv_biomed_audit.json)
* **掃描規模**：從 bioRxiv API 擷取 60 篇實驗生物醫學預印本（神經科學、細胞生物、癌症生物、藥理等），實際成功下載並解析 **54/60 篇**（後 6 篇因連線中斷略過），共萃取出 **201 組真實圖文對**。
* **Track-1 初篩結果**：**`Flagged: 3/201`**（僅 1.49% 觸發 VLM 複檢）。
* **Track-2（本機 `qwen2.5vl:7b`）與人工複檢分析（3 件觸發案例）**：
  1. `10.64898/2026.09.30.754978` Fig 6（[10.64898_2026.09.30.754978v1_fig6_p14.png](file:///d:/_F/Side/_R/track3-ai4science/data/biorxiv_pairs/10.64898_2026.09.30.754978v1_fig6_p14.png)）：**真實異常（`confirmed_issue`，VLM 耗時 13.3s）**。圖中 PANC-1 與 BxPC-3 散點圖確實繪有雙向 error bars，圖說僅寫 `"Error bars reflect propagated uncertainty from the fitted LQ parameter estimates"`，未說明是 1-sigma/SE 還是 95% CI。
  2. `10.64898/2026.09.25.754065` Fig 3（神經科學）：圖說實際已寫明 `"the shaded area is the 95% C.I."`（VLM 耗時 4.63s 且於 reasoning 中正確點出 `95% C.I.`，但 verdict 誤標為 `confirmed_issue`）。
  3. `10.64898/2026.09.25.754349` Fig 4（神經科學）：圖說實際已寫明 `"(shaded area: s.d.)"`（VLM 判為 `false_positive`）。
* **關鍵 Bug 發現與修正**：
  * 案例 2、3 暴露出 [11_audit_real_papers.py](file:///d:/_F/Side/_R/track3-ai4science/src/11_audit_real_papers.py#L33-L36) 中 `SD_SEM_RE` 原本在 `s\.d\.` 後方接了 `\b`，因 `.` 為非單字字元，導致 `s.d.)` 與 `95% C.I. ` 無法匹配詞界而產生假警報。
  * 已改用 `(?<!\w)(?:s\.d\.|s\.e\.m?\.|(?:95%\s*)?c\.i\.|i\.q\.r\.)(?!\w)` 修正，並在 [test_audit_pipeline.py](file:///d:/_F/Side/_R/track3-ai4science/tests/test_audit_pipeline.py) 新增單元測試 `test_dotted_ci_and_sd_definitions_are_recognized`，目前 5 項單元測試全數通過（`Ran 5 tests in 0.079s - OK`）。

---

### 後續優化規劃（路線 B：學術強化與系統精進待辦，2026-11-16 記錄）
1. **真實論文漏報率（Recall）抽樣評估**：
   * 從目前已萃取但未被 Track-1 觸發的 309 組真實圖文對（arXiv 111 組 + bioRxiv 198 組）中隨機抽樣 50 組進行人工標註，量化真實文獻上是否有 Track-1 漏抓的 `C5` 效應方向反轉、星號與 `p` 值衝突或圖表異常。
2. **跨章節／附錄定義追蹤（Cross-Section Resolution）**：
   * 針對如 `2611.13760v1` Fig 2 將誤差棒定義延遲至 `Appendix D.3` 的案例，實作全文章節／附錄／Methods 段落索引檢索器，自動回查被引用章節是否已補充定義，以區分「真遺漏」與「跨章節延遲定義」。
3. **光柵化圖表（Raster PDF）強化**：
   * 針對 Exp-13 中本機 `qwen2.5vl:7b` 在 Raster PDF（53.8%）相較 `gemini-3.5-flash-lite`（92.3%）的落差，實作座標軸與資料點群之自動裁切放大前處理，或依 PDF 類型自動路由升級高階 VLM。
4. **GitHub 開源發布前整理（路線 A）**：
   * 更新 `.gitignore` 排除下載的第三方 PDF 與大量切圖快取（`data/real_papers*`、`data/biorxiv_*`、`data/epmc_*`），並更新頂層 [README.md](file:///d:/_F/Side/_R/track3-ai4science/README.md) 與 `requirements.txt`。
