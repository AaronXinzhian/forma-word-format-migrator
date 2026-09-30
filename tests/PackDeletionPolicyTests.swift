/**
 * [INPUT]: 依赖 AppKit, Foundation
 * [OUTPUT]: 提供 PackDeletionPolicyTests
 * [POS]: 验证 Mac 格式库删除的路径、链接和扩展名边界
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
import AppKit
import Foundation

private enum DeletionTestFailure: LocalizedError {
    case failed(String)

    var errorDescription: String? {
        switch self {
        case .failed(let message): return message
        }
    }
}

@main
struct PackDeletionPolicyTests {
    static func main() throws {
        let fileManager = FileManager.default
        let testRoot = fileManager.temporaryDirectory.appendingPathComponent(
            "word-format-library-delete-tests-\(UUID().uuidString)",
            isDirectory: true
        )
        let library = testRoot.appendingPathComponent("style-packs", isDirectory: true)
        try fileManager.createDirectory(at: library, withIntermediateDirectories: true)
        defer { try? fileManager.removeItem(at: testRoot) }

        let validURL = library.appendingPathComponent("valid.wfstyle")
        try Data("test-format-pack".utf8).write(to: validURL)
        let validPack = try makePack(id: "shared-id", path: validURL.path)
        let validResult = try PackDeletionPolicy.validatedURL(
            for: validPack,
            currentPacks: [validPack],
            libraryDirectory: library
        )
        try require(
            validResult.path == validURL.path,
            "格式库根目录中的普通 .wfstyle 文件应通过校验"
        )

        let duplicateURL = library.appendingPathComponent("duplicate-id.wfstyle")
        try Data("another-format-pack".utf8).write(to: duplicateURL)
        let duplicatePack = try makePack(id: "shared-id", path: duplicateURL.path)
        let duplicateResult = try PackDeletionPolicy.validatedURL(
            for: duplicatePack,
            currentPacks: [validPack, duplicatePack],
            libraryDirectory: library
        )
        try require(
            duplicateResult.path == duplicateURL.path,
            "重复 manifest id 时必须按精确 packPath 识别"
        )
        try expectRejection("同 id 但不在当前列表中的路径必须拒绝") {
            let unknownURL = library.appendingPathComponent("unknown.wfstyle")
            try Data("unknown".utf8).write(to: unknownURL)
            let unknownPack = try makePack(id: "shared-id", path: unknownURL.path)
            _ = try PackDeletionPolicy.validatedURL(
                for: unknownPack,
                currentPacks: [validPack, duplicatePack],
                libraryDirectory: library
            )
        }

        let outsideURL = testRoot.appendingPathComponent("outside.wfstyle")
        try Data("outside".utf8).write(to: outsideURL)
        let outsidePack = try makePack(id: "outside", path: outsideURL.path)
        try expectRejection("格式库外部文件必须拒绝") {
            _ = try PackDeletionPolicy.validatedURL(
                for: outsidePack,
                currentPacks: [outsidePack],
                libraryDirectory: library
            )
        }

        let nestedDirectory = library.appendingPathComponent("nested", isDirectory: true)
        try fileManager.createDirectory(at: nestedDirectory, withIntermediateDirectories: true)
        let nestedURL = nestedDirectory.appendingPathComponent("nested.wfstyle")
        try Data("nested".utf8).write(to: nestedURL)
        let nestedPack = try makePack(id: "nested", path: nestedURL.path)
        try expectRejection("格式库子目录中的文件必须拒绝") {
            _ = try PackDeletionPolicy.validatedURL(
                for: nestedPack,
                currentPacks: [nestedPack],
                libraryDirectory: library
            )
        }

        let disguisedDirectory = library.appendingPathComponent("folder.wfstyle", isDirectory: true)
        try fileManager.createDirectory(at: disguisedDirectory, withIntermediateDirectories: true)
        let disguisedPack = try makePack(id: "folder", path: disguisedDirectory.path)
        try expectRejection("伪装成 .wfstyle 的目录必须拒绝") {
            _ = try PackDeletionPolicy.validatedURL(
                for: disguisedPack,
                currentPacks: [disguisedPack],
                libraryDirectory: library
            )
        }

        let symlinkURL = library.appendingPathComponent("outside-link.wfstyle")
        try fileManager.createSymbolicLink(
            atPath: symlinkURL.path,
            withDestinationPath: outsideURL.path
        )
        let symlinkPack = try makePack(id: "symlink", path: symlinkURL.path)
        try expectRejection("指向格式库外部的符号链接必须拒绝") {
            _ = try PackDeletionPolicy.validatedURL(
                for: symlinkPack,
                currentPacks: [symlinkPack],
                libraryDirectory: library
            )
        }

        try require(
            PackDeletionPolicy.fallbackIndex(afterDeleting: 0, remainingCount: 2) == 0,
            "删除中间项后应优先选择原位置的下一项"
        )
        try require(
            PackDeletionPolicy.fallbackIndex(afterDeleting: 2, remainingCount: 2) == 1,
            "删除末项后应选择上一项"
        )
        try require(
            PackDeletionPolicy.fallbackIndex(afterDeleting: 0, remainingCount: 0) == nil,
            "删除唯一项后不应保留选择"
        )

        let trashableURL = library.appendingPathComponent(
            "trash-roundtrip-\(UUID().uuidString).wfstyle"
        )
        try Data("trash-roundtrip".utf8).write(to: trashableURL)
        let trashablePack = try makePack(id: "trash-roundtrip", path: trashableURL.path)
        let validatedTrashableURL = try PackDeletionPolicy.validatedURL(
            for: trashablePack,
            currentPacks: [trashablePack],
            libraryDirectory: library
        )
        var trashedURL: NSURL?
        try fileManager.trashItem(at: validatedTrashableURL, resultingItemURL: &trashedURL)
        try require(!fileManager.fileExists(atPath: trashableURL.path), "文件应从格式库中消失")
        guard let trashedURL = trashedURL as URL? else {
            throw DeletionTestFailure.failed("系统没有返回废纸篓位置")
        }
        try require(fileManager.fileExists(atPath: trashedURL.path), "文件应存在于废纸篓")
        try fileManager.moveItem(at: trashedURL, to: trashableURL)
        try require(fileManager.fileExists(atPath: trashableURL.path), "废纸篓文件应可恢复")

        try runParagraphEditorTests()
        try runFontCatalogTests()

        print("PackDeletionPolicyTests: deletion, paragraph editor, and font catalog checks passed")
    }

    private static func runParagraphEditorTests() throws {
        let legacy = try makeUsedFormat()
        try require(legacy.fontLatinAliases == nil, "旧格式 JSON 缺少西文字体别名时应解码为 nil")
        try require(legacy.fontEastAsiaAliases == nil, "旧格式 JSON 缺少中文字体别名时应解码为 nil")
        try require(legacy.leftIndentChars == nil, "旧格式 JSON 缺少字符缩进时应解码为 nil")
        try require(legacy.leftIndentPt == nil, "旧格式 JSON 缺少磅缩进时应解码为 nil")
        try require(legacy.alignment == nil, "旧格式 JSON 缺少对齐时应继续兼容")
        let legacyDraft = StyleEditDraft(format: legacy)
        try require(legacyDraft.payload == nil, "未编辑的旧格式不应产生修改请求")
        try require(
            legacyDraft.indentUnit == .characters,
            "没有缩进元数据时应优先使用字符单位"
        )

        let modern = try makeUsedFormat(overrides: [
            "alignment": "center",
            "space_before_pt": 6.0,
            "space_after_pt": 8.0,
            "line_spacing": 1.25,
            "line_rule": "auto",
            "left_indent_chars": 1.0,
            "right_indent_chars": 0.0,
            "first_line_indent_chars": 2.0,
            "hanging_indent_chars": 0.0
        ])
        try require(modern.lineSpacing == 1.25, "新格式 JSON 应保留两位小数行距")
        try require(modern.firstLineIndentChars == 2, "字符缩进应使用真实字符数")

        var edited = StyleEditDraft(format: modern)
        edited.alignmentChoice = .justified
        edited.spaceBeforeOverride = "12"
        edited.spaceAfterOverride = "0"
        edited.lineSpacingChoice = .auto
        edited.lineSpacingOverride = "1,5"
        edited.leftIndentOverride = "0"
        edited.rightIndentOverride = "-1.25"
        edited.specialIndentChoice = .firstLine
        edited.specialIndentOverride = "3"
        try require(edited.validationError == nil, "合法段落修改应通过 Swift 校验")
        guard let payload = edited.payload else {
            throw DeletionTestFailure.failed("合法段落修改应生成请求")
        }
        try require(payload.alignment == "both", "两端对齐应编码为 both")
        try require(payload.spaceBeforePt == 12, "段前间距应进入请求")
        try require(payload.spaceAfterPt == 0, "显式零段后间距不能被遗漏")
        try require(payload.lineRule == "auto", "倍数行距必须携带 auto 规则")
        try require(payload.lineSpacing == 1.5, "逗号小数应规范化为行距数值")
        try require(payload.leftIndentChars == 0, "显式零左缩进不能被遗漏")
        try require(payload.rightIndentChars == -1.25, "负字符缩进应在范围内保留")
        try require(payload.firstLineIndentChars == 3, "首行缩进应使用字符数")
        try require(payload.hangingIndentChars == 0, "首行缩进应显式清零悬挂缩进")
        try require(payload.leftIndentPt == nil, "字符编辑不应同时发送磅缩进")

        let encoded = try JSONEncoder().encode(payload)
        guard let object = try JSONSerialization.jsonObject(with: encoded) as? [String: Any] else {
            throw DeletionTestFailure.failed("段落修改请求应编码为 JSON 对象")
        }
        try require(
            (object["space_after_pt"] as? NSNumber)?.doubleValue == 0,
            "JSON 编码必须保留显式零段后间距"
        )
        try require(
            (object["hanging_indent_chars"] as? NSNumber)?.doubleValue == 0,
            "JSON 编码必须保留互斥缩进的显式零"
        )
        try require(object["left_indent_pt"] == nil, "nil 字段应从修改 JSON 中省略")

        var hanging = StyleEditDraft(format: modern)
        hanging.specialIndentChoice = .hanging
        hanging.specialIndentOverride = "1.5"
        try require(hanging.validationError == nil, "合法悬挂缩进应通过校验")
        try require(
            hanging.payload?.firstLineIndentChars == 0 &&
                hanging.payload?.hangingIndentChars == 1.5,
            "悬挂缩进应显式清零首行缩进"
        )

        var noSpecialIndent = StyleEditDraft(format: modern)
        noSpecialIndent.specialIndentChoice = .none
        try require(
            noSpecialIndent.payload?.firstLineIndentChars == 0 &&
                noSpecialIndent.payload?.hangingIndentChars == 0,
            "选择无特殊缩进应将首行和悬挂都清零"
        )

        var exactLine = StyleEditDraft(format: modern)
        exactLine.lineSpacingChoice = .exact
        exactLine.lineSpacingOverride = "20"
        try require(exactLine.validationError == nil, "固定 20 pt 行距应通过校验")
        try require(
            exactLine.payload?.lineRule == "exact" && exactLine.payload?.lineSpacing == 20,
            "行距规则和值必须成对发送"
        )

        var invalidLine = StyleEditDraft(format: modern)
        invalidLine.lineSpacingChoice = .auto
        invalidLine.lineSpacingOverride = "0.333"
        try require(invalidLine.validationError != nil, "倍数行距应限制为 0.01 递增")

        var invalidSpacing = StyleEditDraft(format: modern)
        invalidSpacing.spaceBeforeOverride = "-1"
        try require(invalidSpacing.validationError != nil, "段前间距不能为负数")

        var invalidSpecial = StyleEditDraft(format: modern)
        invalidSpecial.specialIndentChoice = .firstLine
        invalidSpecial.specialIndentOverride = "1.001"
        try require(invalidSpecial.validationError != nil, "字符缩进应限制为 0.01 递增")

        let startAligned = try makeUsedFormat(overrides: ["alignment": "start"])
        var normalizedAlignment = StyleEditDraft(format: startAligned)
        normalizedAlignment.alignmentChoice = .left
        try require(
            normalizedAlignment.payload == nil,
            "start 与 left 应视为相同对齐，避免生成无意义修改"
        )

        let pointsOnly = try makeUsedFormat(overrides: ["left_indent_pt": 24.0])
        var pointsDraft = StyleEditDraft(format: pointsOnly)
        try require(pointsDraft.indentUnit == .points, "仅有磅缩进时应默认使用磅单位")
        pointsDraft.leftIndentOverride = "12.05"
        try require(pointsDraft.validationError == nil, "磅缩进应允许 0.05 pt 递增")
        try require(pointsDraft.payload?.leftIndentPt == 12.05, "磅缩进应进入 pt 字段")
        try require(pointsDraft.payload?.leftIndentChars == nil, "磅缩进不应发送字符字段")

        edited.reset()
        try require(!edited.hasUserInput, "重置后不应保留段落输入或选择")
        try require(edited.payload == nil, "重置后不应产生修改请求")
        try require(edited.indentUnit == .characters, "重置后应恢复原格式首选缩进单位")
    }

    private static func runFontCatalogTests() throws {
        let records = [
            InstalledFontFaceRecord(
                familyName: "Times New Roman",
                localizedFamilyName: "泰晤士新罗马",
                postScriptName: "TimesNewRomanPSMT",
                displayName: "Times New Roman Regular",
                faceName: "Regular"
            ),
            InstalledFontFaceRecord(
                familyName: "Times New Roman",
                localizedFamilyName: "泰晤士新罗马",
                postScriptName: "TimesNewRomanPS-BoldMT",
                displayName: "Times New Roman Bold",
                faceName: "Bold",
                weight: 9,
                traitsRawValue: NSFontTraitMask.boldFontMask.rawValue
            ),
            InstalledFontFaceRecord(
                familyName: "Songti SC",
                localizedFamilyName: "宋体-简",
                postScriptName: "STSongti-SC-Regular",
                displayName: "Songti SC Regular",
                faceName: "Regular"
            ),
            InstalledFontFaceRecord(
                familyName: "Conflict One",
                postScriptName: "ConflictOne-Regular",
                displayName: "Shared Alias"
            ),
            InstalledFontFaceRecord(
                familyName: "Conflict Two",
                postScriptName: "ConflictTwo-Regular",
                displayName: "Shared-Alias"
            )
        ]
        let catalog = InstalledFontCatalog(records: records)

        let familyMatch = catalog.match(name: "Times New Roman")
        try require(familyMatch.kind == .installed, "字体 family 原名应识别为已安装")
        try require(
            familyMatch.postScriptName == "TimesNewRomanPSMT",
            "family 预览应选常规 PostScript 字体"
        )

        let postScriptMatch = catalog.match(name: "TimesNewRomanPS-BoldMT")
        try require(postScriptMatch.kind == .installed, "PostScript 原名应识别为已安装")
        try require(
            postScriptMatch.postScriptName == "TimesNewRomanPS-BoldMT",
            "精确 PostScript 查询应保留对应字形"
        )

        let localizedMatch = catalog.match(name: "宋体-简")
        try require(localizedMatch.kind == .alias, "本地化名称应通过别名匹配")
        try require(
            localizedMatch.canonicalFamilyName == "Songti SC",
            "本地化名称应解析到规范 family 名"
        )

        let compactMatch = catalog.match(name: "TimesNewRoman")
        try require(
            compactMatch.canonicalFamilyName == "Times New Roman",
            "忽略空格的查询应匹配字体 family"
        )
        try require(
            catalog.search("STSongti").map(\.canonicalFamilyName) == ["Songti SC"],
            "搜索应匹配 PostScript 名"
        )
        try require(
            catalog.search("宋体").map(\.canonicalFamilyName) == ["Songti SC"],
            "搜索应匹配本地化名称"
        )

        let exactDisplayAlias = catalog.match(name: "Shared Alias")
        try require(
            exactDisplayAlias.kind == .alias &&
                exactDisplayAlias.canonicalFamilyName == "Conflict One",
            "唯一的精确 display 名应优先于宽松规范化结果"
        )

        let ambiguous = catalog.match(name: "SharedAlias")
        try require(ambiguous.kind == .ambiguous, "冲突别名不得静默选择字体")
        try require(
            ambiguous.candidateFamilyNames == ["Conflict One", "Conflict Two"],
            "冲突结果应列出全部候选 family"
        )

        let exactWithConflictingAliases = catalog.match(
            name: "Times New Roman",
            aliases: ["SharedAlias"]
        )
        try require(
            exactWithConflictingAliases.kind == .installed &&
                exactWithConflictingAliases.canonicalFamilyName == "Times New Roman",
            "原名唯一命中时，冲突的文档别名不得覆盖精确结果"
        )

        let templateAliasMatch = catalog.match(
            name: "Template Song Font",
            aliases: ["宋体-简"]
        )
        try require(
            templateAliasMatch.kind == .alias &&
                templateAliasMatch.canonicalFamilyName == "Songti SC",
            "未注册模板原名应允许通过文档别名解析"
        )
        try require(
            catalog.match(name: "SimSun").kind == .missing,
            "本机没有的模板字体必须保持未注册状态"
        )

        let first = try makeUsedFormat(overrides: [
            "font_latin": "TimesNewRomanPSMT",
            "font_latin_aliases": ["Times New Roman", "泰晤士新罗马"],
            "font_east_asia": "Template Song Font",
            "font_east_asia_aliases": ["宋体-简"]
        ])
        let second = try makeUsedFormat(overrides: [
            "style_id": "Heading2",
            "font_latin": "TimesNewRomanPSMT",
            "font_latin_aliases": ["Times New Roman"],
            "font_east_asia": "SimSun"
        ])
        let latinOptions = templateFontOptions(from: [first, second], role: .latin)
        try require(latinOptions.count == 1, "整份模板的重复字体应合并为一个选项")
        try require(
            Set(latinOptions[0].aliases) == Set(["Times New Roman", "泰晤士新罗马"]),
            "合并模板字体时应保留全部别名"
        )
        let eastAsiaOptions = templateFontOptions(from: [first, second], role: .eastAsia)
        try require(
            eastAsiaOptions.map(\.name) == ["SimSun", "Template Song Font"],
            "模板字体目录应包含整份模板使用过且本机可能未安装的字体"
        )
    }

    private static func makePack(id: String, path: String) throws -> PackManifest {
        let object: [String: Any] = [
            "id": id,
            "name": "临时格式",
            "used_formats": [],
            "used_style_count": 0,
            "manual_formatting": ["paragraph_count": 0, "run_count": 0],
            "document_summary": [
                "paragraph_count": 0,
                "run_count": 0,
                "table_count": 0,
                "section_count": 0
            ],
            "page_layout": [:],
            "pack_path": path
        ]
        let data = try JSONSerialization.data(withJSONObject: object)
        return try JSONDecoder().decode(PackManifest.self, from: data)
    }

    private static func makeUsedFormat(
        overrides: [String: Any] = [:]
    ) throws -> UsedFormat {
        var object: [String: Any] = [
            "style_id": "Heading1",
            "name": "标题 1",
            "type": "paragraph",
            "usage_count": 1,
            "sample": "标题示意",
            "numbered": false
        ]
        for (key, value) in overrides { object[key] = value }
        let data = try JSONSerialization.data(withJSONObject: object)
        return try JSONDecoder().decode(UsedFormat.self, from: data)
    }

    private static func require(_ condition: @autoclosure () -> Bool, _ message: String) throws {
        guard condition() else { throw DeletionTestFailure.failed(message) }
    }

    private static func expectRejection(_ message: String, operation: () throws -> Void) throws {
        do {
            try operation()
            throw DeletionTestFailure.failed(message)
        } catch is DeletionTestFailure {
            throw DeletionTestFailure.failed(message)
        } catch {
            return
        }
    }
}
