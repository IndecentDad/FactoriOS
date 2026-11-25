#import <Foundation/Foundation.h>
NS_ASSUME_NONNULL_BEGIN
@interface FactorioSaveSync : NSObject
+ (BOOL)hasFolder;
+ (BOOL)saveFolder:(NSURL *)folder error:(NSError **)error;
+ (BOOL)synchronize:(NSError **)error;
@end
NS_ASSUME_NONNULL_END
