#import "FactorioTouchUIKit.h"
#import "FactorioControllerBridge.h"
#import "FactorioKeyboardBridge.h"

@interface FactorioMovePad : UIView
@property(nonatomic, copy) void (^movement)(NSSet<NSNumber *> *keys);
@property(nonatomic, strong) NSMutableSet<NSNumber *> *held;
@end
@implementation FactorioMovePad
- (instancetype)initWithFrame:(CGRect)f {
  if ((self = [super initWithFrame:f])) {
    self.held = [NSMutableSet set];
    self.multipleTouchEnabled = NO;
    self.backgroundColor = [UIColor colorWithWhite:0.05 alpha:0.45];
    self.layer.borderColor =
        [UIColor colorWithRed:.96 green:.70 blue:.30 alpha:.9].CGColor;
    self.layer.borderWidth = 2;
    self.layer.cornerRadius = f.size.width / 2;
  }
  return self;
}
- (void)update:(CGPoint)p {
  CGFloat dx = p.x - self.bounds.size.width / 2,
          dy = p.y - self.bounds.size.height / 2, r = hypot(dx, dy);
  NSMutableSet *next = [NSMutableSet set];
  if (r > self.bounds.size.width * .14) {
    CGFloat t = r * .38;
    if (dx < -t)
      [next addObject:@4];
    if (dx > t)
      [next addObject:@7];
    if (dy < -t)
      [next addObject:@26];
    if (dy > t)
      [next addObject:@22];
  }
  for (NSNumber *n in self.held)
    if (![next containsObject:n])
      FactorioKeyboardTouchKeyUp(n.intValue, 0);
  for (NSNumber *n in next)
    if (![self.held containsObject:n])
      FactorioKeyboardTouchKeyDown(n.intValue, 0);
  self.held = next;
  if (self.movement)
    self.movement(next);
  [self setNeedsDisplay];
}
- (void)touchesBegan:(NSSet<UITouch *> *)t withEvent:(UIEvent *)e {
  [self update:[[t anyObject] locationInView:self]];
}
- (void)touchesMoved:(NSSet<UITouch *> *)t withEvent:(UIEvent *)e {
  [self update:[[t anyObject] locationInView:self]];
}
- (void)touchesEnded:(NSSet<UITouch *> *)t withEvent:(UIEvent *)e {
  [self update:CGPointMake(self.bounds.size.width / 2,
                           self.bounds.size.height / 2)];
}
- (void)touchesCancelled:(NSSet<UITouch *> *)t withEvent:(UIEvent *)e {
  [self touchesEnded:t withEvent:e];
}
- (void)drawRect:(CGRect)r {
  [[UIColor colorWithWhite:.8 alpha:.65] setStroke];
  UIBezierPath *p = [UIBezierPath
      bezierPathWithOvalInRect:CGRectInset(self.bounds,
                                           self.bounds.size.width * .22,
                                           self.bounds.size.height * .22)];
  p.lineWidth = 2;
  [p stroke];
}
@end


@interface FactorioTouchUIKit ()
@property(nonatomic, strong) FactorioMovePad *pad;
@property(nonatomic, strong) NSMutableArray<UIButton *> *buttons;
@property(nonatomic, strong) UIButton *keyboardButton;
@property(nonatomic) BOOL showing;
@end

@implementation FactorioTouchUIKit

- (instancetype)initWithFrame:(CGRect)frame {
  if ((self = [super initWithFrame:frame])) {
    self.backgroundColor = UIColor.clearColor;
    self.buttons = [NSMutableArray array];
    self.showing = YES;
    _enabled = YES;
    self.pad = [[FactorioMovePad alloc] initWithFrame:CGRectZero];
    [self addSubview:self.pad];

    NSArray<NSString *> *titles = @[
      @"Build", @"Mine", @"Turn", @"Pick", @"Items", @"Map", @"Research",
      @"Zoom +", @"Zoom −"
    ];
    for (NSUInteger i = 0; i < titles.count; i++) {
      UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
      [button setTitle:titles[i] forState:UIControlStateNormal];
      button.titleLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightSemibold];
      button.backgroundColor = [UIColor colorWithWhite:.07 alpha:.80];
      [button setTitleColor:[UIColor colorWithRed:.96 green:.73 blue:.39 alpha:1]
                   forState:UIControlStateNormal];
      button.layer.cornerRadius = 12;
      button.layer.borderWidth = 1;
      button.layer.borderColor = [UIColor colorWithWhite:.6 alpha:.35].CGColor;
      button.tag = i;
      [button addTarget:self action:@selector(down:)
           forControlEvents:UIControlEventTouchDown];
      [button addTarget:self action:@selector(up:)
           forControlEvents:UIControlEventTouchUpInside |
                            UIControlEventTouchUpOutside |
                            UIControlEventTouchCancel];
      [self addSubview:button];
      [self.buttons addObject:button];
    }

    // Even with a connected controller, the keyboard remains reachable.
    // The old top-screen Home and Show Pad buttons are intentionally gone.
    self.keyboardButton = [UIButton buttonWithType:UIButtonTypeSystem];
    UIImage *icon = [UIImage systemImageNamed:@"keyboard"];
    [self.keyboardButton setImage:icon forState:UIControlStateNormal];
    if (!icon) [self.keyboardButton setTitle:@"⌨" forState:UIControlStateNormal];
    self.keyboardButton.tintColor = UIColor.whiteColor;
    self.keyboardButton.backgroundColor = [UIColor colorWithWhite:.04 alpha:.76];
    self.keyboardButton.layer.cornerRadius = 11;
    self.keyboardButton.layer.borderWidth = .5;
    self.keyboardButton.layer.borderColor = [UIColor colorWithWhite:.7 alpha:.45].CGColor;
    self.keyboardButton.accessibilityLabel = @"Keyboard";
    self.keyboardButton.accessibilityHint = @"Tap to type, hold for game options";
    [self.keyboardButton addTarget:self action:@selector(openKeyboard)
                   forControlEvents:UIControlEventTouchUpInside];
    UILongPressGestureRecognizer *hold =
        [[UILongPressGestureRecognizer alloc] initWithTarget:self
                                                     action:@selector(keyboardLongPress:)];
    hold.minimumPressDuration = .48;
    [self.keyboardButton addGestureRecognizer:hold];
    [self addSubview:self.keyboardButton];
  }
  return self;
}

- (BOOL)pointInside:(CGPoint)point withEvent:(UIEvent *)event {
  if (CGRectContainsPoint(self.keyboardButton.frame, point)) return YES;
  if (!self.showing) return NO;
  if (CGRectContainsPoint(self.pad.frame, point)) return YES;
  for (UIButton *button in self.buttons) {
    if (!button.hidden && CGRectContainsPoint(button.frame, point)) return YES;
  }
  return NO;
}

- (void)layoutSubviews {
  [super layoutSubviews];
  CGFloat height = self.bounds.size.height;
  CGFloat width = self.bounds.size.width;
  CGFloat diameter = MIN(146, MAX(100, height * .30));
  self.pad.frame = CGRectMake(18, height - diameter - 16, diameter, diameter);
  self.pad.hidden = !self.showing;
  CGFloat w = 54, h = 43, gap = 7;
  CGFloat right = width - 18;
  for (NSUInteger i = 0; i < self.buttons.count; i++) {
    NSUInteger col = i % 2, row = i / 2;
    UIButton *button = self.buttons[i];
    // Avoid the persistent keyboard button at the bottom-right.
    button.frame = CGRectMake(right - 2 * w - gap + col * (w + gap),
                              height - 70 - (row + 1) * (h + gap), w, h);
    button.hidden = !self.showing;
  }
  self.keyboardButton.frame = CGRectMake(right - 46, height - 58, 46, 46);
  [self bringSubviewToFront:self.keyboardButton];
}

- (void)setEnabled:(BOOL)enabled {
  // enabled controls the optional touch pad, never keyboard availability.
  _enabled = YES;
  self.hidden = NO;
  self.showing = enabled;
  self.pad.hidden = !enabled;
  for (UIButton *button in self.buttons) button.hidden = !enabled;
  self.keyboardButton.hidden = NO;
  [self setNeedsLayout];
}

- (void)keyboardLongPress:(UILongPressGestureRecognizer *)recognizer {
  if (recognizer.state != UIGestureRecognizerStateBegan) return;
  UIAlertController *menu = [UIAlertController
      alertControllerWithTitle:@"FactoriOS"
                      message:nil
               preferredStyle:UIAlertControllerStyleActionSheet];
  __weak typeof(self) weak = self;
  [menu addAction:[UIAlertAction actionWithTitle:
       self.showing ? @"Hide touch controls" : @"Show touch controls"
       style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
         typeof(self) strong = weak;
         if (!strong) return;
         strong.showing = !strong.showing;
         strong.pad.hidden = !strong.showing;
         for (UIButton *button in strong.buttons) button.hidden = !strong.showing;
         [strong setNeedsLayout];
       }]];
  [menu addAction:[UIAlertAction actionWithTitle:@"Return to FactoriOS"
       style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
         typeof(self) strong = weak;
         if (strong.onExit) strong.onExit();
       }]];
  [menu addAction:[UIAlertAction actionWithTitle:@"Cancel"
       style:UIAlertActionStyleCancel handler:nil]];
  menu.popoverPresentationController.sourceView = self.keyboardButton;
  menu.popoverPresentationController.sourceRect = self.keyboardButton.bounds;
  [self.window.rootViewController presentViewController:menu
                                              animated:YES completion:nil];
}

- (void)openKeyboard {
  UIAlertController *alert = [UIAlertController
      alertControllerWithTitle:@"Keyboard"
                      message:nil
               preferredStyle:UIAlertControllerStyleAlert];
  [alert addTextFieldWithConfigurationHandler:^(UITextField *field) {
    field.placeholder = @"Type for Factorio";
    field.autocorrectionType = UITextAutocorrectionTypeNo;
    field.autocapitalizationType = UITextAutocapitalizationTypeNone;
  }];
  [alert addAction:[UIAlertAction actionWithTitle:@"Send"
       style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
         NSString *value = alert.textFields.firstObject.text ?: @"";
         if (value.length) FactorioKeyboardInsertText(value);
       }]];
  [alert addAction:[UIAlertAction actionWithTitle:@"Cancel"
       style:UIAlertActionStyleCancel handler:nil]];
  [self.window.rootViewController presentViewController:alert
                                              animated:YES completion:nil];
}

- (NSArray<NSNumber *> *)keyForButton:(NSInteger)index {
  switch (index) {
    case 2: return @[@21, @114];
    case 3: return @[@20, @113];
    case 4: return @[@8, @101];
    case 5: return @[@16, @109];
    case 6: return @[@23, @116];
    default: return @[];
  }
}

- (void)down:(UIButton *)button {
  if (button.tag == 0 || button.tag == 1) {
    CGPoint p = FactorioControllerBridgeGetCursorPosition();
    FactorioTouchMouseButton(button.tag == 0 ? 1 : 3, true, (int)p.x, (int)p.y);
    return;
  }
  if (button.tag == 7 || button.tag == 8) {
    FactorioMouseWheel(0, button.tag == 7 ? 1 : -1);
    return;
  }
  NSArray<NSNumber *> *keys = [self keyForButton:button.tag];
  if (keys.count == 2) FactorioKeyboardTouchKeyDown(keys[0].intValue, keys[1].intValue);
}

- (void)up:(UIButton *)button {
  if (button.tag == 0 || button.tag == 1) {
    CGPoint p = FactorioControllerBridgeGetCursorPosition();
    FactorioTouchMouseButton(button.tag == 0 ? 1 : 3, false, (int)p.x, (int)p.y);
    return;
  }
  NSArray<NSNumber *> *keys = [self keyForButton:button.tag];
  if (keys.count == 2) FactorioKeyboardTouchKeyUp(keys[0].intValue, keys[1].intValue);
}
@end
