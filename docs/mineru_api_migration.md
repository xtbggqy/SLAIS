# MinerU API 使用指南

## 概述

本项目使用 MinerU 在线 API 服务进行PDF解析。这样可以避免复杂的本地模型部署，提供更稳定的服务体验。

## 配置步骤

### 1. 获取 MinerU API 密钥

1. 访问 [https://mineru.net](https://mineru.net)
2. 注册账号并获取 API 密钥
3. 每个账号每天享有 2000 页最高优先级解析额度

### 2. 配置环境变量

在项目根目录的 `.env` 文件中添加以下配置：

```bash
# MinerU API 配置
MINERU_API_KEY=your-mineru-api-key-here
MINERU_API_BASE_URL=https://mineru.net/api/v4
MINERU_MAX_WAIT_TIME=3600
MINERU_CHECK_INTERVAL=10
MINERU_MAX_RETRIES=3
MINERU_RETRY_DELAY=5
```

### 3. 配置说明

- `MINERU_API_KEY`: 从 mineru.net 获取的 API 密钥（必填）
- `MINERU_API_BASE_URL`: API 基础 URL，默认为官方地址
- `MINERU_MAX_WAIT_TIME`: API 任务的最大等待时间（秒），默认 1 小时
- `MINERU_CHECK_INTERVAL`: 检查任务状态的间隔（秒），默认 10 秒
- `MINERU_MAX_RETRIES`: 文件上传失败时的最大重试次数，默认 3 次
- `MINERU_RETRY_DELAY`: 重试间隔基础时间（秒），实际等待时间为 retry_delay × 尝试次数

## API 模式优势

| 功能 | API 模式优势 |
|------|-------------|
| 部署复杂度 | 简单，无需安装模型 |
| 硬件要求 | 无特殊要求 |
| 处理速度 | 高性能云端处理 |
| 成本 | 按使用量付费，性价比高 |
| 维护成本 | 低，自动模型更新 |
| 服务稳定性 | 专业团队维护，稳定可靠 |

## 支持的文件格式

- PDF
- DOC、DOCX
- PPT、PPTX
- PNG、JPG、JPEG

## 文件限制

- 单个文件不超过 200MB
- 页数不超过 600 页
- 超过 2000 页的部分优先级会降低

## 错误处理

常见错误码及解决方案：

- `A0202`: Token 错误 - 检查 API 密钥是否正确
- `A0211`: Token 过期 - 更换新的 API 密钥
- `-60005`: 文件大小超出限制 - 检查文件大小
- `-60006`: 文件页数超过限制 - 拆分文件后重试

## 备注说明

本项目已完全迁移到API模式，提供更简单、稳定的使用体验。

## 使用示例

```python
from slais.pdf_utils_api import convert_pdf_to_markdown

# 使用MinerU API进行PDF处理
markdown_path = await convert_pdf_to_markdown("path/to/file.pdf")
```

## 注意事项

1. **网络连接**: 确保有稳定的网络连接
2. **API 额度**: 注意每日解析额度限制
3. **文件隐私**: 文件会上传到MinerU服务器进行处理
4. **异步处理**: API 调用都是异步的，需要等待处理完成

## 故障排除

### 1. API 密钥问题
确保在 `.env` 文件中正确设置了 `MINERU_API_KEY`

### 2. 网络连接问题
- 检查网络连接
- 确认 API 服务是否可访问

### 3. 文件上传失败
- 检查文件大小和格式
- 确认文件未损坏

### 4. 任务超时
- 调整 `MINERU_MAX_WAIT_TIME` 参数
- 对于大文件，考虑拆分处理

## 技术支持

如有问题，请：
1. 检查日志文件中的详细错误信息
2. 参考 MinerU 官方文档
3. 提交 Issue 到项目仓库 