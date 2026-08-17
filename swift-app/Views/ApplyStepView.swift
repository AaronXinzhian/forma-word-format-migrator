import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct ApplyStepView: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    header
                    if let pack = model.selectedPack {
                        SelectedPackBanner(pack: pack) { model.highlightLibrary() }
                    }
                    HStack(alignment: .top, spacing: 20) {
                        TargetDocumentCard(model: model)
                            .frame(maxWidth: .infinity, minHeight: 255)
                        ApplyOptionsCard(model: model)
                            .frame(width: 355)
                    }
                    if let outputURL = model.outputURL {
                        SuccessCard(url: outputURL, warnings: model.outputWarnings) {
                            model.clearTarget()
                        }
                    }
                }
                .padding(28)
            }

            Divider().overlay(Palette.line)

            // 应用按钮固定在页脚，与 Windows 端的位置一致。
            HStack(spacing: 14) {
                Text(UIStrings.ApplyStep.noteKeepContent)
                    .font(.system(size: 11))
                    .foregroundStyle(Palette.mutedInk)
                Spacer()
                Button {
                    applyToDestination()
                } label: {
                    Label(
                        model.outputURL == nil
                            ? UIStrings.ApplyStep.applyButton
                            : UIStrings.ApplyStep.applyAgainButton,
                        systemImage: "wand.and.stars"
                    )
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(model.targetURL == nil || model.selectedPack == nil)
                .opacity(model.targetURL == nil ? 0.48 : 1)
            }
            .padding(.horizontal, 28)
            .frame(height: 66)
        }
    }

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 5) {
                Text(UIStrings.ApplyStep.title)
                    .font(.system(size: 27, weight: .bold, design: .rounded))
                Text(UIStrings.ApplyStep.subtitle)
                    .font(.system(size: 13))
                    .foregroundStyle(Palette.mutedInk)
            }
            Spacer()
            Button {
                model.currentStep = 2
            } label: {
                Label(UIStrings.ApplyStep.backButton, systemImage: "arrow.left")
            }
            .buttonStyle(SecondaryButtonStyle())
        }
    }

    private func applyToDestination() {
        guard let targetURL = model.targetURL,
              let destination = FilePanels.chooseDestination(basedOn: targetURL) else { return }
        Task { await model.applyPack(savingTo: destination) }
    }
}

private struct SelectedPackBanner: View {
    let pack: PackManifest
    let changeAction: () -> Void

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: "text.book.closed.fill")
                .font(.system(size: 22))
                .foregroundStyle(Palette.green)
                .frame(width: 48, height: 48)
                .background(Palette.mint)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            VStack(alignment: .leading, spacing: 3) {
                Text(UIStrings.ApplyStep.packTitle(name: pack.name))
                    .font(.system(size: 15, weight: .bold))
                Text(summary)
                    .font(.system(size: 11.5))
                    .foregroundStyle(Palette.mutedInk)
            }
            Spacer()
            Button(UIStrings.ApplyStep.changePackButton) { changeAction() }
                .buttonStyle(SecondaryButtonStyle())
        }
        .padding(16)
        .background(Color.white.opacity(0.62))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(Palette.line, lineWidth: 1)
        }
    }

    private var summary: String {
        pack.inferredCount > 0
            ? UIStrings.ApplyStep.packSummaryWithInferred(
                used: "\(pack.usedStyleCount)",
                inferred: "\(pack.inferredCount)"
            )
            : UIStrings.ApplyStep.packSummary(used: "\(pack.usedStyleCount)")
    }
}

private struct TargetDocumentCard: View {
    @ObservedObject var model: WordFormatLibraryModel
    @State private var isTargeted = false

    var body: some View {
        AppCard {
            VStack(spacing: 15) {
                Text(UIStrings.ApplyStep.targetTitle)
                    .font(.system(size: 14, weight: .bold))
                    .frame(maxWidth: .infinity, alignment: .leading)

                ZStack {
                    Circle().fill(Palette.mint)
                    Image(systemName: model.targetURL == nil ? "doc.badge.arrow.up" : "doc.fill")
                        .font(.system(size: 31, weight: .medium))
                        .foregroundStyle(Palette.green)
                }
                .frame(width: 66, height: 66)

                if let targetURL = model.targetURL {
                    Text(targetURL.lastPathComponent)
                        .font(.system(size: 16, weight: .bold))
                        .lineLimit(2)
                        .multilineTextAlignment(.center)
                    Text(targetURL.deletingLastPathComponent().path)
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Button(UIStrings.ApplyStep.changeTargetButton) { chooseTarget() }
                        .buttonStyle(SecondaryButtonStyle())
                } else {
                    Text(UIStrings.ApplyStep.targetEmptyTitle)
                        .font(.system(size: 17, weight: .bold))
                    Text(UIStrings.ApplyStep.targetEmptyHint)
                        .font(.system(size: 12))
                        .foregroundStyle(Palette.mutedInk)
                    Button {
                        chooseTarget()
                    } label: {
                        Label(UIStrings.ApplyStep.chooseTargetButton, systemImage: "folder")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    Text(UIStrings.ApplyStep.targetDropHint)
                        .font(.system(size: 11))
                        .foregroundStyle(Palette.mutedInk)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 235)
        }
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(Palette.green, style: StrokeStyle(lineWidth: 2, dash: [7, 5]))
                .opacity(isTargeted ? 1 : 0)
        }
        .onDrop(of: [UTType.fileURL], isTargeted: $isTargeted) { providers in
            FilePanels.firstFileURL(from: providers) { url in
                model.chooseTarget(url)
            }
        }
    }

    private func chooseTarget() {
        guard let url = FilePanels.chooseTarget() else { return }
        model.chooseTarget(url)
    }
}

private struct ApplyOptionsCard: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        AppCard {
            VStack(alignment: .leading, spacing: 17) {
                Text(UIStrings.ApplyStep.optionsTitle)
                    .font(.system(size: 16, weight: .bold))
                Toggle(isOn: $model.applySourcePageLayout) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(UIStrings.ApplyStep.optionPageLayout)
                            .font(.system(size: 13, weight: .semibold))
                        Text(UIStrings.ApplyStep.optionPageLayoutHint)
                            .font(.system(size: 10.5))
                            .foregroundStyle(Palette.mutedInk)
                    }
                }
                .toggleStyle(.switch)
                .tint(Palette.green)

                Divider().overlay(Palette.line)
                Toggle(isOn: $model.demoteHeadings) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(UIStrings.ApplyStep.optionDemote)
                            .font(.system(size: 13, weight: .semibold))
                        Text(UIStrings.ApplyStep.optionDemoteHint)
                            .font(.system(size: 10.5))
                            .foregroundStyle(Palette.mutedInk)
                    }
                }
                .toggleStyle(.switch)
                .tint(Palette.green)
                Text(UIStrings.ApplyStep.optionDemoteNote)
                    .font(.system(size: 10.5))
                    .foregroundStyle(Palette.mutedInk)
                    .fixedSize(horizontal: false, vertical: true)

                Divider().overlay(Palette.line)
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(ApplyNotes.notes(for: model.selectedPack), id: \.text) { note in
                        OptionLine(icon: note.icon, text: note.text)
                    }
                }
                Spacer(minLength: 2)
            }
            .frame(minHeight: 235)
        }
    }
}

/// 处理说明按格式包内容动态生成，两端使用同一套规则。
enum ApplyNotes {
    struct Note {
        let icon: String
        let text: String
    }

    static func notes(for pack: PackManifest?) -> [Note] {
        var notes: [Note] = [
            Note(icon: "checkmark.circle", text: UIStrings.ApplyStep.noteKeepContent),
            Note(icon: "eraser", text: UIStrings.ApplyStep.noteCleanup)
        ]
        if (pack?.inferredCount ?? 0) > 0 {
            notes.append(
                Note(icon: "wand.and.stars", text: UIStrings.ApplyStep.noteInferredHeadings)
            )
        }
        notes.append(Note(icon: "doc.on.doc", text: UIStrings.ApplyStep.noteSaveAsNew))
        if pack?.hasNumberedHeadings == true {
            notes.append(Note(icon: "list.number", text: UIStrings.ApplyStep.noteNumbering))
            notes.append(
                Note(icon: "checkmark.circle", text: UIStrings.ApplyStep.noteManualPrefix)
            )
        }
        if let pack, !pack.hasTableStyles {
            notes.append(Note(icon: "tablecells", text: UIStrings.ApplyStep.noteTableFallback))
        }
        return notes
    }
}

private struct OptionLine: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(Palette.green)
                .frame(width: 16)
            Text(text)
                .font(.system(size: 11.5))
                .foregroundStyle(Palette.mutedInk)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct SuccessCard: View {
    let url: URL
    let warnings: [String]
    let restart: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 15) {
                ZStack {
                    Circle().fill(Palette.success)
                    Image(systemName: "checkmark")
                        .font(.system(size: 19, weight: .bold))
                        .foregroundStyle(.white)
                }
                .frame(width: 44, height: 44)
                VStack(alignment: .leading, spacing: 3) {
                    Text(UIStrings.Success.title)
                        .font(.system(size: 15, weight: .bold))
                    Text(url.path)
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                Spacer()
                Button(UIStrings.Success.revealButton) {
                    NSWorkspace.shared.activateFileViewerSelecting([url])
                }
                .buttonStyle(SecondaryButtonStyle())
                Button(UIStrings.Success.openButton) {
                    NSWorkspace.shared.open(url)
                }
                .buttonStyle(PrimaryButtonStyle(compact: true))
                Button(UIStrings.Success.nextButton) { restart() }
                    .buttonStyle(.plain)
                    .font(.system(size: 11.5, weight: .semibold))
                    .foregroundStyle(Palette.green)
            }

            if !warnings.isEmpty {
                Label(
                    UIStrings.Success.warnings(
                        details: warnings.prefix(3)
                            .joined(separator: UIStrings.Success.warningSeparator)
                    ),
                    systemImage: "exclamationmark.triangle"
                )
                .font(.system(size: 11))
                .foregroundStyle(Palette.amber)
                .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(17)
        .background(Palette.mint.opacity(0.74))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(Palette.success.opacity(0.4), lineWidth: 1)
        }
    }
}
