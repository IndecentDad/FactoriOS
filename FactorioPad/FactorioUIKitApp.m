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
#import <QuartzCore/CAGradientLayer.h>
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
- (BOOL)usesRawMouse {
  if (self.mice.count == 0)
    return NO;
  if (UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPhone)
    return YES;
  UIWindowScene *scene = self.window.windowScene;
  return scene.pointerLockState.locked;
}
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
    UIPanGestureRecognizer *scroll = [[UIPanGestureRecognizer alloc]
        initWithTarget:self action:@selector(pointerScrolled:)];
    scroll.allowedScrollTypesMask = UIScrollTypeMaskAll;
    scroll.allowedTouchTypes = @[];
    scroll.cancelsTouchesInView = NO;
    [self addGestureRecognizer:scroll];
    NSNotificationCenter *center = NSNotificationCenter.defaultCenter;
    [center addObserver:self selector:@selector(mouseConnected:)
                   name:GCMouseDidConnectNotification object:nil];
    [center addObserver:self selector:@selector(mouseDisconnected:)
                   name:GCMouseDidDisconnectNotification object:nil];
    [center addObserver:self selector:@selector(pointerLockChanged:)
                   name:UIPointerLockStateDidChangeNotification object:nil];
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
- (void)updateMouseButtons:(UIEventButtonMask)buttons at:(CGPoint)p {
  UIEventButtonMask masks[] = {
      UIEventButtonMaskPrimary, UIEventButtonMaskSecondary,
      UIEventButtonMaskForButtonNumber(3)};
  const int buttonsToSend[] = {1, 3, 2};
  for (NSUInteger i = 0; i < 3; ++i) {
    BOOL wasPressed = (self.mouseButtons & masks[i]) != 0;
    BOOL isPressed = (buttons & masks[i]) != 0;
    if (wasPressed != isPressed)
      FactorioMouseButton(buttonsToSend[i], isPressed, (int)p.x, (int)p.y);
  }
  self.mouseButtons = buttons;
}
- (void)pointerEvent:(UITouch *)touch buttons:(UIEventButtonMask)buttons {
  CGPoint p = [touch locationInView:self];
  [self movePointer:p];
  [self updateMouseButtons:buttons at:p];
}
- (void)pointerHovered:(UIHoverGestureRecognizer *)g {
  if (![self usesRawMouse] &&
      UIApplication.sharedApplication.applicationState == UIApplicationStateActive &&
      (g.state == UIGestureRecognizerStateBegan ||
       g.state == UIGestureRecognizerStateChanged))
    [self movePointer:[g locationInView:self]];
}
- (void)pointerScrolled:(UIPanGestureRecognizer *)g {
  if ([self usesRawMouse] ||
      UIApplication.sharedApplication.applicationState != UIApplicationStateActive ||
      (g.state != UIGestureRecognizerStateBegan &&
       g.state != UIGestureRecognizerStateChanged))
    return;
  CGPoint delta = [g translationInView:self];
  [g setTranslation:CGPointZero inView:self];
  self.scrollRemainder.x += delta.x / 20.0;
  self.scrollRemainder.y -= delta.y / 20.0;
  int sx = (int)trunc(self.scrollRemainder.x);
  int sy = (int)trunc(self.scrollRemainder.y);
  self.scrollRemainder.x -= sx;
  self.scrollRemainder.y -= sy;
  if (sx || sy)
    FactorioMouseWheel(sx, sy);
}
- (void)pointerLockChanged:(NSNotification *)n {
  self.scrollRemainder = CGPointZero;
  [self updateMouseButtons:0 at:self.pointerPosition];
}
- (void)mouseConnected:(NSNotification *)n {
  GCMouse *m = n.object;
  if (m)
    [self installMouse:m];
}
- (void)mouseDisconnected:(NSNotification *)n {
  GCMouse *m = n.object;
  if (m)
    [self.mice removeObject:m];
  self.scrollRemainder = CGPointZero;
  [self updateControllerCursor];
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
    if (!self || ![self usesRawMouse] ||
        UIApplication.sharedApplication.applicationState != UIApplicationStateActive)
      return;
    CGPoint p = self.pointerPosition;
    p.x += dx;
    p.y -= dy;
    [self movePointer:p];
  };
  input.leftButton.pressedChangedHandler =
      ^(GCControllerButtonInput *b, float v, BOOL down) {
        typeof(self) self = weak;
        if (self && [self usesRawMouse]) {
          CGPoint p = self.pointerPosition;
          FactorioMouseButton(1, down, (int)p.x, (int)p.y);
        }
      };
  input.rightButton.pressedChangedHandler =
      ^(GCControllerButtonInput *b, float v, BOOL down) {
        typeof(self) self = weak;
        if (self && [self usesRawMouse]) {
          CGPoint p = self.pointerPosition;
          FactorioMouseButton(3, down, (int)p.x, (int)p.y);
        }
      };
  input.middleButton.pressedChangedHandler =
      ^(GCControllerButtonInput *b, float v, BOOL down) {
        typeof(self) self = weak;
        if (self && [self usesRawMouse]) {
          CGPoint p = self.pointerPosition;
          FactorioMouseButton(2, down, (int)p.x, (int)p.y);
        }
      };
  input.scroll.valueChangedHandler = ^(GCControllerDirectionPad *scroll,
                                       float x, float y) {
    typeof(self) self = weak;
    if (self && [self usesRawMouse]) {
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
    if (t.type == UITouchTypeIndirectPointer) {
      if (![self usesRawMouse])
        [self pointerEvent:t buttons:e.buttonMask];
      continue;
    }
    CGPoint p = [t locationInView:self];
    FactorioTouchBegin(p.x, p.y);
  }
}
- (void)touchesMoved:(NSSet<UITouch *> *)ts withEvent:(UIEvent *)e {
  for (UITouch *t in ts) {
    if (t.type == UITouchTypeIndirectPointer) {
      if (![self usesRawMouse])
        [self pointerEvent:t buttons:e.buttonMask];
      continue;
    }
    CGPoint p = [t locationInView:self];
    FactorioTouchMove(p.x, p.y);
  }
}
- (void)touchesEnded:(NSSet<UITouch *> *)ts withEvent:(UIEvent *)e {
  for (UITouch *t in ts) {
    if (t.type == UITouchTypeIndirectPointer) {
      if (![self usesRawMouse])
        [self pointerEvent:t buttons:0];
      continue;
    }
    CGPoint p = [t locationInView:self];
    FactorioTouchEnd(p.x, p.y);
  }
}
- (void)touchesCancelled:(NSSet<UITouch *> *)ts withEvent:(UIEvent *)e {
  BOOL cancelledTouch = NO;
  for (UITouch *t in ts) {
    if (t.type == UITouchTypeIndirectPointer) {
      if (![self usesRawMouse])
        [self updateMouseButtons:0 at:[t locationInView:self]];
    } else {
      cancelledTouch = YES;
    }
  }
  if (cancelledTouch)
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
@property(nonatomic, strong) UIScrollView *scroller;
@property(nonatomic, strong) UIView *heroCard;
@property(nonatomic, strong) UIView *settingsCard;
@property(nonatomic, strong) CAGradientLayer *heroGradient;
@property(nonatomic, strong) UILabel *dataStatus;
@property(nonatomic, strong) UILabel *syncStatus;
@property(nonatomic, strong) UIButton *playButton;
@property(nonatomic, strong) UIButton *importButton;
@property(nonatomic, strong) UISegmentedControl *graphicsControl;
@property(nonatomic, strong) UISegmentedControl *controllerControl;
@end

@implementation FactorioHomeController

- (UILabel *)label:(NSString *)text size:(CGFloat)size weight:(UIFontWeight)weight {
  UILabel *label = [UILabel new];
  label.text = text;
  label.font = [UIFont systemFontOfSize:size weight:weight];
  label.textColor = UIColor.whiteColor;
  label.numberOfLines = 0;
  return label;
}

- (UIButton *)button:(NSString *)title action:(SEL)selector primary:(BOOL)primary {
  UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
  [button setTitle:title forState:UIControlStateNormal];
  button.titleLabel.font = [UIFont systemFontOfSize:16 weight:UIFontWeightSemibold];
  button.backgroundColor = primary
      ? [UIColor colorWithRed:.97 green:.48 blue:.28 alpha:1]
      : [UIColor colorWithWhite:.19 alpha:1];
  [button setTitleColor:primary ? UIColor.blackColor : UIColor.whiteColor
              forState:UIControlStateNormal];
  button.layer.cornerRadius = 14;
  button.contentEdgeInsets = UIEdgeInsetsMake(14, 12, 14, 12);
  [button.heightAnchor constraintGreaterThanOrEqualToConstant:47].active = YES;
  [button addTarget:self action:selector forControlEvents:UIControlEventTouchUpInside];
  return button;
}

- (UIStackView *)cardStack:(UIView *)card {
  UIStackView *stack = [UIStackView new];
  stack.axis = UILayoutConstraintAxisVertical;
  stack.spacing = 11;
  stack.alignment = UIStackViewAlignmentFill;
  stack.distribution = UIStackViewDistributionFill;
  stack.translatesAutoresizingMaskIntoConstraints = NO;
  [card addSubview:stack];
  [NSLayoutConstraint activateConstraints:@[
    [stack.topAnchor constraintEqualToAnchor:card.topAnchor constant:22],
    [stack.leadingAnchor constraintEqualToAnchor:card.leadingAnchor constant:22],
    [stack.trailingAnchor constraintEqualToAnchor:card.trailingAnchor constant:-22],
    [stack.bottomAnchor constraintLessThanOrEqualToAnchor:card.bottomAnchor constant:-20]
  ]];
  return stack;
}

- (UIView *)card {
  UIView *view = [UIView new];
  view.backgroundColor = [UIColor colorWithRed:.13 green:.14 blue:.17 alpha:1];
  view.layer.cornerRadius = 23;
  view.clipsToBounds = YES;
  view.layer.borderColor = [UIColor colorWithWhite:.42 alpha:.30].CGColor;
  view.layer.borderWidth = 1;
  return view;
}

- (void)viewDidLoad {
  [super viewDidLoad];
  self.title = @"FactoriOS";
  self.view.backgroundColor = [UIColor colorWithRed:.055 green:.061 blue:.073 alpha:1];
  self.scroller = [UIScrollView new];
  self.scroller.alwaysBounceVertical = YES;
  self.scroller.backgroundColor = UIColor.clearColor;
  [self.view addSubview:self.scroller];

  self.heroCard = [self card];
  self.heroGradient = [CAGradientLayer layer];
  self.heroGradient.colors = @[
    (id)[UIColor colorWithRed:.27 green:.20 blue:.17 alpha:1].CGColor,
    (id)[UIColor colorWithRed:.12 green:.13 blue:.18 alpha:1].CGColor,
    (id)[UIColor colorWithRed:.08 green:.09 blue:.11 alpha:1].CGColor
  ];
  self.heroGradient.startPoint = CGPointMake(0, 0);
  self.heroGradient.endPoint = CGPointMake(1, 1);
  [self.heroCard.layer insertSublayer:self.heroGradient atIndex:0];
  [self.scroller addSubview:self.heroCard];
  UIStackView *hero = [self cardStack:self.heroCard];

  UIImage *brand = [UIImage imageWithContentsOfFile:
      [NSBundle.mainBundle pathForResource:@"FactoriOS-icon" ofType:@"png"]];
  UIImageView *artwork = [[UIImageView alloc] initWithImage:brand];
  artwork.contentMode = UIViewContentModeScaleAspectFit;
  artwork.clipsToBounds = YES;
  [artwork.heightAnchor constraintEqualToConstant:138].active = YES;
  [hero addArrangedSubview:artwork];

  UILabel *title = [self label:@"FACTORIO" size:35 weight:UIFontWeightHeavy];
  [hero addArrangedSubview:title];
  UILabel *subtitle = [self label:@"Desktop game · native ARM64 compatibility"
                             size:14 weight:UIFontWeightRegular];
  subtitle.textColor = [UIColor colorWithWhite:.80 alpha:1];
  [hero addArrangedSubview:subtitle];

  self.dataStatus = [self label:@"" size:14 weight:UIFontWeightMedium];
  [hero addArrangedSubview:self.dataStatus];

  self.playButton = [self button:@"▶  Play" action:@selector(play) primary:YES];
  [hero addArrangedSubview:self.playButton];

  self.importButton = [self button:@"Import FactorioData"
                             action:@selector(importData) primary:NO];
  [hero addArrangedSubview:self.importButton];

  UILabel *footnote = [self label:@"Your game files and saves remain on this device."
                             size:12 weight:UIFontWeightRegular];
  footnote.textColor = [UIColor colorWithWhite:.67 alpha:1];
  [hero addArrangedSubview:footnote];

  self.settingsCard = [self card];
  [self.scroller addSubview:self.settingsCard];
  UIStackView *settings = [self cardStack:self.settingsCard];
  [settings addArrangedSubview:[self label:@"Settings" size:25 weight:UIFontWeightBold]];
  UILabel *description = [self label:@"Adjust your preferences before playing."
                                  size:13 weight:UIFontWeightRegular];
  description.textColor = [UIColor colorWithWhite:.75 alpha:1];
  [settings addArrangedSubview:description];

  UILabel *graphicsLabel = [self label:@"Graphics preset" size:15
                                     weight:UIFontWeightSemibold];
  [settings addArrangedSubview:graphicsLabel];
  self.graphicsControl = [[UISegmentedControl alloc]
      initWithItems:@[@"Low", @"Balanced", @"Quality"]];
  self.graphicsControl.selectedSegmentTintColor =
      [UIColor colorWithRed:.94 green:.58 blue:.36 alpha:1];
  [self.graphicsControl addTarget:self action:@selector(changeGraphics:)
                  forControlEvents:UIControlEventValueChanged];
  [self.graphicsControl.heightAnchor constraintEqualToConstant:40].active = YES;
  [settings addArrangedSubview:self.graphicsControl];

  UILabel *controllerLabel = [self label:@"Controller input" size:15
                                       weight:UIFontWeightSemibold];
  [settings addArrangedSubview:controllerLabel];
  self.controllerControl = [[UISegmentedControl alloc]
      initWithItems:@[@"Native", @"Keyboard / Mouse"]];
  self.controllerControl.selectedSegmentTintColor =
      [UIColor colorWithRed:.94 green:.58 blue:.36 alpha:1];
  [self.controllerControl addTarget:self action:@selector(changeController:)
                    forControlEvents:UIControlEventValueChanged];
  [self.controllerControl.heightAnchor constraintEqualToConstant:40].active = YES;
  [settings addArrangedSubview:self.controllerControl];

  [settings addArrangedSubview:[self button:@"Choose Save Sync Folder"
                                      action:@selector(chooseSaveFolder) primary:NO]];
  self.syncStatus = [self label:@"" size:13 weight:UIFontWeightRegular];
  self.syncStatus.textColor = [UIColor colorWithWhite:.73 alpha:1];
  [settings addArrangedSubview:self.syncStatus];
  [settings addArrangedSubview:[self button:@"Share Startup Log"
                                      action:@selector(shareLog) primary:NO]];
  UILabel *hint = [self label:@"In game: tap ⌨ to type, hold ⌨ for options."
                               size:12 weight:UIFontWeightRegular];
  hint.textColor = [UIColor colorWithWhite:.65 alpha:1];
  [settings addArrangedSubview:hint];

  [[NSNotificationCenter defaultCenter] addObserver:self
                                           selector:@selector(stopped:)
                                               name:@"FactorioStopped"
                                             object:nil];

  // Only automatically import bundled game files if the IPA really contains
  // them. Private --no-data IPAs use the user's existing Documents folder.
  NSString *bundleData = [NSBundle.mainBundle.bundlePath
      stringByAppendingPathComponent:@"FactorioData/base/info.json"];
  if (![FactorioLoader hasValidGameData] &&
      [NSFileManager.defaultManager fileExistsAtPath:bundleData]) {
    __weak typeof(self) weak = self;
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
      NSError *error = nil;
      BOOL ok = [FactorioLoader importSavedGameDataWithProgress:^(double f) {}
                                                       error:&error];
      dispatch_async(dispatch_get_main_queue(), ^{
        typeof(self) strong = weak;
        if (!strong) return;
        [strong refreshState];
        if (!ok) [strong alert:error.localizedDescription
                              ?: @"Could not import packaged FactorioData."];
      });
    });
  }
}

- (void)viewWillAppear:(BOOL)animated {
  [super viewWillAppear:animated];
  self.navigationController.navigationBarHidden = YES;
  [self refreshState];
  [self.view setNeedsLayout];
}

- (void)viewDidLayoutSubviews {
  [super viewDidLayoutSubviews];
  UIEdgeInsets insets = self.view.safeAreaInsets;
  CGRect usable = UIEdgeInsetsInsetRect(self.view.bounds, insets);
  self.scroller.frame = usable;
  CGFloat margin = 18, gap = 16;
  CGFloat width = MAX(1, CGRectGetWidth(usable) - 2 * margin);
  BOOL sideBySide = CGRectGetWidth(usable) >= 730 &&
                    CGRectGetWidth(usable) > CGRectGetHeight(usable);
  if (sideBySide) {
    CGFloat heroWidth = (width - gap) * .56;
    CGFloat h = MAX(530, CGRectGetHeight(usable) - 2 * margin);
    self.heroCard.frame = CGRectMake(margin, margin, heroWidth, h);
    self.settingsCard.frame = CGRectMake(margin + heroWidth + gap, margin,
                                        width - heroWidth - gap, h);
    self.scroller.contentSize = CGSizeMake(CGRectGetWidth(usable), h + 2 * margin);
  } else {
    CGFloat heroHeight = 510, settingsHeight = 520;
    self.heroCard.frame = CGRectMake(margin, margin, width, heroHeight);
    self.settingsCard.frame = CGRectMake(margin, margin + heroHeight + gap,
                                        width, settingsHeight);
    self.scroller.contentSize =
        CGSizeMake(CGRectGetWidth(usable),
                   2 * margin + heroHeight + gap + settingsHeight);
  }
  self.heroGradient.frame = self.heroCard.bounds;
}

- (void)refreshState {
  BOOL ready = [FactorioLoader hasValidGameData];
  NSString *version = [FactorioLoader installedGameVersion] ?: @"unknown";
  self.dataStatus.text = ready
      ? [NSString stringWithFormat:@"●  Game data ready · %@", version]
      : @"○  Game data missing";
  self.dataStatus.textColor = ready
      ? [UIColor colorWithRed:.58 green:.91 blue:.71 alpha:1]
      : [UIColor colorWithRed:1 green:.75 blue:.43 alpha:1];
  self.importButton.hidden = ready;
  self.playButton.enabled = ready;
  self.playButton.alpha = ready ? 1 : .50;
  NSArray<NSString *> *graphics = @[@"low", @"medium", @"high"];
  NSUInteger index = [graphics indexOfObject:FactorioLoader.graphicsPreset ?: @"medium"];
  self.graphicsControl.selectedSegmentIndex =
      index == NSNotFound ? 1 : (NSInteger)index;
  self.controllerControl.selectedSegmentIndex =
      [NSUserDefaults.standardUserDefaults boolForKey:@"FactorioNativeController"] ? 0 : 1;
  self.syncStatus.text = [FactorioSaveSync hasFolder]
      ? @"Save sync folder connected" : @"Save sync not configured";
}

- (void)changeGraphics:(UISegmentedControl *)control {
  NSArray *graphics = @[@"low", @"medium", @"high"];
  NSInteger selected = control.selectedSegmentIndex;
  if (selected >= 0 && selected < (NSInteger)graphics.count)
    [NSUserDefaults.standardUserDefaults
        setObject:graphics[selected] forKey:@"FactorioGraphicsPreset"];
}

- (void)changeController:(UISegmentedControl *)control {
  [NSUserDefaults.standardUserDefaults
      setBool:control.selectedSegmentIndex == 0 forKey:@"FactorioNativeController"];
}

- (void)importData {
  self.selectingSaveFolder = NO;
  UIDocumentPickerViewController *picker = [[UIDocumentPickerViewController alloc]
      initForOpeningContentTypes:@[UTTypeFolder] asCopy:NO];
  picker.delegate = self;
  [self presentViewController:picker animated:YES completion:nil];
}

- (void)chooseSaveFolder {
  self.selectingSaveFolder = YES;
  UIDocumentPickerViewController *picker = [[UIDocumentPickerViewController alloc]
      initForOpeningContentTypes:@[UTTypeFolder] asCopy:NO];
  picker.delegate = self;
  [self presentViewController:picker animated:YES completion:nil];
}

- (void)documentPicker:(UIDocumentPickerViewController *)picker
    didPickDocumentsAtURLs:(NSArray<NSURL *> *)urls {
  if (!urls.count) return;
  NSError *error = nil;
  if (self.selectingSaveFolder) {
    BOOL ok = [FactorioSaveSync saveFolder:urls[0] error:&error];
    if (ok) ok = [FactorioSaveSync synchronize:&error];
    [self refreshState];
    [self alert:ok ? @"Save folder selected and synchronized."
                   : (error.localizedDescription ?: @"Could not configure save sync.")];
  } else {
    BOOL ok = [FactorioLoader selectGameDataFromURL:urls[0]
                                           progress:^(double fraction) {}
                                              error:&error];
    [self refreshState];
    [self alert:ok ? @"FactorioData imported."
                   : (error.localizedDescription ?: @"Import failed.")];
  }
}

- (void)play {
  if (![FactorioLoader hasValidGameData]) {
    [self refreshState];
    [self alert:@"Import matching FactorioData before launching."];
    return;
  }
  NSError *error = nil;
  if ([FactorioSaveSync hasFolder] && ![FactorioSaveSync synchronize:&error]) {
    [self alert:error.localizedDescription ?: @"Save sync failed."];
    return;
  }
  [self.navigationController pushViewController:[FactorioGameController new] animated:YES];
}

- (void)shareLog {
  NSURL *url = FactorioLoader.startupLogURL;
  if (!url) {
    [self alert:@"Startup log is not available."];
    return;
  }
  UIActivityViewController *controller = [[UIActivityViewController alloc]
      initWithActivityItems:@[url] applicationActivities:nil];
  controller.popoverPresentationController.sourceView = self.view;
  controller.popoverPresentationController.sourceRect =
      CGRectMake(CGRectGetMidX(self.view.bounds), CGRectGetMidY(self.view.bounds), 1, 1);
  [self presentViewController:controller animated:YES completion:nil];
}

- (void)stopped:(NSNotification *)notification {
  [self alert:notification.userInfo[@"message"] ?: @"Factorio stopped."];
}

- (void)alert:(NSString *)message {
  UIAlertController *alert = [UIAlertController
      alertControllerWithTitle:@"FactoriOS"
                      message:message
               preferredStyle:UIAlertControllerStyleAlert];
  [alert addAction:[UIAlertAction actionWithTitle:@"OK"
                                      style:UIAlertActionStyleDefault handler:nil]];
  [self presentViewController:alert animated:YES completion:nil];
}

- (void)dealloc {
  [[NSNotificationCenter defaultCenter] removeObserver:self];
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
    self.touchPad.enabled = [GCController controllers].count == 0;
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
  self.touchPad.enabled = [GCController controllers].count == 0;
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
  // The unfolded Duo presents two broad panels under one UIWindowScene.
  // Draw the game full bleed across the scene in landscape; keep floating
  // controls within the actual (potentially asymmetric) UIKit safe area.
  // Other devices keep the conventional safe-area game viewport.
  BOOL unfoldedDuo =
      UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPhone &&
      MIN(CGRectGetWidth(bounds), CGRectGetHeight(bounds)) >= 600;
  BOOL duoPortrait = unfoldedDuo &&
      CGRectGetHeight(bounds) > CGRectGetWidth(bounds) * 1.15;
  CGRect gameRect = unfoldedDuo ? bounds : usable;
  CGRect controlsRect = usable;
  if (duoPortrait) {
    CGFloat hinge = CGRectGetMidY(bounds);
    gameRect = CGRectMake(0, 0, CGRectGetWidth(bounds), MAX(1, hinge - 3));
    CGFloat controlsTop = hinge + 3;
    controlsRect = CGRectMake(CGRectGetMinX(usable), controlsTop,
                              CGRectGetWidth(usable),
                              MAX(1, CGRectGetMaxY(usable) - controlsTop));
  }
  // No blanket phone padding. Metal and SDL must use the same current
  // gameView bounds, including changes caused by unfolding or rotation.
  self.gameView.frame = CGRectIntegral(gameRect);
  self.touchPad.frame = CGRectIntegral(controlsRect);
  [self.gameView setNeedsLayout];
  [self.touchPad setNeedsLayout];

  UIWindowScene *scene = self.view.window.windowScene;
  CAMetalLayer *metal = (CAMetalLayer *)self.gameView.layer;
  [FactorioLoader logMessage:[NSString stringWithFormat:
      @"Duo geometry scene=%@ window=%@ screen=%@ safe=%@ game=%@ touch=%@ "
       @"drawable=%@ orientation=%ld unfolded=%d duoPortrait=%d",
      NSStringFromCGRect(scene.coordinateSpace.bounds),
      NSStringFromCGRect(self.view.window.bounds),
      NSStringFromCGRect(scene.screen.bounds), NSStringFromUIEdgeInsets(safe),
      NSStringFromCGRect(self.gameView.frame),
      NSStringFromCGRect(self.touchPad.frame),
      NSStringFromCGSize(metal.drawableSize),
      (long)scene.interfaceOrientation, unfoldedDuo, duoPortrait]];
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
