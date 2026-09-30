/**
 * [INPUT]: 依赖 (未检出外部依赖)
 * [OUTPUT]: 提供 Program
 * [POS]: 初始化 Windows 单线程桌面应用
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
namespace FormaFushi.Windows;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}
