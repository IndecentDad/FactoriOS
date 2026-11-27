#import "FactorioControllerBridge.h"
#import "FactorioCursorView.h"
#import "FactorioKeyboardBridge.h"
#import "FactorioLoader.h"
#import "FactorioMetalHost.h"
#import "FactorioMetalLayer.h"
#import "FactorioSaveSync.h"
#import "FactorioTouchBridge.h"
#import "FactorioTouchUIKit.h"
#import <AVFAudio/AVFAudio.h>
#import <GameController/GameController.h>
#import <QuartzCore/CAMetalLayer.h>
#import <UIKit/UIKit.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>

@interface FactorioAppDelegate : UIResponder <UIApplicationDelegate>
@end
@interface FactorioSceneDelegate : UIResponder <UIWindowSceneDelegate>
@property(nonatomic, strong) UIWindow *window;
@end
@class FactorioGameView;
@interface FactorioGameController : UIViewController
@property(nonatomic, readonly) BOOL prefersPointerLocked;
@property(nonatomic, strong) FactorioGameView *gameView;
@property(nonatomic, strong) FactorioTouchUIKit *touchPad;
@end

@interface FactorioGameView : UIView <UIPointerInteractionDelegate>
@property(nonatomic, strong) FactorioCursorView *cursorView;
@property(nonatomic, strong) CADisplayLink *cursorDisplayLink;
@property(nonatomic, strong) UIPointerInteraction *pointerInteraction;
@property(nonatomic, strong) NSMutableSet<NSNumber *> *pressedKeys;
@property(nonatomic, strong) NSMutableArray<GCMouse *> *mice;
@property(nonatomic) CGPoint pointerPosition;
@property(nonatomic) CGPoint scrollRemainder;
@property(nonatomic) UIEventButtonMask mouseButtons;
@end
@implementation FactorioGameView
+ (Class)layerClass {
  return FactorioMetalLayer.class;
}
- (instancetype)initWithFrame:(CGRect)frame {
  if ((self = [super initWithFrame:frame])) {
    self.pressedKeys = [NSMutableSet set];
    self.mice = [NSMutableArray array];
    self.multipleTouchEnabled = YES;
    self.cursorView =
        [[FactorioCursorView alloc] initWithFrame:CGRectMake(0, 0, 18, 23)];
    [self addSubview:self.cursorView];
    self.pointerInteraction =
        [[UIPointerInteraction alloc] initWithDelegate:self];
    [self addInteraction:self.pointerInteraction];
    self.cursorDisplayLink =
        [CADisplayLink displayLinkWithTarget:self
                                    selector:@selector(updateControllerCursor)];
    [self.cursorDisplayLink addToRunLoop:NSRunLoop.mainRunLoop
                                 forMode:NSRunLoopCommonModes];
    UIHoverGestureRecognizer *h = [[UIHoverGestureRecognizer alloc]
        initWithTarget:self
                action:@selector(pointerHovered:)];
    [self addGestureRecognizer:h];
    [[NSNotificationCenter defaultCenter]
        addObserver:self
           selector:@selector(mouseConnected:)
               name:GCMouseDidConnectNotification
             object:nil];
    for (GCMouse *m in GCMouse.mice)
      [self installMouse:m];
  }
  return self;
}
- (void)movePointer:(CGPoint)p {
  p.x = MIN(MAX(p.x, 0), MAX(self.bounds.size.width - 1, 0));
  p.y = MIN(MAX(p.y, 0), MAX(self.bounds.size.height - 1, 0));
  CGPoint old = self.pointerPosition;
  self.pointerPosition = p;
  FactorioControllerBridgeSetCursorPosition(p.x, p.y);
  FactorioMouseMove((int)lrint(p.x), (int)lrint(p.y), (int)lrint(p.x - old.x),
                    (int)lrint(p.y - old.y));
}
- (void)updateControllerCursor {
  BOOL active = UIApplication.sharedApplication.applicationState ==
                UIApplicationStateActive;
  BOOL native = FactorioLoader.usesNativeController;
  BOOL mouse = GCMouse.mice.count > 0;
  BOOL hiddenByGame = native && FactorioMouseCursorVisibility() == 0;
  self.cursorView.hidden = !active || hiddenByGame || (!native && !mouse);
  CGPoint p = FactorioControllerBridgeGetCursorPosition();
  self.cursorView.frame = CGRectMake(p.x, p.y, 18, 23);
}
- (UIPointerRegion *)pointerInteraction:(UIPointerInteraction *)interaction
                       regionForRequest:(UIPointerRegionRequest *)request
                          defaultRegion:(UIPointerRegion *)region {
  return region;
}
- (UIPointerStyle *)pointerInteraction:(UIPointerInteraction *)interaction
                        styleForRegion:(UIPointerRegion *)region {
  if (FactorioLoader.usesNativeController &&
      FactorioMouseCursorVisibility() == 0)
    return UIPointerStyle.hiddenPointerStyle;
  return nil;
}
- (void)pointerHovered:(UIHoverGestureRecognizer *)g {
  if (g.state == UIGestureRecognizerStateBegan ||
      g.state == UIGestureRecognizerStateChanged)
    [self movePointer:[g locationInView:self]];
}
- (void)mouseConnected:(NSNotification *)n {
  GCMouse *m = n.object;
  if (m)
    [self installMouse:m];
}
- (void)installMouse:(GCMouse *)m {
  if ([self.mice containsObject:m] || !m.mouseInput)
    return;
  [self.mice addObject:m];
  m.handlerQueue = dispatch_get_main_queue();
  __weak typeof(self) weak = self;
  GCMouseInput *input = m.mouseInput;
  input.mouseMovedHandler = ^(GCMouseInput *mouse, float dx, float dy) {
    typeof(self) self = weak;
    if (!self)
      return;
    CGPoint p = self.pointerPosition;
    p.x += dx;
    p.y -= dy;
    [self movePointer:p];
  };
  input.leftButton.pressedChangedHandler =
      ^(GCControllerButtonInput *b, float v, BOOL down) {
        typeof(self) self = weak;
        if (self) {
          CGPoint p = self.pointerPosition;
          FactorioMouseButton(1, down, (int)p.x, (int)p.y);
        }
      };
  input.rightButton.pressedChangedHandler =
      ^(GCControllerButtonInput *b, float v, BOOL down) {
        typeof(self) self = weak;
        if (self) {
          CGPoint p = self.pointerPosition;
          FactorioMouseButton(3, down, (int)p.x, (int)p.y);
        }
      };
  input.middleButton.pressedChangedHandler =
      ^(GCControllerButtonInput *b, float v, BOOL down) {
        typeof(self) self = weak;
        if (self) {
          CGPoint p = self.pointerPosition;
          FactorioMouseButton(2, down, (int)p.x, (int)p.y);
        }
      };
  input.scroll.valueChangedHandler = ^(GCControllerDirectionPad *scroll,
                                       float x, float y) {
    typeof(self) self = weak;
    if (self) {
      self.scrollRemainder =
          CGPointMake(self.scrollRemainder.x + x, self.scrollRemainder.y + y);
      int sx = (int)trunc(self.scrollRemainder.x),
          sy = (int)trunc(self.scrollRemainder.y);
      self.scrollRemainder =
          CGPointMake(self.scrollRemainder.x - sx, self.scrollRemainder.y - sy);
      if (sx || sy)
        FactorioMouseWheel(sx, sy);
    }
  };
}
- (uint16_t)modifiers:(UIKeyModifierFlags)f {
  uint16_t m = 0;
  if (f & UIKeyModifierShift)
    m |= 1;
  if (f & UIKeyModifierControl)
    m |= 0x40;
  if (f & UIKeyModifierAlternate)
    m |= 0x100;
  if (f & UIKeyModifierCommand)
    m |= 0x400;
  return m;
}
- (BOOL)canBecomeFirstResponder {
  return YES;
}
- (void)dealloc {
  [self.cursorDisplayLink invalidate];
  [[NSNotificationCenter defaultCenter] removeObserver:self];
}
- (void)didMoveToWindow {
  [super didMoveToWindow];
  self.contentScaleFactor = self.window.windowScene.screen.scale;
  [FactorioMetalHost setHostView:self];
}
- (void)layoutSubviews {
  [super layoutSubviews];
  CGFloat s =
      self.window.windowScene.screen.scale ?: self.traitCollection.displayScale;
  CAMetalLayer *l = (CAMetalLayer *)self.layer;
  l.contentsScale = s;
  l.drawableSize =
      CGSizeMake(self.bounds.size.width * s, self.bounds.size.height * s);
  [FactorioMetalHost setHostView:self];
  FactorioControllerBridgeSetViewportSize(self.bounds.size.width,
                                          self.bounds.size.height);
  FactorioTouchUpdateWindowSize();
  [self bringSubviewToFront:self.cursorView];
  [self updateControllerCursor];
}
- (void)touchesBegan:(NSSet<UITouch *> *)ts withEvent:(UIEvent *)e {
  for (UITouch *t in ts) {
    CGPoint p = [t locationInView:self];
    FactorioTouchBegin(p.x, p.y);
  }
}
- (void)touchesMoved:(NSSet<UITouch *> *)ts withEvent:(UIEvent *)e {
  for (UITouch *t in ts) {
    CGPoint p = [t locationInView:self];
    FactorioTouchMove(p.x, p.y);
  }
}
- (void)touchesEnded:(NSSet<UITouch *> *)ts withEvent:(UIEvent *)e {
  for (UITouch *t in ts) {
    CGPoint p = [t locationInView:self];
    FactorioTouchEnd(p.x, p.y);
  }
}
- (void)touchesCancelled:(NSSet<UITouch *> *)ts withEvent:(UIEvent *)e {
  FactorioTouchCancel();
}
- (void)pressesBegan:(NSSet<UIPress *> *)ps withEvent:(UIPressesEvent *)e {
  NSMutableSet *other = [NSMutableSet set];
  for (UIPress *p in ps) {
    UIKey *k = p.key;
    if (!k || k.keyCode < 4 || k.keyCode > 231) {
      [other addObject:p];
      continue;
    }
    int32_t code = (int32_t)k.keyCode;
    FactorioInputPerform(^{
      if (![self.pressedKeys containsObject:@(code)]) {
        [self.pressedKeys addObject:@(code)];
        FactorioKeyboardSetPhysicalModifierState(
            [self modifiers:k.modifierFlags]);
        FactorioKeyboardPhysicalKeyDown(code, 0);
      }
      if (code == 42)
        FactorioKeyboardBackspace();
      if (!(k.modifierFlags & (UIKeyModifierCommand | UIKeyModifierControl)) &&
          k.characters.length)
        FactorioKeyboardInsertText(k.characters);
    });
  }
  if (other.count)
    [super pressesBegan:other withEvent:e];
}
- (void)pressesEnded:(NSSet<UIPress *> *)ps withEvent:(UIPressesEvent *)e {
  NSMutableSet *other = [NSMutableSet set];
  for (UIPress *p in ps) {
    UIKey *k = p.key;
    if (!k) {
      [other addObject:p];
      continue;
    }
    int32_t code = (int32_t)k.keyCode;
    if ([self.pressedKeys containsObject:@(code)]) {
      FactorioInputPerform(^{
        FactorioKeyboardPhysicalKeyUp(code, 0);
        [self.pressedKeys removeObject:@(code)];
        FactorioKeyboardSetPhysicalModifierState(
            [self modifiers:k.modifierFlags]);
      });
    } else
      [other addObject:p];
  }
  if (other.count)
    [super pressesEnded:other withEvent:e];
}
- (void)pressesCancelled:(NSSet<UIPress *> *)ps withEvent:(UIPressesEvent *)e {
  [self pressesEnded:ps withEvent:e];
}
@end

@interface FactorioNavigationController : UINavigationController
@end

@interface FactorioHomeController : UIViewController <UIDocumentPickerDelegate>
@property(nonatomic) BOOL selectingSaveFolder;
@end
@implementation FactorioHomeController
- (void)viewDidLoad {
  [super viewDidLoad];
  self.title = @"FactoriOS";
  self.view.backgroundColor = UIColor.systemBackgroundColor;
  UIStackView *s = [UIStackView new];
  s.axis = UILayoutConstraintAxisVertical;
  s.spacing = 14;
  s.translatesAutoresizingMaskIntoConstraints = NO;
  UILabel *t = [UILabel new];
  t.text = @"FactoriOS";
  t.font = [UIFont preferredFontForTextStyle:UIFontTextStyleLargeTitle];
  t.textAlignment = NSTextAlignmentCenter;
  UILabel *d = [UILabel new];
  d.text = @"Import your FactorioData folder, then launch the game.";
  d.numberOfLines = 0;
  d.textAlignment = NSTextAlignmentCenter;
  [s addArrangedSubview:t];
  [s addArrangedSubview:d];
  [s addArrangedSubview:[self button:@"Import FactorioData"
                              action:@selector(importData)]];
  [s addArrangedSubview:[self button:@"Choose Factorio save folder"
                              action:@selector(chooseSaveFolder)]];
  [s addArrangedSubview:[self button:@"Play" action:@selector(play)]];
  [s addArrangedSubview:[self button:@"Graphics: Cycle Preset"
                              action:@selector(cycleGraphics)]];
  [s addArrangedSubview:[self button:@"Controller: Toggle Native Mode"
                              action:@selector(toggleController)]];
  [s addArrangedSubview:[self button:@"Share Startup Log"
                              action:@selector(shareLog)]];
  [self.view addSubview:s];
  UILayoutGuide *g = self.view.safeAreaLayoutGuide;
  [NSLayoutConstraint activateConstraints:@[
    [s.centerXAnchor constraintEqualToAnchor:g.centerXAnchor],
    [s.centerYAnchor constraintEqualToAnchor:g.centerYAnchor],
    [s.widthAnchor constraintLessThanOrEqualToAnchor:g.widthAnchor
                                            constant:-40],
    [s.widthAnchor constraintEqualToConstant:380]
  ]];
  [[NSNotificationCenter defaultCenter] addObserver:self
                                           selector:@selector(stopped:)
                                               name:@"FactorioStopped"
                                             object:nil];
  NSString *guest = [NSBundle.mainBundle.privateFrameworksPath
      stringByAppendingPathComponent:@"FactorioGuest.framework/FactorioGuest"];
  if ([NSFileManager.defaultManager fileExistsAtPath:guest])
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
      NSError *e = nil;
      BOOL ok = [FactorioLoader
          importSavedGameDataWithProgress:^(double f) {
          }
                                    error:&e];
      if (!ok)
        dispatch_async(dispatch_get_main_queue(), ^{
          [self alert:e.localizedDescription
                          ?: @"Could not import packaged game data."];
        });
    });
}
- (UIButton *)button:(NSString *)title action:(SEL)sel {
  UIButton *b = [UIButton buttonWithType:UIButtonTypeSystem];
  [b setTitle:title forState:UIControlStateNormal];
  b.titleLabel.font =
      [UIFont preferredFontForTextStyle:UIFontTextStyleHeadline];
  b.backgroundColor = UIColor.secondarySystemBackgroundColor;
  b.layer.cornerRadius = 10;
  b.contentEdgeInsets = UIEdgeInsetsMake(14, 12, 14, 12);
  [b addTarget:self action:sel forControlEvents:UIControlEventTouchUpInside];
  return b;
}
- (void)importData {
  self.selectingSaveFolder = NO;
  UIDocumentPickerViewController *p = [[UIDocumentPickerViewController alloc]
      initForOpeningContentTypes:@[ UTTypeFolder ]
                          asCopy:NO];
  p.delegate = self;
  [self presentViewController:p animated:YES completion:nil];
}
- (void)chooseSaveFolder {
  self.selectingSaveFolder = YES;
  UIDocumentPickerViewController *p = [[UIDocumentPickerViewController alloc]
      initForOpeningContentTypes:@[ UTTypeFolder ]
                          asCopy:NO];
  p.delegate = self;
  [self presentViewController:p animated:YES completion:nil];
}
- (void)documentPicker:(UIDocumentPickerViewController *)p
    didPickDocumentsAtURLs:(NSArray<NSURL *> *)urls {
  NSError *e = nil;
  if (!urls.count)
    return;
  if (self.selectingSaveFolder) {
    BOOL ok = [FactorioSaveSync saveFolder:urls[0] error:&e];
    if (ok)
      ok = [FactorioSaveSync synchronize:&e];
    [self alert:ok ? @"Save folder selected and synchronized."
                   : e.localizedDescription];
  } else {
    BOOL ok = [FactorioLoader selectGameDataFromURL:urls[0]
                                           progress:^(double f) {
                                           }
                                              error:&e];
    [self alert:ok ? @"FactorioData imported." : e.localizedDescription];
  }
}
- (void)play {
  NSError *e = nil;
  if ([FactorioSaveSync hasFolder] && ![FactorioSaveSync synchronize:&e]) {
    [self alert:e.localizedDescription ?: @"Save sync failed."];
    return;
  }
  [self.navigationController pushViewController:[FactorioGameController new]
                                       animated:YES];
}
- (void)cycleGraphics {
  NSArray *a = @[ @"low", @"medium", @"high" ];
  NSUInteger i = [a indexOfObject:FactorioLoader.graphicsPreset];
  [[NSUserDefaults standardUserDefaults] setObject:a[(i + 1) % a.count]
                                            forKey:@"FactorioGraphicsPreset"];
  [self alert:[NSString stringWithFormat:@"Graphics preset: %@",
                                         FactorioLoader.graphicsPreset]];
}
- (void)toggleController {
  NSUserDefaults *d = NSUserDefaults.standardUserDefaults;
  BOOL b = ![d boolForKey:@"FactorioNativeController"];
  [d setBool:b forKey:@"FactorioNativeController"];
  [self alert:b ? @"Native controller mode selected."
                : @"Controller keyboard/mouse emulation selected."];
}
- (void)shareLog {
  NSURL *u = FactorioLoader.startupLogURL;
  if (!u) {
    [self alert:@"Startup log is not available."];
    return;
  }
  UIActivityViewController *a =
      [[UIActivityViewController alloc] initWithActivityItems:@[ u ]
                                        applicationActivities:nil];
  a.popoverPresentationController.sourceView = self.view;
  a.popoverPresentationController.sourceRect = CGRectMake(
      CGRectGetMidX(self.view.bounds), CGRectGetMidY(self.view.bounds), 1, 1);
  [self presentViewController:a animated:YES completion:nil];
}
- (void)stopped:(NSNotification *)n {
  [self alert:n.userInfo[@"message"] ?: @"Factorio stopped."];
}
- (void)alert:(NSString *)m {
  UIAlertController *a =
      [UIAlertController alertControllerWithTitle:@"FactoriOS"
                                          message:m
                                   preferredStyle:UIAlertControllerStyleAlert];
  [a addAction:[UIAlertAction actionWithTitle:@"OK"
                                        style:UIAlertActionStyleDefault
                                      handler:nil]];
  [self presentViewController:a animated:YES completion:nil];
}
@end

@implementation FactorioGameController
- (BOOL)prefersPointerLocked {
  if (GCMouse.mice.count == 0)
    return NO;
  if (UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPad &&
      FactorioLoader.usesNativeController)
    return UIScreen.screens.count == 1;
  return YES;
}
- (UIRectEdge)preferredScreenEdgesDeferringSystemGestures {
  return UIRectEdgeBottom | UIRectEdgeRight;
}
- (BOOL)prefersHomeIndicatorAutoHidden {
  return YES;
}
- (BOOL)prefersStatusBarHidden {
  return YES;
}
- (void)pointerConfigurationChanged:(NSNotification *)n {
  [self setNeedsUpdateOfPrefersPointerLocked];
  [self.navigationController setNeedsUpdateOfPrefersPointerLocked];
  // A controller hides the on-screen pad, but never the keyboard shortcut.
  // The user can still reveal touch controls via the keyboard's hold menu.
  if ([n.name isEqualToString:GCControllerDidConnectNotification] ||
      [n.name isEqualToString:GCControllerDidDisconnectNotification]) {
    self.touchPad.enabled = GCController.controllers.count == 0;
  }
}
- (UIInterfaceOrientationMask)supportedInterfaceOrientations {
  // The Duo has a useful two-panel portrait layout. Do not force landscape.
  return UIInterfaceOrientationMaskAllButUpsideDown;
}
- (void)viewDidLoad {
  [super viewDidLoad];
  self.view.backgroundColor = UIColor.blackColor;
  FactorioGameView *v = [FactorioGameView new];
  self.gameView = v;
  // Manual scene-based layout lets the unfolded Duo use both orientations.
  // Metal host and input viewport follow the actual gameView bounds.
  v.frame = self.view.bounds;
  v.autoresizingMask = UIViewAutoresizingNone;
  [self.view addSubview:v];
  self.touchPad = [FactorioTouchUIKit new];
  self.touchPad.translatesAutoresizingMaskIntoConstraints = NO;
  self.touchPad.enabled = GCController.controllers.count == 0;
  __weak typeof(self) weakSelf = self;
  self.touchPad.onExit = ^{
    [weakSelf.navigationController popViewControllerAnimated:YES];
  };
  [self.view addSubview:self.touchPad];
  for (NSString *name in @[
         UIScreenDidConnectNotification, UIScreenDidDisconnectNotification,
         GCMouseDidConnectNotification, GCMouseDidDisconnectNotification,
         GCControllerDidConnectNotification, GCControllerDidDisconnectNotification
       ])
    [[NSNotificationCenter defaultCenter]
        addObserver:self
           selector:@selector(pointerConfigurationChanged:)
               name:name
             object:nil];
  self.touchPad.frame = self.view.bounds;
  self.touchPad.autoresizingMask = UIViewAutoresizingNone;
  self.navigationController.navigationBarHidden = YES;
}
- (void)dealloc {
  [[NSNotificationCenter defaultCenter] removeObserver:self];
}
- (void)viewDidAppear:(BOOL)animated {
  [super viewDidAppear:animated];
  [self setNeedsUpdateOfPrefersPointerLocked];
  [self setNeedsUpdateOfHomeIndicatorAutoHidden];
  [self setNeedsUpdateOfScreenEdgesDeferringSystemGestures];
  UIView *v = self.view.subviews.firstObject;
  [v becomeFirstResponder];
  FactorioControllerBridgeSetActive(YES);
  FactorioInputSetActive(YES);
  NSError *audioError = nil;
  AVAudioSession *audio = AVAudioSession.sharedInstance;
  if ([audio setCategory:AVAudioSessionCategoryPlayback error:&audioError] &&
      [audio setActive:YES error:&audioError])
    [FactorioLoader logMessage:@"Audio is ready"];
  else
    [FactorioLoader
        logMessage:[NSString stringWithFormat:@"Audio session failed: %@",
                                              audioError.localizedDescription]];
  [FactorioLoader startWithWindowSize:v.bounds.size];
}
- (void)viewWillDisappear:(BOOL)animated {
  [super viewWillDisappear:animated];
  FactorioControllerBridgeSetActive(NO);
  FactorioInputSetActive(NO);
  NSError *e = nil;
  if ([FactorioSaveSync hasFolder] && ![FactorioSaveSync synchronize:&e])
    [FactorioLoader
        logMessage:[NSString stringWithFormat:@"Save sync failed: %@",
                                              e.localizedDescription]];
  self.navigationController.navigationBarHidden = NO;
}
- (void)viewDidLayoutSubviews {
  [super viewDidLayoutSubviews];
  CGRect bounds = self.view.bounds;
  UIEdgeInsets safe = self.view.safeAreaInsets;
  CGRect usable = UIEdgeInsetsInsetRect(bounds, safe);
  // A single unfolded Duo scene is two landscape panels in portrait.
  // Do not apply this split to ordinary narrow iPhones or iPads.
  BOOL duoPortrait =
      UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPhone &&
      CGRectGetHeight(bounds) > CGRectGetWidth(bounds) * 1.15 &&
      CGRectGetWidth(bounds) >= 600;
  CGRect gameRect = usable, controlsRect = usable;
  if (duoPortrait) {
    CGFloat hinge = CGRectGetMidY(bounds);
    gameRect.size.height = MAX(1, hinge - CGRectGetMinY(usable) - 3);
    CGFloat controlsTop = hinge + 3;
    controlsRect = CGRectMake(CGRectGetMinX(usable), controlsTop,
                              CGRectGetWidth(usable),
                              MAX(1, CGRectGetMaxY(usable) - controlsTop));
  }
  // Rely on actual asymmetric scene safe areas, not the former blanket
  // 16-point phone padding that needlessly shrank the game on the Duo.
  self.gameView.frame = CGRectIntegral(gameRect);
  self.touchPad.frame = CGRectIntegral(controlsRect);
  [self.gameView setNeedsLayout];
  [self.touchPad setNeedsLayout];

  UIWindowScene *scene = self.view.window.windowScene;
  CAMetalLayer *metal = (CAMetalLayer *)self.gameView.layer;
  [FactorioLoader logMessage:[NSString stringWithFormat:
      @"Duo geometry scene=%@ window=%@ safe=%@ game=%@ touch=%@ "
       "drawable=%@ orientation=%ld duoPortrait=%d",
      NSStringFromCGRect(scene.coordinateSpace.bounds),
      NSStringFromCGRect(self.view.window.bounds),
      NSStringFromUIEdgeInsets(safe), NSStringFromCGRect(self.gameView.frame),
      NSStringFromCGRect(self.touchPad.frame),
      NSStringFromCGSize(metal.drawableSize),
      (long)scene.interfaceOrientation, duoPortrait]];
}
@end

@implementation FactorioNavigationController
- (BOOL)prefersPointerLocked {
  UIViewController *top = self.topViewController;
  return [top isKindOfClass:FactorioGameController.class]
             ? ((FactorioGameController *)top).prefersPointerLocked
             : NO;
}
@end

@implementation FactorioAppDelegate
- (BOOL)application:(UIApplication *)a
    didFinishLaunchingWithOptions:(NSDictionary *)o {
  [FactorioLoader restoreStartupLogFolder];
  return YES;
}
- (UISceneConfiguration *)application:(UIApplication *)a
    configurationForConnectingSceneSession:(UISceneSession *)s
                                   options:(UISceneConnectionOptions *)o {
  UISceneConfiguration *c =
      [[UISceneConfiguration alloc] initWithName:@"FactoriOS"
                                     sessionRole:s.role];
  c.delegateClass = FactorioSceneDelegate.class;
  return c;
}
- (void)applicationDidBecomeActive:(UIApplication *)a {
  [FactorioMetalLayer setApplicationActive:YES];
  FactorioInputSetActive(YES);
}
- (void)applicationWillResignActive:(UIApplication *)a {
  [FactorioMetalLayer setApplicationActive:NO];
  FactorioInputSetActive(NO);
}
@end
@implementation FactorioSceneDelegate
- (void)scene:(UIScene *)scene
    willConnectToSession:(UISceneSession *)session
                 options:(UISceneConnectionOptions *)options {
  if (![scene isKindOfClass:UIWindowScene.class])
    return;
  UIWindowScene *s = (UIWindowScene *)scene;
  self.window = [[UIWindow alloc] initWithWindowScene:s];
  self.window.rootViewController = [[FactorioNavigationController alloc]
      initWithRootViewController:[FactorioHomeController new]];
  [self.window makeKeyAndVisible];
  // Let UIKit deliver portrait or landscape geometry for the Duo.
  // We compose game + controls from the scene bounds, not a forced rotation.
  [FactorioLoader
      logMessage:[NSString
                     stringWithFormat:@"Scene connected screen=%@ window=%@",
                                      NSStringFromCGRect(
                                          s.coordinateSpace.bounds),
                                      NSStringFromCGRect(self.window.bounds)]];
}
@end
