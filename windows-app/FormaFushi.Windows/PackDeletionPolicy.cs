/**
 * [INPUT]: 依赖 FormaFushi.Windows.Generated, Microsoft.VisualBasic.FileIO
 * [OUTPUT]: 提供 PackDeletionPolicy
 * [POS]: 验证格式库文件身份并限制回收站删除范围
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
using FormaFushi.Windows.Generated;
using Microsoft.VisualBasic.FileIO;

namespace FormaFushi.Windows;

/// <summary>
/// 与 swift-app/Models/PackModels.swift 的 PackDeletionPolicy 行为对齐。
/// 校验顺序、拒绝条件与文案必须两端一致，tests/WindowsPackDeletionPolicyTests 会逐条比对。
/// </summary>
internal static class PackDeletionPolicy
{
    /// <summary>
    /// 校验并返回可以删除的真实路径；任何不确定的情况一律拒绝。
    /// </summary>
    public static string ValidatedPath(
        PackManifest pack,
        IReadOnlyCollection<PackManifest> currentPacks,
        string libraryDirectory)
    {
        if (!currentPacks.Any(item => item.Id == pack.Id && item.PackPath == pack.PackPath))
        {
            throw new AppFailure(UIStrings.Errors.PackNotInLibrary);
        }

        if (string.IsNullOrWhiteSpace(pack.PackPath))
        {
            throw new AppFailure(UIStrings.Errors.PackWithoutPath);
        }

        var fullLibrary = Path.TrimEndingDirectorySeparator(Path.GetFullPath(libraryDirectory));
        var fullPack = Path.GetFullPath(pack.PackPath);
        var parent = Path.TrimEndingDirectorySeparator(Path.GetDirectoryName(fullPack) ?? "");
        if (!string.Equals(Path.GetExtension(fullPack), ".wfstyle", StringComparison.OrdinalIgnoreCase) ||
            !string.Equals(parent, fullLibrary, StringComparison.OrdinalIgnoreCase))
        {
            throw new AppFailure(UIStrings.Errors.PackOutsideLibrary);
        }

        if (!string.Equals(ResolveDirectory(parent), ResolveDirectory(fullLibrary), StringComparison.OrdinalIgnoreCase))
        {
            throw new AppFailure(UIStrings.Errors.PackEscapesLibrary);
        }

        if (Directory.Exists(fullPack) || !File.Exists(fullPack))
        {
            throw new AppFailure(UIStrings.Errors.PackMissingFile);
        }

        var attributes = File.GetAttributes(fullPack);
        if (attributes.HasFlag(FileAttributes.Directory) || attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            throw new AppFailure(UIStrings.Errors.PackNotRegularFile);
        }

        return fullPack;
    }

    public static void MoveToRecycleBin(
        PackManifest pack,
        IReadOnlyCollection<PackManifest> currentPacks,
        string libraryDirectory)
    {
        var path = ValidatedPath(pack, currentPacks, libraryDirectory);
        FileSystem.DeleteFile(
            path,
            UIOption.OnlyErrorDialogs,
            RecycleOption.SendToRecycleBin,
            UICancelOption.ThrowException);
    }

    /// <summary>
    /// 删除后应该顶上来的条目下标；没有剩余条目时返回 null。
    /// </summary>
    public static int? FallbackIndex(int deletedIndex, int remainingCount)
    {
        if (remainingCount <= 0)
        {
            return null;
        }

        return Math.Min(Math.Max(deletedIndex, 0), remainingCount - 1);
    }

    /// <summary>
    /// 展开目录链接后的真实路径，用来发现「格式库目录本身是个链接」这类越界情况。
    /// </summary>
    private static string ResolveDirectory(string path)
    {
        try
        {
            var resolved = Directory.ResolveLinkTarget(path, returnFinalTarget: true);
            return Path.TrimEndingDirectorySeparator(
                Path.GetFullPath(resolved?.FullName ?? path));
        }
        catch (IOException)
        {
            return Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));
        }
    }
}
