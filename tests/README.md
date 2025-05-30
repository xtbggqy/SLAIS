# 测试文件夹说明

欢迎使用 `tests` 文件夹，这里包含了项目的测试用例和相关文档。以下是文件夹的结构和内容说明：

## 文件夹结构

- **/basic/**: 包含基础功能测试文件。
  - `test_basic_imports.py`: 测试基本模块导入。
  - `test_quick_imports.py`: 测试快速导入功能。
- **/fixes/**: 包含针对特定问题的修复测试文件。
  - `test_all_nameerror_fixes.py`: 测试所有名称错误修复。
  - `test_complete_fix.py`: 测试完整修复功能。
  - `test_logger_fix.py`: 测试日志记录器修复。
  - `test_reference_fix.py`: 测试参考文献修复。
  - `test_save_csv_report_fix.py`: 测试保存CSV报告的修复。
  - `test_save_csv_report_syntax.py`: 测试保存CSV报告的语法修复。
  - `test_save_report_fix.py`: 测试保存报告的修复。
- **/utils/**: 包含工具和辅助功能测试文件。
  - `test_args.py`: 测试命令行参数处理。
- **/debug/**: 包含调试相关的测试文件。
  - `debug_report_detection.py`: 调试报告检测功能。
- **/docs/**: 包含测试相关的文档。
  - `TESTS_ORGANIZATION_SUMMARY.md`: 测试组织结构总结。

## 使用说明

每个测试文件都针对特定的功能或问题进行测试。请根据需要运行相应的测试用例，确保代码更改不会引入新的问题。您可以使用 `pytest` 运行所有测试：

```bash
pytest tests/
```

如果您需要运行特定文件夹或文件中的测试，可以指定路径：

```bash
pytest tests/basic/
pytest tests/fixes/test_logger_fix.py
```

感谢您对项目的贡献和测试！
