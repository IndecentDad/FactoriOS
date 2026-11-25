#import "FactorioCursorView.h"
@implementation FactorioCursorView
- (instancetype)initWithFrame:(CGRect)frame {
  if ((self = [super initWithFrame:frame])) {
    self.userInteractionEnabled = NO;
    self.accessibilityElementsHidden = YES;
    CAShapeLayer *pointer = [CAShapeLayer layer];
    UIBezierPath *path = [UIBezierPath bezierPath];
    [path moveToPoint:CGPointMake(1.5, 1.5)];
    for (NSValue *v in @[
           [NSValue valueWithCGPoint:CGPointMake(16.5, 9.5)],
           [NSValue valueWithCGPoint:CGPointMake(10.5, 12)],
           [NSValue valueWithCGPoint:CGPointMake(13, 18.5)],
           [NSValue valueWithCGPoint:CGPointMake(9.5, 20)],
           [NSValue valueWithCGPoint:CGPointMake(6.5, 13.5)],
           [NSValue valueWithCGPoint:CGPointMake(2.5, 16)]
         ])
      [path addLineToPoint:v.CGPointValue];
    [path closePath];
    pointer.path = path.CGPath;
    pointer.fillColor =
        [UIColor colorWithRed:.93 green:.59 blue:.14 alpha:1].CGColor;
    pointer.strokeColor =
        [UIColor colorWithRed:.18 green:.11 blue:.05 alpha:1].CGColor;
    pointer.lineWidth = 2.3;
    pointer.lineJoin = kCALineJoinRound;
    pointer.lineCap = kCALineCapRound;
    pointer.shadowColor = UIColor.blackColor.CGColor;
    pointer.shadowOpacity = .55;
    pointer.shadowRadius = 1.2;
    pointer.shadowOffset = CGSizeMake(1, 1);
    [self.layer addSublayer:pointer];
    CAShapeLayer *highlight = [CAShapeLayer layer];
    UIBezierPath *highlightPath = [UIBezierPath bezierPath];
    [highlightPath moveToPoint:CGPointMake(4, 4)];
    [highlightPath addLineToPoint:CGPointMake(12, 8.5)];
    highlight.path = highlightPath.CGPath;
    highlight.fillColor = UIColor.clearColor.CGColor;
    highlight.strokeColor =
        [UIColor colorWithRed:1 green:.8 blue:.35 alpha:.75].CGColor;
    highlight.lineWidth = 1;
    highlight.lineCap = kCALineCapRound;
    [self.layer addSublayer:highlight];
  }
  return self;
}
@end
