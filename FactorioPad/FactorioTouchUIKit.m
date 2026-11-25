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
@property(nonatomic, strong) UIButton *toggle;
@property(nonatomic, strong) UIButton *exitButton;
@property(nonatomic) BOOL showing;
@end
@implementation FactorioTouchUIKit
- (instancetype)initWithFrame:(CGRect)f {
  if ((self = [super initWithFrame:f])) {
    self.backgroundColor = UIColor.clearColor;
    self.buttons = [NSMutableArray array];
    self.showing = YES;
    self.pad = [[FactorioMovePad alloc] initWithFrame:CGRectZero];
    [self addSubview:self.pad];
    NSArray *titles = @[
      @"Build", @"Mine", @"Turn", @"Pick", @"Items", @"Map", @"Research",
      @"Zoom +", @"Zoom −", @"Keyboard"
    ];
    for (NSUInteger i = 0; i < titles.count; i++) {
      UIButton *b = [UIButton buttonWithType:UIButtonTypeSystem];
      [b setTitle:titles[i] forState:UIControlStateNormal];
      b.titleLabel.font = [UIFont systemFontOfSize:12
                                            weight:UIFontWeightSemibold];
      b.backgroundColor = [UIColor colorWithWhite:.08 alpha:.82];
      [b setTitleColor:[UIColor colorWithRed:.96 green:.73 blue:.39 alpha:1]
              forState:UIControlStateNormal];
      b.layer.cornerRadius = 12;
      b.layer.borderWidth = 1;
      b.layer.borderColor = [UIColor colorWithWhite:.6 alpha:.35].CGColor;
      b.tag = i;
      [b addTarget:self
                    action:@selector(down:)
          forControlEvents:UIControlEventTouchDown];
      [b addTarget:self
                    action:@selector(up:)
          forControlEvents:UIControlEventTouchUpInside |
                           UIControlEventTouchUpOutside |
                           UIControlEventTouchCancel];
      [self addSubview:b];
      [self.buttons addObject:b];
    }
    self.exitButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self.exitButton setTitle:@"Home" forState:UIControlStateNormal];
    self.exitButton.backgroundColor = [UIColor colorWithWhite:.08 alpha:.75];
    self.exitButton.layer.cornerRadius = 10;
    [self.exitButton addTarget:self
                        action:@selector(exitGame)
              forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:self.exitButton];
    self.toggle = [UIButton buttonWithType:UIButtonTypeSystem];
    [self.toggle setTitle:@"Hide pad" forState:UIControlStateNormal];
    self.toggle.titleLabel.font = [UIFont systemFontOfSize:11
                                                    weight:UIFontWeightMedium];
    self.toggle.backgroundColor = [UIColor colorWithWhite:.08 alpha:.72];
    self.toggle.layer.cornerRadius = 10;
    [self.toggle addTarget:self
                    action:@selector(togglePad)
          forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:self.toggle];
  }
  return self;
}
- (BOOL)pointInside:(CGPoint)p withEvent:(UIEvent *)e {
  if (!self.enabled)
    return NO;
  if (CGRectContainsPoint(self.pad.frame, p) && self.showing)
    return YES;
  if (CGRectContainsPoint(self.toggle.frame, p) ||
      CGRectContainsPoint(self.exitButton.frame, p))
    return YES;
  for (UIButton *b in self.buttons)
    if (!b.hidden && CGRectContainsPoint(b.frame, p))
      return YES;
  return NO;
}
- (void)layoutSubviews {
  [super layoutSubviews];
  CGFloat d = MIN(150, MAX(112, self.bounds.size.height * .25));
  self.pad.frame = CGRectMake(20, self.bounds.size.height - d - 18, d, d);
  self.pad.hidden = !self.showing;
  CGFloat w = 56, h = 46, g = 7;
  CGFloat right = self.bounds.size.width - 20;
  for (NSUInteger i = 0; i < self.buttons.count; i++) {
    UIButton *b = self.buttons[i];
    NSUInteger col = i % 2, row = i / 2;
    b.frame =
        CGRectMake(right - 2 * w - g + col * (w + g),
                   self.bounds.size.height - 18 - (row + 1) * (h + g), w, h);
    b.hidden = !self.showing;
  }
  self.toggle.frame = CGRectMake(right - 100, 12, 100, 34);
  self.exitButton.frame = CGRectMake(20, 12, 72, 34);
  [self.toggle setTitle:self.showing ? @"Hide pad" : @"Show pad"
               forState:UIControlStateNormal];
}
- (void)exitGame {
  if (self.onExit)
    self.onExit();
}
- (void)togglePad {
  self.showing = !self.showing;
  self.pad.hidden = !self.showing;
  for (UIButton *b in self.buttons)
    b.hidden = !self.showing;
  [self setNeedsLayout];
}
- (NSArray<NSNumber *> *)keyForButton:(NSInteger)i {
  switch (i) {
  case 2:
    return @[ @21, @114 ];
  case 3:
    return @[ @20, @113 ];
  case 4:
    return @[ @8, @101 ];
  case 5:
    return @[ @16, @109 ];
  case 6:
    return @[ @23, @116 ];
  default:
    return @[];
  }
}
- (void)setEnabled:(BOOL)e {
  _enabled = YES;
  self.hidden = NO;
  self.showing = e;
  self.pad.hidden = !e;
  for (UIButton *b in self.buttons)
    b.hidden = !e;
  self.toggle.hidden = NO;
}
- (void)down:(UIButton *)b {
  if (b.tag == 0 || b.tag == 1) {
    CGPoint p = FactorioControllerBridgeGetCursorPosition();
    FactorioTouchMouseButton(b.tag == 0 ? 1 : 3, true, (int)p.x, (int)p.y);
    return;
  }
  if (b.tag == 7) {
    FactorioMouseWheel(0, 1);
    return;
  }
  if (b.tag == 8) {
    FactorioMouseWheel(0, -1);
    return;
  }
  if (b.tag == 9) {
    UIAlertController *a = [UIAlertController
        alertControllerWithTitle:@"Keyboard"
                         message:nil
                  preferredStyle:UIAlertControllerStyleAlert];
    [a addTextFieldWithConfigurationHandler:^(UITextField *t) {
      t.placeholder = @"Type text for Factorio";
    }];
    [a addAction:[UIAlertAction actionWithTitle:@"Send"
                                          style:UIAlertActionStyleDefault
                                        handler:^(UIAlertAction *x) {
                                          FactorioKeyboardInsertText(
                                              a.textFields.firstObject.text
                                                  ?: @"");
                                        }]];
    [a addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                          style:UIAlertActionStyleCancel
                                        handler:nil]];
    [self.window.rootViewController presentViewController:a
                                                 animated:YES
                                               completion:nil];
    return;
  }
  NSArray<NSNumber *> *k = [self keyForButton:b.tag];
  if (k.count == 2)
    FactorioKeyboardTouchKeyDown(k[0].intValue, k[1].intValue);
}
- (void)up:(UIButton *)b {
  if (b.tag == 0 || b.tag == 1) {
    CGPoint p = FactorioControllerBridgeGetCursorPosition();
    FactorioTouchMouseButton(b.tag == 0 ? 1 : 3, false, (int)p.x, (int)p.y);
    return;
  }
  NSArray<NSNumber *> *k = [self keyForButton:b.tag];
  if (k.count == 2)
    FactorioKeyboardTouchKeyUp(k[0].intValue, k[1].intValue);
}
@end
