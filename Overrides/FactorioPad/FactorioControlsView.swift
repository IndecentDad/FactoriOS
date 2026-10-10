import SwiftUI

struct FactorioControlsView: View {
    var onClose: () -> Void
    var onSaves: () -> Void
    var logURL: URL? = nil

    var body: some View {
        VStack(spacing: 24) {
            Text("FactoriOS").font(.largeTitle.bold())
            Text("Settings").font(.headline).foregroundStyle(.secondary)
            Button("Save Sync", action: onSaves)
                .buttonStyle(.borderedProminent)
                .tint(.orange)
                .controlSize(.large)
                .focusable(false)
            Link("GitHub Repository", destination: URL(string: "https://github.com/IndecentDad/FactoriOS")!)
                .buttonStyle(.bordered)
                .controlSize(.large)
                .focusable(false)
            Button("Back to game", action: onClose)
                .buttonStyle(.bordered)
                .controlSize(.large)
                .focusable(false)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(white: 0.06).ignoresSafeArea())
        .preferredColorScheme(.dark)
        .accessibilityAddTraits(.isModal)
    }
}
