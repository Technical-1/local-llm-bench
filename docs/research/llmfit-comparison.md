# llmfit vs llm-bench: feature inventory and what to adopt

Studied: [AlexsJones/llmfit](https://github.com/AlexsJones/llmfit), Rust, MIT,
version 1.1.17 (`version.txt`), commit `e915091` (2026-10-18). Read only; nothing
was built or run. All llmfit paths below are relative to the repo root, and
`core/` means `llmfit-core/src/`. Line numbers are from that commit.

llm-bench was read at its current `main` (`src/llm_bench/*.py`, `README.md`).

## Short version

llmfit is a **predictor**: it reads the hardware, looks up a 17,700-entry model
catalogue, and estimates memory, best quantisation, tok/s and a heuristic
"quality" for every model without running any of them. It has a small
benchmark (tok/s and TTFT only, three runs) whose results feed back into the
estimates and can be shared as a GitHub PR.

llm-bench is a **measurer**: a short hand-checked model list, a coarse fit
check, then real runs that score answer quality by code and record speed and
peak memory.

The two overlap on hardware detection and the fit check. llmfit is far ahead
there. llm-bench is ahead on everything that involves actually running a
model and checking what it said.

---

## 1. Feature-by-feature table

Gap size is how far llm-bench is behind llmfit on that row ("none" also covers
rows where llm-bench is ahead).

### Hardware detection

| Feature | llmfit (how, where) | llm-bench today | Gap | Adopt? |
|---|---|---|---|---|
| NVIDIA | `nvidia-smi --query-gpu=addressing_mode,memory.total,memory.free,name` (`core/hardware.rs:408-428`), falls back to a 2-column query (`:379-405`), then sysfs (`:596`), then a name-to-VRAM table when the tool fails (`estimate_vram_from_name`, `:3641`). `addressing_mode=ATS` flags Grace/Tegra unified memory (`:430-535`, `:3616`). | `nvidia-smi --query-gpu=name,memory.total` (`hwprobe.py:_nvidia_smi`), resolved to an absolute path. | small | yes: add `memory.free`; skip the name table (it is a guess) |
| Free vs total VRAM | Tracks `free_vram_gb` per card (`hardware.rs:34-49`); discrete GPUs are graded against free VRAM when known (`SystemSpecs::gpu_fit_pool_gb`, `:103-109`). AMD free = `mem_info_vram_total - mem_info_vram_used` (`:51-60`). CPU paths use `available_ram_gb` (free right now), not total. | Total only, for both VRAM and RAM. | small | yes: report both, grade on free with a note |
| Multi-GPU | Groups same-model cards with a `count` and sums VRAM across all GPUs, including mixed models (`hardware.rs:136-158`, `:201`). Fit uses total VRAM (`core/fit.rs:624-626`). | Picks the single largest GPU (`hwprobe.py:probe`). | small | maybe: sum same-model NVIDIA cards only; Ollama splits across them, but measure first |
| AMD on Linux | `rocm-smi` first (`hardware.rs:683-925`), sysfs `mem_info_vram_total` fallback (`:926-1100`), names from `lspci` (`:1101`). Drops the iGPU when a dGPU exists (`:1040`). | sysfs `mem_info_vram_total`, generic name "AMD GPU (cardN)". | small | yes: read the name from `lspci` or `device/product_name`; add free VRAM |
| AMD on Windows | WMI via PowerShell then registry `qwMemorySize` override (`hardware.rs:1240-1335`, PS command at `:2921`). Backend set to **Vulkan** for AMD on Windows (`infer_gpu_backend`, `:1661-1690`). | Same registry key, WMI as last resort, plus a note that Ollama may fall back to CPU. Nearly the same approach. | none | no: already equivalent |
| AMD APUs (Ryzen AI Max, Strix Halo) | Treated as unified memory with the whole RAM pool (`apply_amd_unified_apu_override`, `hardware.rs:341-377`); BIOS UMA carveout added back to RAM (`apu_total_ram_gb`, `:1378-1427`). | Would see the carveout as a small "GPU" or drop it under 2 GB. | small | maybe: only matters for that hardware class |
| Intel Arc / integrated | Discrete Arc VRAM from sysfs: `tileN/physical_vram_size_bytes` (xe) or `lmem_total_bytes` (i915) (`hardware.rs:1693-1842`). Iris Xe / Arc iGPU = unified pool. Legacy HD/UHD iGPUs are ignored as useless (`:1520`). Backend SYCL. | Name match only; a note that stock Ollama does not accelerate Intel. | small | maybe: add discrete Arc VRAM; keep the "not accelerated" note |
| Apple Silicon | `system_profiler -json` (`hardware.rs:1914-1986`, text fallback `:1867`). Reads Metal's `recommendedMaxWorkingSetSize` (`:2738-2742`), **but only displays it**: fit is graded against the whole unified pool (`gpu_fit_pool_gb`, `:103-109`; unified path in `core/fit.rs:602-622`). | `sysctl hw.memsize`, GPU share = 66% (75% above 36 GB) minus 2 GB (`hwprobe.py:apple_gpu_share`). Fit uses that share. | none (llm-bench is more realistic here) | yes: replace the 66/75% heuristic with the measured wiring limit (see improvement 5) |
| NPU | Huawei Ascend via `npu-smi` (`hardware.rs:2252-2313`). No Intel/AMD/Qualcomm NPU. | None. | small | no: no local runtime llm-bench uses targets them |
| Vulkan | `vulkaninfo --summary` as a last-resort GPU list, filters software renderers like llvmpipe (`hardware.rs:2012-2055`, `:2230`). | None. | small | no: names only, no VRAM; low value for Ollama/MLX |
| System RAM bandwidth | Measures it: multithreaded 32 MiB memcpy for 80 ms, sanity band 2 to 4000 GB/s (`measure_ram_bandwidth_gbps`, `hardware.rs:2997-3057`). Used for CPU-offload and MoE-offload speed. | None. | small | maybe: only needed if we add tok/s estimates for CPU offload |
| GPU memory bandwidth table | 92 name entries (NVIDIA consumer and datacenter, AMD, Apple M1 to M5) in `gpu_memory_bandwidth_gbps` (`hardware.rs:3079-3408`). Laptop GPUs deliberately return `None` because they share model numbers with different buses (`:3059-3077`). | None. | large | yes, a small subset, if we add tok/s estimates |
| Manual overrides | `--memory`, `--ram`, `--cpu-cores`, `--memory-percent`, `--ram-percent` (`hardware.rs:2470-2614`); whole-machine JSON profiles via `--profile` (`core/hwprofile.rs`, `llmfit-core/data/hardware/`). | None. | small | maybe: `--vram`/`--ram` overrides are cheap and help when detection fails |
| Diagnostics | `llmfit doctor` dumps raw output of every probe tool for bug reports; each report becomes a test fixture (`core/doctor.rs:1-10`). | Tests already use recorded tool output, but no user-facing dump. | small | yes: cheap, fits the existing fixture tests |
| How tools are launched | Bare names via `std::process::Command::new("nvidia-smi")`, `"powershell"`, `"rocm-smi"`, `"system_profiler"` and others (`hardware.rs:388, 409, 684, 1246, 1429, 1869, 2017, 2254`). Relies on Rust's PATH search. | Every tool resolved to an absolute path, current directory and relative PATH entries skipped (`_exe.py`). | none (llm-bench is stricter) | no |

### Memory, quantisation and context

| Feature | llmfit (how, where) | llm-bench today | Gap | Adopt? |
|---|---|---|---|---|
| Memory formula | `weights + kv_cache + 0.5 GB` where `weights = params_b * quant_bpp(quant)` (`core/models.rs:1440-1451`). | `params_b * 0.6 + 1.5` GB, always 4-bit (`registry.py:Model.need_gb`). | large | yes: see improvement 2 |
| Bytes per weight | `quant_bpp`: Q8_0 1.05, Q6_K 0.80, Q5_K_M 0.68, Q4_K_M 0.58, Q3_K_M 0.48, Q2_K 0.37, mlx-4bit 0.55, mlx-8bit 1.0, F16 2.0, MXFP4 0.55 (`core/models.rs:26-64`). A separate `quant_bytes_per_param` (Q4_K_M 0.5, Q8_0 1.0) is used for speed (`:100-131`). | 0.6 for every model. | small | yes: copy the table for the quants Ollama and MLX actually ship |
| KV cache | Precise: `2 * n_layers * n_kv_heads * head_dim * ctx * bytes_per_element`, counting only full-attention layers for hybrids (`kv_cache_gb`, `core/models.rs:1465-1505`). MLA models (DeepSeek V2/V3, Kimi) cache a 576-wide latent instead (`:1510-1518`). Fallback when metadata is missing: `0.000008 * params_b * ctx` GB at fp16. KV quant options fp16/fp8/q8_0/q4_0 (`:815-826`). | Folded into the flat 1.5 GB. | large | yes: needs 3 numbers per registry model |
| Context used for estimates | Capped at 8,192 tokens by default (`DEFAULT_ESTIMATION_CTX`, `core/fit.rs:15`), overridable with `--max-context`, else `OLLAMA_CONTEXT_LENGTH` (`llmfit-tui/src/main.rs:170-177`). | Not modelled. Also **not set** on Ollama runs (`runners.py:run_ollama` sends no `num_ctx`). | large | yes: see improvement 1 |
| Usable context | `(budget - weights - overhead) / kv_per_token`, capped at the model maximum (`core/fit.rs:848-862`). | None. | small | yes, once KV is modelled |
| Best quant selection | Walks Q8_0 > Q6_K > Q5_K_M > Q4_K_M > Q3_K_M > Q2_K (`core/models.rs:7`), or mlx-8bit > mlx-4bit on MLX (`:10`), and picks the first that fits 98% of the pool; if none fit, retries once at half context if that is still >= 1,024 tokens (`best_quant_for_budget_with`, `:1546-1572`; budget `quant_budget`, `core/fit.rs:1005`). | Fixed 4-bit. | small | maybe: a "you could run the q8 tag" hint is useful, but llm-bench's quality numbers are for the 4-bit builds it tested |
| Fit verdicts | Ratio of required to available: <= 60% Perfect, <= 85% Good, <= 98% Marginal, else Too Tight (`core/fit.rs:998-1028`). CPU and offload paths are capped at Good (`:1031-1044`). | fast / slow / too big against two budgets (`hwprobe.py:fit`). | small | maybe: a "tight" band between 85% and 98% would warn before a load fails |
| Run modes | GPU, MoE offload (active experts in VRAM, rest in RAM), CPU+GPU offload, CPU only, tensor parallel (`core/fit.rs:213-219`, path selection `:579-677`). | fast vs slow (offload) vs no. | small | no: MoE expert offload is llama.cpp-specific; Ollama does not expose it |
| MoE memory | Full model must be resident for the GPU path; offload path puts `active_params * bpp * 1.1` in VRAM and the rest in RAM (`core/fit.rs:1175-1192`). | Total params for memory (correct). | none | no |

### Speed estimation

| Feature | llmfit (how, where) | llm-bench today | Gap | Adopt? |
|---|---|---|---|---|
| Bandwidth roofline | `tok/s = bandwidth_GBps / (params_b * bytes_per_param) * 0.55 * run_mode_factor` (`estimate_tps`, `core/fit.rs:1807-2045`; efficiency default `:73-75`). Run-mode factors: GPU 1.0, TP 0.9, MoE offload 0.8, CPU offload 0.5, CPU 0.3 (`:85-95`). | None: speed is only measured. | large | yes: see improvement 6 |
| Unknown GPU fallback | `K / params_b * quant_speed_multiplier`, K: CUDA 220, Metal+MLX 250, Metal+llama.cpp 160, ROCm 180, Vulkan 150, SYCL 100, CPU ARM 90, CPU x86 70, Ascend 390 (`core/fit.rs:2048-2062`); +10% with >= 8 cores. | None. | small | no: say "unknown" instead; these constants are guesses |
| MoE decode | Uses **active** params. Tier 1 (full metadata): `bw / (active_ffn_params * bpp + fixed_params * 3.2)` with attention, router, embeddings counted as fixed (`core/models.rs:1376-1432`, `core/fit.rs:1990-2012`). Tier 2: active params with per-architecture efficiency/overhead (`:1494-1600`). A VRAM cache-pressure penalty above 60% utilisation (`:1457-1465`, `:1940-1985`). | Not estimated. | small | maybe: use active params only; skip the tiers |
| CPU offload | Weights split by whole layers between VRAM and RAM; time per token is the sum of the GPU and DDR transfers (`dense_cpu_offload_tps`, `core/fit.rs:1727-1800`). DDR bandwidth: config, `LLMFIT_DDR_BANDWIDTH`, measured, else 50 GB/s (`:1699-1715`). | Not estimated. | small | maybe, later |
| Prefill / TTFT estimate | `2 * active_params` FLOPs per token at 35% of fp16 peak, only when TFLOPS is configured; otherwise `null`, never 0 (`core/fit.rs:1643-1697`). | Measured only. | none | no: measuring is better and we already do |
| Accuracy checked against reality | CI replays 665 measured rows through the estimator and gates the median error per chip class. Baseline: unified median error 0.206 (median ratio 0.84), discrete 0.301 (ratio 0.96) (`llmfit-core/tests/estimator_accuracy.rs:1-40`; older gate `core/fit.rs:3593-3718`). | Memory estimate vs measured peak shown in the README sample, not gated. | small | yes: worth copying the idea, see improvement 6 |

### Catalogue and runtimes

| Feature | llmfit (how, where) | llm-bench today | Gap | Adopt? |
|---|---|---|---|---|
| Catalogue size | 17,700 entries in `llmfit-core/data/hf_models.json`, of which 17,477 are auto-discovered (`_discovered: true`); 14,364 GGUF, 1,342 safetensors, 1,214 MLX, plus AWQ/GPTQ/AutoRound. 12,935 have layer metadata, 3,118 are MoE. Embedded at compile time (`core/models.rs:1719`). `MODELS.md` still says 108, so it is stale. | 15 hand-picked models, each with an Ollama tag and MLX repo (`registry.py:MODELS`). | large | no: see "What llm-bench does that llmfit doesn't" |
| How it is built | `scripts/scrape_hf_models.py` (stdlib Python) pulls the HF API: params from `safetensors.total`, architecture from `config.json`, MoE from `num_local_experts`/`num_experts_per_tok`, respecting HF rate-limit headers. Memory fields: `min_ram = size * overhead`, `recommended_ram = size * 2.0`, `min_vram = size * 1.1` (`:723-747`). Weekly GitHub Action, Monday 02:00, `-n 5000 --threads 8`, opens a PR (`.github/workflows/weekly-model-update.yml`). | Edited by hand. | large | maybe: a small script that fills `layers / kv_heads / head_dim / context` for our 15 models from each `config.json` |
| Ollama name mapping | ~150-row HF-name to Ollama-tag table (`OLLAMA_MAPPINGS`, `core/providers.rs:4582-4795`); installed tags checked for a size mismatch over 2x (`:4860-4890`). So only about 1% of the catalogue can be pulled through Ollama. | Every model has a verified Ollama tag and MLX repo. | none | no |
| Runtimes | Ollama, MLX (cache scan plus `mlx_lm.server`/oMLX at `localhost:8080`/`127.0.0.1:8000`), llama.cpp, Docker Model Runner, LM Studio, vLLM, RamaLama, Ferrum (`core/providers.rs:52, 698, 1198, 2214, 2498, 3376, 3599`; trait at `:15-30`). Each has a `*_HOST` env var. | Ollama (HTTP) and MLX (in-process `mlx_lm`). | small | maybe: an OpenAI-compatible runner would cover llama-server, LM Studio and vLLM in one adapter |
| Installed-model detection | Ollama `/api/tags`; MLX and GGUF by scanning the HF cache (`core/providers.rs:841-912`, cache dirs `:914-970`); LM Studio only counts **loaded** models. | Ollama `/api/tags` then `ollama list`; MLX by HF cache blobs (`runners.py:ollama_status`, `mlx_downloaded`). | none | no |

### Scoring, confidence and benchmarking

| Feature | llmfit (how, where) | llm-bench today | Gap | Adopt? |
|---|---|---|---|---|
| Ranking dimensions | Four 0-100 scores, weighted per use case. Weights (quality, speed, fit, context): General .45/.30/.15/.10, Coding .50/.20/.15/.15, Reasoning .55/.15/.15/.15, Chat .40/.35/.15/.10, Multimodal .50/.20/.15/.15, Embedding .30/.40/.20/.10 (`core/fit.rs:99-120`, combine `:2363-2368`). | 70% measured quality + 30% measured speed, speed full marks at 80 tok/s (`report.py:composite`). | small | maybe: a `--use-case coding` preset that re-weights our measured categories |
| "Quality" in the fit table | **Not measured.** Base by active params (<1B 30, <3B 45, <7B 60, <10B 75, <20B 82, <40B 89, else 95), plus name bumps (Qwen +2, DeepSeek +3, Llama +2...), recency bonus, quant penalty (Q4_K_M -5, Q2_K -12), and a task bump `((bench - 72) * 0.4)` clamped to [-8, 9] from a 20-family leaderboard table (`quality_score`, `core/fit.rs:2150-2268`; `llmfit-core/data/use_case_benchmarks.json`; `core/task_bench.rs`). | Measured by code on 13 tasks. | none (llm-bench is ahead) | no |
| Speed score | `tps / target * 100`, target 40 tok/s (25 reasoning, 200 embedding) (`core/fit.rs:2318-2326`). | `min(tps / 80, 1)`. | none | no |
| Fit score | Flat 100 up to 70% utilisation, then a one-sided Gaussian with sigma 0.20 (`core/fit.rs:2328-2343`). | Not part of the ranking. | small | no: our ranking is over models that already ran |
| Context score | 100 if the model's max context >= target (4k general, 8k coding/reasoning), 70 at half, else 30 (`core/fit.rs:2345-2361`). | Not scored; one long-context recall task instead. | none | no |
| Confidence labels | Every tok/s carries `measured_local`, `measured_community`, `calibrated`, `estimated` or `unsupported`, first match wins (`EstimateConfidence`, `core/fit.rs:269-355`). The inputs are exposed in `estimate_basis` (method, bandwidth used, efficiency, context, calibration factor) (`:237-262`). | Estimates and measurements sit in separate places; the scorecard shows "est. -> measured" for memory only. | small | yes: matches the modelfit rule that every answer states its source |
| Calibration from your own runs | Median of measured/estimated over dense models >= 1B on identical hardware (same CPU and GPU name, `core/benchmarks.rs:546-557`), clamped to [0.05, 3.0], scales every other estimate (`apply_local_calibration`, `core/analysis.rs:340-395`). | None. | small | yes, after tok/s estimates exist |
| Benchmark command | `llmfit bench`: one warmup ("Say hello."), then 3 runs cycling 4 fixed prompts, `num_predict` 300, runtime-default temperature (`core/bench.rs:125-186`, `:188-247`). Ollama tok/s from `eval_count / eval_duration`, falling back to wall clock when count < 2 or the rate exceeds 10,000 tok/s (`:55-60`, `:249-271`). TTFT = `prompt_eval_duration` only (`:220-222`). OpenAI-compatible endpoints get no TTFT (`:16-20`). Reports avg/min/max. No memory measurement. | 13 quality tasks, one pass each, temperature 0, records load, TTFT (load + prompt eval), prompt and gen tok/s, peak memory (`runners.py`, `bench.py:bench_one`). | small | yes: warmup, repeated fixed-length speed runs, min/max, plausibility guard (improvement 8) |
| Quality benchmark | `llmfit bench --quality`: 92 tests in 19 roles (`llmfit-core/data/benchmarks.yaml`, `rubric_version: 2`; the module header still says 13 roles, `core/quality.rs:1-4`). Scored by **regex rules with weights**, clamped 0-10 (`evaluate_response`, `core/quality.rs:132-148`). No code is executed (`extract_code_block` only extracts, `:156`). Temperature 0.3, max 1,024 tokens (`:388-389`). Ollama requests send `"think": false` (`:191`). Composite `(quality*2 + min(tps/3,10)*speed_weight) / (2 + speed_weight)`. Produces a role-to-model routing matrix (`:479`). | Code-scored: hidden unit tests executed, exact numeric match, needle retrieval, programmatic format checks; thinking stripped, not disabled. | none (llm-bench is ahead) | no, but the YAML task format is worth a look (improvement 12) |
| Community sharing | `bench --share`: results stored locally first (`core/share.rs:397`), then GitHub device-flow login (baked public client id, `:44`), fork, branch, one file per submission at `llmfit-core/data/community/<hardware-slug>/<unix>-<8-hex>.json`, appends to an existing open PR (`:503-700`, `:1049-1160`). `--dry-run` prints payloads. Merged files are embedded in the next release. 498 files across 48 hardware folders today. | None. | large | later: the payload and CI checks are worth copying now (improvement 9); the auto-PR flow is a lot of code |
| Submission payload | `schemaVersion`, `submittedAtUnix`, `tool{name,version}`, `hardware{hwClass DISCRETE_GPU/UNIFIED/CPU_ONLY, hardwareName, memTierGb, vramGb, gpuCount, unifiedMemory, cpu, cpuCores, ramGb, os}`, `results[{model, provider, numRuns, avgTps, minTps, maxTps, avgTtftMs, avgTotalMs, avgOutputTokens}]` (`llmfit-core/data/community/schema.json`, built in `core/share.rs:141-199`). Memory tier is snapped down to 2/3/4/6/8/12/16/24/32/48/64/80/96/128/192/256 GB (`:127-139`). | `results.json` rows have no hardware block and no schema version (`bench.py:bench_one`, `hardware.json` written separately by `cli.py`). | small | yes |
| CI validation of submissions | `scripts/validate_community_benchmarks.py` on every PR touching the folder (`.github/workflows/community-benchmarks.yml`): path and file-name regex, 64 KiB cap, JSON Schema, timestamp not before 2026-07-01 and not in the future, RAM <= 8192 GB, VRAM <= 2048 GB, cores <= 1024, GPUs <= 64, <= 100 results per file, `minTps <= avgTps <= maxTps`, `avgTps > 0` (`:39-125`). | None. | small | yes, with improvement 9 |
| Output modes | TUI (default), `--cli` tables, `--json` on every subcommand, REST API `llmfit serve` (`/api/v1/system`, `/models`, `/models/top`, `/plan`, `/concurrency`, `/storage`, downloads; `llmfit-tui/src/serve_api.rs:436-450`), MCP server with 2 tools `get_system_specs` and `recommend_models` (`llmfit-tui/src/mcp_server.rs:108-124`), web dashboard, Tauri desktop app. | Console text for `check`, Markdown scorecard, `results.json`, `hardware.json`. | large | partly: `check --json` yes; REST, MCP, TUI no |
| Other commands | `plan` (hardware needed for a model at a context and target tok/s, `core/plan.rs`), `concurrency` (sessions that fit: `floor((pool - weights) / kv(ctx))`, `core/concurrency.rs:1-20`), `storage` (SSD size for a model library, `core/storage.rs`), `claim` (Kubernetes DRA ResourceClaim, `core/claim.rs`), `diff`, `download`, `hf-search`, `update`, `run`, `hardware list/show/validate` (`llmfit-tui/src/main.rs:299-1076`). | `check`, `run`, `report`. | large | no: out of scope for a benchmark tool |

---

## 2. What llm-bench does that llmfit doesn't

Being specific, and fair to llmfit where it tries.

1. **Answer quality is measured, and measured by code.** llm-bench runs the
   model's code against hidden tests, matches math answers exactly, checks
   recall with a needle in a long document, and checks format rules
   programmatically (`tasks.py`). llmfit's ranking "Quality" is not measured
   at all: it is parameter count plus name-based bumps plus a 20-row
   leaderboard table (`core/fit.rs:2150-2268`). Its optional
   `bench --quality` scores with weighted regex rules (`core/quality.rs:132-148`),
   so an answer that mentions "Python" and "palindrome" earns points without
   being correct, and the bat-and-ball test gives +2 for writing "let"
   (`llmfit-core/data/benchmarks.yaml`). No code is ever executed.
2. **Deterministic.** llm-bench uses temperature 0, so a re-run gives the same
   score. llmfit's quality tests run at 0.3 (`core/quality.rs:389`) and its
   speed bench at the runtime default.
3. **Reasoning models are graded on the answer.** llm-bench lets the model
   think, then strips the `<think>` block or Gemma's channel marker before
   scoring (`runners.py:strip_thinking`). llmfit sends `"think": false` to
   Ollama (`core/quality.rs:191`), so it tests a different mode than people
   use, and does nothing equivalent on OpenAI-compatible endpoints.
4. **Peak memory is measured.** MLX via `mx.get_peak_memory()`, Ollama via
   `/api/ps` (`runners.py`). The scorecard compares estimate and measurement.
   llmfit's benchmark records no memory at all (`core/bench.rs` has no memory
   field), so its memory formula has never been checked against a run.
5. **MLX runs in-process.** llm-bench loads the model with `mlx_lm` and gets
   load time, TTFT, prompt and generation tok/s directly. llmfit needs an
   `mlx_lm.server` running and gets no TTFT on that path
   (`core/bench.rs:16-20`).
6. **Same model, two runtimes, side by side.** The scorecard's MLX vs Ollama
   table (`report.py`) has no llmfit equivalent.
7. **A more realistic Apple Silicon budget.** llmfit reads Metal's
   working-set cap but grades fit against the whole unified pool
   (`core/hardware.rs:103-109`, `core/fit.rs:602-622`), so a 20 GB model on a
   24 GB Mac is rated "Good" (83% of the pool) while macOS only lets the GPU
   wire about 16 GB by default. llm-bench's 66% / 75% share minus 2 GB is closer to
   what loads.
8. **Every model in the list is runnable as listed.** Each registry row has a
   checked Ollama tag and MLX repo. Of llmfit's 17,700 entries, about 150 map
   to an Ollama tag (`core/providers.rs:4582-4795`) and many are
   auto-discovered repos with partial metadata (`parameter_count: "0K"` on
   the first entry of `hf_models.json`).
9. **Tool paths are pinned.** llm-bench resolves every external tool to an
   absolute path and skips the current directory (`_exe.py`); llmfit
   launches `nvidia-smi`, `powershell`, `rocm-smi` and others by bare name
   (`core/hardware.rs:388, 409, 1246` and more).
10. **Small, stdlib-only probe and offline tests with a right and a wrong
    answer for every task.** Easy to read and audit in one sitting.

---

## 3. Prioritised improvements for llm-bench

Ordered by value for effort. Sizes: S = under a day, M = a few days, L = a
week or more. If code is ported from llmfit (not just a formula or a
constant), keep its MIT notice: add a comment at the top of the ported block,
for example `# Adapted from llmfit (c) Alex Jones, MIT licence,
https://github.com/AlexsJones/llmfit`, and mention it in the README. Copying
published facts (GPU bandwidths, bytes per weight) needs no attribution, but
citing the source is good practice.

### 1. Set and check the Ollama context window (S, do first)

- **What:** pass an explicit `num_ctx` in `run_ollama` (16,384 covers the
  long-context task with room for the answer), record it in the result row,
  and compare `prompt_eval_count` with the expected prompt length so a
  truncated prompt is flagged instead of scored.
- **Why:** `run_ollama` sends no `num_ctx` (`runners.py`), so Ollama uses its
  default. The long-context document is about 9,000 words, roughly 12,000
  tokens. If the default is smaller, Ollama drops the start of the prompt and
  the needle may never reach the model, which would make the Ollama
  long-context score, and the MLX vs Ollama comparison, wrong. The default has
  changed between Ollama versions, so **check it on a real machine** rather
  than assume: run the task and look at `prompt_eval_count`. llmfit treats
  context as a first-class input for the same reason (`core/fit.rs:15`,
  `llmfit-tui/src/main.rs:170-177`).
- **Files:** `runners.py`, `bench.py`, `tasks.py` (expose the expected token
  count), `tests/test_runners.py`.
- **Note:** a larger `num_ctx` raises memory use, so the measured peak will
  move. That is the honest number for this task.

### 2. Replace the flat memory estimate with weights + KV cache + overhead (M)

- **What:** add `layers`, `kv_heads`, `head_dim`, `max_ctx` (and the actual
  quant of the MLX build) to each `Model` row, and estimate
  `params_b * bpp(quant) + kv_gb(ctx) + 0.5`.
- **Why:** `params_b * 0.6 + 1.5` ignores context and quant. It works at
  short context for the three models in the README, but it cannot answer
  "does this fit at 16k?" and is wrong for 3-bit MLX builds already in the
  registry (`granite-4-h-tiny`, `lfm2-8b-a1b`).
- **Files:** `registry.py`, `hwprobe.py:fit` callers in `cli.py`, `report.py`
  (estimate vs measured column), `tests/`.
- **Copy from llmfit** (`core/models.rs:26-64`, `:1440-1505`):

  ```text
  quant_bpp: Q8_0 1.05, Q6_K 0.80, Q5_K_M 0.68, Q4_K_M 0.58, Q4_0 0.58,
             Q3_K_M 0.48, Q2_K 0.37, mlx-4bit 0.55, mlx-8bit 1.0, F16 2.0
  memory_gb = params_b * quant_bpp + kv_cache_gb + 0.5
  kv_bytes  = 2 * n_layers * n_kv_heads * head_dim * ctx * bytes_per_element
              (fp16 = 2; count only full-attention layers in hybrids)
  fallback  = 0.000008 * params_b * ctx   # GB, when layer metadata is missing
  ```

  KV is divided by 1,073,741,824 (GiB) in llmfit. Pick GB or GiB once and use
  it everywhere, including the measured peak (MLX reports bytes, we divide by
  1e9 today).
- **Measure:** the scorecard already has measured peaks; add a test that the
  new estimate is within a stated tolerance for every model we have numbers
  for.

### 3. Record whether Ollama actually offloaded to the CPU (S)

- **What:** `/api/ps` returns both `size` and `size_vram`. Store
  `vram_fraction = size_vram / size` and show "100% GPU" or "62% GPU" in the
  performance table.
- **Why:** `check` predicts fast or slow; this measures it. It also explains
  slow results without guessing. llmfit can only predict offload
  (`core/fit.rs:1727-1800`).
- **Files:** `runners.py:_ollama_resident_gb`, `bench.py`, `report.py`.

### 4. Free memory next to total memory (S)

- **What:** read free VRAM (`nvidia-smi` `memory.free`; AMD
  `mem_info_vram_total - mem_info_vram_used`) and available RAM
  (`MemAvailable` in `/proc/meminfo`, `ullAvailPhys` from
  `GlobalMemoryStatusEx`, `vm_stat` on macOS). Show both in `check`; warn
  when a "fits" model would not fit in what is free right now.
- **Why:** a browser or a game holding 6 GB of VRAM turns a "fast" verdict
  into an offloaded run. llmfit grades discrete GPUs on free VRAM when known
  (`core/hardware.rs:103-109`, query at `:410`).
- **Files:** `hwprobe.py`, `cli.py`, `tests/test_hwprobe.py` (new fixtures).

### 5. Read the real Apple GPU memory limit (S)

- **What:** when `mlx` is installed, read the recommended working-set size
  from MLX's Metal device info (this is the same Metal value llmfit reads,
  `recommendedMaxWorkingSetSize`, `core/hardware.rs:2738-2742`); also read
  `sysctl -n iogpu.wired_limit_mb` (via the absolute `/usr/sbin/sysctl`),
  which is non-zero when the user raised the limit. Fall back to the current
  66% / 75% rule only when neither is available, and label which source was
  used.
- **Why:** the current rule is a heuristic and ignores a user-raised limit.
  "Measure, don't assume." Keep our stricter grading (point 7 in section 2);
  just feed it a measured number.
- **Files:** `hwprobe.py:apple_gpu_share` and `probe`, `tests/test_hwprobe.py`.
- **Verify:** the exact MLX key name for the working-set size on the
  installed `mlx` version before relying on it.

### 6. Estimated tok/s before download, checked against measured (M)

- **What:** for models that fit, print an estimated generation speed in
  `check`; after a run, show "est. -> measured" for tok/s as the scorecard
  already does for memory, and track the median ratio.
- **Why:** users decide what to download on speed as much as on fit. The
  estimate is cheap, and llm-bench is in the unusual position of being able
  to check every estimate it makes.
- **Files:** new `estimate.py` (or inside `registry.py`), `hwprobe.py` (GPU
  name to bandwidth), `cli.py`, `report.py`; add `active_b` to MoE rows in
  `registry.py`.
- **Copy from llmfit** (`core/fit.rs:1807-1850`, `:2040-2045`, `:73-75`):

  ```text
  tok_s = bandwidth_GBps / (active_params_b * bytes_per_param) * 0.55
  bytes_per_param (speed table): Q4_K_M 0.5, Q8_0 1.0, F16 2.0, mlx-4bit 0.5
  MoE: use active parameters for speed, total parameters for memory
  ```

  Bandwidths worth carrying (`core/hardware.rs:3079-3408`), GB/s: RTX 5090
  1792, 5080 960, 5070 Ti 896, 5070 672, 4090 1008, 4080 717, 4070 504,
  4060 Ti 288, 4060 272; Apple M1 68, M1 Pro 200, M1 Max 400, M2 100,
  M2 Pro 200, M2 Max 400, M3 100, M3 Pro 150, M3 Max 400, M4 120,
  M4 Pro 273, M4 Max 546, M5 153.6. These are public spec-sheet figures.
  Keep llmfit's rule that **laptop GPUs return no estimate**
  (`core/hardware.rs:3059-3077`): a "5070 Laptop GPU" has a narrower bus than
  the desktop card. When the GPU is unknown, print "unknown", not a
  per-backend constant.
- **Expect:** llmfit's own replay puts the median error at about 21% on
  unified memory and 30% on discrete GPUs
  (`llmfit-core/tests/estimator_accuracy.rs:34-37`). Label these numbers as
  estimates.

### 7. Label every number with its source (S)

- **What:** each speed and memory figure in `check` and the scorecard carries
  `measured`, `similar-hardware` or `estimate`, the same three words the
  modelfit plan uses.
- **Why:** llmfit's `EstimateConfidence` (`core/fit.rs:269-355`) shows why
  this matters: a formula number and a measurement both look like "42 tok/s".
  Exposing the inputs, as llmfit's `estimate_basis` does (`:237-262`), also
  makes every estimate reproducible.
- **Files:** `cli.py`, `report.py`, `bench.py` (store the label in rows).

### 8. A proper speed pass: warmup, repeats, spread (S to M)

- **What:** before the quality tasks, run one warmup request, then 3 short
  fixed prompts with a fixed output length; report median, min and max
  generation tok/s, and TTFT separately from load time. Keep the quality
  tasks as they are.
- **Why:** today `gen_tps` is an average over 13 tasks with very different
  output lengths, `ttft_s` is the maximum of (load + prompt eval), and the
  first task pays the load. llmfit warms up and repeats
  (`core/bench.rs:154-186`) and guards against impossible rates: fall back to
  wall clock when `eval_count < 2` or the rate exceeds 10,000 tok/s
  (`:55-60`, `:249-271`).
- **Files:** `runners.py`, `bench.py`, `report.py`, `tests/test_runners.py`.

### 9. A versioned, shareable result format with CI checks (M)

- **What:** give each result row a `schemaVersion`, the tool version, a
  timestamp and a hardware block, and write a JSON Schema plus a validator
  script that runs in CI. Add `check --json`. This prepares a future
  `llm-bench run --share` (the modelfit plan's data collector) without
  building the GitHub flow yet.
- **Why:** results are only comparable across machines if the hardware is in
  the same file as the numbers. llmfit's payload is a good, small starting
  point, and llm-bench would add what llmfit lacks: quality per category and
  measured peak memory.
- **Files:** `bench.py`, `cli.py`, new `schema/result.schema.json`, new
  `scripts/validate_results.py`, `.github/workflows/ci.yml`.
- **Copy from llmfit** (`llmfit-core/data/community/schema.json`,
  `core/share.rs:127-199`, `scripts/validate_community_benchmarks.py:39-125`):
  hardware fields `hwClass` (DISCRETE_GPU / UNIFIED / CPU_ONLY),
  `hardwareName`, `memTierGb` (snap to 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64,
  80, 96, 128, 192, 256), `vramGb`, `gpuCount`, `unifiedMemory`, `cpu`,
  `cpuCores`, `ramGb`, `os`; checks: file under 64 KiB, at most 100 results,
  timestamp not in the future, RAM <= 8192 GB, VRAM <= 2048 GB,
  `min <= avg <= max`, `avg > 0`. Never include user names, paths or
  hostnames (llmfit strips GGUF paths from model ids, `core/share.rs:141-160`).

### 10. Broader GPU detection (M)

- **What:** sum VRAM for identical NVIDIA cards (with a note that the split
  is Ollama's choice); read discrete Intel Arc VRAM from sysfs; name AMD
  cards from `device/product_name` or `lspci`; skip legacy Intel HD/UHD; treat
  Ryzen AI Max APUs as unified memory.
- **Why:** each is a real machine class that `check` gets wrong today. Do each
  only when a CI runner or a recorded tool output can test it.
- **Files:** `hwprobe.py`, `tests/test_hwprobe.py` with new fixtures.
- **Copy from llmfit:** the sysfs paths `tileN/physical_vram_size_bytes` (xe
  driver) and `drm/cardN/lmem_total_bytes` (i915) (`core/hardware.rs:1792-1842`);
  the legacy-iGPU reasoning (`:1510-1527`); the APU carveout logic
  (`:1378-1427`). llmfit's parser fixtures under
  `llmfit-core/tests/fixtures/hardware/` show real tool output formats; read
  them, but record our own fixtures rather than copying theirs.

### 11. `llm-bench doctor` (S)

- **What:** print the raw output of every probe (`nvidia-smi`, registry
  values, `sysctl`, sysfs files, `/api/tags`, `/api/ps`) next to what
  `probe()` concluded, ready to paste into an issue.
- **Why:** detection bugs are found on hardware we do not have, and each
  report becomes a test fixture, which is how the existing tests already
  work. llmfit's `core/doctor.rs:1-10` does exactly this.
- **Files:** `cli.py`, `hwprobe.py` (return raw text alongside parsed values).

### 12. Context-aware `check` and a `--vram/--ram` override (S, after 2)

- **What:** `check --ctx 16384` re-grades every model at that context, prints
  the largest context that fits for each model, and `--vram` / `--ram` let a
  user grade a machine they are about to buy or one where detection failed.
- **Why:** cheap once KV is modelled; llmfit's "usable context"
  (`core/fit.rs:848-862`) and overrides (`core/hardware.rs:2470-2614`) are
  among its most-used features.
- **Copy from llmfit:**
  `usable_ctx = min(max_ctx, (budget - weights - 0.5) / kv_gb_per_token)`.
- **Files:** `cli.py`, `hwprobe.py`, `registry.py`.

### Considered and not recommended

- **The 17,700-model catalogue.** It would turn a curated, runnable list into
  a predictor full of entries that no runtime we support can pull. A small
  script that refreshes metadata for our own rows is enough (see row
  "How it is built").
- **Heuristic quality scores** (params plus name bumps, `core/fit.rs:2150-2268`).
  llm-bench measures quality; mixing in guesses would weaken its main claim.
- **Regex rubric scoring** (`core/quality.rs`). Weaker than our code checks.
  Its YAML task format (prompt, rules, `max_tokens`) is a reasonable model if
  we ever let users add tasks without writing Python, but scorers should stay
  functions.
- **Per-backend speed constants** (`core/fit.rs:2048-2062`). Say "unknown".
- **TUI, REST API, MCP server, desktop app, Kubernetes claims, storage
  planning.** Out of scope for a benchmark CLI.
- **The GitHub device-flow auto-PR** (`core/share.rs`, about 1,700 lines).
  Worth revisiting once improvement 9 exists and there is demand.

---

## Method and caveats

- llmfit was shallow-cloned into a fresh temporary folder, read, and deleted.
  No llmfit code was built, installed or executed. Catalogue statistics come
  from loading `hf_models.json` as data with an isolated Python
  (`python3 -I`).
- "Ollama's default context is smaller than our long-context prompt" is a
  hypothesis to check (improvement 1), not a confirmed bug.
- The Rust `Command::new` note in section 2 is about pinning, not a claimed
  exploit: recent Rust versions do not search the current directory on
  Windows, but the lookup still depends on PATH order.
