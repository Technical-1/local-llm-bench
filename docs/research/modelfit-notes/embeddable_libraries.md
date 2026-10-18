# Embeddable libraries that detect hardware and pick or check a local LLM (as of 2026-10-18)

Scope: installable code (npm, PyPI, crates.io, Go modules, platform SDKs), not end-user websites. Research done 2026-10-18 with web search and page fetches. Star counts and versions are as seen on the fetched pages that day.

## Are there npm, PyPI or crates.io packages that recommend a local model for the current hardware?

### Takeaway
Yes, and the space got crowded in 2026. The leader is **llmfit** (Rust, MIT, about 38k GitHub stars, on crates.io as `llmfit` / `llmfit-core` and on PyPI as `llmfit`, v1.1.17 released 2026-10-08). It already does hardware detection, fit ranking, estimated tok/s, a "measured vs estimated" confidence field, and replaces estimates with local `llmfit bench` results. But every one of these tools is shaped as an **end-user CLI/TUI, HTTP server or MCP server over its own model catalog**. None documents a one-call, in-process library API where the app developer passes their own shortlist. That gap is the opening for modelfit, and it is narrower than it looks: `llmfit-core` is a real library crate, so a determined Rust developer could embed it today.

### Cited Findings

**llmfit (AlexsJones/llmfit): the main competitor**
- Detects CPU, RAM, GPUs and VRAM, then ranks open models by fit, speed, quality and context. Ships a TUI, a CLI and a web dashboard. Supports Ollama, llama.cpp, MLX, Docker Model Runner and LM Studio. MIT. 38.1k stars, 2.5k forks at time of fetch — [GitHub](https://github.com/AlexsJones/llmfit)
- Memory is projected from parameter count, context length and quantization. Speed comes from a memory-bandwidth model "grounded in runtime sampling and real community measurements". `llmfit bench` measures real tok/s and TTFT, and measured results replace estimates in the fit table — [GitHub](https://github.com/AlexsJones/llmfit)
- GPU support listed: NVIDIA CUDA, Apple Silicon, AMD ROCm, Intel OneAPI, discrete and integrated, unified memory — [GitHub](https://github.com/AlexsJones/llmfit)
- Has a "planning mode" (what hardware a given model needs) — [Hongkiat](https://www.hongkiat.com/blog/llmfit-local-llm-guide/); [Terminal Trove](https://terminaltrove.com/llmfit/)
- `llmfit-core` crate: "Core library for llmfit — hardware detection, model fitting, and provider integration", v1.1.17, 2026-10-08. Depends on `sysinfo` ^0.39, `objc2-metal`, `ureq`, `which` and others. No `nvml-wrapper` dependency. Only about 51% of items documented, no examples — [docs.rs](https://docs.rs/crate/llmfit-core/latest)
- A third-party write-up says llmfit gets RAM from `sysinfo` and GPU VRAM from vendor command-line probes — [Instagit](https://instagit.com/AlexsJones/llmfit/how-llmfit-detects-hardware-specs/) (secondary source)
- PyPI `llmfit` 1.1.17 (2026-10-08): platform wheels of about 6 to 7 MB. The page documents only CLI commands (`recommend`, `fit`, `serve`), no Python import API. That points to a binary shipped through pip — [PyPI](https://pypi.org/project/llmfit/)
- REST API (`llmfit serve`, default `127.0.0.1:8787`): `/api/v1/system`, `/api/v1/models`, `/api/v1/models/top`, `/api/v1/models/{name}`, `/api/v1/concurrency`, `/api/v1/storage`, `POST /api/v1/plan`. Filters include `use_case`, `runtime`, `min_fit`, `max_context`, `force_runtime`. Each row returns `fit_level`, `run_mode`, `score` plus `score_components`, `estimated_tps`, `estimate_confidence` (from `measured_local` down to `unsupported`), `prefill_tps`, `ttft_ms`, `memory_required_gb`, `memory_available_gb`, `best_quant`, `usable_context`, `estimate_basis`, `verify_command` (a `llama-bench` command) and `measured_tps`. It also has an MCP mode with `recommend_models` and `plan_hardware` tools. API.md documents no Rust-library or Python-import usage — [API.md](https://github.com/AlexsJones/llmfit/blob/main/API.md)
- No npm package was found in any source — [GitHub](https://github.com/AlexsJones/llmfit); [Hongkiat](https://www.hongkiat.com/blog/llmfit-local-llm-guide/)
- Name collision: a site at modelfit.io runs an "LLMfit ... No-Install Online Option" blog page — [modelfit.io](https://modelfit.io/blog/llmfit-find-best-llm-for-your-hardware/)

**llm-checker (npm, Pavelevich/llm-checker)**
- Node.js CLI plus MCP server. Detects Apple Silicon, NVIDIA CUDA, AMD ROCm, Intel Arc and CPU in "pure JavaScript" (`src/hardware/detector.js`). The detection library is not named. About 3.0k stars. Newest release on the page is v3.7.0 (no date). A separate listing shows a v3.8.2 under the `signerless/llm-checker` owner — [GitHub](https://github.com/Pavelevich/llm-checker); [newreleases](https://newreleases.io/project/github/signerless/llm-checker/release/v3.8.2)
- **Licence NPDL-1.0 (No Paid Distribution License)**: selling it, or offering it as a paid hosted or API service, needs a commercial licence. A different page says MIT. The repo says NPDL — [GitHub](https://github.com/Pavelevich/llm-checker); [x-cmd](https://x-cmd.com/install/llm-checker)
- Uses a deterministic formula: Quality, Speed, Fit and Context scores, weighted by use case. Memory uses "calibrated bytes-per-parameter values". Speed is estimated tok/s from backend and model size. Quality can come from measured public benchmarks, and results are tagged `measured` or `estimated`. It measures real speed through `ai-run` and `benchmark` — [GitHub](https://github.com/Pavelevich/llm-checker)
- Catalog: a packaged SQLite snapshot of the Ollama catalog plus a multi-source registry (HF, ModelScope, Ollama, Docker Hub, GPT4All). Runtimes: `--runtime auto/ollama/vllm/mlx/llama.cpp/transformers`. No documented `require`/`import` API — [GitHub](https://github.com/Pavelevich/llm-checker)
- Older predecessor package: `ollama-checker` 3.0.7 — [jsDelivr README](https://cdn.jsdelivr.net/npm/ollama-checker@3.0.7/README.md)

**Smaller PyPI CLIs (all CLI-first, none documents an import API)**
- **whichllm** 0.5.20 (2026-10-03, MIT, Python 3.11+): detects NVIDIA (via `nvidia-ml-py`), AMD ROCm, Intel, Apple Metal and CPU. Ranks HuggingFace models by blending leaderboards (LiveBench, Artificial Analysis, Aider, Arena ELO, Open LLM Leaderboard) with size, quant, runtime fit and estimated speed from memory bandwidth. Does not measure tok/s. Can simulate a GPU (`--gpu "RTX 4090"`). Has `--json` output — [PyPI](https://pypi.org/project/whichllm/)
- **canirunllm** 0.1.4 (2026-09-21, MIT): estimates weights, KV cache, overhead and safety margin, picks a memory strategy, and gives a modelled tok/s labelled as an estimate. Each verdict carries a confidence and a reason. GPU detection is NVIDIA-only — [PyPI](https://pypi.org/project/canirunllm/)
- **llmscan**: rates each model great/ok/tight/no with reason codes. Has a `--backend` flag for Ollama, llama.cpp or MLX, a bundled catalog of 45+ models, and NVIDIA (nvidia-smi), AMD (rocm-smi) and Apple detection. Version and licence not shown — [PyPI](https://pypi.org/project/llmscan/)
- Also on PyPI, not inspected: `bestllm`, `ggufit` (page did not load), `spec2llm`, `best-engine-ai-helper` — [PyPI bestllm](https://pypi.org/project/bestllm/); [PyPI ggufit](https://pypi.org/project/ggufit/); [PyPI spec2llm](https://pypi.org/project/spec2llm/); [PyPI best-engine-ai-helper](https://pypi.org/project/best-engine-ai-helper/1.0.0/)
- **llm-fit** (HF repo, npm project): the user passes `--ram=16 --vram=8` by hand. Auto-detection is still listed as a future milestone — [Hugging Face](https://huggingface.co/williamKang112/llm-fit)

### Inferences
- llmfit has already taken the "which model fits my machine" spot for end users, along with its name space ("llmfit" vs "modelfit"). modelfit's difference has to be the developer-facing shape: (1) an in-process call with the developer's own shortlist, not a catalog, (2) npm and PyPI bindings with a real import API, (3) a shared, crowd-measured dataset across machines (llmfit's measured data is per machine, from local `bench`), and (4) a stable, documented contract.
- llmfit's response schema (`estimated_tps`, `estimate_confidence`, `measured_tps`, `verify_command`) is very close to modelfit's planned "measured / similar-hardware / estimate" field. Expect llmfit could add this quickly if it chose to. It is MIT, so modelfit could also study or reuse its heuristics, with attribution.
- llm-checker's NPDL licence makes it a poor building block for commercial apps. That is an argument for an MIT/Apache modelfit.

### Gaps
- No `llmfit-core` public function list was readable, so it is unconfirmed whether it offers a clean `rank(models, hardware)` call that would let it be embedded today. Worth reading the crate source directly.
- Weekly download numbers for npm, PyPI and crates.io were not collected for any package.
- llmfit's exact tok/s formula (`docs/how-it-works.md`) was not read.

## What do app frameworks bundling local models do?

### Takeaway
The runtimes have moved hard toward **auto-fitting one given model to the hardware** (GPU layers, context size, variant) rather than **choosing between models**. node-llama-cpp is the closest in-process API: it scores how well a given GGUF fits and returns RAM and VRAM usage, but gives no tok/s and has no "pick from a list" call. Foundry Local chooses a hardware-specific *variant* of one model. Platform SDKs (Apple, Chrome) only answer "is the built-in model available on this device".

### Cited Findings

**node-llama-cpp (npm), the most relevant**
- CLI: `inspect gpu` reports hardware. `inspect estimate <model path or URL>` estimates "compatibility of a model with the current hardware" without downloading the file. Options cover `--gpu auto|metal|cuda|vulkan|false`, `--gpuLayers` (default worked out from available VRAM), `--contextSize`, and `--maxRam`/`--maxVram`, which lower the compatibility score — [inspect estimate docs](https://node-llama-cpp.withcat.ai/cli/inspect/estimate); [choosing a model guide](https://node-llama-cpp.withcat.ai/guide/choosing-a-model)
- Programmatic: `GgufInsights.from(ggufFileInfo, llama?)`, `estimateModelResourceRequirementsV2({gpuLayers, useMmap})`, `estimateContextResourceRequirementsV2({contextSize, modelGpuLayers, flashAttention, kvCacheKeyType, ...})`. The docs call the graph overhead estimate rough — [GgufInsights API](https://node-llama-cpp.withcat.ai/api/classes/GgufInsights)
- `GgufInsightsConfigurationResolver.resolveAndScoreConfig()` and `scoreModelConfigurationCompatibility()` return `{compatibilityScore, bonusScore, totalScore, resolvedValues}`. `resolvedValues` holds `gpuLayers`, `contextSize`, `useMmap`, and RAM and VRAM usage for model, context and total. The score is based on how many layers offload, whether everything fits on the GPU, and whether the requested context fits. **No tokens/sec in the output** — [ConfigurationResolver API](https://node-llama-cpp.withcat.ai/api/classes/GgufInsightsConfigurationResolver)
- `readGgufFileInfo` reads metadata from a URL without a download. `resolveModelFile` was added in v3.1.0 — [choosing a model guide](https://node-llama-cpp.withcat.ai/guide/choosing-a-model)
- Inference: a developer *could* loop `resolveAndScoreConfig` over a shortlist to pick the best-fitting model. That is the closest existing thing to `pickModel` for JS, but it is GGUF/llama.cpp-only and gives no speed.

**llama.cpp itself (and bindings)**
- llama.cpp binaries now auto-fit a model to free device memory through `-fit`/`--fit` (on by default). `--fit-target` is a per-device margin (default 1024 MiB) and `--fit-ctx` a minimum context (default 4096). They call `llama_params_fit`, and `llama-fit-params` prints the resulting CLI arguments — [fit-params README mirror](https://huggingface.co/datasets/echodict/llama.cpp/blob/main/tools/fit-params/README.md); [llama-cli man page](https://dyn.manpages.debian.org/testing/llama.cpp-tools/llama-cli.1.en.html)
- Rust crate `llama-cpp-2` exposes `fit_params`, which works out n_gpu_layers, tensor_split and tensor_buft_overrides from available VRAM — [docs.rs llama-cpp-2](https://docs.rs/llama-cpp-2/latest/llama_cpp_2/model/params/struct.LlamaModelParams.html)
- LocalAI deleted its own Go GGUF VRAM estimator because "this is now handled directly in llama.cpp" — [LocalAI commit mirror](https://gitea.varghacsongor.hu/GithubMirror/LocalAI/commit/800f749c7ba2fdefce6270fc22167a256a418983)

**LM Studio**
- The app estimates memory before a load and warns (guardrails). Since 0.3.27 the estimate counts context length, flash attention and vision. The CLI has `lms load --estimate-only` — [LM Studio 0.3.27 blog](https://lmstudio.ai/blog/lmstudio-v0.3.27); [lms load docs](https://www.lmstudio.ai/docs/cli/local-models/load)
- Accuracy complaints: one estimate was about 22.9 GB against about 11.5 GB actually used in llama.cpp — [lms issue #499](https://github.com/lmstudio-ai/lms/issues/499)

**Microsoft Foundry Local**
- Detects hardware and downloads the variant that best matches it: CUDA build for NVIDIA, NPU build for Qualcomm NPU, CPU otherwise. Selected once per model and cached. "Zero detection code required" (GA, April 2026). The Windows package `foundry-local-sdk-winml` uses Windows ML, and Apple silicon uses WebGPU — [Microsoft Learn: what is Foundry Local](https://learn.microsoft.com/en-us/azure/foundry-local/what-is-foundry-local); [Foundry Local GA blog](https://devblogs.microsoft.com/foundry/foundry-local-ga/); [architecture](https://learn.microsoft.com/en-my/Azure/foundry-local/concepts/foundry-local-architecture)
- It picks a variant of one model, not which model. It works only with Foundry's ONNX catalog.

**Jan**
- The Hub labels models "Slow on your device" or "Not enough RAM". Per a mirrored commit, the llamacpp extension compares total required memory with usable memory, and returns YELLOW when a model fits combined RAM+VRAM but not VRAM — [Jan local models docs](https://www.mintlify.com/janhq/jan/features/local-models); [Jan mirror](https://git.biohazardvfx.com/Nicholai/jan/src/tag/v0.6.10)

**Platform SDKs (availability checks only)**
- Apple Foundation Models: `SystemLanguageModel.default.availability` returns available, or unavailable with a reason such as `.deviceNotEligible`, Apple Intelligence turned off, or model still downloading. iOS 26+ — [Apple docs](https://developer.apple.com/documentation/foundationmodels/systemlanguagemodel.md); [Kodeco](https://www.kodeco.com/53631607-getting-started-with-apple-s-foundation-models)
- Chrome Prompt API: `LanguageModel.availability()` returns states such as "unavailable" or "downloadable". Hardware bar: GPU with strictly more than 4 GB VRAM, or CPU with 16 GB+ RAM and 4+ cores, plus 22 GB free disk — [Chrome Prompt API](https://developer.chrome.com/docs/ai/prompt-api)

**WebLLM (`@mlc-ai/web-llm`)**
- `prebuiltAppConfig.model_list` lists built-in models — [unpkg README](https://app.unpkg.com/@mlc-ai/web-llm@0.2.84/files/README.md). A secondary article says each entry has `vram_required_MB` (about 0.7 GB for gemma3-1b up to about 6.4 GB for Qwen3.5-9B, 4-bit) — [tproger](https://tproger.ru/articles/webllm-zapuskaet-yazykovuyu-model-v-brauzere-bez-servera-za-odin) (not checked against source). This is static metadata the developer could filter on. There is no picker.

### Inferences
- The trend (llama.cpp `--fit`, LM Studio guardrails, Foundry variants) means "will this one model load" is becoming a solved, built-in problem. modelfit's value has to sit one level up: which of N candidates, how fast, measured or not, across runtimes.
- modelfit could use llama.cpp's `llama_params_fit` (through `llama-cpp-2`) or node-llama-cpp's resolver as a ground-truth memory check for GGUF, rather than re-deriving formulas.

### Gaps
Not verified in this session (no sources fetched), so no claims are made: Ollama SDKs (ollama-js, ollama-python), llama-cpp-python, lmstudio-js / lmstudio-python SDK surface (the search found no SDK-level estimate API), AnythingLLM, Msty, GPT4All, Windows AI / Phi Silica ready-state APIs, Google AI Edge / MediaPipe LLM Inference, ONNX Runtime GenAI, Vercel AI SDK local providers, transformers.js, llamafile, mlx-lm. In my training knowledge none of these ships a cross-model recommender, but that is unverified for October 2026 and should be checked.

## Hardware detection building blocks

### Takeaway
On the Rust side no single crate gives cross-vendor total *and free* VRAM. Projects combine `sysinfo` (RAM/CPU) with NVML and per-OS probes. This is the hard engineering part modelfit would own.

### Cited Findings
- `nvml-wrapper`: safe NVML wrapper that loads NVML at runtime, so a binary still starts without an NVIDIA driver (`Nvml::init()` returns an error) — [ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Frust-nvml%2Fnvml-wrapper)
- `gpu-probe` 0.1.0: VRAM through NVML (NVIDIA), Linux DRM sysfs (AMD/Intel), and macOS system_profiler/sysctl. Only NVIDIA tested. Returns an empty list on unsupported platforms — [docs.rs gpu-probe](https://docs.rs/crate/gpu-probe/0.1.0/source/README.md)
- `hypomnesis` 0.2.x: process and device GPU memory, Windows PDH backend for per-process VRAM on WDDM (0.2.2), NVML v2 reserved memory (0.2.4) — [docs.rs hypomnesis](https://docs.rs/crate/hypomnesis/0.2.4)
- `gfxinfo` 0.1.2: NVIDIA/AMD/Intel total and used VRAM behind a `gpu_info` feature — [docs.rs gfxinfo](https://docs.rs/crate/gfxinfo/latest)
- llmfit-core uses `sysinfo` ^0.39 and `objc2-metal` (Metal device queries on macOS) — [docs.rs llmfit-core](https://docs.rs/crate/llmfit-core/latest)
- whichllm uses `nvidia-ml-py` for NVIDIA. llmscan shells out to nvidia-smi and rocm-smi — [PyPI whichllm](https://pypi.org/project/whichllm/); [PyPI llmscan](https://pypi.org/project/llmscan/)

### Inferences
- The `local-llm-bench` hwprobe.py approach (vendor tools by absolute path) matches what the Python competitors do. A Rust core would more likely use NVML through `nvml-wrapper`, Metal through `objc2-metal`, DXGI on Windows, and sysfs on Linux.

### Gaps
- `systeminformation` (npm), `wgpu` adapter limits, GPUtil, pynvml and py-cpuinfo were not checked this session. One search noted that wgpu does not appear to expose free VRAM, but that was not confirmed.

## VRAM / memory estimator libraries

### Takeaway
GGUF memory estimation is mature and open (gpustack's gguf-parser-go, node-llama-cpp's GgufInsights, llama.cpp's own fitter). HF-safetensors estimators exist as small Python CLIs. None ships measured cross-machine speed data.

### Cited Findings
- **gpustack/gguf-parser-go** (Go, MIT, about 306 stars): estimates RAM and per-GPU VRAM for a GGUF from remote metadata without downloading it. Supports `--tensor-split` multi-GPU, RPC, and UMA (macOS: sum RAM and VRAM 0). Claims results usually deviate by about 100 MiB. Can "experimentally" estimate MAX TPS through `--device-metric` flags. Devices are supplied by flag, not auto-detected — [GitHub](https://github.com/gpustack/gguf-parser-go); [pkg.go.dev](https://pkg.go.dev/github.com/gpustack/gguf-parser-go)
- It is part of GPUStack (a GPU cluster manager using llama.cpp) — [sourcepulse](https://www.sourcepulse.org/projects/1758373). How GPUStack's scheduler uses these estimates for placement was not found.
- **hf-mem** (PyPI, 0.5.3, 2026-05-04): reads Safetensors/GGUF metadata through HTTP Range requests, depends only on httpx, has a Python API (`from hf_mem import run`), and keeps KV cache behind `--experimental`. Self-described as experimental before 1.0 — [PyPI](https://pypi.org/project/hf-mem/); [piwheels](https://www.piwheels.org/project/hf-mem/)
- **accelerate estimate-memory**: loads on the meta device, supports timm and transformers models, reports largest layer, total size and Adam training memory per dtype (weights only, no KV cache) — [HF Accelerate docs](https://huggingface.co/docs/accelerate/usage_guides/model_size_estimator)
- Others: `llm-mem` — [PyPI](https://pypi.org/project/llm-mem/); `llm-resource-planner` (heuristic) — [PyPI](https://pypi.org/project/llm-resource-planner/); `llm-mem-planner` — [PyPI](https://pypi.org/project/llm-mem-planner/); `gpu_poor` — [sourcepulse](https://www.sourcepulse.org/projects/1828209); `gguf-llm-vram-calculator` — [GitHub](https://github.com/dlsniper/gguf-llm-vram-calculator)

### Inferences
- modelfit's memory side is a commodity. Port or wrap gguf-parser's approach, or cross-check against llama.cpp's fitter. The defensible part is measured tok/s across many machines plus the cross-runtime, developer-shortlist API.

### Gaps
- Latest gguf-parser-go release date not seen. Python bindings for it not confirmed.

## Academic / industry work on hardware-aware model selection for on-device LLMs

### Takeaway
There is research on quantization trade-offs and hardware co-design. No paper found builds a consumer-device "pick among models" recommender with a measured dataset.

### Cited Findings
- Systematic evaluation of on-device LLMs (arXiv 2505.15030, v5 March 2026): 0.5B–14B models, seven PTQ methods, commodity hardware. Finds a threshold near 3.5 effective bits per weight, where heavily quantized larger models beat smaller high-precision ones. Gives selection guidelines — [arXiv](https://arxiv.org/html/2505.15030v5)
- Hardware co-design scaling laws through roofline modelling (arXiv 2602.10377): predicts latency with a roofline model, 1,942 candidate architectures on Jetson Orin. About architecture design, not picking existing models — [arXiv](https://arxiv.org/html/2602.10377)
- HAQA hardware-aware quantization agent (arXiv 2601.03484, Jan 2026): an LLM agent tunes quantization and deployment settings, up to 2.3x speedup — [arXiv](https://arxiv.org/html/2601.03484v1)

### Inferences
- The 3.5-bpw finding is a useful prior for modelfit's ranking (prefer a bigger model at Q4 over a smaller one at Q8 when both fit). The roofline/bandwidth model is the standard estimate fallback, and it is what llmfit and whichllm already use.

### Gaps
- Mobile-specific benchmark datasets (e.g. MLPerf Client, Geekbench AI) and industry routing work were not searched in this session.
