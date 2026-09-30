// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供FormatPreviewStepView 中的类型与接口
// [POS]: Mac 原生终端 - 实际使用格式筛选、卡片与编辑入口
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

enum FormatFilter: String, CaseIterable, Identifiable {
    case all = "全部"
    case headings = "标题"
    case paragraphs = "正文与段落"
    case characters = "字符"
    case tables = "表格"

    var id: String { rawValue }

    func includes(_ format: UsedFormat) -> Bool {
        switch self {
        case .all: return true
        case .headings: return format.type == "paragraph" && format.outlineLevel != nil
        case .paragraphs: return format.type == "paragraph" && format.outlineLevel == nil
        case .characters: return format.type == "character"
        case .tables: return format.type == "table"
        }
    }
}

struct FormatPreviewStepView: View {
    @ObservedObject var model: WordFormatLibraryModel
    @State private var filter: FormatFilter = .all
    @State private var isShowingStyleEditor = false

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
                        Text(pack.formatOverviewDescription)
                            .font(.system(size: 12.5))
                            .foregroundStyle(Palette.mutedInk)
                    }
                    Spacer()
                    Button {
                        isShowingStyleEditor = true
                    } label: {
                        Label("编辑格式方案", systemImage: "slider.horizontal.3")
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    .help("调整标题、段落、字符或表格样式，并另存为新方案")
                    Button {
                        model.highlightLibrary()
                    } label: {
                        Label("换一套格式", systemImage: "arrow.left.arrow.right")
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    Button {
                        model.beginTargetStep()
                    } label: {
                        Label("下一步", systemImage: "arrow.right")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                }
                .padding(.horizontal, 28)
                .padding(.vertical, 18)

                Divider().overlay(Palette.line)

                HStack(spacing: 0) {
                    VStack(spacing: 0) {
                        SummaryBar(pack: pack)
                        if pack.manualFormatting.paragraphCount > 0 || pack.manualFormatting.runCount > 0 {
                            ManualFormattingNotice(manual: pack.manualFormatting)
                                .padding(.horizontal, 24)
                                .padding(.top, 12)
                        }
                        if let conflicts = pack.headingNumberingConflicts, !conflicts.isEmpty {
                            Label(
                                "检测到 \(conflicts.count) 个标题样式使用多套编号；将采用最常用规则，请在生成后检查章节重启。",
                                systemImage: "exclamationmark.triangle"
                            )
                            .font(.system(size: 11.5, weight: .medium))
                            .foregroundStyle(Color.orange)
                            .padding(.horizontal, 24)
                            .padding(.top, 12)
                        }
                        if let warnings = pack.headingCompletionWarnings, !warnings.isEmpty {
                            ForEach(warnings, id: \.self) { warning in
                                Label(warning, systemImage: "exclamationmark.triangle")
                                    .font(.system(size: 11.5, weight: .medium))
                                    .foregroundStyle(Color.orange)
                                    .padding(.horizontal, 24)
                                    .padding(.top, 12)
                            }
                        }
                        FormatFilterBar(
                            filter: $filter,
                            formats: pack.usedFormats
                        )
                        ScrollView {
                            if formats.isEmpty {
                                VStack(spacing: 10) {
                                    Image(systemName: "line.3.horizontal.decrease.circle")
                                        .font(.system(size: 26))
                                    Text("这一类没有被使用的格式")
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
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                    Divider().overlay(Palette.line)

                    StyleInspector(
                        format: formats.first(where: { $0.id == model.selectedFormatID }),
                        pageLayout: pack.pageLayout
                    )
                    .frame(width: 310)
                    .background(Color.white.opacity(0.34))
                }
            }
            .sheet(isPresented: $isShowingStyleEditor) {
                StyleEditorSheet(model: model, pack: pack)
            }
            .onAppear { reconcileSelection() }
            .onChange(of: filter) { _ in reconcileSelection() }
            .onChange(of: pack.libraryIdentity) { _ in reconcileSelection() }
        } else {
            EmptySelectionView { model.currentStep = 1 }
        }
    }

    private func reconcileSelection() {
        model.selectedFormatID = FormatSelectionPolicy.selectedID(
            current: model.selectedFormatID,
            visibleIDs: formats.map(\.id)
        )
    }
}

struct SummaryBar: View {
    let pack: PackManifest

    var body: some View {
        HStack(spacing: 10) {
            MiniStat(
                value: "\(pack.usedStyleCount + (pack.inferredStyleCount ?? 0) + pack.resolvedCustomStyleCount)",
                label: pack.resolvedCustomStyleCount > 0
                    ? "格式总数（含自定义）"
                    : ((pack.inferredStyleCount ?? 0) > 0 ? "实际 + 补全" : "实际使用"),
                icon: "textformat"
            )
            MiniStat(value: "\(pack.documentSummary.paragraphCount)", label: "段落", icon: "paragraphsign")
            MiniStat(value: "\(pack.documentSummary.tableCount)", label: "表格", icon: "tablecells")
            MiniStat(value: "\(pack.documentSummary.sectionCount)", label: "节", icon: "doc.text")
        }
        .padding(.horizontal, 24)
        .padding(.top, 16)
    }
}

struct MiniStat: View {
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

struct ManualFormattingNotice: View {
    let manual: ManualFormatting

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "paintbrush.pointed")
                .foregroundStyle(Palette.amber)
            Text("发现 \(manual.paragraphCount) 个手工设置段落、\(manual.runCount) 处手工字符格式。它们不是可复用样式，因此不会出现在下方列表中；应用时会清理目标文档的手工视觉格式。")
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

struct FormatFilterBar: View {
    @Binding var filter: FormatFilter
    let formats: [UsedFormat]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(FormatFilter.allCases) { item in
                    Button {
                        filter = item
                    } label: {
                        Text("\(item.rawValue)  \(formats.filter(item.includes).count)")
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
                    .accessibilityAddTraits(filter == item ? .isSelected : [])
                }
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 14)
        }
    }
}

struct FormatCard: View {
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
                    Text(format.inferred == true
                         ? (format.inferenceLabel ?? "智能补全")
                         : "用过 \(format.usageCount) 次")
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
                    TypeBadge(format: format)
                    if let font = format.fontEastAsia ?? format.fontLatin {
                        Text(font).lineLimit(1)
                    }
                    if let size = format.sizePt {
                        Text("\(number(size)) pt")
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
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    private func alignment(_ value: String?) -> Alignment {
        switch value {
        case "center": return .center
        case "right", "end": return .trailing
        default: return .leading
        }
    }
}

struct TypeBadge: View {
    let format: UsedFormat

    var body: some View {
        Text(label)
            .font(.system(size: 9.5, weight: .bold))
            .foregroundStyle(Palette.green)
    }

    private var label: String {
        if format.outlineLevel != nil { return "标题" }
        switch format.type {
        case "character": return "字符"
        case "table": return "表格"
        default: return "段落"
        }
    }
}
