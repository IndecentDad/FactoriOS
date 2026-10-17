# FactorioPad

Play Factorio on your iPhone or iPad. You need iOS 17 or iPadOS 17 or newer. Use touch controls, a gamepad, or a keyboard and mouse.

You need your own copy of Factorio. You do not need Xcode or a Mac.
Tested on Factorio 2.0.77. Other versions are allowed but untested.
The companion skips texture fixes when it cannot find their instruction patterns.
The executable and game data must use the same version.
The companion supports Windows x64, Macs with Apple silicon, and Linux x64.

## Install on your device

1. Download the companion for your computer from [Releases](https://github.com/MyNameIsArko/FactorioPad/releases).
2. Extract the download and open FactorioPad Companion.
3. Download the Mac Factorio DMG from [factorio.com](https://factorio.com/download), even if you use Windows or Linux. Use 2.0.77 for the tested version.
4. In the companion, select the DMG and click `Prepare app`.
5. Click `Open result` when preparation finishes.
6. Install `FactorioPad.ipa` with [Sideloadly](https://sideloadly.io/) on Windows or Mac, or [iloader](https://github.com/nab138/iloader) on Linux.
7. Copy the generated `FactorioData` folder to Files on your iPhone or iPad.
8. Open FactorioPad, tap `Import game data`, and select that folder.

Wait for the import progress bar to finish. FactorioPad keeps its own copy for later launches.
After import, you can remove the original folder.
Before you press `Play`, choose a mode from the `Controls` and `Graphics` dropdowns.
`Medium` is the default. `Low` also reduces animation quality. `High` increases texture and shadow detail but can exceed your device's memory limit.
The app remembers your choice and preserves existing Low or High selections. Supported GPUs use Factorio's default texture compression.
Save sharing is optional. Choose `Play without sync` to start without it.

Keep your generated IPA private because it contains your Factorio executable.

## What changes on iPhone and iPad

- A gamepad uses `Mouse and keyboard emulation` by default. Select `Factorio native controls` for analog movement and Factorio's controller interface.
- Physical keyboards and mice support typing, clicks, dragging, and scrolling.
- Touch controls provide movement, aiming, building, mining, and shortcuts on iPhone and iPad.
- New installations use a 150% interface scale and one visible quickbar.
- New freeplay games skip the opening cutscene and tutorial prompt.
- Tap the keyboard button to type. Hold it to see the guide for your current controls.
- Full-screen play keeps a connected mouse pointer inside the game.

## Share saves through iCloud

Use the same iCloud Drive folder to share saves between your iPhone and iPad:

1. Create a folder in iCloud Drive, such as `FactorioPad Saves`.
2. In FactorioPad, tap `Choose save folder`.
3. Select that iCloud Drive folder on each device.

FactorioPad syncs saves before the game starts and after you exit the game.
Let iCloud finish transferring saves before you continue on another device.
For Mac saves, use the [Mac setup script](Tools/link_macos_saves.sh).

```sh
bash Tools/link_macos_saves.sh
```

For development, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Report a crash

If the app or game crashes, reopen FactorioPad.
Tap `Share log` on the setup screen.
Attach `FactorioPad.log` to your GitHub issue.

## FactoriOS fork builds

In this fork, open Actions and run **Build FactoriOS Template** from `main`.
Set **source_ref** to `main` or `external-display`. After it succeeds, run
**Build FactoriOS Windows Companion**, also from `main`, with the same source_ref.
The companion build checks that its source commit matches the published template.

Main builds publish to `FactoriOS-latest`; other branches publish prereleases such as
`FactoriOS-branch-external-display`. Download the Windows companion ZIP from that
release and select the same source in its Build source menu. The first device
installation needs FactorioData; later wrapper updates can use app-only packaging
when the installed Factorio data matches the executable version.

These workflows build this fork directly. No Factorio game files are downloaded or
published by Actions. The template gets the existing FactoriOS icon/display name
at build time; source on the external-display contribution branch remains upstream-branded.
The upstream **Build companion releases** workflow is also retained for its original
FactorioPad-template.ipa release format; use the two FactoriOS workflows above for this fork.
