#!/usr/bin/env python3
"""Game-free source contract checks for the Duo UIKit UX.

These do not replace a Windows SDK build or physical Duo layout/input test.
Run: python -m unittest discover -s Tests -p test_duo_uikit_ux.py
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "FactorioPad/FactorioUIKitApp.m").read_text(encoding="utf-8")
TOUCH = (ROOT / "FactorioPad/FactorioTouchUIKit.m").read_text(encoding="utf-8")
LOADER = (ROOT / "FactorioPad/FactorioLoader.mm").read_text(encoding="utf-8")
BUILDER = (ROOT / "Tools/build_windows_template.py").read_text(encoding="utf-8")


class DuoUIKitUXTests(unittest.TestCase):
    def test_duo_rotation_and_split_layout(self):
        self.assertIn("UIInterfaceOrientationMaskAllButUpsideDown", APP)
        self.assertNotIn("initWithInterfaceOrientations:UIInterfaceOrientationMaskLandscape", APP)
        self.assertIn("BOOL duoPortrait", APP)
        self.assertIn("CGFloat hinge = CGRectGetMidY(bounds)", APP)
        self.assertIn("self.gameView.frame = CGRectIntegral(gameRect)", APP)
        self.assertIn("self.touchPad.frame = CGRectIntegral(controlsRect)", APP)
        self.assertIn('"UIInterfaceOrientationPortrait"', BUILDER)

    def test_no_blanket_phone_inset(self):
        self.assertIn("UIEdgeInsetsInsetRect(bounds, safe)", APP)
        self.assertNotIn("constant:pad", APP)
        self.assertIn("Duo geometry scene=", APP)

    def test_keyboard_icon_and_long_press_menu_are_always_accessible(self):
        self.assertIn('systemImageNamed:@"keyboard"', TOUCH)
        self.assertIn("keyboardLongPress:", TOUCH)
        self.assertIn("self.keyboardButton.hidden = NO", TOUCH)
        self.assertIn("Return to FactoriOS", TOUCH)
        self.assertNotIn('setTitle:@"Home" forState:', TOUCH)
        self.assertNotIn('setTitle:@"Hide pad" forState:', TOUCH)

    def test_connected_controller_hides_pad_not_keyboard(self):
        self.assertIn("GCControllerDidConnectNotification", APP)
        self.assertIn("GCControllerDidDisconnectNotification", APP)
        self.assertIn("self.touchPad.enabled = [GCController controllers].count == 0;", APP)
        self.assertIn("self.showing = enabled;", TOUCH)

    def test_launcher_responds_to_game_data(self):
        self.assertIn("[FactorioLoader hasValidGameData]", APP)
        self.assertIn("self.importButton.hidden = ready;", APP)
        self.assertIn("self.playButton.enabled = ready;", APP)
        self.assertIn("FactorioDataProblem(path, version) == nil", LOADER)
        self.assertIn("initWithItems:@[", APP)

    def test_compatibility_routing_is_not_changed_for_ui(self):
        canonical = (ROOT / "Tools/patch_factorio.py").read_text(encoding="utf-8")
        self.assertIn('"Foundation",', canonical.split("SHIM_FRAMEWORKS =", 1)[1])
        self.assertIn('"CoreGraphics",', canonical.split("SHIM_FRAMEWORKS =", 1)[1])


if __name__ == "__main__":
    unittest.main()
