import SwiftUI
import UniformTypeIdentifiers

/// 步骤 1 主区：只做导入引导。格式库列表已经移到常驻侧边栏。
struct ImportStepView: View {
    @ObservedObject var model: WordFormatLibraryModel
    @State private var isDropTarget = false

    var body: some View {
        ScrollView {
            HStack(alignment: .top, spacing: 22) {
                ImportDropCard(model: model, isTargeted: $isDropTarget)
                    .frame(maxWidth: .infinity, minHeight: 320)
                VStack(alignment: .leading, spacing: 14) {
                    Label(UIStrings.ImportStep.infoTitle, systemImage: "checklist")
                        .font(.system(size: 15, weight: .bold))
                    ExplanationRow(number: "01", text: UIStrings.ImportStep.info1)
                    ExplanationRow(number: "02", text: UIStrings.ImportStep.info2)
                    ExplanationRow(number: "03", text: UIStrings.ImportStep.info3)
                    Spacer(minLength: 0)
                }
                .frame(width: 300, alignment: .leading)
                .padding(24)
                .background(Palette.mint.opacity(0.66))
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            .padding(28)
        }
    }
}

private struct ImportDropCard: View {
    @ObservedObject var model: WordFormatLibraryModel
    @Binding var isTargeted: Bool

    var body: some View {
        VStack(spacing: 12) {
            Text(UIStrings.ImportStep.eyebrow)
                .font(.system(size: 11.5, weight: .bold))
                .foregroundStyle(Palette.green)
            ZStack {
                Circle().fill(Palette.mint)
                Image(systemName: "doc.badge.plus")
                    .font(.system(size: 31, weight: .medium))
                    .foregroundStyle(Palette.green)
            }
            .frame(width: 68, height: 68)
            Text(UIStrings.ImportStep.title)
                .font(.system(size: 21, weight: .bold, design: .rounded))
            Text(UIStrings.ImportStep.subtitle)
                .font(.system(size: 12.5))
                .foregroundStyle(Palette.mutedInk)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 34)
            Button {
                if let url = FilePanels.chooseSource() {
                    Task { await model.importSource(url) }
                }
            } label: {
                Label(UIStrings.ImportStep.chooseButton, systemImage: "folder")
            }
            .buttonStyle(PrimaryButtonStyle())
            .padding(.top, 4)
            Text(UIStrings.ImportStep.dropHint)
                .font(.system(size: 11.5))
                .foregroundStyle(Palette.mutedInk)
            Text(UIStrings.ImportStep.supportedFormats)
                .font(.system(size: 10.5, weight: .medium))
                .foregroundStyle(Palette.mutedInk)
        }
        .padding(.vertical, 34)
        .frame(maxWidth: .infinity, minHeight: 320)
        .background(isTargeted ? Palette.mint : Palette.card)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(
                    isTargeted ? Palette.green : Palette.line,
                    style: StrokeStyle(lineWidth: isTargeted ? 2 : 1, dash: [7, 5])
                )
        }
        .onDrop(of: [UTType.fileURL], isTargeted: $isTargeted) { providers in
            FilePanels.firstFileURL(from: providers) { url in
                Task { await model.importSource(url) }
            }
        }
    }
}

private struct ExplanationRow: View {
    let number: String
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 11) {
            Text(number)
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundStyle(Palette.green)
                .frame(width: 26, height: 26)
                .background(Color.white.opacity(0.78))
                .clipShape(Circle())
            Text(text)
                .font(.system(size: 12.5))
                .foregroundStyle(Palette.ink.opacity(0.88))
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
