// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers, CoreText
// [OUTPUT]: 提供FontCatalog 中的类型与接口
// [POS]: Mac 原生终端 - 本机字体目录、模板字体别名与字体匹配
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers
import CoreText

// MARK: - Local font discovery and template font aliases

struct InstalledFontFaceRecord: Hashable {
    let familyName: String
    let localizedFamilyName: String?
    let postScriptName: String
    let displayName: String?
    let faceName: String?
    let weight: Int
    let traitsRawValue: UInt

    init(
        familyName: String,
        localizedFamilyName: String? = nil,
        postScriptName: String,
        displayName: String? = nil,
        faceName: String? = nil,
        weight: Int = 5,
        traitsRawValue: UInt = 0
    ) {
        self.familyName = familyName
        self.localizedFamilyName = localizedFamilyName
        self.postScriptName = postScriptName
        self.displayName = displayName
        self.faceName = faceName
        self.weight = weight
        self.traitsRawValue = traitsRawValue
    }
}

struct InstalledFontFamily: Hashable, Identifiable {
    let canonicalFamilyName: String
    let localizedFamilyNames: [String]
    let postScriptNames: [String]
    let displayNames: [String]
    let faceNames: [String]
    let preferredPostScriptName: String
    fileprivate let records: [InstalledFontFaceRecord]

    var id: String { fontStrictLookupKey(canonicalFamilyName) }

    var displayName: String {
        localizedFamilyNames.first(where: {
            fontStrictLookupKey($0) != fontStrictLookupKey(canonicalFamilyName)
        }) ?? canonicalFamilyName
    }

    var secondaryDescription: String {
        var values: [String] = []
        if displayName != canonicalFamilyName { values.append(canonicalFamilyName) }
        if preferredPostScriptName != canonicalFamilyName {
            values.append(preferredPostScriptName)
        }
        return values.joined(separator: " · ")
    }

    fileprivate var searchableNames: [String] {
        uniqueFontNames(
            [canonicalFamilyName] + localizedFamilyNames + postScriptNames +
                displayNames + faceNames
        )
    }

    fileprivate func exactPostScriptName(for rawName: String) -> String? {
        let key = fontStrictLookupKey(rawName)
        return postScriptNames.first { fontStrictLookupKey($0) == key }
    }
}

enum InstalledFontMatchKind: String, Equatable {
    case loading
    case inherited
    case installed
    case alias
    case ambiguous
    case missing
}

struct InstalledFontMatch: Equatable {
    let kind: InstalledFontMatchKind
    let canonicalFamilyName: String?
    let postScriptName: String?
    let candidateFamilyNames: [String]

    var isUsableForPreview: Bool {
        kind == .installed || kind == .alias
    }
}

struct InstalledFontCatalog {
    let isLoaded: Bool
    let families: [InstalledFontFamily]
    private let strictAliasIndex: [String: Set<String>]
    private let compactAliasIndex: [String: Set<String>]
    private let familiesByID: [String: InstalledFontFamily]

    init(records: [InstalledFontFaceRecord], isLoaded: Bool = true) {
        self.isLoaded = isLoaded
        var grouped: [String: [InstalledFontFaceRecord]] = [:]
        for record in records {
            let family = record.familyName.trimmingCharacters(in: .whitespacesAndNewlines)
            let postScript = record.postScriptName.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !family.isEmpty, !postScript.isEmpty else { continue }
            let normalizedRecord = InstalledFontFaceRecord(
                familyName: family,
                localizedFamilyName: normalizedFontName(record.localizedFamilyName),
                postScriptName: postScript,
                displayName: normalizedFontName(record.displayName),
                faceName: normalizedFontName(record.faceName),
                weight: record.weight,
                traitsRawValue: record.traitsRawValue
            )
            grouped[fontStrictLookupKey(family), default: []].append(normalizedRecord)
        }

        var built: [InstalledFontFamily] = []
        for records in grouped.values {
            guard let first = records.first else { continue }
            let orderedRecords = records.sorted(by: preferredFontRecordOrder)
            let canonical = records
                .map(\.familyName)
                .sorted { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }
                .first ?? first.familyName
            built.append(
                InstalledFontFamily(
                    canonicalFamilyName: canonical,
                    localizedFamilyNames: uniqueFontNames(
                        records.compactMap(\.localizedFamilyName)
                    ),
                    postScriptNames: uniqueFontNames(records.map(\.postScriptName)),
                    displayNames: uniqueFontNames(records.compactMap(\.displayName)),
                    faceNames: uniqueFontNames(records.compactMap(\.faceName)),
                    preferredPostScriptName: orderedRecords[0].postScriptName,
                    records: orderedRecords
                )
            )
        }
        built.sort {
            $0.displayName.localizedCaseInsensitiveCompare($1.displayName) == .orderedAscending
        }
        families = built
        familiesByID = Dictionary(uniqueKeysWithValues: built.map { ($0.id, $0) })

        var strictAliases: [String: Set<String>] = [:]
        var compactAliases: [String: Set<String>] = [:]
        for family in built {
            for name in family.searchableNames {
                let strictKey = fontStrictLookupKey(name)
                if !strictKey.isEmpty {
                    strictAliases[strictKey, default: []].insert(family.id)
                }
                let compactKey = fontCompactLookupKey(name)
                if !compactKey.isEmpty {
                    compactAliases[compactKey, default: []].insert(family.id)
                }
            }
        }
        strictAliasIndex = strictAliases
        compactAliasIndex = compactAliases
    }

    static func system() -> InstalledFontCatalog {
        // Core Text discovery is safe off the main thread. Avoid AppKit's
        // shared NSFontManager while a SwiftUI editor is being presented.
        let names = CTFontManagerCopyAvailablePostScriptNames() as? [String] ?? []
        let records = names.map { name -> InstalledFontFaceRecord in
            let font = CTFontCreateWithName(name as CFString, 12, nil)
            let family = CTFontCopyName(font, kCTFontFamilyNameKey) as String? ?? name
            let localized = CTFontCopyLocalizedName(font, kCTFontFamilyNameKey, nil) as String?
            let traits = CTFontCopyTraits(font) as NSDictionary
            let weight = (traits[kCTFontWeightTrait] as? NSNumber)?.doubleValue ?? 0
            return InstalledFontFaceRecord(
                familyName: family, localizedFamilyName: localized,
                postScriptName: CTFontCopyPostScriptName(font) as String,
                displayName: CTFontCopyDisplayName(font) as String,
                faceName: CTFontCopyName(font, kCTFontSubFamilyNameKey) as String?,
                weight: Int((weight * 5 + 5).rounded()),
                traitsRawValue: UInt(CTFontGetSymbolicTraits(font).rawValue)
            )
        }
        return InstalledFontCatalog(records: records)
    }

    // Font discovery can involve hundreds of faces. Reuse the latest complete
    // scan when editors are reopened. SwiftUI invokes both accessors on the
    // main thread, so a manual refresh can safely replace this process cache.
    @MainActor private static var cachedSystemStorage = InstalledFontCatalog(records: [], isLoaded: false)

    @MainActor static var cachedSystem: InstalledFontCatalog { cachedSystemStorage }

    @MainActor static func refreshSystem() async -> InstalledFontCatalog {
        let refreshed = await Task.detached(priority: .userInitiated) { InstalledFontCatalog.system() }.value
        cachedSystemStorage = refreshed
        return refreshed
    }

    func match(name: String?, aliases: [String] = []) -> InstalledFontMatch {
        guard let rawName = normalizedFontName(name) else {
            return InstalledFontMatch(
                kind: .inherited,
                canonicalFamilyName: nil,
                postScriptName: nil,
                candidateFamilyNames: []
            )
        }
        guard isLoaded else {
            return InstalledFontMatch(kind: .loading, canonicalFamilyName: nil, postScriptName: nil, candidateFamilyNames: [])
        }

        // The document's primary name has priority.  A supplemental w:altName
        // must never turn an already unique family/PostScript match into a
        // conflict with an unrelated installed family.
        let strictRawCandidateIDs = strictAliasIndex[fontStrictLookupKey(rawName)] ?? []
        let rawCandidateIDs = strictRawCandidateIDs.isEmpty
            ? (compactAliasIndex[fontCompactLookupKey(rawName)] ?? [])
            : strictRawCandidateIDs
        let candidateIDs: Set<String>
        if rawCandidateIDs.isEmpty {
            var aliasCandidateIDs: Set<String> = []
            for alias in aliases.compactMap(normalizedFontName) {
                let strictIDs = strictAliasIndex[fontStrictLookupKey(alias)] ?? []
                aliasCandidateIDs.formUnion(
                    strictIDs.isEmpty
                        ? (compactAliasIndex[fontCompactLookupKey(alias)] ?? [])
                        : strictIDs
                )
            }
            candidateIDs = aliasCandidateIDs
        } else {
            candidateIDs = rawCandidateIDs
        }
        let matchedFamilies = candidateIDs.compactMap { familiesByID[$0] }.sorted {
            $0.canonicalFamilyName.localizedCaseInsensitiveCompare($1.canonicalFamilyName) ==
                .orderedAscending
        }
        guard matchedFamilies.count == 1, let family = matchedFamilies.first else {
            return InstalledFontMatch(
                kind: matchedFamilies.isEmpty ? .missing : .ambiguous,
                canonicalFamilyName: nil,
                postScriptName: nil,
                candidateFamilyNames: matchedFamilies.map(\.canonicalFamilyName)
            )
        }

        let strictRaw = fontStrictLookupKey(rawName)
        let isRegisteredName = fontStrictLookupKey(family.canonicalFamilyName) == strictRaw ||
            family.postScriptNames.contains { fontStrictLookupKey($0) == strictRaw }
        return InstalledFontMatch(
            kind: isRegisteredName ? .installed : .alias,
            canonicalFamilyName: family.canonicalFamilyName,
            postScriptName: family.exactPostScriptName(for: rawName) ??
                family.preferredPostScriptName,
            candidateFamilyNames: [family.canonicalFamilyName]
        )
    }

    func search(_ query: String) -> [InstalledFontFamily] {
        let key = fontCompactLookupKey(query)
        guard !key.isEmpty else { return families }
        return families.filter { family in
            family.searchableNames.contains {
                fontCompactLookupKey($0).contains(key)
            }
        }
    }
}

enum TemplateFontRole {
    case latin
    case eastAsia
}

struct TemplateFontOption: Hashable, Identifiable {
    let name: String
    let aliases: [String]

    var id: String { fontStrictLookupKey(name) }

    func matches(_ query: String) -> Bool {
        let key = fontCompactLookupKey(query)
        guard !key.isEmpty else { return true }
        return ([name] + aliases).contains {
            fontCompactLookupKey($0).contains(key)
        }
    }
}

func templateFontOptions(
    from formats: [UsedFormat],
    role: TemplateFontRole
) -> [TemplateFontOption] {
    var namesByKey: [String: String] = [:]
    var aliasesByKey: [String: Set<String>] = [:]
    for format in formats {
        let rawName: String?
        let rawAliases: [String]
        switch role {
        case .latin:
            rawName = format.fontLatin
            rawAliases = format.fontLatinAliases ?? []
        case .eastAsia:
            rawName = format.fontEastAsia
            rawAliases = format.fontEastAsiaAliases ?? []
        }
        guard let name = normalizedFontName(rawName) else { continue }
        let key = fontStrictLookupKey(name)
        namesByKey[key] = namesByKey[key] ?? name
        for alias in rawAliases.compactMap(normalizedFontName)
            where fontStrictLookupKey(alias) != key {
            aliasesByKey[key, default: []].insert(alias)
        }
    }
    return namesByKey.map { key, name in
        TemplateFontOption(
            name: name,
            aliases: (aliasesByKey[key] ?? []).sorted {
                $0.localizedCaseInsensitiveCompare($1) == .orderedAscending
            }
        )
    }.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
}

func templateAliases(
    for name: String?,
    in options: [TemplateFontOption]
) -> [String] {
    guard let name = normalizedFontName(name) else { return [] }
    let key = fontStrictLookupKey(name)
    return options.first { $0.id == key }?.aliases ?? []
}

func localPreviewDescription(
    requestedName: String?,
    match: InstalledFontMatch
) -> String {
    guard normalizedFontName(requestedName) != nil else {
        return "继承主题，本机使用系统字体示意"
    }
    switch match.kind {
    case .loading:
        return "正在读取本机字体，预览暂用系统字体"
    case .inherited:
        return "继承主题"
    case .installed:
        return match.postScriptName ?? "本机字体"
    case .alias:
        return match.postScriptName.map { "别名解析为 \($0)" } ?? "已通过别名解析"
    case .ambiguous:
        return "名称匹配冲突，预览使用系统字体"
    case .missing:
        return "本机未注册，预览使用系统字体"
    }
}

func normalizedFontName(_ value: String?) -> String? {
    guard let value else { return nil }
    let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
    return trimmed.isEmpty ? nil : trimmed
}

func fontStrictLookupKey(_ value: String) -> String {
    value.folding(
        options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive],
        locale: Locale(identifier: "en_US_POSIX")
    )
}

func fontCompactLookupKey(_ value: String) -> String {
    let folded = fontStrictLookupKey(value)
    return String(folded.unicodeScalars.filter {
        CharacterSet.alphanumerics.contains($0)
    })
}

func uniqueFontNames(_ names: [String]) -> [String] {
    var seen: Set<String> = []
    var result: [String] = []
    for name in names.compactMap(normalizedFontName) {
        let key = fontStrictLookupKey(name)
        if seen.insert(key).inserted { result.append(name) }
    }
    return result.sorted { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }
}

func preferredFontRecordOrder(
    _ lhs: InstalledFontFaceRecord,
    _ rhs: InstalledFontFaceRecord
) -> Bool {
    let styleMask = NSFontTraitMask.boldFontMask.rawValue |
        NSFontTraitMask.italicFontMask.rawValue
    let lhsStyled = lhs.traitsRawValue & styleMask != 0
    let rhsStyled = rhs.traitsRawValue & styleMask != 0
    if lhsStyled != rhsStyled { return !lhsStyled }
    let lhsDistance = abs(lhs.weight - 5)
    let rhsDistance = abs(rhs.weight - 5)
    if lhsDistance != rhsDistance { return lhsDistance < rhsDistance }
    return lhs.postScriptName.localizedCaseInsensitiveCompare(rhs.postScriptName) == .orderedAscending
}
