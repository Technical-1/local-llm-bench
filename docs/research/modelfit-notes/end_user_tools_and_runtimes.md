# End-user tools and runtime features that tell a person which local LLM their computer can run

Research date: 2026-10-18. About 40 searches and fetches. Popularity numbers (GitHub stars etc.) are as read on the fetch date. Note: the project's docs rule forbids em dashes, so fact-to-source separators below use " - ".

## Summary table (master map)

| Name | Type | Inputs | Output | Formula or measured | Runtimes / formats | Popularity / date |
|---|---|---|---|---|---|---|
| llmfit (AlexsJones) | CLI/TUI, web UI, REST, Python pkg (Rust) | Auto-detect CPU/RAM/GPU/VRAM; `--memory=24G` override | Fit tier (Perfect/Good/Marginal/Too Tight), speed, quality, context scores; per-estimate confidence label | Formula (bandwidth model), replaced by local `llmfit bench` or community-submitted measurements when available | Ollama, llama.cpp, MLX, Docker Model Runner, LM Studio as providers | 38.1k stars, MIT, crate v1.1.15 |
| whichllm (Andyyyy64) | CLI (Python) | Auto-detect GPU/CPU/RAM | Ranked HF models, 0-100 composite score, est. tok/s, `--json` | Speed is formula; quality from public leaderboards | GGUF (llama-cpp-python), AWQ/GPTQ/FP16 (transformers); maps to Ollama names; no MLX | 6.8k stars, MIT; Show HN |
| llm-checker (Pavelevich / signerless) | CLI (Node), MCP server | Auto-detect | Scores (Quality/Speed/Fit/Context), pull commands, JSON/CSV/SARIF | Formula (bytes-per-param calibrated to Ollama sizes) + optional measured `benchmark` | Ollama, vLLM, MLX, llama.cpp, Transformers (`--runtime`) | 3.0k stars; restrictive NPDL-1.0 license |
| gguf-parser-go (GPUStack) | CLI/Go library | A GGUF file (local or remote, metadata only) + flags | RAM/VRAM per device, offload layers, rough max tok/s | Formula from GGUF metadata, claims ~100 MiB accuracy | GGUF / llama.cpp only | v0.22.1 Aug 2025 |
| LocalScore (Mozilla Builders) | CLI benchmark + public results site | Runs on your machine | Measured prompt tok/s, gen tok/s, TTFT, single score | Measured | llamafile/llama.cpp, single GPU | Apr 2025 launch |
| CanIRun.ai (midudev) | Website | WebGPU auto-detect (GPU name, then spec lookup) or manual dropdown | S to F grade per model, VRAM per quant | Formula (bandwidth) | Data from llama.cpp, Ollama, LM Studio | ~Mar 2026 |
| canirunthisllm.com | Website | Pick computer from list or custom specs | Runnable models, quant, tok/s | Not stated (computed in browser) | Not stated | 65 models tracked |
| llmconfigurator.com | Website | Pick GPU or auto-detect; VRAM and RAM | Compatible models, VRAM, tok/s, Ollama commands | Estimate | Ollama-oriented | n/a |
| apxml VRAM calculator ("Can I Run This LLM?") | Website | Model, precision, GPU or custom VRAM, context, batch, users | VRAM %, tok/s, TTFT, rental cost | Simulation/formula | Quant levels incl. GGUF Q2_K to Q8_0 | n/a |
| Other calculators: devtk.ai, flaviocopes, rapidtoolset, bmdpat, HF Spaces "LLM Model VRAM Calculator", dlsniper/gguf-llm-vram-calculator | Websites / CLI | Manual | VRAM, offload layers | Formula | Mostly GGUF | HF Space ~430 likes |
| Hugging Face Hardware compatibility | Website feature (Hub) | User saves hardware manually in settings | Per-quant fit estimate on GGUF and MLX model pages | Estimate (method undocumented) | GGUF, MLX; pairs with Local Apps (llama.cpp, Ollama, Jan, LM Studio...) | Shipped; also exposed via OAuth `hardwareItems` |
| LM Studio | Desktop app feature | Auto-detect | Per-quant label in Discover ("Full/Partial GPU offload possible", "Likely too large"); `lms load --estimate-only` | Estimate (heuristic) | llama.cpp + MLX engines inside LM Studio only | Shipped |
| Ollama | Runtime feature | Auto-detect | Auto context size by VRAM tier; memory measured before load; `ollama ps` shows split | Measured at load time (since v0.12, Sep 2025) | Ollama only | Shipped; no model recommendation found |
| Jan | Desktop app feature | Auto-detect (Hardware settings page) | Hub fit label (Fits / May be slow / Won't fit), "Recommended" quant per size group | Estimate | Jan's llama.cpp engine | Secondary-source only |
| Msty Studio | Desktop app feature | Auto-detect | Chip indicator for fit, VRAM calculator, recommended engine per machine | Not stated | Ollama, MLX, llama.cpp (cross-engine) | "One Model Hub" blog 2026-06-16 |
| GPT4All | Desktop app | None (static) | Vendor RAM label per model (e.g. 8 GB) | Static vendor label | GPT4All (llama.cpp) | Shipped |
| Foundry Local (Microsoft) | Runtime feature | Auto-detect | Picks CPU/GPU/NPU variant for an alias | Rule-based, by hardware | ONNX Runtime EPs: CUDA, WebGPU, AMD Vitis, Qualcomm NPU, OpenVINO | Preview |
| Chrome built-in AI (Gemini Nano) | Browser runtime | Auto | `availability()` gate | Hard thresholds (>4 GB VRAM or 16 GB RAM + 4 cores, 22 GB disk) | One Google model only | Docs updated 2026-08-26 |
| Apple Foundation Models | OS runtime | Auto | `availability` incl. `.unavailable(.deviceNotEligible)` | Device eligibility | One Apple model only | iOS/macOS 26+ |
| Windows AI APIs (Phi Silica) | OS runtime | Auto | Requires Copilot+ PC (40+ TOPS NPU, 16 GB RAM) | Hard gate | One inbox model | Since Jan 2025 |
| Intel AI Playground | Vendor app | Installer checks hardware | Offers Essentials vs Studio build; suggests models | Rule-based | Intel (and some Nvidia RTX in 3.2 beta) | Shipped |
| AMD GAIA | Vendor app | n/a | Runs on Ryzen AI NPU, falls back to Ollama backend | n/a | Lemonade/ONNX, Ollama | 2025 launch |
| Nvidia ChatRTX / NIM / AI Workbench | Vendor apps | n/a | No per-machine model recommendation found | n/a | TensorRT-LLM, NIM | ChatRTX v0.5 |

## Key question 1: Websites ("Can I run it" style sites, VRAM calculators, Hugging Face)

### Takeaway
There are many free "can I run this LLM" websites, nearly all formula-based (weights from parameter count times bits per weight, plus KV cache, plus overhead), most requiring manual hardware entry; the most significant is Hugging Face's own Hardware compatibility panel, which estimates per-quant fit on every GGUF and MLX model page from hardware the user saves in their profile, and exposes that hardware via API.

### Cited Findings
- Hugging Face Hub: users add hardware manually (type GPU/CPU/Apple Silicon, provider, model, memory, number of units) in Hardware settings; "On model pages that offer GGUF or MLX files, a Hardware compatibility panel estimates whether each quantization will run on your saved hardware." Hardware is public by default; public hardware produces a TFLOPS profile badge and a community comparison page at huggingface.co/hardware - [HF Hub docs: Hardware](https://huggingface.co/docs/hub/main/hardware.md)
- HF exposes the user's hardware programmatically: `GET /oauth/userinfo` includes a `hardwareItems` claim with the `profile` scope, and `GET /api/users/{username}/overview` returns `hardwareItems` (`sku` triplet, `mem` GB, `num`, `isPrimary`) for users whose hardware is public - [HF Hub docs: Hardware](https://huggingface.co/docs/hub/main/hardware.md)
- HF docs do not say how the panel calculates fit - [HF Hub docs: Hardware](https://huggingface.co/docs/hub/main/hardware.md); third-party guide also notes the estimates are approximate - [yuv.ai blog](https://yuv.ai/blog/huggingface-hardware-filter)
- HF "Local Apps" ("Use this model" dropdown) gives copy-paste commands for llama.cpp (`llama-server -hf repo:Q4_K_M`), Ollama (`ollama run hf.co/...:Q4_K_M`), and deep links to Jan and LM Studio; it does not itself pick a runtime for the user - [HF Hub docs: Local Apps](https://huggingface.co/docs/hub/local-apps)
- CanIRun.ai: browser tool that uses WebGPU to detect hardware, grades models S to F, shows VRAM per quantization, manual GPU/RAM dropdown fallback; data from llama.cpp, Ollama and LM Studio - [runaihome review](https://runaihome.com/blog/canirun-ai-local-llm-hardware-checker-review-2026/), [toolcenter review](https://www.toolcenter.ai/en/articles/canirun-ai-review-2026). One review says WebGPU hides true VRAM so the tool infers from GPU name plus a spec database and estimates tok/s from a bandwidth formula; Apple Silicon unified memory is an edge case - [runaihome review](https://runaihome.com/blog/canirun-ai-local-llm-hardware-checker-review-2026/). Attributed to Miguel Angel Duran (midudev); coverage dated around 2026-03-14 - [Agent Wars](https://agent-wars.com/news/2026-03-14-canirun-ai-browser-based-hardware-compatibility-checker-for-local-llms)
- canirunthisllm.com: pick computer from dropdown or "Advanced: enter custom specs"; no auto-detect mentioned; "Estimates are computed in your browser"; "65 models tracked", specs refreshed weekly from Hugging Face - [canirunthisllm.com](https://canirunthisllm.com/)
- llmconfigurator.com: select GPU or Auto-Detect, enter VRAM and RAM; outputs compatible models with VRAM use and tok/s estimates, plus Ollama install commands - [LLM Configurator analyzer](https://llmconfigurator.com/en/analyzer)
- apxml "LLM VRAM Calculator - Can I Run This LLM?": model, precision, KV cache precision, GPU or custom VRAM, GPU count, batch, sequence length (1K to 131K), concurrent users, CPU/NVMe offload; outputs VRAM %, generation speed, TTFT and rental cost; described as an "Inference Simulation"; no auto-detect - [apxml](https://apxml.com/tools/vram-calculator)
- caniusellm.com was posted as a Show HN (auto-detects specs, shows HF models, tok/s estimates, quant recommendation) - [HN item 43183963](https://news.ycombinator.com/item?id=43183963) (thread itself returned HTTP 429; description via search snippet only)
- More formula calculators: devtk.ai (GGUF quants, simplified GQA KV estimate, notes MoE needs all experts in VRAM) - [devtk.ai](https://devtk.ai/en/tools/vram-calculator/); bmdpat (estimates GGUF layer offload, e.g. 46/80 layers for Llama 3.3 70B Q4_K_M on RTX 4090) - [bmdpat](https://bmdpat.com/tools/vram-calculator); flaviocopes - [flaviocopes](https://flaviocopes.com/tools/llm-vram/); rapidtoolset - [rapidtoolset](https://rapidtoolset.com/en/tool/llm-vram-calculator); HF Space "LLM Model VRAM Calculator" with ~428-429 likes - [HF likes page](https://huggingface.co/erenaslandev/activity/likes); canirunai-five.vercel.app - [CanIRunAI](https://canirunai-five.vercel.app/); tool.rabrain.com (generic transformer memory estimator) - [rabrain](https://tool.rabrain.com/)
- Many content sites publish static "which Ollama model for 8/16/24 GB" tier guides (e.g. hookflow model picker, benchlm, localaimaster), which are editorial, not per-machine - [hookflow](https://hookflow.ai/guides/ollama-model-picker), [benchlm](https://benchlm.ai/best/ollama-models)

### Inferences
- The website category is crowded and commoditized; differentiation is thin because they share the same formula. None found uses a measured benchmark dataset as the primary source.
- Browser auto-detection is fundamentally weak (WebGPU hides VRAM), which is a structural advantage for a native library that can read hardware directly.
- Hugging Face is the most important potential competitor on the data side: it already holds self-reported hardware for many users, exposes it via OAuth, and renders per-quant fit on GGUF and MLX pages. It does not (as far as found) publish measured speed.

### Gaps
- Could not verify vram.asmirnov.xyz or "llm-calc" (not returned by searches).
- HF hardware compatibility launch date and fit algorithm not documented.
- No traffic numbers for any website.

## Key question 2: CLIs and open-source tools

### Takeaway
llmfit is the dominant open-source tool (38k stars, Rust, MIT) and is closer to modelfit than anything else: it auto-detects hardware, scores fit/speed/quality/context, has JSON and REST and Python interfaces, and already labels each estimate's provenance (`measured_local`, `measured_community`, `calibrated`, `estimated`) with crowdsourced `llmfit bench --share` results. It is a user-facing recommender over its own catalog, not an embeddable picker over a developer-supplied shortlist, and it does not choose between runtimes.

### Cited Findings
- llmfit: 38.1k stars, 2.5k forks, MIT, 1,271 commits; detects CPU/RAM/GPU/VRAM; NVIDIA CUDA, Apple Silicon, AMD ROCm, Intel OneAPI; macOS/Linux/Windows; providers Ollama, llama.cpp, MLX, Docker Model Runner, LM Studio; scores fit, speed, quality, context; `llmfit recommend --json`, `llmfit serve` REST (`/api/v1/system`, `/api/v1/models`) with web UI on port 8787, Python package `llmfit-python`, a `llmfit-desktop` directory - [GitHub AlexsJones/llmfit](https://github.com/AlexsJones/llmfit)
- llmfit method: fit verdict by memory ratio (<=60% Perfect, <=85% Good, <=98% Marginal, >98% Too Tight); decode speed = (bandwidth / model size) x 0.55 efficiency, bandwidth from a ~80 GPU name table or per-backend constants (CUDA 220, Metal 160, ROCm 180, SYCL 100, CPU ARM 90, x86 70 GB/s); prefill from FLOPs only if TFLOPS known; each estimate tagged `measured_local`, `measured_community`, `calibrated`, `estimated` or `unsupported`; it does not describe picking between runtimes (backend detection feeds speed constants only) - [llmfit docs/how-it-works.md](https://github.com/AlexsJones/llmfit/blob/main/docs/how-it-works.md)
- llmfit sharing: `llmfit bench --share`; docs say estimates are "grounded in runtime sampling and real community measurements" - [docs.rs llmfit](https://docs.rs/crate/llmfit); a third-party walkthrough says sharing opens a GitHub PR feeding a community index (unverified) - [instagit](https://instagit.com/AlexsJones/llmfit/llmfit-benchmark-share-feature/)
- llmfit press: How-To Geek and XDA covered it - [How-To Geek](https://www.howtogeek.com/stop-guessing-which-local-llm-will-run-on-your-pc/), [XDA](https://www.xda-developers.com/open-source-tool-is-the-first-step-before-trying-out-local-ai-llms-llmfit/); numerous forks/copies exist (Cazorlas, porsen, JasonWilder117) and an unrelated YoannDL/LLMFit - [search results](https://github.com/YoannDL/LLMFit)
- whichllm: 6.8k stars, MIT; Python; ranks HF models by composite of LiveBench, Artificial Analysis, Aider, Chatbot Arena ELO, Open LLM Leaderboard v2; speed "a planning range, not a live benchmark" from bandwidth, quant, backend, fit type, MoE active params; GGUF via llama-cpp-python, AWQ/GPTQ/FP16 via transformers; Apple restricted to GGUF; no MLX; `--json` with `fit_type`, `estimated_tok_per_sec`, `benchmark_source` - [GitHub Andyyyy64/whichllm](https://github.com/Andyyyy64/whichllm). Latest release 2026-07-03 per a directory listing - [dev.co](https://dev.co/ai/frameworks/whichllm). Queries top ~300 HF models - [Medium review](https://medium.com/@kunal1520018/whichllm-the-smart-way-to-find-the-right-local-llm-for-your-hardware-a6bbb424b049). Launched as Show HN - [feedbagel](https://feedbagel.com/post/show-hn-find-the-best-local-llm-for-your-hardware-ranked-by-benchmarks)
- llm-checker: 3.0k stars; Node.js; NPDL-1.0 (no paid distribution); memory by bytes-per-param per quant "calibrated" against Ollama sizes; `quality-sync` pulls public benchmarks; `benchmark`/`ai-run` measure tok/s; runtimes Ollama, vLLM, MLX, llama.cpp, Transformers via `--runtime`; MCP server with ~30 tools; catalog 229 Ollama models / 7,176 variants; conflicting registry sizes (55k+ vs ~33,700) - [GitHub llm-checker](https://github.com/Pavelevich/llm-checker)
- gguf-parser-go (GPUStack): estimates RAM/VRAM per device from GGUF metadata, reads remote files by chunked metadata reads, supports tensor-split and RPC, claims ~100 MiB deviation, experimental max tok/s; v0.22.1 Aug 18 2025 - [GitHub gguf-parser-go](https://github.com/thxcode/gguf-parser-go), [pkg.go.dev](https://pkg.go.dev/github.com/gpustack/gguf-parser-go)
- dlsniper/gguf-llm-vram-calculator: CLI parsing GGUF metadata, estimates memory across context lengths and KV cache types - [GitHub](https://github.com/dlsniper/gguf-llm-vram-calculator)
- LocalScore (Mozilla Builders): measures prompt processing, generation speed and TTFT into one score (1,000 excellent, 250 passable, <100 poor); CPUs, NVIDIA, AMD, Apple Silicon, single GPU only; built on llamafile; Apache 2.0; public results at localscore.ai; launched April 2025 - [GitHub cjpais/LocalScore](https://github.com/cjpais/LocalScore), [Mozilla Builders](https://builders.mozilla.org/announcing-localscore/), [Phoronix](https://www.phoronix.com/news/LocalScore-AI-LLM-Benchmark). OpenBenchmarking hosts a LocalScore profile with 238 public results as of Oct 2025 - [OpenBenchmarking](https://mail.openbenchmarking.org/performance/test/pts/localscore/692af4a31308c0aed31872990c62e0bcb1da9e9d)

### Inferences
- llmfit has already shipped the "source label" idea (measured vs community vs estimate) and a crowdsourced bench path. modelfit's differentiators would have to be: embeddable in someone else's app, picks from a developer shortlist, cross-runtime choice, and a larger, curated measured dataset. The plan should cite llmfit explicitly as nearest prior art.
- LocalScore is the closest existing measured, crowdsourced dataset but is llamafile-only and not tied to a recommender.

### Gaps
- llmfit's community dataset size and launch date not found; GitHub release dates not visible.
- Could not find a standalone "can-i-run" npm/PyPI package beyond the above.
- llama.cpp itself: no evidence found of a built-in "will this fit" recommender beyond its auto `-ngl`/fit logic; not researched in depth.

## Key question 3: Runtime and app features

### Takeaway
Every major runtime or app now does some hardware-awareness, but only for its own engine: LM Studio labels quants by offload feasibility and has `--estimate-only`; Ollama measures memory at load and auto-sizes context by VRAM tier but does not recommend models; Jan and Msty show fit indicators; Foundry Local auto-picks CPU/GPU/NPU variants; Chrome, Apple and Windows only gate a single built-in model on hard device thresholds.

### Cited Findings
- LM Studio labels: users quote LM Studio's Discover labels "Partial GPU offload possible" and "likely too large" per quant (Feb 2026 forum post; 16 GB VRAM + 32 GB RAM machine); the poster overrode "likely too large" and loaded a 70B Q3_K_S anyway, so labels are advisory heuristics - [HF forum](https://discuss.huggingface.co/t/ram-usage-model-streaming-or-alternatives/173719). A Mac bug report shows models above ~70 GB flagged "Likely too large" - [lmstudio bug tracker #651](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/651). The exact "Full GPU offload possible" wording was not found in an official LM Studio doc; a guide describes green (fully on GPU) and yellow (partial offload) badges - [insiderllm guide via search snippet](https://insiderllm.com/guides/lm-studio-tips-tricks/)
- LM Studio CLI: `lms load --estimate-only <model>` prints "Estimated GPU Memory" and "Estimated Total Memory" and "This model may be loaded based on your resource guardrails settings"; honors `--context-length` and `--gpu`; accounts for context length, flash attention and vision - [LM Studio docs: lms load](https://lmstudio.ai/docs/cli/local-models/load). Default `--gpu` behaviour: "LM Studio will automatically determine optimal GPU usage" - [same](https://lmstudio.ai/docs/cli/local-models/load). Official download doc only advises "Choose a 4-bit option or higher if your machine is capable enough" - [LM Studio docs: download](https://lmstudio.ai/docs/app/basics/download-model)
- LM Studio v0.3.14 "limit to dedicated GPU memory" mode shrinks offload to fit dedicated VRAM - [LM Studio blog](https://lmstudio.ai/blog/lmstudio-v0.3.14)
- LM Studio "staff picks" or a hardware-matched recommendation feature: not confirmed in any official source found; a third-party guide says a fresh install "may suggest a starter model" - [houtini guide](https://houtini.com/how-to-set-up-lm-studio)
- Ollama: since the Sept 2025 "New model scheduling" (v0.12.x), the engine "will now measure the exact amount of memory required compared to an estimation in previous versions", with `ollama ps` matching nvidia-smi; example gemma3:12b at 128k on RTX 4090 52 to 85 tok/s - [Ollama blog mirror](https://www.plushcap.com/content/ollama/blog/ollama-new-model-scheduling); an independent tester found v0.12.1 pushed 3 of 4 partially fitting models more to CPU - [glukhov.org](https://www.glukhov.org/post/2025/09/memory-allocation-in-ollama-new-version)
- Ollama default context by VRAM: "< 24 GiB VRAM: 4k", "24-48 GiB: 32k", ">= 48 GiB: 256k"; `ollama ps` shows PROCESSOR split and allocated context - [Ollama docs: context length](https://docs.ollama.com/context-length)
- Ollama: no official model-recommendation or "fits your machine" feature found in release notes; `ollama launch` added Feb 2026 (third-party timeline) - [fazm.ai](https://fazm.ai/t/ollama-release-notes-2026); v0.30 pre-release moves to directly using llama.cpp with MLX on Apple Silicon; stable 0.34.3 on 2026-09-19 - [releasebot](https://releasebot.io/updates/ollama), [Wikipedia](https://en.wikipedia.org/wiki/Ollama)
- Jan: Hardware settings page detects CPU, RAM, GPU/VRAM (v0.8.6) and each model entry has a hardware compatibility indicator - [StorageReview](https://www.storagereview.com/review/jan-v0-8-6-hands-on-running-local-llms-on-windows); Hub labels "Fits", "May be slow", "Won't fit", quants grouped Small/Balanced/Large with a "Recommended" default (secondary source) - [bestllmfor.com](https://bestllmfor.com/guide/jan-app-desktop/)
- Msty Studio: Local Models covers Ollama, MLX and llama.cpp; catalog entries show hardware fit; Model Hub includes a VRAM Calculator; a chip indicator flags device suitability - [Msty docs: Local Models](https://docs.msty.ai/studio/managing-models/local-models). "One Model Hub" (2026-06-16): "On Apple Silicon, that may be MLX. On other systems, it may be Ollama or LLaMA.cpp" - [Msty blog](https://msty.ai/blog/one-model-hub/)
- GPT4All: static vendor RAM figure per model (e.g. Llama 3 Instruct 8 GB, Phi-3 Mini 4 GB) - [GPT4All docs mirror](https://git.hackliberty.org/AI/gpt4all/src/branch/main/gpt4all-chat/system_requirements.md)
- Foundry Local: with an alias, "if you have an Nvidia GPU available, Foundry Local selects the best GPU model. If you have a supported NPU available, Foundry Local selects the NPU model"; CPU fallback; EPs CUDA, WebGPU, AMD Vitis, Qualcomm NPU, Intel OpenVINO; EPs downloaded on first run - [MS Learn: Foundry Local CLI](https://learn.microsoft.com/en-us/azure/foundry-local/reference/reference-cli), [MS Learn: architecture](https://learn.microsoft.com/en-my/Azure/foundry-local/concepts/foundry-local-architecture). It chooses execution-provider variant of a given model, not which model. Described as preview - [sourcepulse](https://www.sourcepulse.org/projects/2639079)
- Windows: Copilot+ PC = NPU 40+ TOPS, 16 GB+ RAM, Snapdragon X / Core Ultra 200V / Ryzen AI 300; required for Windows AI APIs (Phi Silica) but not for Foundry Local or Windows ML - [MS Learn comparison](https://learn.microsoft.com/windows/ai/windows-ai-comparison); Phi Silica available to developers since Jan 2025 - [Windows blog](https://blogs.windows.com/windowsexperience/2024/12/06/phi-silica-small-but-mighty-on-device-slm/)
- Chrome built-in AI: GPU "strictly more than 4 GB of VRAM" or CPU with 16 GB RAM and 4+ cores; 22 GB free disk; model removed if free space falls under 10 GB; desktop only; `availability()` returns values including "downloading" and "unavailable"; docs updated 2026-08-26; no hardware-based variant selection described - [Chrome Prompt API docs](https://developer.chrome.com/docs/ai/prompt-api)
- Apple Foundation Models: check `SystemLanguageModel` availability; depends on device and region supporting Apple Intelligence - [Apple docs](https://developer.apple.com/documentation/foundationmodels/systemlanguagemodel.md); unavailable reasons include `deviceNotEligible`, `appleIntelligenceNotEnabled`, `modelNotReady` - [Superwall](https://superwall.com/blog/an-introduction-to-apples-foundation-model-framework)
- Intel AI Playground: installer checks hardware and offers Essentials (min 12 GB system memory, Core Series 3) or Studio builds; "will suggest AI models to install as you use the app"; 3.2.0 beta adds some Nvidia RTX GPUs - [Intel](https://game.intel.com/stories/ai-playground-essentials-for-intel-core-series-3-processors/); older build targeted Core Ultra H/V or Arc with 8 GB VRAM - [HotHardware](https://hothardware.com/news/intel-ai-playground-released)
- AMD GAIA: for Ryzen AI PCs with XDNA NPU via Lemonade SDK; switches to Ollama backend on any PC (2025 launch) - [Phoronix](https://www.phoronix.com/news/AMD-GAIA-Open-Source)
- Nvidia ChatRTX (v0.5), NIM for RTX, AI Workbench: no per-machine model recommendation found - [NVIDIA blog](https://blogs.nvidia.com/blog/ai-decoded-gtc-chatrtx-workbench-nim/), [NVIDIA CES blog](https://blogs.nvidia.com/blog/rtx-ai-garage-ces-pc-nim-blueprints/)

### Inferences
- The plan's claim that runtimes "could add a 'recommended for your machine' label" is already partly true: LM Studio, Jan and Msty ship per-quant fit labels today. What none of them ship (found) is a ranked "best model for this machine" recommendation backed by measured speed.
- OS and browser runtimes (Chrome, Apple, Windows) are binary eligibility gates for one model; apps using them need a fallback picker, which is a use case for modelfit.

### Gaps
- Exact LM Studio label strings from official docs not found; staff picks status unconfirmed.
- Jan labels are from a secondary source only.
- Pinokio and Open WebUI: no hardware-fit or recommendation features found (searches returned nothing). Open WebUI relies on Ollama/backends.
- Ollama's new desktop app: no model recommendation feature found, but official app changelog not fetched directly.

## Key question 4: Does any tool recommend across multiple runtimes?

### Takeaway
Partially. Msty Studio routes users to an engine per machine (MLX on Apple Silicon, otherwise Ollama or llama.cpp) inside one app, and llmfit and llm-checker cover several runtimes, but none found recommends across runtimes using measured per-runtime performance, and none covers browser runtimes (WebLLM, Transformers.js, Chrome built-in AI). The plan's claim needs softening: an app that bundles several engines (Msty, LM Studio with llama.cpp + MLX, Ollama now using llama.cpp + MLX) can and does recommend across engines it bundles.

### Cited Findings
- Msty: covers Ollama, MLX, llama.cpp and "route[s] you towards the engine that makes the most sense for your setup" - [Msty blog](https://msty.ai/blog/one-model-hub/), [Msty docs](https://docs.msty.ai/studio/managing-models/local-models)
- llmfit lists Ollama, llama.cpp, MLX, Docker Model Runner, LM Studio as providers - [GitHub llmfit](https://github.com/AlexsJones/llmfit) - but its method doc shows no runtime selection logic; backend only affects speed constants - [how-it-works](https://github.com/AlexsJones/llmfit/blob/main/docs/how-it-works.md)
- llm-checker takes `--runtime` (Ollama, vLLM, MLX, llama.cpp, Transformers) as an input rather than recommending one - [GitHub llm-checker](https://github.com/Pavelevich/llm-checker)
- LM Studio and Ollama each bundle llama.cpp and MLX engines - [promptquorum / guides comparison](https://www.promptquorum.com/power-local-llm/local-llm-run-serve-compared); Ollama v0.30 pre-release uses MLX on Apple Silicon - [releasebot](https://releasebot.io/updates/ollama)
- Foundry Local picks across hardware execution providers within ONNX Runtime, not across runtimes - [MS Learn](https://learn.microsoft.com/en-us/azure/foundry-local/reference/reference-cli)
- Searches for a cross-runtime recommender including WebLLM returned no such tool - [search; e.g. localmodel.run tools list](https://localmodel.run/tools)

### Inferences
- Defensible version of the claim: "A runtime recommends only among the engines it ships, and only for its own catalog; no tool recommends across independent runtimes (Ollama vs LM Studio vs MLX-LM vs WebLLM vs Chrome built-in) from measured data, and none is embeddable in a third-party app."

### Gaps
- No measured cross-runtime benchmark dataset found (same model, same hardware, multiple runtimes).

## Key question 5: Companies or startups building model selection for local AI apps; funding

### Takeaway
No funded company was found whose product is "pick the right local model for this device" as an API or SDK. Adjacent funded players build on-device inference engines and SDKs (Mirai $10M seed, Nexa AI ~$8.75M, Cactus YC S25, RunAnywhere YC ~$0.5M), and cloud-side routing (OpenRouter) is well funded, but device-aware model selection appears to be a feature inside those stacks rather than a standalone product.

### Cited Findings
- Mirai: $10M seed led by Uncork Capital (Feb 2026), London, founders from Reface and Prisma; builds models, inference runtime and quantization stack "designed for Apple Silicon specifically"; no per-device model selection mentioned - [TechCrunch](https://techcrunch.com/2026/02/19/co-founders-behind-reface-and-prisma-join-hands-to-improve-on-device-model-inference-with-mirai/), [Mirai blog](https://trymirai.com/blog/mirai-raises-10m-to-build-the-on-device-ai-capability-layer)
- Nexa AI: $8.75M total per Tracxn; stage reported inconsistently - [Tracxn](https://tracxn.com/d/companies/nexaai/__ijGPt7-OwiFx5BFm6T2jPtVmoSEO7W3N6U5hpXYuKmU)
- Cactus: YC S25, open-source C++ on-device engine with React Native/Flutter/KMP SDKs; funding ~$0.5M to $1M (sources conflict) - [InfoQ](https://infoq.com/news/2025/12/cactus-on-device-inference/), [extruct](https://www.extruct.ai/hub/cactuscompute-com/)
- RunAnywhere: YC-backed, Bengaluru, ~$500K Jan 2026 (per Tracxn, via search snippet); on-device AI infrastructure platform - [RunAnywhere blog](https://www.runanywhere.ai/blog/best-on-device-ai-infrastructure-platforms-2026)
- OpenRouter (cloud model routing, not local) reportedly raising near $1.3B valuation (Apr 2026) - [The Information](https://www.theinformation.com/articles/startup-helps-developers-pick-ai-models-nears-1-3-billion-valuation)
- Hugging Face holds user hardware profiles and exposes them via OAuth `hardwareItems`, which positions it to offer device-aware selection - [HF docs](https://huggingface.co/docs/hub/main/hardware.md)

### Inferences
- The most likely competitive threats are not startups but (a) llmfit adding a library/SDK mode with shortlist input, (b) Hugging Face extending its compatibility panel into an API, and (c) on-device SDK vendors (Cactus, Nexa, RunAnywhere) adding per-device model selection to their SDKs.

### Gaps
- Did not find whether Cactus, Nexa or RunAnywhere SDKs already auto-select model size per device; worth a targeted check of their docs.
- No Product Hunt data gathered.
