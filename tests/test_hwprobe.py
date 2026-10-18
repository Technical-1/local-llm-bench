"""Hardware probing. Windows paths are exercised with faked OS output, so the
whole suite runs anywhere; CI also runs it on a real Windows runner."""

import json

import pytest

from llm_bench import hwprobe


def test_probe_is_complete_on_this_machine():
    hw = hwprobe.probe()
    keys = {
        "os",
        "arch",
        "cpu",
        "ram_gb",
        "gpu",
        "accelerator",
        "mlx_ok",
        "fast_gb",
        "spill_gb",
        "notes",
    }
    assert keys <= hw.keys()
    assert hw["ram_gb"] > 0
    assert hw["spill_gb"] >= hw["fast_gb"] >= 0


@pytest.mark.parametrize(
    "need,expected",
    [(5.0, "fast"), (7.5, "fast"), (7.6, "slow"), (19.5, "slow"), (19.6, "no")],
)
def test_fit_boundaries_on_a_discrete_gpu(need, expected):
    assert hwprobe.fit(need, {"fast_gb": 7.5, "spill_gb": 19.5}) == expected


def test_cpu_only_is_never_fast():
    hw = {"fast_gb": 0.0, "spill_gb": 9.6}
    assert hwprobe.fit(3.0, hw) == "slow"
    assert hwprobe.fit(12.0, hw) == "no"


@pytest.mark.parametrize("ram,share", [(16, 0.66), (36, 0.66), (64, 0.75), (128, 0.75)])
def test_apple_gpu_share(ram, share):
    assert hwprobe.apple_gpu_share(ram) == pytest.approx(ram * share)


def test_nvidia_smi_output_is_parsed(monkeypatch):
    monkeypatch.setattr(hwprobe.platform, "system", lambda: "Linux")
    monkeypatch.setattr(hwprobe, "find_exe", lambda *a, **k: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(hwprobe, "_run", lambda *a, **k: "NVIDIA GeForce RTX 4070, 12282\n")
    assert hwprobe._nvidia_smi() == [
        {"name": "NVIDIA GeForce RTX 4070", "vram_gb": 12282 / 1024, "kind": "nvidia"}
    ]


def test_windows_prefers_system32_nvidia_smi(monkeypatch, tmp_path):
    sys32 = tmp_path / "System32"
    sys32.mkdir()
    exe = sys32 / "nvidia-smi.exe"
    exe.write_text("")
    exe.chmod(0o755)
    seen = []
    monkeypatch.setattr(hwprobe.platform, "system", lambda: "Windows")
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    monkeypatch.setattr(hwprobe, "_run", lambda cmd, **k: seen.append(cmd[0]) or "")
    hwprobe._nvidia_smi()
    assert seen == [str(exe)]


def test_run_refuses_a_bare_command_name():
    assert hwprobe._run(["nvidia-smi"]) == ""


def test_wmi_fallback_flags_the_4gb_cap(monkeypatch):
    out = json.dumps(
        [
            {"Name": "AMD Radeon RX 7800 XT", "AdapterRAM": 4293918720},
            {"Name": "Intel(R) UHD Graphics 770", "AdapterRAM": 1073741824},
        ]
    )
    monkeypatch.setattr(hwprobe, "_run", lambda *a, **k: out)
    gpus = hwprobe._windows_wmi_gpus()
    assert [g["kind"] for g in gpus] == ["amd", "intel"]
    assert all(g["vram_capped"] for g in gpus)


def _fake_windows(monkeypatch, gpus, ram):
    monkeypatch.setattr(hwprobe.platform, "system", lambda: "Windows")
    monkeypatch.setattr(hwprobe.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(hwprobe, "ram_gb", lambda: ram)
    monkeypatch.setattr(hwprobe, "cpu_name", lambda: "Fake CPU")
    monkeypatch.setattr(hwprobe, "gpus", lambda: gpus)


def test_windows_nvidia_budget(monkeypatch):
    _fake_windows(
        monkeypatch,
        [
            {"name": "NVIDIA GeForce RTX 4070", "vram_gb": 12.0, "kind": "nvidia"},
            {"name": "Intel(R) UHD Graphics", "vram_gb": 0.5, "kind": "intel"},
        ],
        ram=32.0,
    )
    hw = hwprobe.probe()
    assert hw["accelerator"] == "nvidia" and not hw["mlx_ok"]
    assert hw["fast_gb"] == 11.5
    assert hw["spill_gb"] == round(11.5 + 32 * 0.6, 1)


def test_windows_integrated_graphics_only_means_cpu(monkeypatch):
    _fake_windows(
        monkeypatch,
        [{"name": "Intel(R) Iris(R) Xe Graphics", "vram_gb": 0.1, "kind": "intel"}],
        ram=16.0,
    )
    hw = hwprobe.probe()
    assert hw["gpu"] is None and hw["accelerator"] == "cpu"
    assert hw["fast_gb"] == 0.0


def test_windows_amd_gets_a_support_note(monkeypatch):
    _fake_windows(
        monkeypatch, [{"name": "AMD Radeon RX 7800 XT", "vram_gb": 16.0, "kind": "amd"}], ram=32.0
    )
    assert any("AMD" in n for n in hwprobe.probe()["notes"])


def test_capped_vram_gets_a_note(monkeypatch):
    _fake_windows(
        monkeypatch,
        [
            {
                "name": "NVIDIA GeForce RTX 3080",
                "vram_gb": 4.0,
                "kind": "nvidia",
                "vram_capped": True,
            }
        ],
        ram=32.0,
    )
    assert any("4 GB" in n for n in hwprobe.probe()["notes"])


# Recorded from an Apple M4 Pro (24 GB) with a browser and an editor open.
VM_STAT_M4 = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                                     9115.
Pages active:                                 511060.
Pages inactive:                               516046.
Pages speculative:                              1621.
Pages throttled:                                   0.
Pages wired down:                             325810.
Pages purgeable:                                6132.
"""


def test_vm_stat_counts_reclaimable_pages():
    pages = 9115 + 516046 + 1621 + 6132
    assert hwprobe.parse_vm_stat(VM_STAT_M4) == pytest.approx(pages * 16384 / hwprobe.GB)
    assert hwprobe.parse_vm_stat("garbage") is None


def test_nvidia_smi_reads_free_vram(monkeypatch):
    monkeypatch.setattr(hwprobe.platform, "system", lambda: "Linux")
    monkeypatch.setattr(hwprobe, "find_exe", lambda *a, **k: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(hwprobe, "_run", lambda *a, **k: "NVIDIA GeForce RTX 4070, 12282, 6141\n")
    (gpu,) = hwprobe._nvidia_smi()
    assert gpu["free_gb"] == pytest.approx(6141 / 1024)


def test_amd_sysfs_free_vram(monkeypatch, tmp_path):
    dev = tmp_path / "card0" / "device"
    dev.mkdir(parents=True)
    (dev / "mem_info_vram_total").write_text(str(16 * hwprobe.GB))
    (dev / "mem_info_vram_used").write_text(str(4 * hwprobe.GB))
    (tmp_path / "renderD128").mkdir()  # not a card; ignored
    monkeypatch.setattr(hwprobe, "DRM", str(tmp_path))
    (gpu,) = hwprobe._linux_amd_gpus()
    assert gpu["vram_gb"] == 16.0 and gpu["free_gb"] == 12.0


def test_free_budget_discrete_and_unified():
    discrete = {"accelerator": "nvidia", "gpu": {"free_gb": 6.0}, "fast_gb": 11.5}
    assert hwprobe.free_budget(discrete) == 5.5
    mac = {"accelerator": "apple-unified", "gpu": {}, "fast_gb": 17.8, "ram_free_gb": 8.1}
    assert hwprobe.free_budget(mac) == 8.1
    assert hwprobe.free_budget({"accelerator": "cpu", "gpu": None, "fast_gb": 0.0}) is None


def _fake_apple(monkeypatch, wired="0", metal=None):
    monkeypatch.setattr(hwprobe, "_run", lambda cmd, **k: wired if "iogpu" in cmd[-1] else "")
    monkeypatch.setattr(hwprobe, "_metal_working_set", lambda: metal)


def test_apple_limit_prefers_a_user_raised_wired_limit(monkeypatch):
    _fake_apple(monkeypatch, wired="20480", metal=19_069_665_280)
    assert hwprobe.apple_gpu_limit(24.0) == (20.0, "iogpu.wired_limit_mb")


def test_apple_limit_reads_metal_when_the_default_applies(monkeypatch):
    _fake_apple(monkeypatch, metal=19_069_665_280)  # recorded on a 24 GB M4 Pro
    gb, source = hwprobe.apple_gpu_limit(24.0)
    assert source == "Metal" and gb == pytest.approx(17.76, abs=0.01)


def test_apple_limit_falls_back_to_the_rule(monkeypatch):
    _fake_apple(monkeypatch)
    assert hwprobe.apple_gpu_limit(16.0) == (pytest.approx(16 * 0.66), "estimate")


def test_override_grades_a_bigger_graphics_card(nvidia_hw):
    hw = hwprobe.override(nvidia_hw, vram=24)
    assert hw["gpu"]["vram_gb"] == 24.0 and hw["fast_gb"] == 23.5
    assert hw["gpu"]["name"] == "NVIDIA GeForce RTX 4070"  # kept, so bandwidth still resolves
    assert hw["spill_gb"] == round(23.5 + 32 * 0.6, 1)
    assert any("--vram 24 GB" in n for n in hw["notes"])
    assert nvidia_hw["fast_gb"] == 11.5, "the detected hardware is not modified"


def test_override_ram_on_a_mac_regrades_unified_memory():
    mac = {
        "accelerator": "apple-unified",
        "gpu": {"name": "Apple M4 Pro", "vram_gb": 17.8, "kind": "apple"},
        "ram_gb": 24.0,
        "ram_free_gb": 8.0,
        "fast_gb": 15.8,
        "spill_gb": 15.8,
        "notes": [],
    }
    hw = hwprobe.override(mac, ram=48)
    assert hw["fast_gb"] == hw["spill_gb"] == round(48 * 0.75 - 2.0, 1)
    assert hw["ram_free_gb"] is None and hw["gpu_limit_source"] == "estimate"
    with pytest.raises(SystemExit):
        hwprobe.override(mac, vram=24)


def test_no_override_returns_the_detected_hardware(nvidia_hw):
    assert hwprobe.override(nvidia_hw) is nvidia_hw


def test_raw_sources_on_linux_include_sysfs(monkeypatch, tmp_path):
    dev = tmp_path / "card1" / "device"
    dev.mkdir(parents=True)
    (dev / "vendor").write_text("0x1002\n")
    (dev / "mem_info_vram_total").write_text("17163091968\n")
    monkeypatch.setattr(hwprobe.platform, "system", lambda: "Linux")
    monkeypatch.setattr(hwprobe, "find_exe", lambda *a, **k: None)
    monkeypatch.setattr(hwprobe, "DRM", str(tmp_path))
    raw = dict(hwprobe.raw_sources())
    assert raw[f"{tmp_path}/card1/device/vendor"] == "0x1002"
    assert raw[f"{tmp_path}/card1/device/mem_info_vram_total"] == "17163091968"


def test_raw_sources_never_include_the_hostname():
    text = "\n".join(t for _, t in hwprobe.raw_sources())
    assert hwprobe.platform.node() not in text


def test_identical_cards_pool_their_memory(monkeypatch):
    card = {"name": "NVIDIA GeForce RTX 3090", "vram_gb": 24.0, "free_gb": 23.0, "kind": "nvidia"}
    _fake_windows(monkeypatch, [dict(card), dict(card)], ram=64.0)
    hw = hwprobe.probe()
    assert hw["gpu"]["name"] == "2x NVIDIA GeForce RTX 3090"
    assert hw["gpu"]["vram_gb"] == 48.0 and hw["gpu"]["free_gb"] == 46.0
    assert hw["gpu"]["count"] == 2 and hw["fast_gb"] == 47.0
    assert any("one card's speed" in n for n in hw["notes"])


def test_registry_duplicates_are_not_pooled():
    # Windows keeps entries for removed adapters; two may be the same card
    ghost = {
        "name": "AMD Radeon RX 7800 XT",
        "vram_gb": 16.0,
        "kind": "amd",
        "from_registry": True,
    }
    assert len(hwprobe.combine_identical([dict(ghost), dict(ghost)])) == 2


@pytest.mark.parametrize(
    "name,integrated",
    [
        ("Intel(R) UHD Graphics 770", True),
        ("Intel(R) Iris(R) Xe Graphics", True),
        ("Intel(R) Arc(TM) Graphics", True),  # Meteor Lake's built-in Arc
        ("Intel(R) Arc(TM) A770 Graphics", False),
        ("Intel(R) Arc(TM) B580 Graphics", False),
        ("NVIDIA GeForce RTX 4070", False),
    ],
)
def test_is_integrated_intel(name, integrated):
    assert hwprobe.is_integrated_intel(name) is integrated


def test_integrated_intel_reporting_shared_memory_is_not_an_accelerator(monkeypatch):
    _fake_windows(
        monkeypatch,
        [{"name": "Intel(R) Iris(R) Xe Graphics", "vram_gb": 8.0, "kind": "intel"}],
        ram=16.0,
    )
    hw = hwprobe.probe()
    assert hw["gpu"] is None and hw["fast_gb"] == 0.0
