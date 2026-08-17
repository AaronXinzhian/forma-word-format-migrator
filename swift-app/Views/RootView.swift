import AppKit
import SwiftUI

struct WordFormatLibraryView: View {
    @StateObject private var model = WordFormatLibraryModel()

    var body: some View {
        ZStack {
            Palette.paper.ignoresSafeArea()
            VStack(spacing: 0) {
                AppHeader(model: model)
                StepStrip(model: model)
                Divider().overlay(Palette.line)

                HStack(spacing: 0) {
                    LibrarySidebar(model: model)
                        .frame(width: 310)
                    Divider().overlay(Palette.line)
                    Group {
                        switch model.currentStep {
                        case 1: ImportStepView(model: model)
                        case 2: FormatPreviewStepView(model: model)
                        default: ApplyStepView(model: model)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }

                if let toast = model.toastMessage {
                    ToastBar(message: toast) { model.toastMessage = nil }
                }
            }

            if model.isBusy {
                BusyOverlay(message: model.busyMessage)
            }
        }
        .frame(minWidth: 1080, minHeight: 720)
        .foregroundStyle(Palette.ink)
        .alert(UIStrings.App.errorTitle, isPresented: $model.isShowingError) {
            Button(UIStrings.App.errorConfirm) { model.isShowingError = false }
        } message: {
            Text(model.errorMessage)
        }
    }
}

struct AppHeader: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Palette.green)
                Image(systemName: "textformat.alt")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(.white)
            }
            .frame(width: 42, height: 42)

            VStack(alignment: .leading, spacing: 2) {
                Text(UIStrings.App.brand)
                    .font(.system(size: 19, weight: .bold, design: .rounded))
                Text(UIStrings.App.slogan)
                    .font(.system(size: 12))
                    .foregroundStyle(Palette.mutedInk)
            }
            Spacer()
            HStack(spacing: 7) {
                Image(systemName: "archivebox")
                Text(UIStrings.App.libraryCount(count: "\(model.packs.count)"))
            }
            .font(.system(size: 12, weight: .medium))
            .foregroundStyle(Palette.mutedInk)
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(Color.white.opacity(0.62))
            .clipShape(Capsule())
        }
        .padding(.horizontal, 28)
        .frame(height: 72)
    }
}

struct StepStrip: View {
    @ObservedObject var model: WordFormatLibraryModel

    private let steps = [
        (1, UIStrings.Steps.importTitle, UIStrings.Steps.importSubtitle),
        (2, UIStrings.Steps.previewTitle, UIStrings.Steps.previewSubtitle),
        (3, UIStrings.Steps.applyTitle, UIStrings.Steps.applySubtitle)
    ]

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(steps.enumerated()), id: \.element.0) { index, item in
                Button {
                    if item.0 == 1 || model.selectedPack != nil {
                        model.currentStep = item.0
                    }
                } label: {
                    HStack(spacing: 11) {
                        ZStack {
                            Circle()
                                .fill(model.currentStep == item.0 ? Palette.green : Palette.mint)
                            Text("\(item.0)")
                                .font(.system(size: 12, weight: .bold))
                                .foregroundStyle(model.currentStep == item.0 ? .white : Palette.green)
                        }
                        .frame(width: 27, height: 27)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(item.1)
                                .font(.system(size: 13, weight: .semibold))
                            Text(item.2)
                                .font(.system(size: 10.5))
                                .foregroundStyle(Palette.mutedInk)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(item.0 > 1 && model.selectedPack == nil)

                if index < steps.count - 1 {
                    Rectangle()
                        .fill(Palette.line)
                        .frame(width: 46, height: 1)
                }
            }
        }
        .padding(.horizontal, 72)
        .frame(height: 67)
        .background(Color.white.opacity(0.28))
    }
}

struct ToastBar: View {
    let message: String
    let dismiss: () -> Void

    var body: some View {
        Button(action: dismiss) {
            HStack(spacing: 9) {
                Image(systemName: "checkmark.circle.fill")
                Text(message)
                    .font(.system(size: 12, weight: .semibold))
                Spacer()
                Image(systemName: "xmark")
                    .font(.system(size: 10, weight: .bold))
            }
            .foregroundStyle(Palette.success)
            .padding(.horizontal, 22)
            .frame(height: 38)
            .frame(maxWidth: .infinity)
            .background(Palette.mint)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityHint(Text(UIStrings.Deletion.confirmCancel))
    }
}

struct EmptySelectionView: View {
    let action: () -> Void

    var body: some View {
        VStack(spacing: 13) {
            Image(systemName: "archivebox")
                .font(.system(size: 34))
                .foregroundStyle(Palette.mutedInk)
            Text(UIStrings.EmptySelection.title)
                .font(.system(size: 18, weight: .bold))
            Button(UIStrings.EmptySelection.action) { action() }
                .buttonStyle(PrimaryButtonStyle())
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct BusyOverlay: View {
    let message: String

    var body: some View {
        ZStack {
            Color.black.opacity(0.16).ignoresSafeArea()
            VStack(spacing: 13) {
                ProgressView()
                    .controlSize(.large)
                    .tint(Palette.green)
                Text(message)
                    .font(.system(size: 13, weight: .semibold))
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, 30)
            .frame(minWidth: 260, minHeight: 116)
            .background(.ultraThickMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .shadow(color: .black.opacity(0.16), radius: 24, y: 10)
        }
    }
}
