#import <UIKit/UIKit.h>
@interface FactorioTouchUIKit : UIView
@property(nonatomic) BOOL enabled;
@property(nonatomic, copy) dispatch_block_t onExit;
@end
