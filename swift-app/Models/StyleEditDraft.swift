// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供StyleEditDraft 中的类型与接口
// [POS]: Mac 原生终端 - 可校验格式编辑草稿与段落单位、修改请求生成
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

enum ParagraphAlignmentEditChoice: String, CaseIterable, Identifiable {
    case unchanged
    case left
    case center
    case right
    case justified
    case distributed

    var id: String { rawValue }

    var label: String {
        switch self {
        case .unchanged: return "不修改"
        case .left: return "左对齐"
        case .center: return "居中"
        case .right: return "右对齐"
        case .justified: return "两端对齐"
        case .distributed: return "分散对齐"
        }
    }

    var encodedValue: String? {
        switch self {
        case .unchanged: return nil
        case .left: return "left"
        case .center: return "center"
        case .right: return "right"
        case .justified: return "both"
        case .distributed: return "distribute"
        }
    }

    func effectiveValue(original: String?) -> String? {
        encodedValue ?? Self.canonical(original)
    }

    func changedValue(original: String?) -> String? {
        guard let encodedValue else { return nil }
        return Self.canonical(original) == encodedValue ? nil : encodedValue
    }

    static func canonical(_ value: String?) -> String? {
        guard let value else { return nil }
        switch value {
        case "start": return "left"
        case "end": return "right"
        default: return value
        }
    }
}

enum LineSpacingEditChoice: String, CaseIterable, Identifiable {
    case unchanged
    case auto
    case exact
    case atLeast

    var id: String { rawValue }

    var label: String {
        switch self {
        case .unchanged: return "不修改"
        case .auto: return "倍数"
        case .exact: return "固定值"
        case .atLeast: return "最小值"
        }
    }

    var encodedValue: String? {
        self == .unchanged ? nil : rawValue
    }

    static func canonical(_ rule: String?, spacing: Double?) -> String? {
        if rule == nil, spacing != nil { return "auto" }
        return rule
    }
}

enum ParagraphIndentUnit: String, CaseIterable, Identifiable {
    case characters
    case points

    var id: String { rawValue }
    var label: String { self == .characters ? "字符" : "pt" }
    var fullLabel: String { self == .characters ? "字符" : "磅" }
}

enum SpecialIndentEditChoice: String, CaseIterable, Identifiable {
    case unchanged
    case none
    case firstLine
    case hanging

    var id: String { rawValue }

    var label: String {
        switch self {
        case .unchanged: return "不修改"
        case .none: return "无"
        case .firstLine: return "首行缩进"
        case .hanging: return "悬挂缩进"
        }
    }

    var requiresValue: Bool {
        self == .firstLine || self == .hanging
    }
}

struct ParagraphIndentMeasurement: Equatable {
    let value: Double
    let unit: ParagraphIndentUnit

    var displayText: String {
        "\(paragraphNumber(value)) \(unit.label)"
    }

    func previewPoints(fontSize: Double) -> Double {
        unit == .characters ? value * fontSize : value
    }
}

struct ParagraphLineEdit {
    let spacing: Double
    let rule: String
}

struct ParagraphSpecialIndentEdit {
    let firstLine: Double
    let hanging: Double
}

enum NumberingFormatEditChoice: String, CaseIterable, Identifiable {
    case unchanged, decimal, decimalZero, upperRoman, lowerRoman, upperLetter, lowerLetter
    case chineseCounting, chineseCountingThousand, chineseLegalSimplified, ideographTraditional
    var id: String { rawValue }
    var label: String {
        switch self {
        case .unchanged: return "不修改"
        case .decimal: return "1、2、3"
        case .decimalZero: return "01、02、03"
        case .upperRoman: return "I、II、III"
        case .lowerRoman: return "i、ii、iii"
        case .upperLetter: return "A、B、C"
        case .lowerLetter: return "a、b、c"
        case .chineseCounting: return "一、二、三"
        case .chineseCountingThousand: return "中文计数（千位）"
        case .chineseLegalSimplified: return "壹、贰、叁"
        case .ideographTraditional: return "传统中文计数"
        }
    }
}

enum NumberingRestartEditChoice: String, CaseIterable, Identifiable {
    case unchanged, restart, continueCount
    var id: String { rawValue }
    var label: String {
        switch self { case .unchanged: return "不修改"; case .restart: return "上级变化时重启"; case .continueCount: return "连续编号" }
    }
    var value: Bool? { self == .unchanged ? nil : self == .restart }
}

enum TableBorderEditChoice: String, CaseIterable, Identifiable {
    case unchanged, none = "nil", single, double, dotted, dashed, dotDash, dotDotDash
    var id: String { rawValue }
    var label: String {
        switch self {
        case .unchanged: return "不修改"; case .none: return "无边框"; case .single: return "实线"
        case .double: return "双线"; case .dotted: return "点线"; case .dashed: return "虚线"
        case .dotDash: return "点划线"; case .dotDotDash: return "双点划线"
        }
    }
}

enum BoldEditChoice: String, CaseIterable, Identifiable {
    case inherit
    case bold
    case regular

    var id: String { rawValue }

    var label: String {
        switch self {
        case .inherit: return "继承"
        case .bold: return "粗体"
        case .regular: return "常规"
        }
    }

    func effectiveValue(original: Bool?) -> Bool? {
        switch self {
        case .inherit: return original
        case .bold: return true
        case .regular: return false
        }
    }

    func changedValue(original: Bool?) -> Bool? {
        switch self {
        case .inherit: return nil
        case .bold: return original == true ? nil : true
        case .regular: return original == false ? nil : false
        }
    }
}

struct StyleEditDraft: Identifiable {
    let format: UsedFormat
    var fontEastAsiaOverride = ""
    var fontLatinOverride = ""
    var sizeOverride = ""
    var boldChoice: BoldEditChoice = .inherit
    var colorOverride = ""
    var alignmentChoice: ParagraphAlignmentEditChoice = .unchanged
    var spaceBeforeOverride = ""
    var spaceAfterOverride = ""
    var lineSpacingChoice: LineSpacingEditChoice = .unchanged
    var lineSpacingOverride = ""
    var indentUnit: ParagraphIndentUnit {
        didSet {
            guard indentUnit != oldValue else { return }
            leftIndentOverride = ""
            rightIndentOverride = ""
            specialIndentChoice = .unchanged
            specialIndentOverride = ""
            indentUnitNotice = "输入单位已切换为\(indentUnit.fullLabel)。左、右及特殊缩进的本次输入已清空，请按新单位重新填写；原方案缩进保持不变。"
        }
    }
    var indentUnitNotice: String?
    var leftIndentOverride = ""
    var rightIndentOverride = ""
    var specialIndentChoice: SpecialIndentEditChoice = .unchanged
    var specialIndentOverride = ""
    var tableFillOverride = ""
    var tableAccentOverride = ""
    var numberingFormatChoice: NumberingFormatEditChoice = .unchanged
    var numberingPatternOverride = ""
    var numberingStartOverride = ""
    var numberingRestartChoice: NumberingRestartEditChoice = .unchanged
    var tableBorderChoice: TableBorderEditChoice = .unchanged
    var tableBorderColorOverride = ""
    var tableBorderWidthOverride = ""
    var tableMarginTopOverride = ""
    var tableMarginBottomOverride = ""
    var tableMarginLeftOverride = ""
    var tableMarginRightOverride = ""

    init(format: UsedFormat) {
        self.format = format
        indentUnit = Self.preferredIndentUnit(for: format)
    }

    var id: String { format.id }
    var isTable: Bool { format.type == "table" }
    var isOptionalTableCandidate: Bool {
        isTable && format.inferenceLabel == "可选表格方案"
    }
    var supportsTextFormatting: Bool {
        format.type == "paragraph" || format.type == "character"
    }
    var supportsParagraphFormatting: Bool { format.type == "paragraph" }
    var supportsNumbering: Bool {
        supportsParagraphFormatting && format.outlineLevel != nil && format.numbered && format.numberingLevel != nil
    }

    var effectiveFontEastAsia: String? {
        normalizedText(fontEastAsiaOverride) ?? format.fontEastAsia
    }

    var effectiveFontLatin: String? {
        normalizedText(fontLatinOverride) ?? format.fontLatin
    }

    var effectiveSize: Double? {
        parsedSize(sizeOverride) ?? format.sizePt
    }

    var effectiveBold: Bool? {
        boldChoice.effectiveValue(original: format.bold)
    }

    var effectiveColorHex: String? {
        normalizedColor(colorOverride) ?? normalizedColor(format.colorHex ?? "")
    }

    var effectiveAlignment: String? {
        alignmentChoice.effectiveValue(original: format.alignment)
    }

    var effectiveSpaceBeforePt: Double? {
        parsedNumber(spaceBeforeOverride) ?? format.spaceBeforePt
    }

    var effectiveSpaceAfterPt: Double? {
        parsedNumber(spaceAfterOverride) ?? format.spaceAfterPt
    }

    var effectiveLineRule: String? {
        lineSpacingChoice.encodedValue ?? LineSpacingEditChoice.canonical(
            format.lineRule,
            spacing: format.lineSpacing
        )
    }

    var effectiveLineSpacing: Double? {
        parsedNumber(lineSpacingOverride) ?? format.lineSpacing
    }

    var effectiveLeftIndent: ParagraphIndentMeasurement? {
        if let value = parsedNumber(leftIndentOverride) {
            return ParagraphIndentMeasurement(value: value, unit: indentUnit)
        }
        return Self.preferredMeasurement(
            chars: format.leftIndentChars,
            points: format.leftIndentPt
        )
    }

    var effectiveRightIndent: ParagraphIndentMeasurement? {
        if let value = parsedNumber(rightIndentOverride) {
            return ParagraphIndentMeasurement(value: value, unit: indentUnit)
        }
        return Self.preferredMeasurement(
            chars: format.rightIndentChars,
            points: format.rightIndentPt
        )
    }

    var originalSpecialIndentChoice: SpecialIndentEditChoice {
        if Self.hasNonzero(format.firstLineIndentChars) ||
            Self.hasNonzero(format.firstLineIndentPt) {
            return .firstLine
        }
        if Self.hasNonzero(format.hangingIndentChars) ||
            Self.hasNonzero(format.hangingIndentPt) {
            return .hanging
        }
        return .none
    }

    var effectiveSpecialIndentChoice: SpecialIndentEditChoice {
        specialIndentChoice == .unchanged
            ? originalSpecialIndentChoice
            : specialIndentChoice
    }

    var effectiveSpecialIndent: ParagraphIndentMeasurement? {
        switch specialIndentChoice {
        case .firstLine, .hanging:
            guard let value = parsedNumber(specialIndentOverride) else { return nil }
            return ParagraphIndentMeasurement(value: value, unit: indentUnit)
        case .none:
            return nil
        case .unchanged:
            switch originalSpecialIndentChoice {
            case .firstLine:
                return Self.preferredMeasurement(
                    chars: format.firstLineIndentChars,
                    points: format.firstLineIndentPt
                )
            case .hanging:
                return Self.preferredMeasurement(
                    chars: format.hangingIndentChars,
                    points: format.hangingIndentPt
                )
            case .none, .unchanged:
                return nil
            }
        }
    }

    var effectiveTableFillHex: String? {
        normalizedColor(tableFillOverride) ?? normalizedColor(format.tableFillHex ?? "")
    }

    var effectiveTableAccentHex: String? {
        normalizedColor(tableAccentOverride) ?? normalizedColor(format.tableAccentHex ?? "")
    }

    var validationError: String? {
        guard isTable || supportsTextFormatting else { return nil }
        if supportsTextFormatting {
            for (label, value) in [
                ("中文字体", fontEastAsiaOverride),
                ("西文字体", fontLatinOverride)
            ] {
                let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                if trimmed.count > 127 {
                    return "\(label)名称最多允许 127 个字符。"
                }
                if trimmed.unicodeScalars.contains(where: {
                    CharacterSet.controlCharacters.contains($0)
                }) {
                    return "\(label)名称不能包含控制字符。"
                }
            }
            if !sizeOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                guard let size = parsedSize(sizeOverride),
                      size >= 5,
                      size <= 200,
                      (size * 2).rounded() == size * 2 else {
                    return "字号需要在 5–200 pt 之间，并以 0.5 pt 递增。"
                }
            }
            if !colorOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
               normalizedColor(colorOverride) == nil {
                return "文字颜色请输入 6 位十六进制色值，例如 165D52。"
            }
        }
        if supportsParagraphFormatting {
            if let error = validateNumber(
                spaceBeforeOverride,
                label: "段前间距",
                range: 0...1584,
                scale: 20,
                unit: "pt"
            ) { return error }
            if let error = validateNumber(
                spaceAfterOverride,
                label: "段后间距",
                range: 0...1584,
                scale: 20,
                unit: "pt"
            ) { return error }

            if lineSpacingChoice != .unchanged,
               lineSpacingOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                return "选择新的行距类型后，请填写行距值。"
            }
            if !lineSpacingOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                let rule = lineSpacingChoice.encodedValue ??
                    LineSpacingEditChoice.canonical(
                        format.lineRule,
                        spacing: format.lineSpacing
                    ) ?? "auto"
                if rule == "auto" {
                    if let error = validateNumber(
                        lineSpacingOverride,
                        label: "倍数行距",
                        range: 0.5...10,
                        scale: 100,
                        unit: "倍"
                    ) { return error }
                } else if let error = validateNumber(
                    lineSpacingOverride,
                    label: rule == "exact" ? "固定行距" : "最小行距",
                    range: 1...1584,
                    scale: 20,
                    unit: "pt"
                ) { return error }
            }

            let sideRange: ClosedRange<Double> = indentUnit == .characters
                ? -100...100
                : -1584...1584
            let positiveRange: ClosedRange<Double> = indentUnit == .characters
                ? 0...100
                : 0...1584
            let scale = indentUnit == .characters ? 100.0 : 20.0
            if let error = validateNumber(
                leftIndentOverride,
                label: "左缩进",
                range: sideRange,
                scale: scale,
                unit: indentUnit.label
            ) { return error }
            if let error = validateNumber(
                rightIndentOverride,
                label: "右缩进",
                range: sideRange,
                scale: scale,
                unit: indentUnit.label
            ) { return error }
            if specialIndentChoice.requiresValue {
                if specialIndentOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    return "请选择首行或悬挂缩进后填写缩进值。"
                }
                if let error = validateNumber(
                    specialIndentOverride,
                    label: specialIndentChoice == .firstLine ? "首行缩进" : "悬挂缩进",
                    range: positiveRange,
                    scale: scale,
                    unit: indentUnit.label
                ) { return error }
            }
        }
        if isTable {
            if !tableFillOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
               normalizedColor(tableFillOverride) == nil {
                return "表格底色请输入 6 位十六进制色值，例如 F7F7F7。"
            }
            if !tableAccentOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
               normalizedColor(tableAccentOverride) == nil {
                return "首行强调色请输入 6 位十六进制色值，例如 165D52。"
            }
            if normalizedText(tableBorderColorOverride) != nil, normalizedColor(tableBorderColorOverride) == nil {
                return "边框颜色请输入 6 位十六进制色值。"
            }
            if let error = validateNumber(tableBorderWidthOverride, label: "边框宽度", range: 0.25...12, scale: 8, unit: "pt") { return error }
            for (label, value) in [("上边距", tableMarginTopOverride), ("下边距", tableMarginBottomOverride), ("左边距", tableMarginLeftOverride), ("右边距", tableMarginRightOverride)] {
                if let error = validateNumber(value, label: label, range: 0...1584, scale: 20, unit: "pt") { return error }
            }
        }
        if supportsNumbering {
            if let start = normalizedText(numberingStartOverride),
               Int(start).map({ !(1...32767).contains($0) }) ?? true {
                return "编号起始值需要填写 1–32767 的整数。"
            }
            if let pattern = normalizedText(numberingPatternOverride) {
                let maxLevel = (format.numberingLevel ?? 0) + 1
                guard pattern.count <= 120, !pattern.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else {
                    return "编号格式最多 120 个字符，不能包含控制字符。"
                }
                let regex = try! NSRegularExpression(pattern: "%([0-9]+)")
                let matches = regex.matches(in: pattern, range: NSRange(pattern.startIndex..., in: pattern))
                let levels = matches.compactMap { Range($0.range(at: 1), in: pattern).flatMap { Int(pattern[$0]) } }
                let stripped = regex.stringByReplacingMatches(in: pattern, range: NSRange(pattern.startIndex..., in: pattern), withTemplate: "")
                if stripped.contains("%") || levels.contains(where: { $0 < 1 || $0 > maxLevel }) || !levels.contains(maxLevel) {
                    return "编号格式需要包含 %\(maxLevel)，只能引用 %1 至 %\(maxLevel)；标点可直接填写。"
                }
            }
            if format.numberingLevel == 0, numberingRestartChoice == .restart {
                return "最高层级不能设置为随上级重启。"
            }
        }
        return nil
    }

    var payload: StyleEditPayload? {
        guard validationError == nil else { return nil }

        let eastAsia = changedText(
            override: fontEastAsiaOverride,
            original: format.fontEastAsia
        )
        let latin = changedText(
            override: fontLatinOverride,
            original: format.fontLatin
        )
        let size = changedSize(override: sizeOverride, original: format.sizePt)
        let textColor = changedColor(
            override: colorOverride,
            original: format.colorHex
        )
        let tableFill = changedColor(
            override: tableFillOverride,
            original: format.tableFillHex
        )
        let tableAccent = changedColor(
            override: tableAccentOverride,
            original: format.tableAccentHex
        )
        let lineEdit = changedLineEdit
        let leftIndent = changedNumber(
            override: leftIndentOverride,
            original: indentUnit == .characters
                ? format.leftIndentChars
                : format.leftIndentPt
        )
        let rightIndent = changedNumber(
            override: rightIndentOverride,
            original: indentUnit == .characters
                ? format.rightIndentChars
                : format.rightIndentPt
        )
        let specialIndent = changedSpecialIndent
        var payload = StyleEditPayload(
            styleID: format.styleID,
            fontEastAsia: supportsTextFormatting ? eastAsia : nil,
            fontLatin: supportsTextFormatting ? latin : nil,
            sizePt: supportsTextFormatting ? size : nil,
            bold: supportsTextFormatting
                ? boldChoice.changedValue(original: format.bold)
                : nil,
            colorHex: supportsTextFormatting ? textColor : nil,
            alignment: supportsParagraphFormatting
                ? alignmentChoice.changedValue(original: format.alignment)
                : nil,
            spaceBeforePt: supportsParagraphFormatting
                ? changedNumber(
                    override: spaceBeforeOverride,
                    original: format.spaceBeforePt
                )
                : nil,
            spaceAfterPt: supportsParagraphFormatting
                ? changedNumber(
                    override: spaceAfterOverride,
                    original: format.spaceAfterPt
                )
                : nil,
            lineSpacing: supportsParagraphFormatting ? lineEdit?.spacing : nil,
            lineRule: supportsParagraphFormatting ? lineEdit?.rule : nil,
            leftIndentPt: supportsParagraphFormatting && indentUnit == .points
                ? leftIndent
                : nil,
            rightIndentPt: supportsParagraphFormatting && indentUnit == .points
                ? rightIndent
                : nil,
            firstLineIndentPt: supportsParagraphFormatting && indentUnit == .points
                ? specialIndent?.firstLine
                : nil,
            hangingIndentPt: supportsParagraphFormatting && indentUnit == .points
                ? specialIndent?.hanging
                : nil,
            leftIndentChars: supportsParagraphFormatting && indentUnit == .characters
                ? leftIndent
                : nil,
            rightIndentChars: supportsParagraphFormatting && indentUnit == .characters
                ? rightIndent
                : nil,
            firstLineIndentChars: supportsParagraphFormatting && indentUnit == .characters
                ? specialIndent?.firstLine
                : nil,
            hangingIndentChars: supportsParagraphFormatting && indentUnit == .characters
                ? specialIndent?.hanging
                : nil,
            tableFillHex: isTable ? tableFill : nil,
            tableAccentHex: isTable ? tableAccent : nil
        )
        if supportsNumbering {
            payload.numberingFormat = numberingFormatChoice == .unchanged || numberingFormatChoice.rawValue == format.numberingFormat ? nil : numberingFormatChoice.rawValue
            payload.numberingPattern = changedText(override: numberingPatternOverride, original: format.numberingPattern)
            payload.numberingStart = normalizedText(numberingStartOverride).flatMap(Int.init).flatMap { $0 == format.numberingStart ? nil : $0 }
            payload.numberingRestart = numberingRestartChoice.value.flatMap { $0 == format.numberingRestart ? nil : $0 }
        }
        if isTable {
            payload.tableBorderStyle = tableBorderChoice == .unchanged || tableBorderChoice.rawValue == format.tableBorderStyle ? nil : tableBorderChoice.rawValue
            payload.tableBorderColorHex = changedColor(override: tableBorderColorOverride, original: format.tableBorderColorHex)
            payload.tableBorderWidthPt = changedNumber(override: tableBorderWidthOverride, original: format.tableBorderWidthPt)
            payload.tableCellMarginTopPt = changedNumber(override: tableMarginTopOverride, original: format.tableCellMarginTopPt)
            payload.tableCellMarginBottomPt = changedNumber(override: tableMarginBottomOverride, original: format.tableCellMarginBottomPt)
            payload.tableCellMarginLeftPt = changedNumber(override: tableMarginLeftOverride, original: format.tableCellMarginLeftPt)
            payload.tableCellMarginRightPt = changedNumber(override: tableMarginRightOverride, original: format.tableCellMarginRightPt)
        }
        return payload.changedFieldCount > 0 ? payload : nil
    }

    var changedFieldCount: Int { payload?.changedFieldCount ?? 0 }
    var isEdited: Bool { changedFieldCount > 0 }
    var hasUserInput: Bool {
        [
            fontEastAsiaOverride,
            fontLatinOverride,
            sizeOverride,
            colorOverride,
            spaceBeforeOverride,
            spaceAfterOverride,
            lineSpacingOverride,
            leftIndentOverride,
            rightIndentOverride,
            tableFillOverride,
            tableAccentOverride
            , numberingPatternOverride, numberingStartOverride, tableBorderColorOverride,
            tableBorderWidthOverride, tableMarginTopOverride, tableMarginBottomOverride,
            tableMarginLeftOverride, tableMarginRightOverride
        ].contains(where: {
            !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }) || boldChoice != .inherit ||
            alignmentChoice != .unchanged ||
            lineSpacingChoice != .unchanged ||
            specialIndentChoice != .unchanged ||
            numberingFormatChoice != .unchanged || numberingRestartChoice != .unchanged ||
            tableBorderChoice != .unchanged ||
            (specialIndentChoice.requiresValue &&
                !specialIndentOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
    }

    mutating func reset() {
        fontEastAsiaOverride = ""
        fontLatinOverride = ""
        sizeOverride = ""
        boldChoice = .inherit
        colorOverride = ""
        alignmentChoice = .unchanged
        spaceBeforeOverride = ""
        spaceAfterOverride = ""
        lineSpacingChoice = .unchanged
        lineSpacingOverride = ""
        indentUnit = Self.preferredIndentUnit(for: format)
        leftIndentOverride = ""
        rightIndentOverride = ""
        specialIndentChoice = .unchanged
        specialIndentOverride = ""
        tableFillOverride = ""
        tableAccentOverride = ""
        indentUnitNotice = nil
        numberingFormatChoice = .unchanged
        numberingPatternOverride = ""
        numberingStartOverride = ""
        numberingRestartChoice = .unchanged
        tableBorderChoice = .unchanged
        tableBorderColorOverride = ""
        tableBorderWidthOverride = ""
        tableMarginTopOverride = ""
        tableMarginBottomOverride = ""
        tableMarginLeftOverride = ""
        tableMarginRightOverride = ""
    }

    private func changedText(override: String, original: String?) -> String? {
        guard let value = normalizedText(override) else { return nil }
        return value == original?.trimmingCharacters(in: .whitespacesAndNewlines)
            ? nil
            : value
    }

    private func changedSize(override: String, original: Double?) -> Double? {
        guard let value = parsedSize(override) else { return nil }
        if let original, abs(original - value) < 0.0001 { return nil }
        return value
    }

    private func changedNumber(override: String, original: Double?) -> Double? {
        guard let value = parsedNumber(override) else { return nil }
        if let original, abs(original - value) < 0.0001 { return nil }
        return value
    }

    private var changedLineEdit: ParagraphLineEdit? {
        let hasValue = !lineSpacingOverride
            .trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        guard hasValue || lineSpacingChoice != .unchanged,
              let value = parsedNumber(lineSpacingOverride) else {
            return nil
        }
        let rule = lineSpacingChoice.encodedValue ??
            LineSpacingEditChoice.canonical(
                format.lineRule,
                spacing: format.lineSpacing
            ) ?? "auto"
        let originalRule = LineSpacingEditChoice.canonical(
            format.lineRule,
            spacing: format.lineSpacing
        )
        if rule == originalRule,
           let originalSpacing = format.lineSpacing,
           abs(originalSpacing - value) < 0.0001 {
            return nil
        }
        return ParagraphLineEdit(spacing: value, rule: rule)
    }

    private var changedSpecialIndent: ParagraphSpecialIndentEdit? {
        switch specialIndentChoice {
        case .unchanged:
            return nil
        case .none:
            guard originalSpecialIndentChoice != .none else { return nil }
            return ParagraphSpecialIndentEdit(firstLine: 0, hanging: 0)
        case .firstLine, .hanging:
            guard let value = parsedNumber(specialIndentOverride) else { return nil }
            let originalValue: Double?
            if indentUnit == .characters {
                originalValue = specialIndentChoice == .firstLine
                    ? format.firstLineIndentChars
                    : format.hangingIndentChars
            } else {
                originalValue = specialIndentChoice == .firstLine
                    ? format.firstLineIndentPt
                    : format.hangingIndentPt
            }
            if originalSpecialIndentChoice == specialIndentChoice,
               let originalValue,
               abs(originalValue - value) < 0.0001 {
                return nil
            }
            return ParagraphSpecialIndentEdit(
                firstLine: specialIndentChoice == .firstLine ? value : 0,
                hanging: specialIndentChoice == .hanging ? value : 0
            )
        }
    }

    private func changedColor(override: String, original: String?) -> String? {
        guard let value = normalizedColor(override) else { return nil }
        return value == normalizedColor(original ?? "") ? nil : value
    }

    private func normalizedText(_ value: String) -> String? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func parsedSize(_ value: String) -> Double? {
        parsedNumber(value)
    }

    private func parsedNumber(_ value: String) -> Double? {
        let normalized = value
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: ",", with: ".")
        guard !normalized.isEmpty,
              let parsed = Double(normalized),
              parsed.isFinite else { return nil }
        return parsed
    }

    private func normalizedColor(_ value: String) -> String? {
        normalizedHexColor(value)
    }

    private func validateNumber(
        _ raw: String,
        label: String,
        range: ClosedRange<Double>,
        scale: Double,
        unit: String
    ) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        guard let value = parsedNumber(raw), range.contains(value) else {
            return "\(label)需要在 \(paragraphNumber(range.lowerBound))–\(paragraphNumber(range.upperBound)) \(unit) 之间。"
        }
        guard abs(value * scale - (value * scale).rounded()) < 0.0001 else {
            let increment = 1 / scale
            return "\(label)请以 \(paragraphNumber(increment)) \(unit) 递增。"
        }
        return nil
    }

    private static func preferredIndentUnit(for format: UsedFormat) -> ParagraphIndentUnit {
        if [
            format.leftIndentChars,
            format.rightIndentChars,
            format.firstLineIndentChars,
            format.hangingIndentChars
        ].contains(where: { $0 != nil }) {
            return .characters
        }
        if [
            format.leftIndentPt,
            format.rightIndentPt,
            format.firstLineIndentPt,
            format.hangingIndentPt
        ].contains(where: { $0 != nil }) {
            return .points
        }
        return .characters
    }

    private static func preferredMeasurement(
        chars: Double?,
        points: Double?
    ) -> ParagraphIndentMeasurement? {
        if let chars {
            return ParagraphIndentMeasurement(value: chars, unit: .characters)
        }
        if let points {
            return ParagraphIndentMeasurement(value: points, unit: .points)
        }
        return nil
    }

    private static func hasNonzero(_ value: Double?) -> Bool {
        guard let value else { return false }
        return abs(value) >= 0.0001
    }
}
