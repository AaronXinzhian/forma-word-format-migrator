import SwiftUI

struct FormatPreviewStepView: View {
    @ObservedObject var model: WordFormatLibraryModel
    @State private var filter: FormatFilter = .all

    private var formats: [UsedFormat] {
        model.selectedPack?.usedFormats.filter(filter.includes) ?? []
    }

    var body: some View {
        if let pack = model.selectedPack {
            VStack(spacing: 0) {
                HStack(spacing: 14) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(pack.name)
                            .font(.system(size: 23, weight: .bold, design: .rounded))
                        Text(summaryText(for: pack))
                            .font(.system(size: 12.5))
                            .foregroundStyle(Palette.mutedInk)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Spacer()
                    Button {
                        model.highlightLibrary()
                    } label: {
                        Label(UIStrings.PreviewStep.switchPackButton, systemImage: "arrow.left.arrow.right")
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    Button {
                        model.beginTargetStep()
                    } label: {
                        Label(UIStrings.PreviewStep.nextButton, systemImage: "arrow.right")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                }
                .padding(.horizontal, 28)
                .padding(.vertical, 18)

                Divider().overlay(Palette.line)

                HStack(spacing: 0) {
                    VStack(spacing: 0) {
                        SummaryBar(pack: pack)
                        PreviewNotices(pack: pack)
                        FormatFilterBar(filter: $filter, formats: pack.usedFormats)
                        formatGrid
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                    Divider().overlay(Palette.line)

                    StyleInspector(
                        format: model.selectedFormat,
                        pageLayout: pack.pageLayout
                    )
                    .frame(width: 310)
                    .background(Color.white.opacity(0.34))
                }

                Divider().overlay(Palette.line)

                HStack {
                    Text(UIStrings.PreviewStep.privacy)
                        .font(.system(size: 11))
                        .foregroundStyle(Palette.mutedInk)
                    Spacer()
                }
                .padding(.horizontal, 28)
                .frame(height: 42)
            }
        } else {
            EmptySelectionView { model.currentStep = 1 }
        }
    }

    @ViewBuilder
    private var formatGrid: some View {
        ScrollView {
            if formats.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: "line.3.horizontal.decrease.circle")
                        .font(.system(size: 26))
                    Text(UIStrings.PreviewStep.emptyList)
                        .font(.system(size: 13, weight: .medium))
                }
                .foregroundStyle(Palette.mutedInk)
                .frame(maxWidth: .infinity)
                .padding(.top, 74)
            } else {
                LazyVGrid(
                    columns: [GridItem(.adaptive(minimum: 270), spacing: 13)],
                    spacing: 13
                ) {
                    ForEach(formats) { format in
                        FormatCard(
                            format: format,
                            isSelected: model.selectedFormatID == format.id
                        ) {
                            model.selectedFormatID = format.id
                        }
                    }
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 28)
            }
        }
    }

    private func summaryText(for pack: PackManifest) -> String {
        pack.inferredCount > 0
            ? UIStrings.PreviewStep.summaryWithInferred(
                inferred: "\(pack.inferredCount)",
                hidden: "\(pack.hiddenCount)"
            )
            : UIStrings.PreviewStep.summary(hidden: "\(pack.hiddenCount)")
    }
}

private struct PreviewNotices: View {
    let pack: PackManifest

    private var hasNotices: Bool {
        pack.manualFormatting.paragraphCount > 0
            || pack.manualFormatting.runCount > 0
            || !(pack.headingNumberingConflicts ?? []).isEmpty
            || !(pack.headingCompletionWarnings ?? []).isEmpty
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if pack.manualFormatting.paragraphCount > 0 || pack.manualFormatting.runCount > 0 {
                ManualFormattingNotice(manual: pack.manualFormatting)
            }
            if let conflicts = pack.headingNumberingConflicts, !conflicts.isEmpty {
                warningRow(UIStrings.PreviewStep.numberingConflict(count: "\(conflicts.count)"))
            }
            ForEach(pack.headingCompletionWarnings ?? [], id: \.self) { text in
                warningRow(text)
            }
            if !hasNotices {
                Label(UIStrings.PreviewStep.structureOk, systemImage: "checkmark.circle")
                    .font(.system(size: 11.5, weight: .medium))
                    .foregroundStyle(Palette.success)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 24)
        .padding(.top, 12)
    }

    private func warningRow(_ text: String) -> some View {
        Label(text, systemImage: "exclamationmark.triangle")
            .font(.system(size: 11.5, weight: .medium))
            .foregroundStyle(Palette.amber)
            .fixedSize(horizontal: false, vertical: true)
    }
}

private struct SummaryBar: View {
    let pack: PackManifest

    var body: some View {
        HStack(spacing: 10) {
            MiniStat(
                value: pack.inferredCount > 0
                    ? "\(pack.usedStyleCount) + \(pack.inferredCount)"
                    : "\(pack.usedStyleCount)",
                label: pack.inferredCount > 0
                    ? UIStrings.PreviewStep.statFormatsBoth
                    : UIStrings.PreviewStep.statFormatsUsed,
                icon: "textformat"
            )
            MiniStat(
                value: "\(pack.documentSummary.paragraphCount)",
                label: UIStrings.PreviewStep.statParagraphs,
                icon: "paragraphsign"
            )
            MiniStat(
                value: "\(pack.documentSummary.tableCount)",
                label: UIStrings.PreviewStep.statTables,
                icon: "tablecells"
            )
            MiniStat(
                value: "\(pack.documentSummary.sectionCount)",
                label: UIStrings.PreviewStep.statSections,
                icon: "doc.text"
            )
        }
        .padding(.horizontal, 24)
        .padding(.top, 16)
    }
}

private struct MiniStat: View {
    let value: String
    let label: String
    let icon: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(Palette.green)
                .frame(width: 29, height: 29)
                .background(Palette.mint)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            VStack(alignment: .leading, spacing: 0) {
                Text(value).font(.system(size: 16, weight: .bold, design: .rounded))
                Text(label).font(.system(size: 10.5)).foregroundStyle(Palette.mutedInk)
            }
        }
        .padding(.horizontal, 13)
        .frame(maxWidth: .infinity, minHeight: 54, alignment: .leading)
        .background(Color.white.opacity(0.72))
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(Palette.line.opacity(0.8), lineWidth: 1)
        }
    }
}

private struct ManualFormattingNotice: View {
    let manual: ManualFormatting

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "paintbrush.pointed")
                .foregroundStyle(Palette.amber)
            Text(UIStrings.PreviewStep.manualNotice(
                paragraphs: "\(manual.paragraphCount)",
                runs: "\(manual.runCount)"
            ))
            .font(.system(size: 11.5))
            .foregroundStyle(Palette.ink.opacity(0.84))
            .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(12)
        .background(Palette.amberWash)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

private struct FormatFilterBar: View {
    @Binding var filter: FormatFilter
    let formats: [UsedFormat]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(FormatFilter.allCases) { item in
                    Button {
                        filter = item
                    } label: {
                        Text(UIStrings.Filters.withCount(
                            name: item.title,
                            count: "\(formats.filter(item.includes).count)"
                        ))
                        .font(.system(size: 11.5, weight: .semibold))
                        .foregroundStyle(filter == item ? .white : Palette.mutedInk)
                        .padding(.horizontal, 12)
                        .frame(height: 31)
                        .background(filter == item ? Palette.green : Color.white.opacity(0.66))
                        .clipShape(Capsule())
                        .overlay {
                            if filter != item {
                                Capsule().stroke(Palette.line, lineWidth: 1)
                            }
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 14)
        }
    }
}

private struct FormatCard: View {
    let format: UsedFormat
    let isSelected: Bool
    let action: () -> Void

    private var previewFont: Font {
        let size = min(max(format.sizePt ?? 14, 11), 25)
        let name = format.fontEastAsia ?? format.fontLatin
        return name.map { .custom($0, size: size) } ?? .system(size: size)
    }

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 11) {
                HStack {
                    Text(format.name)
                        .font(.system(size: 13, weight: .bold))
                        .lineLimit(1)
                    Spacer()
                    Text(FormatDisplay.usage(format))
                        .font(.system(size: 9.5, weight: .semibold))
                        .foregroundStyle(Palette.green)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(Palette.mint)
                        .clipShape(Capsule())
                }
                Text(format.sample)
                    .font(previewFont)
                    .fontWeight(format.bold == true ? .bold : .regular)
                    .italic(format.italic == true)
                    .foregroundStyle(format.colorHex.map(Color.init(hex:)) ?? Palette.ink)
                    .lineLimit(2)
                    .frame(maxWidth: .infinity, minHeight: 45, alignment: alignment(format.alignment))
                    .padding(.horizontal, 10)
                    .background((format.tableFillHex.map(Color.init(hex:)) ?? Palette.paper).opacity(0.7))
                    .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                HStack(spacing: 6) {
                    Text(FormatDisplay.badge(format))
                        .font(.system(size: 9.5, weight: .bold))
                        .foregroundStyle(Palette.green)
                    if let font = format.fontEastAsia ?? format.fontLatin {
                        Text(font).lineLimit(1)
                    }
                    if let size = format.sizePt {
                        Text(UIStrings.Inspector.sizeValue(size: number(size)))
                    }
                }
                .font(.system(size: 10.5))
                .foregroundStyle(Palette.mutedInk)
            }
            .padding(14)
            .background(isSelected ? Palette.mint.opacity(0.55) : Palette.card)
            .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 15, style: .continuous)
                    .stroke(isSelected ? Palette.green : Palette.line, lineWidth: isSelected ? 1.7 : 1)
            }
        }
        .buttonStyle(.plain)
    }

    private func alignment(_ value: String?) -> Alignment {
        switch value {
        case "center": return .center
        case "right", "end": return .trailing
        default: return .leading
        }
    }
}
