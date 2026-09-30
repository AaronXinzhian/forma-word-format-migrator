# swift-app/Bridge/ — 模块索引(L2)

> 本文件夹内文件增删、重命名、接口变更时,必须更新本文件。上级索引:[../../PROJECT_INDEX.md](../../PROJECT_INDEX.md)

## 模块定位
Mac 文件库位置与私有引擎进程边界，由 LibraryModel 调用。

## 文件清单
| 文件 | 职责 | 关键导出 |
|------|------|----------|
| LibraryLocation.swift | 确定新格式库位置并安全迁移旧目录 | LibraryLocation |
| PythonBridge.swift | 桥接打包内的迁移引擎、取消与结构化结果 | PythonOperation, PythonBridge |
