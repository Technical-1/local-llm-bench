# Existing datasets of measured local LLM performance

Research date: 2026-10-18. Scope: datasets and leaderboards of MEASURED (not modelled) local LLM performance across consumer hardware. Note on method: about 24 search/fetch calls; several sources (localscore.ai, OpenBenchmarking) could only be read in part, so counts below are "as visible" and flagged where partial. Per project style, no em dashes are used.

## Q1. LocalScore (Mozilla Builders / llamafile): how big, how open?

### Takeaway
LocalScore is the closest prior art to "llm-bench --share" (opt-in CLI submission to a public leaderboard), but it is small, fixed to 3 official models on one runtime (llamafile/llama.cpp), single-GPU only, has no documented raw-data download or public API, and no stated anti-fraud controls.

### Cited Findings
- Owner/origin: a Mozilla Builders project by cjpais; repo `cjpais/LocalScore`, Apache-2.0, 232 commits, 135 stars, 19 forks, 18 open issues at time of fetch ([GitHub](https://github.com/cjpais/LocalScore); [Mozilla Builders](https://builders.mozilla.org/project/localscore/)).
- Collection: opt-in crowdsourced via the official LocalScore CLI only; other clients must follow a submission spec in `src/pages/api/results` and ask for inclusion via contact@localscore.ai ([GitHub](https://github.com/cjpais/LocalScore)).
- Runtime: built on llamafile; llamafile 0.9.2 (April 2025) bundled LocalScore as a built-in benchmark ([Phoronix](https://www.phoronix.com/news/LocalScore-AI-LLM-Benchmark)).
- Models: three "official" models, Llama 3.2 1B, Llama 3.1 8B and Qwen 2.5 14B, all Q4_K_M ([Hugging Face Mozilla/LocalScore](https://huggingface.co/Mozilla/LocalScore)). Phoronix's launch coverage instead described tiny/small/medium Llama 3.1 models, so the model set changed early on ([Phoronix](https://www.phoronix.com/news/LocalScore-AI-LLM-Benchmark)).
- Metrics: prompt processing tok/s, generation tok/s, time to first token (ms), combined into a single "LocalScore" ([GitHub](https://github.com/cjpais/LocalScore)).
- Hardware: CPU, NVIDIA, AMD, Apple Silicon; single-GPU only for submissions ([r/LocalLLM launch post via mirror](https://redlib.hackliberty.org/r/LocalLLM/comments/1jqn68v/localscore_local_llm_benchmark); [GitHub](https://github.com/cjpais/LocalScore)).
- Storage: SQLite via libSQL with Drizzle ORM; public API endpoints listed as future work; no anti-fraud measures mentioned ([GitHub](https://github.com/cjpais/LocalScore)).
- Size: the localscore.ai front page, as fetched, showed 20 unique accelerators and 43 results across the 3 models (20/11/12). This is the leaderboard view, not necessarily the whole database ([localscore.ai](https://www.localscore.ai/)).
- Phoronix also packages LocalScore as a PTS test; one CPU configuration had 240 public results from 21 May 2025 to 17 Oct 2025 on OpenBenchmarking ([OpenBenchmarking mirror](https://mail.openbenchmarking.org/performance/test/pts/localscore/692af4a31308c0aed31872990c62e0bcb1da9e9d)).

### Inferences
- The front-page counts suggest LocalScore's distinct-hardware coverage is in the tens, not thousands; momentum appears modest 18 months after launch. The licence covers code, not data, so reuse rights for the results are unclear.
- The design shows the limitation of a fixed model set: it gives comparable scores but cannot answer "how fast is model X at quant Y on my machine" for arbitrary shortlists, which is modelfit's question.

### Gaps
- Total submission count, latest submission date and data licence for localscore.ai were not found. The "Download" page in the site nav was not described by the fetch.

## Q2. llama.cpp community benchmark threads and llama-bench collections

### Takeaway
The llama.cpp GitHub Discussions are the largest high-quality, maintainer-moderated, cross-hardware datasets for a single runtime, but they are hand-curated markdown tables in discussion threads (not machine-readable), fixed to one old model (Llama 2 7B, mostly Q4_0), and each thread covers one backend.

### Cited Findings
- Apple Silicon thread #4167: started by ggerganov on 22 Nov 2023; 97 comments and 182 replies; latest visible activity 26 Jun 2026. Method: `llama-bench -p 512 -n 128 -ngl 99`, Llama 2 7B at F16, Q8_0, Q4_0, pinned build commit. Summary table has one row per chip (M1 to M5 Ultra plus an M6 row) with memory bandwidth, GPU cores, PP512 and TG128 t/s; includes a `plot.py` for PP vs cores and TG vs bandwidth ([GitHub #4167](https://github.com/ggml-org/llama.cpp/discussions/4167)).
- Vulkan thread #10879: started 18 Dec 2024 by netrunnereve; about 310 comments and 477 replies; latest visible post 9 Jul 2026. Method: Llama 2 7B Q4_0, `llama-bench -ngl 100 -fa 0,1`, one GPU at a time, must include git hash and Vulkan info string; "only valid runs" go on the scoreboard and newer commits replace older duplicates. Scoreboard (no-FA) has roughly 130 entries across AMD, NVIDIA, Intel, iGPUs, some CPUs, Android/ARM; top entry RTX 5090 at about 10,382 pp512 and 264 tg128 t/s ([GitHub #10879](https://github.com/ggml-org/llama.cpp/discussions/10879)).
- CUDA thread #15013 ("Performance of llama.cpp on Nvidia CUDA"): 120+ comments; CUDA scoreboards for Llama 2 7B Q4_0 with and without flash attention, listing GPU, build commit and power limits ([GitHub #15013](https://github.com/ggml-org/llama.cpp/discussions/15013)).
- No dedicated ROCm scoreboard thread was found; ROCm is discussed inside the CUDA thread ([GitHub #15013](https://github.com/ggml-org/llama.cpp/discussions/15013)). A third-party page reproduces CUDA/ROCm/Vulkan scoreboard tables (unverified) ([knightli.com, Apr 2026](https://knightli.com/en/2026/04/23/llama-cpp-gpu-benchmark-cuda-rocm-vulkan-scoreboard/)).
- XiongjieDai/GPU-Benchmarks-on-LLM-Inference: lab-style single-author collection, llama.cpp `llama-bench`, about 16 NVIDIA GPU models (incl. multi-GPU on RunPod) plus 4 Apple Silicon configs, Llama 3 8B/70B at Q4_K_M and F16, pp/tg at 512 to 8192 tokens plus a perplexity table; snapshot dated May 2024; 1.9k stars, 76 forks, 58 commits; licence not stated ([GitHub](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference)).
- Quality control in the threads is manual: maintainers pin a commit, prescribe exact commands and env vars (e.g. `RADV_PERFTEST=nogttspill`), and curate the summary table ([GitHub #10879](https://github.com/ggml-org/llama.cpp/discussions/10879); [GitHub #4167](https://github.com/ggml-org/llama.cpp/discussions/4167)).

### Inferences
- Combined, the three threads cover perhaps 250 to 300 distinct accelerators, which is likely more distinct hardware than LocalScore, but only for one model/quant. They are a good seed/validation set for modelfit's bandwidth-based estimator (TG scales with memory bandwidth, as the #4167 plot shows) and could be scraped, subject to GitHub content terms.
- They show community willingness to run a standard command and post results when the maintainer is trusted and the output is self-describing (llama-bench prints backend, build, model, test).

### Gaps
- No machine-readable export of these threads exists that I found. Licence of posted results is unclear (GitHub user content).

## Q3. Geekbench AI, MLPerf Client, Procyon AI Text Generation, OpenBenchmarking.org

### Takeaway
Commercial/consortium benchmarks measure LLM speed on client hardware, but either do not publish a browsable per-machine LLM database (MLPerf Client, Procyon) or do not run LLM text generation at all (Geekbench AI). OpenBenchmarking.org (Phoronix Test Suite) is the one large, open, crowdsourced store with a llama.cpp profile, and it is genuinely active in 2026.

### Cited Findings
- Geekbench AI (Primate Labs): launched Aug 2024 with ten tests, eight computer vision and two NLP; no LLM text-generation workload found; has a public results browser; latest version 1.5 described only as framework updates ([HotHardware](https://hothardware.com/news/geekbench-ai-benchmark); [Geekbench blog](https://geekbench.com/blog); [Geekbench AI](https://www.geekbench.com/ml/)). Geekbench 7 (released 23 July, per one report) adds AI workloads, including Whisper; LLM coverage not confirmed ([letsdatascience](https://letsdatascience.com/news/primate-labs-releases-geekbench-7-with-ai-workloads-4fd907fe)).
- MLPerf Client (MLCommons): targets laptops/desktops/workstations; measures time to first token and tokens/s (excluding first token) with an MMLU accuracy gate; v1.5 released Nov 2025 with experimental Linux (OpenVINO only); Windows supports GPUs, NPUs, CPUs via multiple execution providers ([Phoronix](https://www.phoronix.com/news/MLPerf-Client-1.5-Linux); [Signal65](https://signal65.com/research/ai/mlperf-client-v0-5-benchmark-brings-mlcommons-to-pcs/)). Results surface mainly via vendor write-ups, e.g. AMD reports up to 61 tok/s on Ryzen AI Max+ 395 iGPU with Phi-3.5 on v1.0 ([AMD](https://www.amd.com/en/developer/resources/technical-articles/2025/unlocking-peak-ai-performance-with-mlperf-client-on-ryzen-ai-.html)); Intel reported 1.09 s TTFT and 18.55 tok/s on NPU in v0.6 ([Jon Peddie](https://www.jonpeddie.com/news/intel-the-first-company-to-attain-npu-support-in-mlperf-client-v0-6-benchmark/)). One guide claims v1.6.1 was released 20 Apr 2026 (single source, unverified) ([itechguides](https://www.itechguides.com/?p=717793)).
- Procyon AI Text Generation (UL, maker of 3DMark): Windows, four preloaded models, seven prompts covering RAG and non-RAG workloads; measures tokens/s, latency and resource use; runtimes include ONNX Runtime DirectML (e.g. an RTX 4090 sample: Phi-3.5 226.56, Mistral 7B 171.9, Llama 3.1 142.26, Llama 2 90.59 tok/s) ([UL](https://benchmarks.ul.com/en-sc/procyon/ai-text-generation-benchmark); [StorageReview](https://www.storagereview.com/procyon-ai-text-and-image-generation-benchmark)). Procyon is a paid professional product; no public per-machine database found.
- OpenBenchmarking.org `pts/llama-cpp`: created 10 Jan 2024, last updated 25 Apr 2026, 12 profile versions (1.0.0 to 2.5.0, now llama.cpp b8933); backends CPU BLAS (34.1% of use), Vulkan (42.0%), CUDA (23.8%), with ROCm and SYCL options; models include Qwen3.5-9B, gpt-oss-20b, Llama-3.1-Tulu-3-8B, Mistral-7B-v0.3, granite-3.0-3b, DeepSeek-R1-Distill-Llama-8B, GLM-4.7-Flash, MiniMax-M2.5; tests PP512/1024/2048 and TG128; "60k+ downloads"; uploading is opt-in; stats updated weekly (as of 16 Oct 2026) ([OpenBenchmarking](https://mail.openbenchmarking.org/test/pts/llama-cpp)).
- OpenBenchmarking per-configuration counts are in the tens to low hundreds: 198 public results for b8933/Vulkan/gpt-oss-20b-Q8_0/PP2048 since 25 Apr 2026; 252 for CPU BLAS Tulu-3-8B PP512 (Nov 2025 to Feb 2026); 66 for CPU BLAS Tulu TG128 (Apr to May 2026); 92 for Llama 3 8B in mid-2024 ([OpenBenchmarking](https://mail.openbenchmarking.org/test/pts/llama-cpp); [config page](https://mail.openbenchmarking.org/performance/test/pts/llama-cpp/db257a7755adbe206b4709bcdd5c5fdb23ba90fa)).
- OpenBenchmarking also hosts `pts/localscore` ([OpenBenchmarking](https://mail.openbenchmarking.org/test/pts/localscore&eval=2259495c9b14dae5adca2b76d907512e7e5670cd)).

### Inferences
- OpenBenchmarking is the most significant open crowdsourced store: rich system metadata (PTS captures full hardware/software), opt-in upload, years of history. Its weakness for modelfit: results fragment across many profile versions/builds/models (each config sees only tens to hundreds of results), it covers only llama.cpp (no Ollama/MLX/vLLM), and it skews Linux and enthusiast. Version churn (12 versions in under 3 years) resets comparability, a lesson for llm-bench's suite versioning.
- MLPerf Client and Procyon are vendor-facing; they will not supply crowdsourced per-machine data but are useful as credibility references for methodology (accuracy gate, TTFT definitions).

### Gaps
- No total result count for `pts/llama-cpp` was shown; openbenchmarking.org returned 403 to direct fetch. OpenBenchmarking data export/API terms were not confirmed in this pass (PTS does support result export locally; public bulk API not verified).
- Whether MLCommons publishes an official MLPerf Client results table was not confirmed.

## Q4. GitHub aggregations, spreadsheets, r/LocalLLaMA tables, Hugging Face datasets

### Takeaway
Besides the llama.cpp threads and XiongjieDai, there is a new direct competitor: llm-speed (llm-speed.com), a 2026 crowdsourced, cryptographically signed, multi-backend dataset on Hugging Face under CC BY 4.0. It is tiny (220 rows) but its design (signed runs, hardware fingerprint, open licence, multi-runtime, workload suite) is almost exactly modelfit's planned moat.

### Cited Findings
- llm-speed (`llmspeed/llm-speed-benchmarks`): crowdsourced via an open-source CLI; each run is fingerprinted to real hardware and signed (EdDSA/JWS) on upload so values "cannot be edited after the fact"; 220 rows; columns `id, permalink, suite_version, top_model_name, top_backend, top_workload, accelerator_summary, top_decode_tps, received_at`; backends named include ollama, llama.cpp, mlx, vllm, exllamav2 (3 distinct in data); 10 distinct accelerators (RTX 3090/4090/5090, Apple Silicon); workloads chat-short, chat-long, agent-trace, concurrent-decode (suite-v1); CC BY 4.0; received_at 2026-04-26 to 2026-07-08; Zenodo DOI 10.5281/zenodo.21254813 ([Hugging Face](https://huggingface.co/datasets/llmspeed/llm-speed-benchmarks)).
- LocalLLMAdvisor/local-llm-advisor-benchmarks: 253 llama-bench measurements by one party on rented NVIDIA GPUs, six GPUs, 11 GGUF models; not crowdsourced ([Hugging Face](https://huggingface.co/datasets/LocalLLMAdvisor/local-llm-advisor-benchmarks)).
- Tools without shared datasets: inferbench (JoniMartin27; llama.cpp + cloud APIs, 124-model catalog, optimal-quant picker, MCP mode), InferBench (RudrenduPaul; llama.cpp, omlx) ([GitHub](https://github.com/JoniMartin27/inferbench); [GitHub](https://github.com/RudrenduPaul/InferBench)). A gist benchmarks Ollama, LM Studio, Foundry Local and vLLM ([gist](https://gist.github.com/rajbos/8c9a5bfb832469db52482082f88aae06)).
- Academic: Bench360 (arXiv 2511.16682) benchmarks local inference from multiple angles, but is a paper, not a crowdsourced dataset ([arXiv](https://arxiv.org/html/2511.16682v1)).

### Inferences
- The "signed, fingerprinted, open-licensed, multi-runtime crowdsourced dataset" idea already exists in llm-speed, so modelfit's moat cannot be the concept alone; it must be scale and distribution (a library that app developers embed creates pull for llm-bench submissions). llm-speed's small size after ~3 months suggests bootstrapping submissions is the hard part.
- inferbench's "optimal-quant picker" overlaps modelfit's recommendation feature at the CLI level.

### Gaps
- Did not find a widely-cited r/LocalLLaMA master spreadsheet in this pass; Reddit compilations exist anecdotally but none with a stable URL/size was verified. llm-speed's full site data (beyond the HF summary rows) and owner identity were not examined.

## Q5. WebGPU / WebLLM performance across devices

### Takeaway
No public, downloadable cross-device WebLLM/WebGPU LLM performance dataset was found; data exists only as small paper tables, single-device blog numbers, and one unverified community leaderboard.

### Cited Findings
- LlamaWeb paper (arXiv 2605.20706) compares WebGPU engines on four GPUs; reports LlamaWeb median decode tok/s exceeds WebLLM by 54% and Transformers.js by 69% ([alphaXiv](https://www.alphaxiv.org/abs/2605.20706)).
- WebLLM paper claims up to 80% of native performance on the same device ([HF papers](https://huggingface.co/papers?q=WebLLM)).
- InventiveHQ in-browser benchmark loads a model via WebLLM and aggregates submitted results into a community leaderboard; methodology and size unverified ([InventiveHQ](https://inventivehq.com/tools/developer/llm-gpu-benchmark)).

### Inferences
- Browser inference is a gap nobody has filled with data; a WebGPU runner in llm-bench would be differentiated, but browser device identification is weak (GPU strings are masked by browsers), complicating hardware keying.

### Gaps
- No size/schema found for the InventiveHQ leaderboard; WebLLM repo has no results file that surfaced.

## Q6. MLX benchmark collections for Apple Silicon

### Takeaway
No canonical MLX results collection exists; the most direct lead is mlx-chronos, a 2026 open-source CLI with a public leaderboard across MLX engines. Otherwise data is scattered in papers and blogs, and the llama.cpp #4167 thread remains the best Apple Silicon reference (Metal, not MLX).

### Cited Findings
- mlx-chronos (igurss/mlx-chronos): CLI suite comparing mlx-lm, oMLX, vllm-mlx, Rapid-MLX and Ollama's MLX backend; records TTFT, sustained throughput, peak RAM and thermal context; can submit to a public leaderboard ([HF forum](https://discuss.huggingface.co/t/mlx-chronos-reproducible-benchmarks-for-local-mlx-inference-engines-on-apple-silicon/176764)).
- Ollama 0.19 moved to an MLX engine on Mac; Ollama's chart shows Qwen3.5-35B-A3B decode rising from 58 to 112 tok/s vs the old llama.cpp path ([Level Up Coding](https://levelup.gitconnected.com/ollama-mlx-nearly-doubles-llm-speed-on-your-mac-58-to-112-tok-s-and-your-old-models-get-none-of-fd1a9ec531fb)).
- Caveat on metrics: one M1 Max test found MLX showing 51 tok/s decode while effective wall-clock throughput including prefill collapsed to about 3 tok/s at long context ([Towards AI](https://pub.towardsai.net/apples-mlx-runs-local-llms-3x-faster-than-llama-cpp-until-your-context-hits-40k-715ec441afbb)).
- Comparative paper on MLX, MLC-LLM, Ollama, llama.cpp, PyTorch MPS on Apple Silicon (arXiv 2511.05502) ([arXiv](https://arxiv.org/pdf/2511.05502)).

### Inferences
- Runtime choice changes speed by up to 2x on the same Mac (Ollama MLX vs llama.cpp path), confirming that modelfit's key must include runtime and runtime version, and that context length must be part of the workload definition.

### Gaps
- mlx-chronos leaderboard size and data licence not verified.

## Q7. Lessons from analogous crowdsourced hardware datasets

### Takeaway
Crowdsourced benchmark databases face three recurring problems: spoofed device identity, scoring choices perceived as biased (UserBenchmark), and comparability loss from version churn. Geekbench's approach (reject VMs and forgeries, flag invalid configs, consistency checks) is the practical baseline; signing proves a result came from the official client but cannot prove the hardware string.

### Cited Findings
- Geekbench device spoofing: a fake "POCO F1 Lite" listing was created by editing system build properties; the score was real, the device identity invented ([XDA](https://www.xda-developers.com/xiaomi-poco-f1-lite-fake-benchmark/)). Primate Labs' John Poole flagged a supposed M6 Pro result as likely fake in Sept 2026 due to internal inconsistencies ([MacRumors](https://macrumors.com/2026/09/19/m6-pro-geekbench-result-likely-fake)).
- Geekbench 6.7 detects Intel's Binary Optimization Tool and marks such results invalid in the browser; older results remain flagged ([Igor's Lab](https://www.igorslab.de/en/geekbench-6-7-pulls-the-plug-on-intels-bot-and-makes-future-cpu-leaks-much-harder-to-predict/)). Primate Labs removes forged results and results from virtual machines ([Primate Labs, 2008](https://www.primatelabs.com/blog/2008/04/removing-results/)).
- UserBenchmark: 2019 re-weighting of its CPU index (de-emphasising >8 cores) caused large rank shifts and accusations of bias; the site attacked critics as "incompetent smearers"; its reputation never recovered and several communities ban links to it ([Tom's Hardware](https://www.tomshardware.com/news/userbenchmark-benchmark-change-criticism-amd-intel%2C40032.html); [Overclock3D](https://overclock3d.net/news/software/userbenchmark-calls-media-incompetent-smearers-in-the-face-of-cpu-weighting-criticisms/); [r/Amd wiki](https://lr.eu.psf.lt/r/Amd/wiki/userbenchmark)).
- llama.cpp threads use curation (pinned commits, required build hash and device info string, replacing stale entries) as quality control ([GitHub #10879](https://github.com/ggml-org/llama.cpp/discussions/10879)).

### Inferences
- For modelfit: publish raw measurements and keep any composite score transparent (UserBenchmark lesson); store runtime build hash and full device strings and run consistency checks (e.g. reported tok/s vs memory bandwidth ceiling) rather than trusting identity; flag VM/containers; version the suite but keep a stable core workload so results stay comparable across versions (OpenBenchmarking churn lesson). Signing (as llm-speed does) proves provenance, not truth.

### Gaps
- Steam Hardware Survey growth/QC history was not researched in this pass. Geekbench browser total result counts were not found.

## Summary table (as of Oct 2026)

| Dataset | Owner | Collection | Size (verified) | Runtimes | Keying / metrics | Licence / access | Activity |
|---|---|---|---|---|---|---|---|
| LocalScore | Mozilla Builders (cjpais) | Opt-in CLI crowdsource | Front page: 43 results, 20 accelerators | llamafile | 3 fixed models Q4_K_M; PP, TG, TTFT, composite score | Code Apache-2.0; no data API found | Low-moderate |
| llama.cpp #4167 Apple | ggml-org | Community posts, curated table | 97 comments/182 replies; M1 to M5 | llama.cpp Metal | Llama 2 7B F16/Q8_0/Q4_0; pp512, tg128 | Markdown in GitHub | Active (Jun 2026) |
| llama.cpp #10879 Vulkan | ggml-org | Community, curated | ~130 scoreboard rows; 310 comments | llama.cpp Vulkan | Llama 2 7B Q4_0; pp512, tg128, FA on/off | Markdown in GitHub | Active (Jul 2026) |
| llama.cpp #15013 CUDA | ggml-org | Community, curated | 120+ comments | llama.cpp CUDA | Llama 2 7B Q4_0 | Markdown in GitHub | Active |
| OpenBenchmarking pts/llama-cpp | Phoronix | Opt-in crowdsource | Tens to ~250 per config; 60k+ downloads | llama.cpp CPU/Vulkan/CUDA/ROCm/SYCL | Per build+backend+model+test; PP, TG | Public web results; bulk API unverified | Very active (weekly) |
| llm-speed | llmspeed | Signed CLI crowdsource | 220 runs, 10 accelerators | ollama, llama.cpp, mlx, vllm, exllamav2 | model, backend, workload, accelerator; decode tps, TTFT | CC BY 4.0, HF + Zenodo | New (Apr to Jul 2026) |
| XiongjieDai GPU-Benchmarks | individual | Lab (RunPod + own Macs) | ~16 NVIDIA + 4 Apple | llama.cpp | Llama 3 8B/70B; pp/tg 512 to 8192 | GitHub, licence unstated | Stale (May 2024) |
| LocalLLMAdvisor HF | LocalLLMAdvisor | Lab, rented GPUs | 253 rows, 6 GPUs, 11 models | llama.cpp | llama-bench | HF dataset | Unknown |
| MLPerf Client | MLCommons | Lab / vendor | Not a crowd DB | ONNX/OpenVINO/vendor EPs | TTFT, tok/s, MMLU gate | Free tool; results via vendors | v1.5 Nov 2025 |
| Procyon AI Text Gen | UL | Lab, paid tool | No public DB found | ONNX Runtime DirectML etc. | tok/s, latency | Commercial | Active |
| Geekbench AI | Primate Labs | Crowdsource browser | Large, count unknown | CoreML/ONNX/etc. | No LLM text gen | Browser, no bulk export known | v1.5 |
| mlx-chronos | igurss | CLI + leaderboard | Unknown | MLX engines, Ollama MLX | TTFT, throughput, RAM, thermals | Open source | New (2026) |
