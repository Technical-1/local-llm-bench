# Name availability and collisions for "modelfit"

All checks were read-only. They ran on 2026-10-18 with curl against the registry APIs, the GitHub REST API, dig and whois. Nothing was registered or published.

## Is "modelfit" available on npm, PyPI and crates.io (plus the variants and the @modelfit scope)?

### Takeaway
No, in practice. crates.io `modelfit` belongs to another developer who uses it for a crate with the same purpose as ours. PyPI `modelfit` is taken. On npm, the bare name `modelfit` returns 404, but `model-fit` is a published package that does what we plan to do, and npm's punctuation rule almost certainly blocks `modelfit` because of it. The `@modelfit` scope does not exist yet.

### Cited Findings

Availability table (HTTP status from each registry API; 404 = no package with that name):

| Name | npm | PyPI | crates.io |
|---|---|---|---|
| modelfit | 404, but likely **blocked** by the moniker rule because `model-fit` exists | **200, taken** (`modelFit`) | **200, taken** |
| model-fit | **200, taken** | 404 (same normalised name as `modelfit`, so taken in practice) | 404 (crates.io treats `-` and `_` as the same, see Gaps) |
| model_fit / model.fit | not checked on npm (blocked by the same rule) | 404 (normalises to `modelfit`, so taken in practice) | model_fit 404 |
| modelfit-core | 404 | 404 | 404 |
| modelfit-web | 404 | 404 | 404 |
| pymodelfit | 404 | **200, taken** (`PyModelFit`) | n/a |
| fitmodel | 404 | 404 | 404 |
| @modelfit/web, @modelfit/core | 404 | n/a | n/a |
| @modelfit scope (org) | `{"error":"Scope not found"}` | n/a | n/a |

Details on the names that are taken:

- **crates.io `modelfit`**: "Recommends local AI models for this machine, using hwprobe hardware detection". MIT. Five versions, 0.1.0 to 0.4.0, all published 2026-09-04 and 2026-09-05. 78 downloads in total, no reverse dependencies. Owner: GitHub user `rssndr` (Andrea Rossetti). The repo is `rssndr/modelfit`, "Quality × physics local LLM recommendation for your machine", with 0 stars and the last push on 2026-09-05. — [crates.io API](https://crates.io/api/v1/crates/modelfit); [owners](https://crates.io/api/v1/crates/modelfit/owners); [GitHub](https://github.com/rssndr/modelfit)
- **npm `model-fit`**: "Detect your hardware and find LLMs that will actually run on it — with real VRAM/KV-cache fit math, not opaque scores." MIT, maintainer `audranyematha`. Versions 0.1.0 to 0.1.3, from 2026-06-02 to 2026-07-01. 23 downloads between 2026-09-17 and 2026-10-16. A CLI (`npx model-fit`, with `detect`, `recommend` and `check` commands). Keywords: llm, ollama, llama.cpp, gguf, vram, local-ai. — [npm registry](https://registry.npmjs.org/model-fit); [npm downloads API](https://api.npmjs.org/downloads/point/last-month/model-fit)
- **npm `@wecko-ai/modelfit`** v1.5.3, published 2026-10-14: "Detect your machine and get THE best local LLM (Ollama) it can run — from the ModelFit hardware database". Its GitHub README says `npx modelfit`, yet unscoped `modelfit` returns 404 on npm. That fits the bare name being blocked. — [npm search](https://registry.npmjs.org/-/v1/search?text=modelfit&size=10); [GitHub Wecko-ai/modelfit](https://github.com/Wecko-ai/modelfit)
- **PyPI `modelfit`** (shown as `modelFit`): "MAP/MLE fitting helpers" by Gino Battistello. Three releases, all uploaded on 2025-10-27. Requires Python 3.9 or newer. About 11 downloads in the last month. — [PyPI JSON](https://pypi.org/pypi/modelfit/json); [pypistats](https://pypistats.org/api/packages/modelfit/recent)
- **PyPI `pymodelfit`** (`PyModelFit`): "Data-fitting and Model-building package" by Erik Tollerud. Released 2011 to 2013, abandoned. — [PyPI JSON](https://pypi.org/pypi/pymodelfit/json)

Registry naming rules that matter here:

- npm: "you can no longer publish packages that differ from existing packages in punctuation only." The example given is that because `react-native` exists, nobody can publish `reactnative`, `react_native` or `react.native`. — [npm blog, New package moniker rules](https://blog.npmjs.org/post/168978377570/new-package-moniker-rules)
- PyPI: one listed reason a name can be unavailable is "The project name is too similar to an existing project and may be confusable." — [PyPI help](https://pypi.org/help/)
- PyPI's `/simple/` index gave 404 for `model-fit` and `model_fit` and 200 for `modelfit`. PEP 503 normalisation (runs of `-`, `_` and `.` become one `-`, then lowercased) makes `model-fit`, `model_fit` and `model.fit` the same as each other. It does **not** make them the same as `modelfit`, because normalisation replaces separators and never removes them. — [PyPI simple index](https://pypi.org/simple/modelfit/)

### Inferences
- npm `modelfit` should be treated as unavailable. Checking for certain would mean attempting a publish, which was out of scope. The `@modelfit` scope is open (no org exists), so `@modelfit/core` and `@modelfit/web` could probably be claimed by creating the org. That does not fix the unscoped name.
- crates.io `modelfit` is a hard block unless the owner hands it over. The crate is about six weeks old, has 0 stars and is a near-identical idea, so asking for a transfer would be odd.
- On PyPI, `model-fit` / `model_fit` are technically free. The "too similar / confusable" rule could still block them, and a different, abandoned-looking project already holds `modelfit`. PyPI's process for claiming abandoned names (PEP 541) is slow and not guaranteed.

### Gaps
- No publish was attempted, so the npm moniker block on `modelfit` is inferred from the published rule. It was not observed.
- crates.io treats `-` and `_` as the same name, so `model-fit` and `model_fit` probably collide with each other. Whether either collides with `modelfit` was not confirmed: both returned 404, and crates.io's normalisation does not remove separators.
- Could not tell whether an npm *user* (not an org) called `modelfit` exists. npmjs.com user pages returned 403 (Cloudflare).

## Does the name collide with existing projects, domains or trademarks?

### Takeaway
Yes, badly. In 2026 "ModelFit" has become close to a generic label for exactly our product: at least six other "pick a local LLM for your hardware" projects use it. One is a commercial site, modelfit.io, with an npm package and a CC BY 4.0 hardware dataset, the same plan as ours. There is also a live US trademark MODELFIT for fitness instruction, and the term has a long history in statistics.

### Cited Findings

Same-niche collisions (local LLM to hardware matching):

- **modelfit.io**, page title "ModelFit | Find the Best Local AI Model for Your Hardware": "ModelFit helps you choose the best local AI models for your Apple Silicon Mac, iPhone, or NVIDIA GPU. Get Ollama recommendations optimized for your hardware." Domain created 2026-02-19 (Hostinger), on Cloudflare. — [modelfit.io](https://modelfit.io); whois
- **Wecko-ai/modelfit-hardware-dataset** (24 stars, pushed 2026-10-16): "Open CC BY 4.0 dataset: which local LLMs (Ollama) fit which hardware … Powered by modelfit.io". This is the same "dataset of measured results" idea as ours. — [GitHub](https://github.com/Wecko-ai/modelfit-hardware-dataset)
- **Wecko-ai/modelfit** (3 stars, created 2026-06-15): an offline CLI backed by "the ModelFit hardware database". — [GitHub](https://github.com/Wecko-ai/modelfit)
- **rssndr/modelfit**, the crates.io owner (see above). — [GitHub](https://github.com/rssndr/modelfit)
- **harishkotra/ModelFit** (created 2026-06-05): "client-side developer sandbox … determine which open-weight LLMs, Diffusers, and Speech models can run on their specific machine", hosted at model-fit-gamma.vercel.app. — [GitHub](https://github.com/harishkotra/ModelFit)
- **snoydoc/modelfit** (created 2026-05-01): "LLM benchmark for your actual hardware." — [GitHub](https://github.com/snoydoc/modelfit)
- **kwadwoadu/modelfit** (6 stars): "Benchmark LLMs on your own codebase." — [GitHub](https://github.com/kwadwoadu/modelfit)
- **dapinder-dhillon/modelfit** (3 stars, 2026-09-30): choosing a model tier. — [GitHub search](https://api.github.com/search/repositories?q=modelfit+in:name&sort=stars)
- **AlexsJones/llmfit** (38,079 stars, created 2026-02-15): "Hundreds of models & providers. One command to find what runs on your hardware." It is the dominant project in this niche and owns the "-fit" naming pattern. PyPI `llmfit` and crates.io `llmfit` are both taken. — [GitHub](https://github.com/AlexsJones/llmfit)
- **ctkrug/rigfit**: "The best local LLM your GPU can run, with the exact quantiza[tion]…". — [GitHub search](https://api.github.com/search/repositories?q=rigfit+in:name)

Other uses of the name:

- GitHub search finds 110 repos with "modelfit" in the name. The most-starred is jonathantompson/ModelFit (127 stars, hand-pose fitting, 2015). Others include lsst/meas_modelfit (astronomy model fitting, active 2026-10-15) and brian-team/brian2modelfitting. — [GitHub search](https://api.github.com/search/repositories?q=modelfit+in:name&sort=stars)
- US trademark MODELFIT, Reg. No. 4372676, for fitness instruction. Status "Section 8 & 15-Accepted And Acknowledged", meaning it is live. The owner is an LLC whose name is not shown publicly. — [Justia Trademarks](https://trademarks.justia.com/858/64/modelfit-85864336.html)
- A "ModelFit" Shopify app offers AI virtual try-on of clothing. — [Shopify App Store](https://apps.shopify.com/modelfit?locale=ar)
- Wolfram Language documents a `ModelFit` reference page for statistical model fitting. — [Wolfram reference](https://reference.wolfram.com/language/ref/ModelFit.html)
- Statistics registries: CRAN `modelfit` is not found (404). Bioconductor `/packages/modelfit/` redirects to its "Removed Packages" page, which suggests a Bioconductor package of that name once existed and was removed (not confirmed). Not found in r-universe, the Julia General registry (`ModelFit` or `Modelfit`) or conda-forge. — [CRAN](https://cran.r-project.org/package=modelfit); [Bioconductor](https://bioconductor.org/packages/modelfit/)

Domains (dig and whois):

| Domain | Status |
|---|---|
| modelfit.io | Registered 2026-02-19; a competitor's live product site |
| modelfit.com | Registered 2008-08-26 (GoDaddy) |
| modelfit.org | Registered 2025-11-05 (Dynadot); default nginx page |
| modelfit.dev | Registered (Porkbun nameservers, A records); HTTPS did not respond |
| modelfit.ai | Not registered. The .ai whois says "available for application via the Identity Digital Dropzone service" |

### Inferences
- If we ship "modelfit" we would be one of at least seven projects with that name in the same niche. The most visible one (modelfit.io plus its dataset) is building almost the same product: a hardware dataset plus a recommender plus an npm package. Search, support questions and attribution would all suffer, and the crates.io name is already gone.
- The fitness trademark sits in a different class and is unlikely to matter on its own. The niche collisions are the real problem.
- The name should be changed now, while nothing is built (Phase 0). Avoid anything ending in "-fit" (llmfit, model-fit, rigfit and modelfit already cluster there).

### Gaps
- No USPTO search was run for classes 9 or 42 (software). Only the fitness registration surfaced.
- Whether modelfit.io is a company or a side project, and whether it has filed a trademark, is unknown.

## Fallback names: availability on all three registries

### Takeaway
Several names are clean on npm, PyPI and crates.io, including their punctuation variants. **`machinefit`** and **`modelsizer`** are the cleanest, but `machinefit` repeats the crowded "-fit" pattern. **`pickmodel`** / **`modelpick`** say what the library does but have small collisions. Names that avoid "fit" entirely (`modelsizer`, `pickmodel`, `modelmatch`) are the safer choice.

### Cited Findings

Each candidate was checked on npm (package and scope), PyPI `/simple/`, crates.io (with User-Agent), its hyphenated form on all three, GitHub repo search, and dig NS for .dev and .io (empty NS suggests the domain is unregistered but does not prove it).

| Candidate | npm | npm scope | PyPI | crates.io | Hyphen form, all 3 | GitHub collisions | .dev / .io |
|---|---|---|---|---|---|---|---|
| machinefit | free | free | free | free | free | 2 repos, 0 stars (workout tracker) | no NS / no NS |
| modelsizer | free | free | free | free | free | 1 empty repo | not checked |
| pickmodel | free | free | free | free | free (pick-model, pick_model) | cloudcap10/pickmodel, 0 stars, "side-by-side comparison of AI language models" (adjacent) | no NS / no NS |
| modelpick | free | free | free | free | free (model-pick, model_pick) | modelPicker (AR app, unrelated) | **.dev registered** / no NS |
| modelmatch | free | free | free | free | free | AIG-ModelMatching (flight-sim liveries, unrelated, 114 stars) | **both registered** |
| devicefit | free | free | free | free | free | 1 Google Fit repo | not checked |
| benchfit | free | free | free | free | free | siba-p/benchfit, renamed to "Lattent" | not checked |
| rigfit | free | free | free | free | free | **ctkrug/rigfit is a direct competitor** | no NS / no NS |

Sources: [npm registry](https://registry.npmjs.org/), [PyPI simple index](https://pypi.org/simple/), [crates.io API](https://crates.io/api/v1/crates/), [GitHub search API](https://api.github.com/search/repositories)

Rejected because already taken:
- `llmfit`: PyPI 200, crates.io 200, and the 38k-star competitor. — [GitHub](https://github.com/AlexsJones/llmfit)
- `localfit`: npm 200, PyPI 200. `modelscout`: PyPI 200. `fitcheck`: npm, npm scope and PyPI all 200, plus 920 GitHub repos.

### Inferences
- First choice: **`pickmodel`**. It reads as what the library does ("pick the best model"), is free on all three registries with its hyphen variants, and the `@pickmodel` scope is free for `@pickmodel/web`. Its one collision is a 0-star comparison repo, and pickmodel.dev and pickmodel.io show no nameservers.
- Second choice: **`modelsizer`**. Free everywhere with almost no collisions, though "sizer" undersells the recommending part.
- `machinefit` is clean but keeps the "-fit" association with llmfit and the six modelfit projects. Avoid `rigfit`.
- None of these was checked against trademarks.

### Gaps
- No trademark search was run on any fallback name.
- Domain availability is a DNS guess only. No registrar availability check was made.
- The `modelsizer`, `devicefit` and `benchfit` domains were not checked.
