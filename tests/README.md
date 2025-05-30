# 测试文件夹说明

本文档旨在说明 `tests` 文件夹的组织结构、测试策略以及如何运行测试用例。全面的测试是确保SLAIS项目代码质量、稳定性和可维护性的关键组成部分。

## 文件夹结构

当前 `tests` 文件夹包含以下主要子目录和文件：

-   **/basic/**: 包含项目基础功能的导入和快速验证测试。
    -   `test_basic_imports.py`: 测试核心模块是否可以成功导入。
    -   `test_quick_imports.py`: 可能用于更快速的导入检查或特定场景的导入测试。
-   **/fixes/**: 存放针对项目中特定Bug修复的验证测试。
    -   例如 `test_logger_fix.py`, `test_reference_fix.py` 等，确保修复有效且不会回归。
-   **/utils/**: (当前 `environment_details` 中未显示此目录，但原始 `tests/README.md` 中提及) 可能包含对工具函数或辅助模块的测试。
    -   `test_args.py`: 测试命令行参数的解析和处理逻辑。
-   `TESTS_ORGANIZATION_SUMMARY.md`: (如果存在) 提供更详细的测试组织结构总结。

**未来的组织结构规划 (参考 `project.md`)**:
为了更清晰地分离不同类型的测试，项目计划将测试用例组织到以下标准子目录中：
-   `tests/unit/`: 存放单元测试，专注于测试独立的函数或类方法。
-   `tests/integration/`: 存放集成测试，验证多个模块之间的交互。
-   `tests/fixtures/`: (如果需要) 存放测试数据和辅助文件。

当前的目录结构是项目演进过程中的产物，未来可能会根据上述规划进行重构。

## 测试策略与工具

-   **测试框架**: 项目推荐并主要使用 `pytest` 作为测试运行器和框架，因其灵活性和强大的插件生态。
-   **模拟 (Mocking)**: 对于外部依赖（如API调用、文件系统操作、`datetime.now()`等），应使用 `unittest.mock` (Python内置) 或 `pytest-mock` (pytest插件) 进行模拟，以确保测试的独立性、速度和确定性。对于HTTP请求，可以考虑使用 `responses` 或 `aioresponses` (针对异步代码)。
-   **代码覆盖率**: 项目致力于实现高代码覆盖率（目标 >80%），尤其针对核心业务逻辑模块。使用 `pytest-cov` 插件生成覆盖率报告，并定期审查以识别未测试的代码路径。
-   **测试类型**:
    -   **单元测试**: 验证最小代码单元的正确性。
    -   **集成测试**: 确保不同模块协同工作时的正确性。
    -   **(未来) 端到端测试 (E2E)**: 验证完整的用户场景和应用流程。
-   **测试编写**:
    -   测试应遵循 **Arrange-Act-Assert (AAA)** 模式。
    -   测试用例应清晰、独立且可重复。
    -   测试命名应具有描述性，清晰指出被测试的功能和场景 (例如 `test_module_function_with_valid_input_returns_expected_output`)。

## 如何运行测试

1.  **确保开发环境已设置**:
    *   激活项目的虚拟环境 (例如 `conda activate slais_env`)。
    *   确保已安装开发依赖 (通常通过 `pip install -r requirements-dev.txt`，其中应包含 `pytest` 和 `pytest-cov` 等)。

2.  **运行所有测试**:
    在项目根目录下执行：
    ```bash
    pytest tests/
    ```
    或者简单地：
    ```bash
    pytest
    ```

3.  **运行特定目录或文件的测试**:
    ```bash
    pytest tests/basic/
    pytest tests/fixes/test_logger_fix.py
    ```

4.  **生成代码覆盖率报告**:
    ```bash
    pytest --cov=slais --cov-report=html tests/
    ```
    这会在项目根目录下生成一个 `htmlcov/` 目录，其中包含详细的HTML格式覆盖率报告。请将 `slais` 替换为实际的主代码包名（如果不同）。

## 贡献测试

我们鼓励所有开发者为新功能、Bug修复以及现有未覆盖的代码路径积极贡献测试用例。
-   新功能合并前必须包含相应的单元测试和（如果适用）集成测试。
-   修复Bug时，应首先编写一个能够复现该Bug的失败测试用例，然后再进行修复，确保测试通过。

感谢您对提升SLAIS项目质量的贡献！
