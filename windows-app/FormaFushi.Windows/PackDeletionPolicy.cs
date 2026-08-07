using Microsoft.VisualBasic.FileIO;

namespace FormaFushi.Windows;

internal static class PackDeletionPolicy
{
    public static void MoveToRecycleBin(PackManifest pack, IReadOnlyCollection<PackManifest> currentPacks, string libraryDirectory)
    {
        if (!currentPacks.Any(item => item.Id == pack.Id && item.PackPath == pack.PackPath))
        {
            throw new AppFailure("这套格式已不在当前格式库中，请刷新后重试。");
        }

        if (string.IsNullOrWhiteSpace(pack.PackPath))
        {
            throw new AppFailure("这套格式缺少本机存储位置，无法删除。");
        }

        var fullLibrary = Path.TrimEndingDirectorySeparator(Path.GetFullPath(libraryDirectory));
        var fullPack = Path.GetFullPath(pack.PackPath);
        var parent = Path.TrimEndingDirectorySeparator(Path.GetDirectoryName(fullPack) ?? "");
        if (!string.Equals(Path.GetExtension(fullPack), ".wfstyle", StringComparison.OrdinalIgnoreCase) ||
            !string.Equals(parent, fullLibrary, StringComparison.OrdinalIgnoreCase))
        {
            throw new AppFailure("为保护其他文件，只能删除格式库目录中的 .wfstyle 格式方案。");
        }

        if (!File.Exists(fullPack))
        {
            throw new AppFailure("这套格式文件已经不存在，请刷新格式库。");
        }

        var attributes = File.GetAttributes(fullPack);
        if (attributes.HasFlag(FileAttributes.Directory) || attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            throw new AppFailure("为保护其他内容，只能删除普通的 .wfstyle 格式库文件。");
        }

        FileSystem.DeleteFile(
            fullPack,
            UIOption.OnlyErrorDialogs,
            RecycleOption.SendToRecycleBin,
            UICancelOption.ThrowException);
    }
}
