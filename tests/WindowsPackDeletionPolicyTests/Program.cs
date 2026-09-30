/**
 * [INPUT]: 依赖 System.Text.Json, FormaFushi.Windows, Microsoft.VisualBasic.FileIO
 * [OUTPUT]: 提供 DeletionTestFailure, Program
 * [POS]: 隔离验证 Windows 删除策略路径、链接及文件扩展名
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
using System.Text.Json;
using FormaFushi.Windows;
using Microsoft.VisualBasic.FileIO;

// tests/PackDeletionPolicyTests.swift 的 Windows 对照实现。
// 两边逐条对应，任何一端加了检查，另一端也要加，否则删除行为会悄悄分叉。

internal sealed class DeletionTestFailure(string message) : Exception(message);

internal static class Program
{
    private static int _passed;
    private static int _skipped;

    /// <summary>CI 传 --strict，把「环境不支持所以跳过」也算失败。</summary>
    private static bool _strict;

    public static int Main(string[] args)
    {
        _strict = args.Contains("--strict");

        var testRoot = Path.Combine(
            Path.GetTempPath(),
            $"word-format-library-delete-tests-{Guid.NewGuid():N}");
        var library = Path.Combine(testRoot, "style-packs");
        Directory.CreateDirectory(library);

        try
        {
            RunChecks(library, testRoot);
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"WindowsPackDeletionPolicyTests 失败：{error.Message}");
            return 1;
        }
        finally
        {
            try
            {
                Directory.Delete(testRoot, recursive: true);
            }
            catch (IOException)
            {
                // 清理失败不影响结论。
            }
        }

        var suffix = _skipped > 0 ? $"，{_skipped} 项跳过" : "";
        Console.WriteLine($"WindowsPackDeletionPolicyTests: {_passed} checks passed{suffix}");
        return 0;
    }

    private static void RunChecks(string library, string testRoot)
    {
        var validPath = Path.Combine(library, "valid.wfstyle");
        File.WriteAllText(validPath, "test-format-pack");
        var validPack = MakePack("shared-id", validPath);
        Require(
            PackDeletionPolicy.ValidatedPath(validPack, [validPack], library) == validPath,
            "格式库根目录中的普通 .wfstyle 文件应通过校验");

        var duplicatePath = Path.Combine(library, "duplicate-id.wfstyle");
        File.WriteAllText(duplicatePath, "another-format-pack");
        var duplicatePack = MakePack("shared-id", duplicatePath);
        Require(
            PackDeletionPolicy.ValidatedPath(duplicatePack, [validPack, duplicatePack], library) == duplicatePath,
            "重复 manifest id 时必须按精确 packPath 识别");

        ExpectRejection("同 id 但不在当前列表中的路径必须拒绝", () =>
        {
            var unknownPath = Path.Combine(library, "unknown.wfstyle");
            File.WriteAllText(unknownPath, "unknown");
            var unknownPack = MakePack("shared-id", unknownPath);
            PackDeletionPolicy.ValidatedPath(unknownPack, [validPack, duplicatePack], library);
        });

        var outsidePath = Path.Combine(testRoot, "outside.wfstyle");
        File.WriteAllText(outsidePath, "outside");
        var outsidePack = MakePack("outside", outsidePath);
        ExpectRejection("格式库外部文件必须拒绝", () =>
            PackDeletionPolicy.ValidatedPath(outsidePack, [outsidePack], library));

        var nestedDirectory = Path.Combine(library, "nested");
        Directory.CreateDirectory(nestedDirectory);
        var nestedPath = Path.Combine(nestedDirectory, "nested.wfstyle");
        File.WriteAllText(nestedPath, "nested");
        var nestedPack = MakePack("nested", nestedPath);
        ExpectRejection("格式库子目录中的文件必须拒绝", () =>
            PackDeletionPolicy.ValidatedPath(nestedPack, [nestedPack], library));

        var disguisedDirectory = Path.Combine(library, "folder.wfstyle");
        Directory.CreateDirectory(disguisedDirectory);
        var disguisedPack = MakePack("folder", disguisedDirectory);
        ExpectRejection("伪装成 .wfstyle 的目录必须拒绝", () =>
            PackDeletionPolicy.ValidatedPath(disguisedPack, [disguisedPack], library));

        CheckSymlinkRejection(library, outsidePath);

        Require(
            PackDeletionPolicy.FallbackIndex(0, 2) == 0,
            "删除中间项后应优先选择原位置的下一项");
        Require(
            PackDeletionPolicy.FallbackIndex(2, 2) == 1,
            "删除末项后应选择上一项");
        Require(
            PackDeletionPolicy.FallbackIndex(0, 0) is null,
            "删除唯一项后不应保留选择");

        CheckRecycleBinRoundTrip(library);
    }

    /// <summary>
    /// 符号链接需要管理员权限或开发者模式；本机不具备时记为跳过，CI 用 --strict 强制要求。
    /// </summary>
    private static void CheckSymlinkRejection(string library, string outsidePath)
    {
        var symlinkPath = Path.Combine(library, "outside-link.wfstyle");
        try
        {
            File.CreateSymbolicLink(symlinkPath, outsidePath);
        }
        catch (Exception error) when (error is UnauthorizedAccessException or IOException)
        {
            Skip($"指向格式库外部的符号链接必须拒绝（本机无法创建符号链接：{error.Message}）");
            return;
        }

        var symlinkPack = MakePack("symlink", symlinkPath);
        ExpectRejection("指向格式库外部的符号链接必须拒绝", () =>
            PackDeletionPolicy.ValidatedPath(symlinkPack, [symlinkPack], library));
    }

    /// <summary>
    /// 对应 Swift 侧的废纸篓往返：删除必须是「可恢复」的，不能是就地抹掉。
    /// </summary>
    private static void CheckRecycleBinRoundTrip(string library)
    {
        var trashablePath = Path.Combine(library, "trash-roundtrip.wfstyle");
        File.WriteAllText(trashablePath, "trash-roundtrip");
        var trashablePack = MakePack("trash-roundtrip", trashablePath);

        try
        {
            PackDeletionPolicy.MoveToRecycleBin(trashablePack, [trashablePack], library);
        }
        catch (Exception error) when (error is not DeletionTestFailure)
        {
            Skip($"格式包应可送入回收站（本机回收站不可用：{error.Message}）");
            Skip("回收站中的格式包应可恢复（本机回收站不可用）");
            return;
        }

        Require(!File.Exists(trashablePath), "文件应从格式库中消失");

        var recycled = FindInRecycleBin(library);
        if (recycled is null)
        {
            Skip("回收站中的格式包应可恢复（无法枚举回收站内容）");
            return;
        }

        File.Move(recycled, trashablePath);
        Require(File.Exists(trashablePath), "回收站中的格式包应可恢复");
    }

    /// <summary>
    /// 按「原位置」而不是文件名匹配回收站条目：测试目录是唯一的临时目录，
    /// 而条目名会受资源管理器的扩展名显示设置影响。返回条目在 $Recycle.Bin 里的真实路径。
    /// </summary>
    private static string? FindInRecycleBin(string library)
    {
        const int RecycleBinFolder = 10;
        const int OriginalLocationColumn = 1;

        var shellType = Type.GetTypeFromProgID("Shell.Application");
        if (shellType is null)
        {
            return null;
        }

        dynamic? shell = null;
        try
        {
            shell = Activator.CreateInstance(shellType);
            dynamic folder = shell!.NameSpace(RecycleBinFolder);
            var expected = Path.TrimEndingDirectorySeparator(Path.GetFullPath(library));
            foreach (dynamic item in folder.Items())
            {
                string origin = folder.GetDetailsOf(item, OriginalLocationColumn);
                if (string.Equals(
                        Path.TrimEndingDirectorySeparator(origin ?? ""),
                        expected,
                        StringComparison.OrdinalIgnoreCase))
                {
                    return item.Path;
                }
            }
        }
        catch (Exception)
        {
            return null;
        }
        finally
        {
            if (shell is not null)
            {
                System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell);
            }
        }

        return null;
    }

    private static PackManifest MakePack(string id, string path)
    {
        var payload = new
        {
            id,
            name = "临时格式",
            used_formats = Array.Empty<object>(),
            used_style_count = 0,
            manual_formatting = new { paragraph_count = 0, run_count = 0 },
            document_summary = new
            {
                paragraph_count = 0,
                run_count = 0,
                table_count = 0,
                section_count = 0
            },
            page_layout = new { },
            pack_path = path
        };

        return JsonSerializer.Deserialize<PackManifest>(JsonSerializer.Serialize(payload))
            ?? throw new DeletionTestFailure("构造测试用 PackManifest 失败");
    }

    private static void Require(bool condition, string message)
    {
        if (!condition)
        {
            throw new DeletionTestFailure(message);
        }

        _passed++;
    }

    private static void ExpectRejection(string message, Action operation)
    {
        try
        {
            operation();
        }
        catch (AppFailure)
        {
            _passed++;
            return;
        }

        throw new DeletionTestFailure(message);
    }

    private static void Skip(string message)
    {
        if (_strict)
        {
            throw new DeletionTestFailure($"{message}（--strict 下不允许跳过）");
        }

        _skipped++;
        Console.WriteLine($"跳过：{message}");
    }
}
