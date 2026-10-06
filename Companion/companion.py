#!/usr/bin/env python3
"""The FactoriOS companion for Windows, macOS, and Linux."""

from pathlib import Path
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
import urllib.request
import urllib.parse
import json
import zipfile
import io

from package_ipa import MARKER, package_dmg


REPO = "IndecentDad/FactoriOS"
RELEASE_TAG = "FactoriOS-latest"
TEMPLATE_NAME = "FactoriOS-template.ipa"
UPSTREAM_REPO = "MyNameIsArko/FactorioPad"
UPSTREAM_TEMPLATE_NAME = "FactorioPad-template.ipa"

def resource_root():
    return Path(__file__).resolve().parent

def github_request(url, accept="application/vnd.github+json"):
    # Public template downloads never read credentials or invoke GitHub CLI.
    return urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "FactoriOS-Companion"})


def github_branches():
    api = f"https://api.github.com/repos/{REPO}/branches?per_page=100"
    try:
        with urllib.request.urlopen(github_request(api), timeout=30) as response:
            branches = json.load(response)
        return sorted({item.get("name", "").strip() for item in branches if item.get("name")})
    except Exception:
        return []


def cache_root():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path.home() / ".cache"
    root = base / "FactoriOS" / "Companion"
    root.mkdir(parents=True, exist_ok=True)
    return root


def download_release_template(cache, metadata, progress):
    api = f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}"
    with urllib.request.urlopen(github_request(api), timeout=30) as response:
        release = json.load(response)
    asset = next((item for item in release.get("assets", []) if item.get("name") == TEMPLATE_NAME), None)
    if not asset:
        raise ValueError(f"{TEMPLATE_NAME} is missing from {RELEASE_TAG}.")
    key = f"release:{asset.get('id')}"
    current = {}
    if metadata.is_file():
        try:
            current = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            pass
    if cache.is_file() and current.get("key") == key:
        progress("Using the current cached FactoriOS template.")
        return cache
    progress("Downloading the latest FactoriOS release template...")
    with urllib.request.urlopen(github_request(asset["browser_download_url"], "application/octet-stream"), timeout=120) as response:
        data = response.read()
    temporary = cache.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(cache)
    metadata.write_text(json.dumps({"key": key, "updated_at": asset.get("updated_at")}), encoding="utf-8")
    return cache


def download_upstream_template(cache, metadata, progress):
    api = f"https://api.github.com/repos/{UPSTREAM_REPO}/releases/latest"
    with urllib.request.urlopen(github_request(api), timeout=30) as response:
        release = json.load(response)
    asset = next((item for item in release.get("assets", [])
                  if item.get("name") == UPSTREAM_TEMPLATE_NAME), None)
    if not asset:
        raise ValueError(f"{UPSTREAM_TEMPLATE_NAME} is missing from the latest FactorioPad release.")
    key = f"upstream-release:{asset.get('id')}"
    current = {}
    if metadata.is_file():
        try:
            current = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            pass
    if cache.is_file() and current.get("key") == key:
        progress("Using the current cached FactorioPad template.")
        return cache
    progress(f"Downloading FactorioPad {release.get('tag_name', 'latest')} template...")
    with urllib.request.urlopen(github_request(asset["browser_download_url"], "application/octet-stream"), timeout=120) as response:
        data = response.read()
    temporary = cache.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(cache)
    metadata.write_text(json.dumps({"key": key, "tag": release.get("tag_name"),
                                    "updated_at": asset.get("updated_at")}), encoding="utf-8")
    return cache


def download_branch_template(branch, cache, metadata, progress):
    progress(f"Finding the latest successful {branch} template build...")
    query = urllib.parse.urlencode({"branch": branch, "status": "success", "per_page": 20})
    api = f"https://api.github.com/repos/{REPO}/actions/workflows/build.yml/runs?{query}"
    with urllib.request.urlopen(github_request(api), timeout=30) as response:
        runs = json.load(response).get("workflow_runs", [])
    run = next((item for item in runs if item.get("event") == "workflow_dispatch"), None)
    if not run:
        raise ValueError(f"No successful template build was found for branch {branch}.")
    with urllib.request.urlopen(github_request(run["artifacts_url"]), timeout=30) as response:
        artifacts = json.load(response).get("artifacts", [])
    artifact = next((item for item in artifacts if item.get("name") == "FactoriOS-template" and not item.get("expired")), None)
    if not artifact:
        raise ValueError(f"The latest successful {branch} build has no available FactoriOS-template artifact.")
    key = f"artifact:{artifact.get('id')}"
    current = {}
    if metadata.is_file():
        try:
            current = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            pass
    if cache.is_file() and current.get("key") == key:
        progress(f"Using cached template from {branch}.")
        return cache
    progress(f"Downloading template from {branch}...")
    with urllib.request.urlopen(github_request(artifact["archive_download_url"]), timeout=120) as response:
        data = response.read()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [name for name in archive.namelist() if name.endswith(".ipa")]
        if not names:
            raise ValueError("The workflow artifact does not contain a template IPA.")
        temporary = cache.with_suffix(".tmp")
        temporary.write_bytes(archive.read(names[0]))
        temporary.replace(cache)
    metadata.write_text(json.dumps({"key": key, "branch": branch, "run_id": run.get("id")}), encoding="utf-8")
    return cache


def latest_template(resources, progress, source="FactoriOS-latest"):
    bundled = resources / "FactorioPad-template.ipa"
    safe_source = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in source)
    cache = cache_root() / f"{safe_source}-{TEMPLATE_NAME}"
    metadata = cache_root() / f"{safe_source}-template.json"
    progress(f"Checking {source} for a FactoriOS template...")
    try:
        if source == "FactoriOS-latest":
            return download_release_template(cache, metadata, progress)
        if source == "FactorioPad-latest":
            return download_upstream_template(cache, metadata, progress)
        return download_branch_template(source, cache, metadata, progress)
    except Exception as error:
        if cache.is_file():
            progress(f"Update check unavailable; using cached {source} template.")
            return cache
        if source == "FactoriOS-latest" and bundled.is_file():
            progress("GitHub update check unavailable; using bundled FactoriOS template.")
            return bundled
        raise ValueError(f"Could not get a template for {source}: {error}") from error


def result_folder(parent):
    output = parent / "FactoriOS-personal"
    number = 2
    while output.exists():
        output = parent / f"FactoriOS-personal-{number}"
        number += 1
    return output


def prepare_game(dmg, parent, resources, progress, include_data=True, source="FactoriOS-latest"):
    template = latest_template(resources, progress, source)
    extractor = resources / "7zip" / ("7z.exe" if sys.platform == "win32" else "7zz")
    if not template.is_file() or not extractor.is_file():
        raise ValueError("The companion files are missing. Extract the entire release archive, then open the app again.")
    output = result_folder(parent)
    package_dmg(template, dmg, output, extractor, progress=progress, include_data=include_data)
    original = output / "FactorioPad.ipa"
    branded = output / "FactoriOS.ipa"
    if original.is_file():
        original.replace(branded)
    return output


def open_folder(path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


class Companion:
    def __init__(self, window):
        self.window = window
        self.busy = False
        self.output = None
        self.last_include_data = False
        self.events = queue.Queue()
        self.settings_path = cache_root() / "settings.json"
        settings = self.load_settings()
        self.image = tk.StringVar(value=settings.get("dmg", ""))
        self.destination = tk.StringVar(value=settings.get("destination", str(Path.home() / "Downloads")))
        source = settings.get("source", "FactoriOS-latest")
        self.source = tk.StringVar(value=source)
        self.include_data = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Select your game download to start.")
        self.instructions = tk.StringVar(value="The app keeps your DMG unchanged. Keep your prepared IPA private because it contains your Factorio executable.")
        window.title("FactoriOS Companion")
        window.minsize(650, 430)
        window.protocol("WM_DELETE_WINDOW", self.close)
        frame = ttk.Frame(window, padding=24)
        frame.grid(sticky="nsew")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="Prepare FactoriOS", font=("", 20, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(frame, text="Select the Mac Factorio DMG from factorio.com.").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 20))
        ttk.Label(frame, text="Build source").grid(row=3, column=0, sticky="w")
        self.source_box = ttk.Combobox(frame, textvariable=self.source, state="readonly",
                                      values=("FactoriOS-latest", "FactorioPad-latest"))
        self.source_box.grid(row=4, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Label(frame, text="Factorio DMG").grid(row=5, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.image, state="readonly", width=55).grid(row=6, column=0, sticky="ew", pady=6)
        self.choose_image = ttk.Button(frame, text="Choose DMG", command=self.pick_image)
        self.choose_image.grid(row=6, column=1, padx=(12, 0))
        ttk.Label(frame, text="Save the result in").grid(row=7, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frame, textvariable=self.destination, state="readonly").grid(row=8, column=0, sticky="ew", pady=6)
        self.choose_folder = ttk.Button(frame, text="Choose folder", command=self.pick_folder)
        self.choose_folder.grid(row=8, column=1, padx=(12, 0))
        ttk.Checkbutton(frame, text="Include FactorioData (needed for initial installation or game-data updates)",
                        variable=self.include_data).grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=13, column=0, columnspan=2, sticky="w", pady=(16, 8))
        self.prepare_button = ttk.Button(buttons, text="Prepare FactoriOS", command=self.prepare)
        self.prepare_button.pack(side="left")
        self.open_button = ttk.Button(buttons, text="Open result", state="disabled", command=self.open_result)
        self.open_button.pack(side="left", padx=12)
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=11, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(frame, textvariable=self.status, wraplength=600).grid(row=12, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(frame, textvariable=self.instructions, wraplength=600, justify="left").grid(
            row=10, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(frame, text="Sideloading help", command=lambda: webbrowser.open(
            "https://github.com/MyNameIsArko/FactorioPad#install-on-your-device")).grid(row=14, column=0, sticky="w", pady=8)
        window.after(100, self.poll)
        threading.Thread(target=lambda: self.events.put(("branches", github_branches())), daemon=True).start()

    def load_settings(self):
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8")) if self.settings_path.is_file() else {}
        except (OSError, ValueError, TypeError):
            return {}

    def save_settings(self):
        self.settings_path.write_text(json.dumps({
            "dmg": self.image.get(),
            "destination": self.destination.get(),
            "source": self.source.get(),
            "include_data": self.include_data.get(),
        }, indent=2), encoding="utf-8")

    def pick_image(self):
        selected = filedialog.askopenfilename(parent=self.window, title="Select your Factorio DMG", filetypes=[("Mac disk images", "*.dmg")])
        if selected:
            self.image.set(selected)

    def pick_folder(self):
        selected = filedialog.askdirectory(parent=self.window, title="Choose where to save the result", initialdir=self.destination.get())
        if selected:
            self.destination.set(selected)

    def prepare(self):
        dmg = Path(self.image.get())
        if not self.image.get() or not dmg.is_file() or dmg.suffix.lower() != ".dmg":
            messagebox.showerror("Select a game download", "Select your Mac Factorio DMG first.", parent=self.window)
            return
        self.busy = True
        self.output = None
        for button in (self.prepare_button, self.choose_image, self.choose_folder, self.open_button):
            button.configure(state="disabled")
        self.progress.start()
        self.status.set("Preparing your app. Keep this window open until preparation finishes.")
        # Tk calls stay on the main thread. The worker only posts queue messages.
        parent = Path(self.destination.get())
        self.save_settings()
        include_data = self.include_data.get()
        self.last_include_data = include_data
        source = self.source.get()
        def worker():
            try:
                output = prepare_game(dmg, parent, resource_root(), lambda text: self.events.put(("progress", text)), include_data=include_data, source=source)
                self.events.put(("done", output))
            except Exception as error:
                self.events.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                self.status.set(value)
                continue
            if kind == "branches":
                stable = ["FactoriOS-latest", "FactorioPad-latest"]
                choices = stable + [branch for branch in value if branch not in stable]
                self.source_box.configure(values=choices)
                if self.source.get() not in choices:
                    self.source.set("FactoriOS-latest")
                continue
            self.busy = False
            self.progress.stop()
            for button in (self.prepare_button, self.choose_image, self.choose_folder):
                button.configure(state="normal")
            if kind == "done":
                self.output = value
                self.open_button.configure(state="normal")
                self.status.set("Your app is ready. Click Open result to see the files.")
                self.instructions.set("Install FactoriOS.ipa with your sideloading tool." +
                                      ("\nTransfer FactorioData to Files only when you intentionally included fresh game data." if self.last_include_data else
                                       "\nYour existing FactorioData folder on the device can stay in place."))
            else:
                self.status.set("Preparation failed. Select another DMG or destination and try again.")
                messagebox.showerror("Cannot prepare FactoriOS", value, parent=self.window)
        self.window.after(100, self.poll)

    def open_result(self):
        try:
            open_folder(self.output)
        except OSError as error:
            messagebox.showerror("Cannot open the folder", str(error), parent=self.window)

    def close(self):
        if self.busy:
            self.status.set("Wait for preparation to finish before you close this window.")
        else:
            self.window.destroy()


def self_test():
    """Exercise the packaged runtime before publishing a release."""
    window = tk.Tk()
    window.withdraw()
    Companion(window)
    window.update()
    resources = resource_root()
    import zipfile
    with zipfile.ZipFile(resources / "FactorioPad-template.ipa") as archive:
        assert any(name.endswith(MARKER) for name in archive.namelist())
        assert not any("/FactorioData/" in name or "/FactorioGuest.framework/" in name for name in archive.namelist())
    extractor = resources / "7zip" / ("7z.exe" if sys.platform == "win32" else "7zz")
    subprocess.run([str(extractor), "i"], check=True, stdout=subprocess.DEVNULL,
                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    # An optional local DMG exercises extraction and patching with the frozen app.
    if len(sys.argv) == 3:
        with tempfile.TemporaryDirectory(prefix="factoriopad-self-test-") as temporary:
            output = prepare_game(Path(sys.argv[2]), Path(temporary), resources, lambda text: None, include_data=True)
            assert (output / "FactoriOS.ipa").is_file()
            assert (output / "FactorioData/base/info.json").is_file()
    window.destroy()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        try:
            self_test()
        except Exception:
            sys.exit(1)
    else:
        window = tk.Tk()
        Companion(window)
        window.mainloop()

