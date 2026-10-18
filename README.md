<p align="center">
  <img src="docs/assets/banner.png" alt="llm-bench: which local LLMs can your computer run?" width="100%">
</p>

# llm-bench

Find out which local LLMs your computer can run, then measure how good and how fast they are on it.

`llm-bench` reads your hardware (GPU memory, unified memory on Apple Silicon,
system RAM) and tells you which open-weight models will fit. Then it
benchmarks the ones you have downloaded on quality, speed and memory.

Quality is scored by code, not by another model. Generated code runs against
hidden tests, math answers are matched exactly, long-context recall is tested
by hiding one sentence in a 9,000-word document, and instruction-following is
checked against the required format.

It runs on Windows, macOS and Linux through [Ollama](https://ollama.com), and
also through [MLX](https://github.com/ml-explore/mlx) on Apple Silicon Macs.

## Features

- `llm-bench check` finds your GPU and how much memory it really has, using
  `nvidia-smi`, the Windows display-driver registry, `sysctl` and Metal on
  macOS, or `/sys/class/drm` for AMD and Intel Arc on Linux. It reads free
  memory as well as total, so it can warn when other apps are in the way.
- For every model it estimates the memory needed at a given context length
  (weights plus the KV cache, from the model's real architecture), the
  generation speed from your GPU's memory bandwidth, and the longest context
  that still fits. It sorts each model into *fits - fast*, *runs - slow (CPU
  offload)* or *too big*, and prints the `ollama pull` command for each one
  worth downloading.
- Every number says what it is: an estimate, or measured on this machine by
  an earlier `llm-bench run`.
- 13 tasks across coding, math, reasoning, long context and
  instruction-following, each scored by a fixed check. Running the same model
  twice gives the same score.
- Reasoning models are graded on their answer, not their working. The
  `<think>` block (and Gemma's equivalent) is removed before scoring.
- A separate speed pass per model: a warmup that measures load time, then
  three timed runs with a fixed output length, reported as a median with its
  range.
- Measured peak memory, and for Ollama how much of the model actually ran on
  the GPU. A prompt the runtime cut short is flagged, not silently scored.
- Each model is measured alone. Every request to a model uses one context
  window, so Ollama doesn't reload it mid-run, and each model is unloaded
  before the next one starts.
- On a Mac, the same model can run through both MLX and Ollama, and the
  scorecard puts the two side by side.
- A Markdown scorecard (overall ranking at 70% quality and 30% speed, quality
  per category, performance with estimates next to measurements, the best
  model on each measure) and a versioned `results.json` that
  `llm-bench validate` can check.

## Sample results

Apple M4 Pro, 24 GB unified memory, MLX runtime:

| Rank | Model | Quality | Coding | Math | Reasoning | Gen tok/s | Peak memory (est. → measured) | Composite |
|---|---|---|---|---|---|---|---|---|
| 1 | phi4-mini | **77%** | 100% | 75% | 67% | 97 | 4.5 → 4.0 GB | 0.839 |
| 2 | qwen2.5-7b | **85%** | 67% | 100% | 67% | 61 | 5.4 → 5.3 GB | 0.825 |
| 3 | llama3.2-3b | **62%** | 67% | 50% | 33% | 102 | 3.9 → 3.5 GB | 0.734 |

Qwen2.5 7B gives the best answers, but Phi-4 mini ranks first because it is
60% faster for eight points less quality. The estimates are the current
formula at the long-context task's length (about 16k tokens); every estimate
lands within 0.5 GB of the measured peak, on the high side. These runs were
made with llm-bench 0.1, before the dedicated speed pass, so their speeds
are averages over the tasks. Memory is in GiB throughout.

## Getting started

### Prerequisites

- Python 3.10 or newer
- [Ollama](https://ollama.com/download) (required on Windows and Linux, optional on a Mac)
- On Apple Silicon, optionally the MLX runtime: `pip install -e ".[mlx]"`

### Windows

1. Install Python 3.10 or newer from
   [python.org](https://www.python.org/downloads/windows/). In the installer,
   tick "Add python.exe to PATH".
2. Install Ollama from [ollama.com/download](https://ollama.com/download) and
   start it. It runs in the system tray.
3. In PowerShell, from a clone of this repo:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -e .
   llm-bench check
   ```

   If PowerShell refuses to run `Activate.ps1`, run
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip
   activation and call `.venv\Scripts\llm-bench.exe` directly.
4. Pull a model that `check` marks as fitting, then run the benchmark:

   ```powershell
   ollama pull qwen2.5:7b
   llm-bench run
   ```

### macOS

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[mlx]"        # leave off [mlx] on an Intel Mac
llm-bench check
huggingface-cli download mlx-community/Qwen2.5-7B-Instruct-4bit   # or: ollama pull qwen2.5:7b
llm-bench run
```

### Linux

Same as macOS, without `[mlx]`. NVIDIA GPUs are read through `nvidia-smi` and
AMD GPUs through `/sys/class/drm`.

## Usage

```bash
llm-bench check                          # this machine's budget and which models fit; runs nothing
llm-bench check --ctx 32768              # grade every model at a 32k context
llm-bench check --vram 24                # grade a 24 GB graphics card instead of the detected one
llm-bench check --ram 64                 # grade 64 GB of RAM (unified memory on a Mac)
llm-bench check --json                   # the same, as JSON for scripts
llm-bench run                            # every downloaded model that fits on the GPU
llm-bench run --include-slow             # also the ones that need CPU offload
llm-bench run --models qwen2.5-7b,phi4-mini
llm-bench run --runtime ollama           # auto | ollama | mlx | both
llm-bench report                         # rebuild the scorecard from saved results
llm-bench validate                       # check results.json against the result format
llm-bench doctor                         # raw hardware and Ollama details, for a bug report
```

Results go to `./llm-bench-results/` (change it with `--out`). `results.json`
keeps every model you have run, so you can benchmark a few at a time, and
`scorecard.md` is rewritten after each run. Each row records the llm-bench
version, when it was measured, and the class of machine (GPU model, memory
sizes, CPU model, OS family), never a hostname, user name or file path.

### How "fits" is decided

| Machine | Fast budget | With CPU offload |
|---|---|---|
| Apple Silicon | The GPU's memory limit, minus 2 GB for macOS. The limit is read from Metal (through MLX) or from `iogpu.wired_limit_mb` if you raised it; without MLX it falls back to about 66% of RAM (75% above 36 GB) | Same. There is no slower memory to fall back on |
| NVIDIA, AMD or Intel Arc graphics card | VRAM minus 0.5 GB. Identical cards pool their VRAM | VRAM plus 60% of system RAM |
| AMD Ryzen AI Max | The larger of the BIOS carve-out and half of RAM, minus 0.5 GB | Same when that budget is shared RAM |
| No usable GPU (including Intel's integrated graphics) | 0 | 60% of system RAM |

A model's memory need is its weights (Q4_K_M for Ollama; the 3- or 4-bit
build for MLX) plus its KV cache at the chosen context, plus 0.5 GB for the
runtime. The KV cache counts only the layers whose cache grows with context,
so hybrid models such as Qwen3.5, Gemma 4, Granite 4 and Nemotron 3 need far
less memory for long contexts than older models of the same size. The speed
estimate is memory bandwidth divided by the bytes each token reads (active
parameters only, for mixture-of-experts models), times an efficiency factor
calibrated on measured runs. Laptop and unknown GPUs get no speed estimate
rather than a guess. Every run records the real peak and speed, and the
scorecard shows them next to the estimates.

### Windows notes

- NVIDIA cards work best. Ollama uses CUDA automatically, and `nvidia-smi`
  reports VRAM exactly.
- AMD Radeon: Ollama uses the GPU on supported recent Radeon cards and falls
  back to the CPU on others. `check` adds a note when it finds an AMD GPU.
- Intel GPUs (Arc, Iris, UHD) are not accelerated by the standard Ollama build.
- VRAM is read from the display-driver registry key, which stores the full
  size. If that key can't be read, the tool falls back to WMI, which never
  reports more than 4 GB, and prints a note saying so.
- MLX only exists on Apple Silicon, so every Windows result comes from Ollama.
- Laptops slow down on battery. Plug in if you want numbers you can compare.

## Customising

- Models: add a row to the table in [`src/llm_bench/registry.py`](src/llm_bench/registry.py)
  with the Ollama tag, MLX repo, total and active parameter counts, and the
  KV-cache shape. `python scripts/model_metadata.py org/repo` prints the
  KV-cache numbers from the repo's `config.json`.
- Tasks: add to `TASKS` in [`src/llm_bench/tasks.py`](src/llm_bench/tasks.py).
  Each task is a prompt plus a function that scores the reply from 0 to 1.
- Ranking: the quality and speed weights are at the top of
  [`src/llm_bench/report.py`](src/llm_bench/report.py).

## Safety

The coding tasks run code that the model wrote, because that is how they are
scored. The code runs in a temporary folder that is deleted afterwards, in
Python's isolated mode, with a time limit. That stops accidents, but it is not
a sandbox: the code runs with your user's permissions. Stick to models from
sources you trust (the registry only lists well-known open-weight models), or
use a VM or container for anything else.

## Development

```bash
pip install -e ".[dev]"
pytest                      # runs offline: no GPU, model or Ollama needed
ruff check src tests && ruff format --check src tests
```

CI runs the tests, the linter, and a real `llm-bench check`, `check --json`
and `doctor` on Windows, macOS and Linux. Hardware the CI machines don't have (NVIDIA and AMD cards,
integrated graphics, a 4 GB WMI reading) is tested against recorded output
from those tools.

## Project structure

```
llm-bench/
├── src/llm_bench/
│   ├── cli.py         # the check, run, report, validate and doctor commands
│   ├── hwprobe.py     # RAM, GPU and VRAM detection, memory budgets, fit verdicts
│   ├── registry.py    # the model table and the memory estimate
│   ├── estimate.py    # the speed estimate and the GPU bandwidth table
│   ├── runners.py     # Ollama (HTTP) and MLX adapters, download checks
│   ├── tasks.py       # the 13 tasks and how each is scored
│   ├── bench.py       # the speed pass, runs the tasks, saves results
│   ├── schema.py      # the results.json format and its validator
│   └── report.py      # writes the Markdown scorecard
├── scripts/           # model_metadata.py: KV-cache numbers from Hugging Face
├── docs/research/     # notes behind the design, including the llmfit comparison
├── tests/             # offline tests, with a right and a wrong answer for every task
└── .github/workflows/ # CI on Windows, macOS and Linux
```

## Acknowledgements

Several improvements in 0.2 follow a feature study of
[llmfit](https://github.com/AlexsJones/llmfit) (MIT): the KV-cache memory
formula, the bandwidth-based speed estimate and its rule of giving laptop GPUs
no estimate, and the result-validation checks. No llmfit code is included. See
[`docs/research/llmfit-comparison.md`](docs/research/llmfit-comparison.md).

## License

[MIT](LICENSE)

## Author

Jacob Kanfer ([GitHub](https://github.com/Technical-1))
