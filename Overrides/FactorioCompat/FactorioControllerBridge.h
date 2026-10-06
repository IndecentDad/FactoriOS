#pragma once

#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>

#ifdef __cplusplus
extern "C" {
#endif

void FactorioControllerBridgeStart(void);

void FactorioControllerBridgeSetActive(
    BOOL active
);

void FactorioControllerBridgeSetViewportSize(
    CGFloat width,
    CGFloat height
);

void FactorioControllerBridgeSetCursorPosition(
    CGFloat x,
    CGFloat y
);

CGPoint FactorioControllerBridgeGetCursorPosition(void);

#ifdef __cplusplus
}
#endif
