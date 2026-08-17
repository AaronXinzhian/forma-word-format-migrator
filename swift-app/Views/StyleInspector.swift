import SwiftUI

/// 格式属性的取值逻辑集中在这里，Windows 端 `FormatDisplay.cs` 与之一一对应。
enum FormatDisplay {
    static func usage(_ format: UsedFormat) -> String {
        format.inferred == true
            ? (format.inferenceLabel ?? UIStrings.FormatList.usageInferred)
            : UIStrings.FormatList.usageCount(count: "\(format.usageCount)")
    }

    static func source(_ format: UsedFormat) -> String {
        format.inferred == true
            ? (format.inferenceLabel ?? UIStrings.FormatList.usageInferred)
            : UIStrings.Inspector.sourceUsedCount(count: "\(format.usageCount)")
    }

    static func badge(_ format: UsedFormat) -> String {
        if format.outlineLevel != nil { return UIStrings.FormatList.badgeHeading }
        switch format.type {
        case "character": return UIStrings.FormatList.badgeCharacter
        case "table": return UIStrings.FormatList.badgeTable
        default: return UIStrings.FormatList.badgeParagraph
        }
    }

    static func type(_ format: UsedFormat) -> String {
        if let level = format.outlineLevel {
            return UIStrings.Inspector.typeHeading(level: "\(level + 1)")
        }
        switch format.type {
        case "character": return UIStrings.Inspector.typeCharacter
        case "table": return UIStrings.Inspector.typeTable
        default: return UIStrings.Inspector.typeParagraph
        }
    }

    static func traits(_ format: UsedFormat) -> String {
        var traits: [String] = []
        if format.bold == true { traits.append(UIStrings.Inspector.traitBold) }
        if format.italic == true { traits.append(UIStrings.Inspector.traitItalic) }
        return traits.isEmpty
            ? UIStrings.Inspector.traitRegular
            : traits.joined(separator: UIStrings.Inspector.traitSeparator)
    }

    static func alignment(_ value: String?) -> String {
        switch value {
        case "center": return UIStrings.Inspector.alignCenter
        case "right", "end": return UIStrings.Inspector.alignRight
        case "both": return UIStrings.Inspector.alignJustify
        case "distribute": return UIStrings.Inspector.alignDistribute
        case "left", "start": return UIStrings.Inspector.alignLeft
        default: return UIStrings.Inspector.inherit
        }
    }

    static func spacing(_ format: UsedFormat) -> String {
        guard format.spaceBeforePt != nil || format.spaceAfterPt != nil else {
            return UIStrings.Inspector.inherit
        }
        return UIStrings.Inspector.spacingValue(
            before: number(format.spaceBeforePt ?? 0),
            after: number(format.spaceAfterPt ?? 0)
        )
    }

    static func lineSpacing(_ format: UsedFormat) -> String {
        guard let value = format.lineSpacing else { return UIStrings.Inspector.inherit }
        if format.lineRule == nil || format.lineRule == "auto" {
            return UIStrings.Inspector.lineSpacingMultiple(value: number(value))
        }
        return UIStrings.Inspector.lineSpacingExact(value: number(value))
    }

    static func numbering(_ format: UsedFormat) -> String {
        guard format.numbered else { return UIStrings.Inspector.numberingNone }
        if let example = format.numberingExample ?? format.numberingPattern {
            return UIStrings.Inspector.numberingWithExample(example: example)
        }
        return UIStrings.Inspector.numberingPlain
    }

    static func fontSummary(_ format: UsedFormat) -> String {
        let family = format.fontEastAsia ?? format.fontLatin ?? UIStrings.FormatList.inheritFont
        let size = format.sizePt.map { UIStrings.Inspector.sizeValue(size: number($0)) }
            ?? UIStrings.FormatList.inheritSize
        return "\(family) / \(size)"
    }

    static func hex(_ value: String?) -> String {
        guard let value, !value.isEmpty else { return UIStrings.Inspector.inherit }
        return "#\(value)"
    }

    static func optional(_ value: String?) -> String {
        guard let value, !value.isEmpty else { return UIStrings.Inspector.inherit }
        return value
    }
}

struct StyleInspector: View {
    let format: UsedFormat?
    let pageLayout: PageLayout

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text(UIStrings.Inspector.title)
                    .font(.system(size: 16, weight: .bold))
                if let format {
                    preview(format)
                    properties(format)
                } else {
                    Text(UIStrings.Inspector.empty)
                        .font(.system(size: 12))
                        .foregroundStyle(Palette.mutedInk)
                }

                Divider().overlay(Palette.line)
                PageLayoutCard(layout: pageLayout)
            }
            .padding(20)
        }
    }

    private func preview(_ format: UsedFormat) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(format.sample)
                .font(inspectorFont(format))
                .fontWeight(format.bold == true ? .bold : .regular)
                .italic(format.italic == true)
                .foregroundStyle(format.colorHex.map(Color.init(hex:)) ?? Palette.ink)
                .fixedSize(horizontal: false, vertical: true)
            Text(format.name)
                .font(.system(size: 11))
                .foregroundStyle(Palette.mutedInk)
        }
        .frame(maxWidth: .infinity, minHeight: 84, alignment: .leading)
        .padding(14)
        .background(Color.white.opacity(0.78))
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
    }

    @ViewBuilder
    private func properties(_ format: UsedFormat) -> some View {
        VStack(spacing: 0) {
            PropertyRow(label: UIStrings.Inspector.labelType, value: FormatDisplay.type(format))
            PropertyRow(label: UIStrings.Inspector.labelSource, value: FormatDisplay.source(format))
            PropertyRow(
                label: UIStrings.Inspector.labelFontEastAsia,
                value: FormatDisplay.optional(format.fontEastAsia)
            )
            PropertyRow(
                label: UIStrings.Inspector.labelFontLatin,
                value: FormatDisplay.optional(format.fontLatin)
            )
            PropertyRow(
                label: UIStrings.Inspector.labelSize,
                value: format.sizePt.map { UIStrings.Inspector.sizeValue(size: number($0)) }
                    ?? UIStrings.Inspector.inherit
            )
            PropertyRow(label: UIStrings.Inspector.labelTraits, value: FormatDisplay.traits(format))
            PropertyRow(label: UIStrings.Inspector.labelColor, value: FormatDisplay.hex(format.colorHex))
            if format.type == "paragraph" {
                PropertyRow(
                    label: UIStrings.Inspector.labelAlignment,
                    value: FormatDisplay.alignment(format.alignment)
                )
                PropertyRow(
                    label: UIStrings.Inspector.labelSpacing,
                    value: FormatDisplay.spacing(format)
                )
                PropertyRow(
                    label: UIStrings.Inspector.labelLineSpacing,
                    value: FormatDisplay.lineSpacing(format)
                )
                if let level = format.outlineLevel {
                    PropertyRow(
                        label: UIStrings.Inspector.labelOutline,
                        value: UIStrings.Inspector.outlineValue(level: "\(level + 1)")
                    )
                }
                PropertyRow(
                    label: UIStrings.Inspector.labelNumbering,
                    value: FormatDisplay.numbering(format)
                )
            }
            if format.type == "table" {
                PropertyRow(
                    label: UIStrings.Inspector.labelTableFill,
                    value: FormatDisplay.hex(format.tableFillHex)
                )
                PropertyRow(
                    label: UIStrings.Inspector.labelTableAccent,
                    value: FormatDisplay.hex(format.tableAccentHex)
                )
            }
        }
        .background(Color.white.opacity(0.55))
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
    }

    private func inspectorFont(_ format: UsedFormat) -> Font {
        let size = min(max(format.sizePt ?? 14, 11), 24)
        if let name = format.fontEastAsia ?? format.fontLatin {
            return .custom(name, size: size)
        }
        return .system(size: size)
    }
}

struct PropertyRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 9) {
            Text(label)
                .foregroundStyle(Palette.mutedInk)
            Spacer(minLength: 6)
            Text(value)
                .foregroundStyle(Palette.ink)
                .multilineTextAlignment(.trailing)
                .lineLimit(2)
        }
        .font(.system(size: 11))
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Palette.line.opacity(0.65)).frame(height: 1)
        }
    }
}

struct PageLayoutCard: View {
    let layout: PageLayout

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(UIStrings.Inspector.pageTitle)
                    .font(.system(size: 14, weight: .bold))
                Spacer()
                Text(layout.orientation == "landscape"
                     ? UIStrings.Inspector.pageOrientationLandscape
                     : UIStrings.Inspector.pageOrientationPortrait)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(Palette.green)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Palette.mint)
                    .clipShape(Capsule())
            }
            HStack(spacing: 14) {
                ZStack {
                    Rectangle()
                        .fill(Color.white)
                        .shadow(color: Palette.ink.opacity(0.12), radius: 4, y: 2)
                    RoundedRectangle(cornerRadius: 1)
                        .stroke(Palette.line, lineWidth: 1)
                        .padding(7)
                }
                .aspectRatio(pageAspect, contentMode: .fit)
                .frame(width: layout.orientation == "landscape" ? 74 : 52)
                VStack(alignment: .leading, spacing: 5) {
                    Text(pageSize)
                    Text(UIStrings.Inspector.pageMarginVertical(
                        top: centimeters(layout.marginTopCM),
                        bottom: centimeters(layout.marginBottomCM)
                    ))
                    Text(UIStrings.Inspector.pageMarginHorizontal(
                        left: centimeters(layout.marginLeftCM),
                        right: centimeters(layout.marginRightCM)
                    ))
                }
                .font(.system(size: 10.5))
                .foregroundStyle(Palette.mutedInk)
            }
        }
    }

    private var pageAspect: CGFloat {
        guard let width = layout.widthCM, let height = layout.heightCM, height > 0 else {
            return 0.707
        }
        return CGFloat(width / height)
    }

    private var pageSize: String {
        guard let width = layout.widthCM, let height = layout.heightCM else {
            return UIStrings.Inspector.pageSizeDefault
        }
        return UIStrings.Inspector.pageSizeValue(width: number(width), height: number(height))
    }

    private func centimeters(_ value: Double?) -> String {
        value.map { UIStrings.Inspector.centimeterValue(value: number($0)) }
            ?? UIStrings.Inspector.inherit
    }
}
