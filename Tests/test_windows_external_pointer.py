#!/usr/bin/env python3
"""Guard UIKit iPad/external-display mouse routing against regressions."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "FactorioPad" / "FactorioUIKitApp.m").read_text(encoding="utf-8")


class WindowsExternalPointerTests(unittest.TestCase):
    def test_raw_mouse_requires_phone_or_captured_scene(self):
        start = APP.index("- (BOOL)usesRawMouse")
        end = APP.index("+ (Class)layerClass", start)
        policy = APP[start:end]
        self.assertIn("UIUserInterfaceIdiomPhone", policy)
        self.assertIn("scene.pointerLockState.locked", policy)

    def test_relative_mouse_callbacks_are_capture_gated(self):
        self.assertGreaterEqual(APP.count("[self usesRawMouse]"), 7)
        self.assertIn("GCMouseDidDisconnectNotification", APP)

    def test_unlocked_pointer_events_route_position_and_clicks(self):
        self.assertIn("UITouchTypeIndirectPointer", APP)
        self.assertIn("e.buttonMask", APP)
        self.assertIn("[self pointerEvent:t buttons:0]", APP)
        self.assertIn("UIEventButtonMaskForButtonNumber(3)", APP)

    def test_unlocked_scrolling_uses_uikit_scroll_gesture(self):
        self.assertIn("scroll.allowedScrollTypesMask = UIScrollTypeMaskAll", APP)
        self.assertIn("- (void)pointerScrolled:(UIPanGestureRecognizer *)g", APP)
        self.assertIn("FactorioMouseWheel(sx, sy)", APP)

    def test_pointer_lock_changes_release_button_state(self):
        self.assertIn("UIPointerLockStateDidChangeNotification", APP)
        start = APP.index("- (void)pointerLockChanged:")
        end = APP.index("- (void)mouseConnected:", start)
        self.assertIn("updateMouseButtons:0", APP[start:end])
        self.assertIn("UIScreenDidConnectNotification", APP)
        self.assertIn("UIScreenDidDisconnectNotification", APP)

    def test_display_layout_uses_actual_scene_screen(self):
        self.assertIn("self.window.windowScene.screen.scale", APP)
        self.assertIn("scene.screen.bounds", APP)
        self.assertIn("UIScreen.screens.count == 1", APP)


if __name__ == "__main__":
    unittest.main()
