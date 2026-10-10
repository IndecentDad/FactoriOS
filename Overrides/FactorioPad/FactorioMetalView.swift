import AVFAudio
import GameController
import SwiftUI
import UIKit

final class FactorioHostUIView: UIView, UIPointerInteractionDelegate {
    var presentationReady = false
    var inputEnabled = true {
        didSet {
            setInputActive(window != nil && UIApplication.shared.applicationState == .active)
            updatePointerLockPreference()
        }
    }
    weak var hostController: FactorioViewController?
    var hasPhysicalMouse: Bool { !mice.isEmpty }
    private var useRawMouse: Bool {
        hasPhysicalMouse && (UIDevice.current.userInterfaceIdiom == .phone
            || window?.windowScene?.pointerLockState?.isLocked == true)
    }
    private var hasPhysicalKeyboard: Bool { GCKeyboard.coalesced != nil }
    private static var factorioStarted = false
    private var pendingStartSize: CGSize?
    private var primaryTouch: UITouch?
    private var pressedKeys = Set<Int>()
    private var mouseButtons: UIEvent.ButtonMask = []
    private var mouseButtonSources = FactorioMouseButtonSources()
    private var pointerPosition: CGPoint?
    private var scrollRemainder = CGPoint.zero
    private var mice: [GCMouse] = []
    private var lifecycleObservers: [NSObjectProtocol] = []
    private var inputActive = true
    private var cursorDisplayLink: CADisplayLink?
    private let controllerCursor = UIImageView()
    private lazy var nativePointerInteraction = UIPointerInteraction(delegate: self)
    private var guestCursorReceived = false
    private var guestCursorHidden = false
    private var cursorHotSpot = CGPoint.zero
    private var lastPointerMovement: CFTimeInterval = 0
    private let pointerIdleTimeout: CFTimeInterval = 2
    private let onScreenKeyboard = FactorioOnScreenKeyboardView()
    private let keyboardButton = FactorioTouchOnlyButton(type: .system)

    override class var layerClass: AnyClass { FactorioMetalLayer.self }
    override var canBecomeFirstResponder: Bool { true }

    override init(frame: CGRect) {
        FactorioLoader.logMessage("Creating the game view")
        super.init(frame: frame)
        backgroundColor = .black
        isOpaque = true
        isMultipleTouchEnabled = true
        onScreenKeyboard.isHidden = true
        onScreenKeyboard.onClose = { [weak self] in
            self?.onScreenKeyboard.isHidden = true
            self?.updateKeyboardButton()
            self?.keyboardButton.accessibilityLabel = "Show keyboard"
        }
        controllerCursor.isUserInteractionEnabled = false
        controllerCursor.tintColor = .white
        controllerCursor.isHidden = true
        addSubview(controllerCursor)
        addSubview(onScreenKeyboard)
        keyboardButton.setImage(UIImage(systemName: "keyboard"), for: .normal)
        keyboardButton.tintColor = .white
        keyboardButton.backgroundColor = UIColor.black.withAlphaComponent(0.4)
        keyboardButton.layer.cornerRadius = 22
        keyboardButton.accessibilityLabel = "Show keyboard"
        keyboardButton.accessibilityHint = "Touch and hold for FactoriOS settings."
        keyboardButton.accessibilityCustomActions = [UIAccessibilityCustomAction(
            name: "Show FactoriOS settings", target: self, selector: #selector(showControlsWithAccessibility))]
        keyboardButton.addTarget(self, action: #selector(toggleKeyboard), for: .touchUpInside)
        let controlsPress = UILongPressGestureRecognizer(target: self, action: #selector(showControls))
        controlsPress.minimumPressDuration = 0.5
        keyboardButton.addGestureRecognizer(controlsPress)
        addSubview(keyboardButton)
        updateKeyboardButton()

        let hover = UIHoverGestureRecognizer(target: self, action: #selector(pointerHovered))
        addGestureRecognizer(hover)
        addInteraction(nativePointerInteraction)
        let scroll = UIPanGestureRecognizer(target: self, action: #selector(pointerScrolled))
        scroll.allowedScrollTypesMask = .all
        scroll.allowedTouchTypes = []
        scroll.cancelsTouchesInView = false
        addGestureRecognizer(scroll)

        let center = NotificationCenter.default
        lifecycleObservers.append(center.addObserver(forName: Notification.Name("FactoriOSGuestCursorChanged"),
            object: nil, queue: .main) { [weak self] notification in
                guard let self else { return }
                self.guestCursorReceived = true
                self.guestCursorHidden = notification.userInfo?["hidden"] as? Bool ?? false
                self.controllerCursor.image = notification.userInfo?["image"] as? UIImage
                self.cursorHotSpot = (notification.userInfo?["hotspot"] as? NSValue)?.cgPointValue ?? .zero
                self.nativePointerInteraction.invalidate()
                self.updateControllerCursor()
            })
        lifecycleObservers.append(center.addObserver(forName: UIApplication.willResignActiveNotification,
            object: nil, queue: .main) { [weak self] _ in self?.setInputActive(false) })
        lifecycleObservers.append(center.addObserver(forName: UIApplication.didBecomeActiveNotification,
            object: nil, queue: .main) { [weak self] _ in
                self?.setInputActive(true)
                if Self.factorioStarted { self?.configureAudioSession() }
            })
        lifecycleObservers.append(center.addObserver(forName: AVAudioSession.interruptionNotification,
            object: AVAudioSession.sharedInstance(), queue: .main) { [weak self] notification in
                guard let type = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                    type == AVAudioSession.InterruptionType.ended.rawValue,
                    let options = notification.userInfo?[AVAudioSessionInterruptionOptionKey] as? UInt,
                    AVAudioSession.InterruptionOptions(rawValue: options).contains(.shouldResume),
                    UIApplication.shared.applicationState == .active else { return }
                self?.configureAudioSession()
            })
        lifecycleObservers.append(center.addObserver(forName: NSNotification.Name.GCMouseDidConnect,
            object: nil, queue: .main) { [weak self] notification in
            if let mouse = notification.object as? GCMouse { self?.installMouse(mouse) }
        })
        lifecycleObservers.append(center.addObserver(forName: NSNotification.Name.GCMouseDidDisconnect,
            object: nil, queue: .main) { [weak self] notification in
            guard let self, let mouse = notification.object as? GCMouse,
                self.mice.contains(where: { $0 === mouse }) else { return }
            let buttons = self.mouseButtonSources.remove(ObjectIdentifier(mouse))
            self.mice.removeAll { $0 === mouse }
            if self.mice.isEmpty {
                self.releaseMouseInput()
            } else if self.useRawMouse {
                self.updateMouseButtons(UIEvent.ButtonMask(rawValue: buttons),
                    at: self.pointerPosition ?? CGPoint(x: bounds.midX, y: bounds.midY))
            }
            self.updatePointerLockPreference()
            for replacement in GCMouse.mice() { self.installMouse(replacement) }
        })
        lifecycleObservers.append(center.addObserver(forName: UIPointerLockState.didChangeNotification,
            object: nil, queue: .main) { [weak self] _ in self?.releaseMouseInput() })
        for name in [Notification.Name.GCKeyboardDidConnect, .GCKeyboardDidDisconnect,
            .GCControllerDidConnect, .GCControllerDidDisconnect] {
            lifecycleObservers.append(center.addObserver(forName: name, object: nil, queue: .main) {
                [weak self] _ in self?.updateKeyboardButton()
            })
        }
        for mouse in GCMouse.mice() { installMouse(mouse) }
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    deinit {
        for observer in lifecycleObservers { NotificationCenter.default.removeObserver(observer) }
    }

    func detach() {
        cursorDisplayLink?.invalidate()
        cursorDisplayLink = nil
        if !Self.factorioStarted { pendingStartSize = nil; presentationReady = false }
        setInputActive(false)
    }

    private func setInputActive(_ applicationActive: Bool) {
        let active = applicationActive && inputEnabled
        inputActive = active
        primaryTouch = nil
        cursorDisplayLink?.isPaused = !active
        if !active {
            releasePhysicalInput()
            FactorioTouchCancel()
            onScreenKeyboard.reset()
        } else if window != nil {
            becomeFirstResponder()
        }
        // Keep the game rendering under help sheets. Suspend only for app lifecycle events.
        FactorioMetalLayer.setApplicationActive(applicationActive)
    }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        guard window != nil else { detach(); return }
        FactorioLoader.logMessage("Attaching the game view to the window")
        FactorioMetalHost.setHostView(self)
        if cursorDisplayLink == nil {
            let displayLink = CADisplayLink(target: self, selector: #selector(updateControllerCursor))
            displayLink.add(to: .main, forMode: .common)
            cursorDisplayLink = displayLink
        }
        setInputActive(UIApplication.shared.applicationState == .active)
        updatePointerLockPreference()
        // Startup waits for a nonzero layout instead of assuming an iPad model.
        setNeedsLayout()
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        guard window != nil, bounds.width > 0, bounds.height > 0 else { return }
        FactorioMetalHost.setHostView(self)
        // Use equal proportional edge gaps, not the side inset reserved for the iPhone notch.
        let buttonInset = max(8, min(bounds.width, bounds.height) * 0.016)
        keyboardButton.frame = CGRect(x: bounds.maxX - buttonInset - 44,
            y: bounds.maxY - buttonInset - 44, width: 44, height: 44)
        let keyboardHeight = min(280, bounds.height)
        onScreenKeyboard.frame = CGRect(x: 0, y: bounds.maxY - keyboardHeight,
            width: bounds.width, height: keyboardHeight)

        if !Self.factorioStarted && presentationReady {
            let candidate = bounds.size
            if pendingStartSize != candidate {
                pendingStartSize = candidate
                FactorioLoader.logMessage(
                    "Game view candidate: \(Int(candidate.width))x\(Int(candidate.height))"
                )
                DispatchQueue.main.async { [weak self] in
                    self?.startFactorioIfLayoutStable(candidate)
                }
            }
        }
        FactorioTouchUpdateWindowSize()
    }

    private func startFactorioIfLayoutStable(_ expectedSize: CGSize) {
        guard !Self.factorioStarted, window != nil,
            abs(bounds.width - expectedSize.width) < 0.5,
            abs(bounds.height - expectedSize.height) < 0.5 else { return }

        let scene = window?.windowScene
        let screen = scene?.screen
        let windowSize = window?.bounds.size ?? .zero
        let screenSize = screen?.bounds.size ?? .zero
        let nativeSize = screen?.nativeBounds.size ?? .zero
        let orientation = scene?.interfaceOrientation.rawValue ?? 0
        FactorioLoader.logMessage(
            "Stable game view: \(Int(bounds.width))x\(Int(bounds.height)); " +
            "window: \(Int(windowSize.width))x\(Int(windowSize.height)); " +
            "screen: \(Int(screenSize.width))x\(Int(screenSize.height)); " +
            "native: \(Int(nativeSize.width))x\(Int(nativeSize.height)); " +
            "orientation: \(orientation)"
        )

        pendingStartSize = nil
        Self.factorioStarted = true
        configureAudioSession()
        FactorioLoader.start(withWindowSize: bounds.size)
    }

    @objc private func updateControllerCursor() {
        let recentMovement = lastPointerMovement > 0 &&
            CACurrentMediaTime() - lastPointerMovement < pointerIdleTimeout
        controllerCursor.isHidden = !inputActive || !guestCursorReceived || guestCursorHidden ||
            pointerPosition == nil || !recentMovement || controllerCursor.image == nil
        if let point = pointerPosition, let image = controllerCursor.image {
            controllerCursor.frame = CGRect(
                origin: CGPoint(x: point.x - cursorHotSpot.x, y: point.y - cursorHotSpot.y),
                size: image.size)
        }
    }

    func pointerInteraction(_ interaction: UIPointerInteraction,
        styleFor region: UIPointerRegion) -> UIPointerStyle? {
        // Keep a native fallback until the guest supplies its cursor state.
        // An invisible guest cursor lets Factorio render its controller crosshair itself.
        return guestCursorReceived ? .hidden() : nil
    }

    @objc private func toggleKeyboard() {
        guard !hasPhysicalKeyboard else { return }
        onScreenKeyboard.isHidden.toggle()
        updateKeyboardButton()
        keyboardButton.accessibilityLabel = onScreenKeyboard.isHidden ? "Show keyboard" : "Hide keyboard"
    }

    private func updateKeyboardButton() {
        if hasPhysicalKeyboard {
            onScreenKeyboard.isHidden = true
            onScreenKeyboard.reset()
        }
        keyboardButton.isHidden = (hasPhysicalKeyboard) || !onScreenKeyboard.isHidden
    }

    @objc private func showControls(_ gesture: UILongPressGestureRecognizer) {
        switch gesture.state {
        case .began:
            keyboardButton.isHighlighted = false
            requestControls()
        case .ended, .cancelled, .failed:
            keyboardButton.isHighlighted = false
        default:
            break
        }
    }

    @objc private func showControlsWithAccessibility() -> Bool {
        requestControls()
        return true
    }

    private func requestControls() {
        onScreenKeyboard.isHidden = true
        updateKeyboardButton()
        keyboardButton.accessibilityLabel = "Show keyboard"
        NotificationCenter.default.post(name: .factorioControlsRequested, object: nil)
    }

    private func updateTouch(_ touch: UITouch, send: (CGFloat, CGFloat) -> Void) {
        let point = touch.location(in: self)
        send(point.x, point.y)
    }

    private func physicalModifiers() -> UInt16 {
        let keys = pressedKeys
        return (keys.contains(225) ? 0x0001 : 0) | (keys.contains(229) ? 0x0002 : 0)
            | (keys.contains(224) ? 0x0040 : 0) | (keys.contains(228) ? 0x0080 : 0)
            | (keys.contains(226) ? 0x0100 : 0) | (keys.contains(230) ? 0x0200 : 0)
            | (keys.contains(227) ? 0x0400 : 0) | (keys.contains(231) ? 0x0800 : 0)
    }

    private func releasePhysicalInput() {
        FactorioInputPerform {
            for key in self.pressedKeys { FactorioKeyboardPhysicalKeyUp(Int32(key), 0) }
            self.pressedKeys.removeAll()
            FactorioKeyboardSetPhysicalModifierState(0)
        }
        releaseMouseInput()
    }

    private func releaseMouseInput() {
        mouseButtonSources.removeAll()
        if !mouseButtons.isEmpty {
            updateMouseButtons([], at: pointerPosition ?? CGPoint(x: bounds.midX, y: bounds.midY))
        }
        pointerPosition = nil
        lastPointerMovement = 0
        controllerCursor.isHidden = true
        scrollRemainder = .zero
    }

    override func pressesBegan(_ presses: Set<UIPress>, with event: UIPressesEvent?) {
        guard inputActive else { super.pressesBegan(presses, with: event); return }
        var unhandled = Set<UIPress>()
        for press in presses {
            guard let key = press.key, (4...231).contains(Int(key.keyCode.rawValue)) else {
                unhandled.insert(press)
                continue
            }
            // UIKit HID usage values match SDL scancodes for standard keyboard keys.
            let code = Int(key.keyCode.rawValue)
            FactorioInputPerform {
                if self.pressedKeys.insert(code).inserted {
                    FactorioKeyboardSetPhysicalModifierState(self.physicalModifiers())
                    FactorioKeyboardPhysicalKeyDown(Int32(code), 0)
                } else if code == 42 {
                    FactorioKeyboardBackspace()
                }
                if !key.modifierFlags.contains(.command) && !key.modifierFlags.contains(.control)
                    && !key.characters.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) {
                    FactorioKeyboardInsertText(key.characters)
                }
            }
        }
        if !unhandled.isEmpty { super.pressesBegan(unhandled, with: event) }
    }

    override func pressesEnded(_ presses: Set<UIPress>, with event: UIPressesEvent?) {
        let unhandled = endPresses(presses)
        if !unhandled.isEmpty { super.pressesEnded(unhandled, with: event) }
    }

    override func pressesCancelled(_ presses: Set<UIPress>, with event: UIPressesEvent?) {
        let unhandled = endPresses(presses)
        if !unhandled.isEmpty { super.pressesCancelled(unhandled, with: event) }
    }

    private func endPresses(_ presses: Set<UIPress>) -> Set<UIPress> {
        var unhandled = Set<UIPress>()
        for press in presses {
            guard let key = press.key else { unhandled.insert(press); continue }
            let code = Int(key.keyCode.rawValue)
            guard pressedKeys.contains(code) else { unhandled.insert(press); continue }
            FactorioInputPerform {
                FactorioKeyboardPhysicalKeyUp(Int32(code), 0)
                self.pressedKeys.remove(code)
                FactorioKeyboardSetPhysicalModifierState(self.physicalModifiers())
            }
        }
        return unhandled
    }

    private func movePointer(to point: CGPoint) {
        let point = CGPoint(x: min(max(point.x, 0), max(bounds.width - 1, 0)),
            y: min(max(point.y, 0), max(bounds.height - 1, 0)))
        let old = pointerPosition ?? point
        pointerPosition = point
        if old != point || lastPointerMovement == 0 {
            lastPointerMovement = CACurrentMediaTime()
        }
        FactorioMouseMove(Int32(point.x.rounded()), Int32(point.y.rounded()),
            Int32(point.x.rounded() - old.x.rounded()), Int32(point.y.rounded() - old.y.rounded()))
    }

    private func updateMouseButtons(_ buttons: UIEvent.ButtonMask, at point: CGPoint) {
        for (mask, button) in [(UIEvent.ButtonMask.primary, UInt8(1)), (.secondary, 3), (.button(3), 2)] {
            if mouseButtons.contains(mask) != buttons.contains(mask) {
                FactorioMouseButton(button, buttons.contains(mask), Int32(point.x.rounded()), Int32(point.y.rounded()))
            }
        }
        mouseButtons = buttons
    }

    private func pointerEvent(_ touch: UITouch, buttons: UIEvent.ButtonMask) {
        let point = touch.location(in: self)
        FactorioInputPerform {
            self.movePointer(to: point)
            self.updateMouseButtons(buttons, at: point)
        }
    }

    private func installMouse(_ mouse: GCMouse) {
        guard !mice.contains(where: { $0 === mouse }), let input = mouse.mouseInput else { return }
        let device = ObjectIdentifier(mouse)
        mice.append(mouse)
        updatePointerLockPreference()
        mouse.handlerQueue = .main
        input.mouseMovedHandler = { [weak self] _, dx, dy in
            guard let self, self.inputActive, self.useRawMouse else { return }
            let origin = self.pointerPosition ?? CGPoint(x: bounds.midX, y: bounds.midY)
            let speed: CGFloat = 1.0
            self.movePointer(to: CGPoint(x: origin.x + CGFloat(dx) * speed,
                y: origin.y - CGFloat(dy) * speed))
        }
        input.leftButton.pressedChangedHandler = { [weak self] _, _, pressed in
            self?.mouseButton(.primary, pressed: pressed, from: device)
        }
        input.rightButton?.pressedChangedHandler = { [weak self] _, _, pressed in
            self?.mouseButton(.secondary, pressed: pressed, from: device)
        }
        input.middleButton?.pressedChangedHandler = { [weak self] _, _, pressed in
            self?.mouseButton(.button(3), pressed: pressed, from: device)
        }
        input.scroll.valueChangedHandler = { [weak self] _, x, y in
            guard let self, self.inputActive, self.useRawMouse else { return }
            self.scrollRemainder.x += CGFloat(x)
            self.scrollRemainder.y += CGFloat(y)
            let stepsX = Int32(self.scrollRemainder.x.rounded(.towardZero))
            let stepsY = Int32(self.scrollRemainder.y.rounded(.towardZero))
            self.scrollRemainder.x -= CGFloat(stepsX)
            self.scrollRemainder.y -= CGFloat(stepsY)
            if stepsX != 0 || stepsY != 0 { FactorioMouseWheel(stepsX, stepsY) }
        }
    }

    private func mouseButton(_ button: UIEvent.ButtonMask, pressed: Bool, from device: ObjectIdentifier) {
        guard inputActive, useRawMouse, mice.contains(where: { ObjectIdentifier($0) == device }) else { return }
        let point = pointerPosition ?? CGPoint(x: bounds.midX, y: bounds.midY)
        let buttons = mouseButtonSources.set(button.rawValue, pressed: pressed, for: device)
        updateMouseButtons(UIEvent.ButtonMask(rawValue: buttons), at: point)
    }

    private func updatePointerLockPreference() {
        (window?.rootViewController ?? hostController)?.setNeedsUpdateOfPrefersPointerLocked()
    }


    @objc private func pointerHovered(_ gesture: UIHoverGestureRecognizer) {
        guard inputActive, !useRawMouse else { return }
        if gesture.state == .ended || gesture.state == .cancelled {
            pointerPosition = nil
            lastPointerMovement = 0
            controllerCursor.isHidden = true
            return
        }
        guard gesture.state == .began || gesture.state == .changed else { return }
        movePointer(to: gesture.location(in: self))
    }

    @objc private func pointerScrolled(_ gesture: UIPanGestureRecognizer) {
        guard inputActive, !useRawMouse,
            gesture.state == .began || gesture.state == .changed else { return }
        let delta = gesture.translation(in: self)
        gesture.setTranslation(.zero, in: self)
        scrollRemainder.x += delta.x / 20
        scrollRemainder.y -= delta.y / 20
        let x = Int32(scrollRemainder.x.rounded(.towardZero))
        let y = Int32(scrollRemainder.y.rounded(.towardZero))
        scrollRemainder.x -= CGFloat(x)
        scrollRemainder.y -= CGFloat(y)
        if x != 0 || y != 0 { FactorioMouseWheel(x, y) }
    }

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        super.touchesBegan(touches, with: event)
        if let pointer = touches.first(where: { $0.type == .indirectPointer }) {
            if inputActive && !useRawMouse { pointerEvent(pointer, buttons: event?.buttonMask ?? .primary) }
            return
        }
        guard inputActive, primaryTouch == nil, let touch = touches.first else { return }
        primaryTouch = touch
        updateTouch(touch, send: FactorioTouchBegin)
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        super.touchesMoved(touches, with: event)
        if let pointer = touches.first(where: { $0.type == .indirectPointer }) {
            if inputActive && !useRawMouse { pointerEvent(pointer, buttons: event?.buttonMask ?? mouseButtons) }
            return
        }
        guard inputActive, let primaryTouch, touches.contains(primaryTouch) else { return }
        for touch in event?.coalescedTouches(for: primaryTouch) ?? [primaryTouch] {
            updateTouch(touch, send: FactorioTouchMove)
        }
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        super.touchesEnded(touches, with: event)
        if let pointer = touches.first(where: { $0.type == .indirectPointer }) {
            if inputActive && !useRawMouse { pointerEvent(pointer, buttons: []) }
            return
        }
        guard inputActive, let primaryTouch, touches.contains(primaryTouch) else { return }
        updateTouch(primaryTouch, send: FactorioTouchEnd)
        self.primaryTouch = nil
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        super.touchesCancelled(touches, with: event)
        if touches.contains(where: { $0.type == .indirectPointer }) {
            if !useRawMouse, let point = pointerPosition { updateMouseButtons([], at: point) }
            return
        }
        guard let primaryTouch, touches.contains(primaryTouch) else { return }
        FactorioTouchCancel()
        self.primaryTouch = nil
    }

    private func configureAudioSession() {
        FactorioLoader.logMessage("Configuring audio")
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .default)
            try session.setActive(true)
            FactorioLoader.logMessage("Audio is ready")
        } catch { FactorioLoader.logMessage("Audio session failed: \(error.localizedDescription)") }
    }
}

final class FactorioViewController: UIViewController {
    let gameView = FactorioHostUIView(frame: .zero)
    private var hasAppeared = false
    private var lastStartupGeometry: String?
    // Keep the native iPadOS pointer available for external-display and multitasking use.
    // The legacy orange FactorioPad cursor is suppressed separately in the game view.
    override var prefersPointerLocked: Bool { false }
    override var preferredScreenEdgesDeferringSystemGestures: UIRectEdge { [.bottom, .right] }
    override var prefersStatusBarHidden: Bool { true }
    override var prefersHomeIndicatorAutoHidden: Bool { true }

    override func loadView() {
        view = UIView()
        view.backgroundColor = .black
        gameView.hostController = self
        view.addSubview(gameView)
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if let root = view.window?.rootViewController as? FactorioRootController {
            root.gameController = self
            root.setNeedsUpdateOfPrefersPointerLocked()
        }
        setNeedsStatusBarAppearanceUpdate()
        setNeedsUpdateOfHomeIndicatorAutoHidden()
        setNeedsUpdateOfScreenEdgesDeferringSystemGestures()
        setNeedsUpdateOfPrefersPointerLocked()
        hasAppeared = true
        view.window?.windowScene?.requestGeometryUpdate(.iOS(interfaceOrientations: .landscape)) { error in
            FactorioLoader.logMessage("Landscape geometry request failed: \(error.localizedDescription)")
        }
        view.setNeedsLayout()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        // Keep the game landscape-shaped, with black bars outside the game viewport.
        let height = min(view.bounds.height, view.bounds.width * 0.75)
        gameView.frame = CGRect(x: 0, y: (view.bounds.height - height) / 2,
            width: view.bounds.width, height: height)

        guard let scene = view.window?.windowScene else { return }
        let viewSize = view.bounds.size
        let screenSize = scene.screen.bounds.size
        let viewIsLandscape = viewSize.width >= viewSize.height
        let screenIsLandscape = screenSize.width >= screenSize.height
        let geometryMatchesScreen = viewIsLandscape == screenIsLandscape
        let ready = hasAppeared && geometryMatchesScreen

        let geometry = "controller=\(Int(viewSize.width))x\(Int(viewSize.height)); " +
            "screen=\(Int(screenSize.width))x\(Int(screenSize.height)); " +
            "orientation=\(scene.interfaceOrientation.rawValue); ready=\(ready)"
        if geometry != lastStartupGeometry {
            lastStartupGeometry = geometry
            FactorioLoader.logMessage("Startup geometry: \(geometry)")
        }

        if gameView.presentationReady != ready {
            gameView.presentationReady = ready
            if ready { gameView.setNeedsLayout() }
        }
    }
}

struct FactorioMetalView: UIViewControllerRepresentable {
    var inputEnabled = true
    func makeUIViewController(context: Context) -> FactorioViewController { FactorioViewController() }
    func updateUIViewController(_ controller: FactorioViewController, context: Context) {
        if controller.gameView.inputEnabled != inputEnabled {
            controller.gameView.inputEnabled = inputEnabled
        }
    }
    static func dismantleUIViewController(_ controller: FactorioViewController, coordinator: ()) {
        controller.gameView.detach()
    }
}
