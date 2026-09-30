// [INPUT]: 依赖 Foundation
// [OUTPUT]: 提供可见选择归一与格式重置撤销策略
// [POS]: Mac 编辑器 - 与 SwiftUI 无关的交互状态规则
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import Foundation

enum FormatSelectionPolicy {
    static func selectedID(current: String?, visibleIDs: [String]) -> String? {
        if let current, visibleIDs.contains(current) { return current }
        return visibleIDs.first
    }
}

struct StyleResetHistory {
    private var previousDrafts: [StyleEditDraft]?

    var canUndo: Bool { previousDrafts != nil }

    mutating func reset(_ drafts: inout [StyleEditDraft]) {
        previousDrafts = drafts
        for index in drafts.indices { drafts[index].reset() }
    }

    mutating func undo(_ drafts: inout [StyleEditDraft]) {
        guard let previousDrafts else { return }
        drafts = previousDrafts
        self.previousDrafts = nil
    }

    mutating func discardUndoAfterNewInput() { previousDrafts = nil }
}
