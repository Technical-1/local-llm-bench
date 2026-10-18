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
