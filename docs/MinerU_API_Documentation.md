# MinerU API 调用文档

## 概述

MinerU 是一个强大的文档解析服务，支持多种文件格式的智能解析和转换。本文档详细介绍了 MinerU API 的使用方法，包括单个文件解析和批量文件解析功能。

## 基础信息

- **API 基础 URL**: `https://mineru.net/api/v4/`
- **认证方式**: Bearer Token
- **支持格式**: PDF、DOC、DOCX、PPT、PPTX、PNG、JPG、JPEG
- **文件大小限制**: 单个文件不超过 200MB
- **页数限制**: 不超过 600 页
- **每日额度**: 每个账号每天享有 2000 页最高优先级解析额度

## 一、单个文件解析

### 1.1 创建解析任务

#### 接口信息
- **URL**: `POST /extract/task`
- **Content-Type**: `application/json`
- **Authorization**: `Bearer {your_token}`

#### Python 示例

```python
import requests

url = 'https://mineru.net/api/v4/extract/task'
header = {
    'Content-Type': 'application/json',
    "Authorization": "Bearer eyJ0eXBlIjoiSl...请填写准确的token！"
}
data = {
    'url': 'https://cdn-mineru.openxlab.org.cn/demo/example.pdf',
    'is_ocr': True,
    'enable_formula': False,
}
res = requests.post(url, headers=header, json=data)
print(res.status_code)
print(res.json())
print(res.json()["data"])
```

#### CURL 示例

```bash
curl --location --request POST 'https://mineru.net/api/v4/extract/task' \
--header 'Authorization: Bearer ***' \
--header 'Content-Type: application/json' \
--header 'Accept: */*' \
--data-raw '{
    "url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
    "is_ocr": true,
    "enable_formula": false
}'
```

#### 请求参数说明

| 参数 | 类型 | 必选 | 示例 | 描述 |
|------|------|------|------|------|
| url | string | 是 | https://static.openxlab.org.cn/opendatalab/pdf/demo.pdf | 文件 URL，支持多种格式 |
| is_ocr | bool | 否 | false | 是否启动 OCR 功能，默认 false |
| enable_formula | bool | 否 | true | 是否开启公式识别，默认 true |
| enable_table | bool | 否 | true | 是否开启表格识别，默认 true |
| language | string | 否 | ch | 指定文档语言，默认 ch，可设置为 auto |
| data_id | string | 否 | abc** | 解析对象对应的数据 ID，不超过 128 个字符 |
| callback | string | 否 | http://127.0.0.1/callback | 解析结果回调通知 URL |
| seed | string | 否 | abc** | 随机字符串，用于回调通知签名 |
| extra_formats | [string] | 否 | ["docx","html"] | 额外导出格式，支持 docx、html、latex |
| page_ranges | string | 否 | 1-600 | 指定页码范围，如 "2,4-6" |

#### 响应参数说明

| 参数 | 类型 | 示例 | 说明 |
|------|------|------|------|
| code | int | 0 | 接口状态码，成功：0 |
| msg | string | ok | 接口处理信息，成功："ok" |
| trace_id | string | c876cd60b202f2396de1f9e39a1b0172 | 请求 ID |
| data.task_id | string | a90e6ab6-44f3-4554-b459-b62fe4c6b436 | 提取任务 ID |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b4***"
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

### 1.2 获取任务结果

#### 接口信息
- **URL**: `GET /extract/task/{task_id}`
- **Authorization**: `Bearer {your_token}`

#### Python 示例

```python
import requests

url = f'https://mineru.net/api/v4/extract/task/{task_id}'
header = {
    'Content-Type': 'application/json',
    "Authorization": "Bearer eyJ0eXBlIjoiSl...请填写准确的！"
}
res = requests.get(url, headers=header)
print(res.status_code)
print(res.json())
print(res.json()["data"])
```

#### CURL 示例

```bash
curl --location --request GET 'https://mineru.net/api/v4/extract/task/{task_id}' \
--header 'Authorization: Bearer *****' \
--header 'Accept: */*'
```

#### 响应参数说明

| 参数 | 类型 | 示例 | 说明 |
|------|------|------|------|
| code | int | 0 | 接口状态码，成功：0 |
| msg | string | ok | 接口处理信息，成功："ok" |
| trace_id | string | c876cd60b202f2396de1f9e39a1b0172 | 请求 ID |
| data.task_id | string | abc** | 任务 ID |
| data.data_id | string | abc** | 解析对象对应的数据 ID |
| data.state | string | done | 任务处理状态：done(完成)、pending(排队中)、running(正在解析)、failed(解析失败)、converting(格式转换中) |
| data.full_zip_url | string | https://cdn-mineru.openxlab.org.cn/pdf/xxx.zip | 文件解析结果压缩包 |
| data.err_msg | string | 文件格式不支持 | 解析失败原因 |
| data.extract_progress.extracted_pages | int | 1 | 文档已解析页数 |
| data.extract_progress.start_time | string | 2025-01-20 11:43:20 | 文档解析开始时间 |
| data.extract_progress.total_pages | int | 2 | 文档总页数 |

#### 响应示例

**运行中状态：**
```json
{
  "code": 0,
  "data": {
    "task_id": "47726b6e-46ca-4bb9-******",
    "state": "running",
    "err_msg": "",
    "extract_progress": {
      "extracted_pages": 1,
      "total_pages": 2,
      "start_time": "2025-01-20 11:43:20"
    }
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

**完成状态：**
```json
{
  "code": 0,
  "data": {
    "task_id": "47726b6e-46ca-4bb9-******",
    "state": "done",
    "full_zip_url": "https://cdn-mineru.openxlab.org.cn/pdf/018e53ad-d4f1-475d-b380-36bf24db9914.zip",
    "err_msg": ""
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

## 二、批量文件解析

### 2.1 文件批量上传解析

#### 接口信息
- **URL**: `POST /file-urls/batch`
- **Content-Type**: `application/json`
- **Authorization**: `Bearer {your_token}`
- **限制**: 单次申请链接不能超过 200 个，上传链接有效期 24 小时

#### Python 示例

```python
import requests

url = 'https://mineru.net/api/v4/file-urls/batch'
header = {
    'Content-Type': 'application/json',
    "Authorization": "Bearer eyJ0eXBlIjoiSl...请填写准确的token！"
}
data = {
    "enable_formula": True,
    "language": "en",
    "enable_table": True,
    "files": [
        {"name": "demo.pdf", "is_ocr": True, "data_id": "abcd"}
    ]
}
file_path = ["demo.pdf"]

try:
    response = requests.post(url, headers=header, json=data)
    if response.status_code == 200:
        result = response.json()
        print('response success. result:{}'.format(result))
        if result["code"] == 0:
            batch_id = result["data"]["batch_id"]
            urls = result["data"]["file_urls"]
            print('batch_id:{},urls:{}'.format(batch_id, urls))
            for i in range(0, len(urls)):
                with open(file_path[i], 'rb') as f:
                    res_upload = requests.put(urls[i], data=f)
                    if res_upload.status_code == 200:
                        print(f"{urls[i]} upload success")
                    else:
                        print(f"{urls[i]} upload failed")
        else:
            print('apply upload url failed,reason:{}'.format(result.msg))
    else:
        print('response not success. status:{} ,result:{}'.format(response.status_code, response))
except Exception as err:
    print(err)
```

#### CURL 示例

**申请上传链接：**
```bash
curl --location --request POST 'https://mineru.net/api/v4/file-urls/batch' \
--header 'Authorization: Bearer ***' \
--header 'Content-Type: application/json' \
--header 'Accept: */*' \
--data-raw '{
    "enable_formula": true,
    "language": "en",
    "enable_table": true,
    "files": [
        {"name":"demo.pdf", "is_ocr": true, "data_id": "abcd"}
    ]
}'
```

**文件上传：**
```bash
curl -X PUT -T /path/to/your/file.pdf 'https://****'
```

#### 请求参数说明

| 参数 | 类型 | 必选 | 示例 | 描述 |
|------|------|------|------|------|
| enable_formula | bool | 否 | true | 是否开启公式识别，默认 true |
| enable_table | bool | 否 | true | 是否开启表格识别，默认 true |
| language | string | 否 | ch | 指定文档语言，默认 ch |
| file.name | string | 是 | demo.pdf | 文件名，支持多种格式 |
| file.is_ocr | bool | 否 | true | 是否启动 OCR 功能，默认 false |
| file.data_id | string | 否 | abc** | 解析对象对应的数据 ID |
| file.page_ranges | string | 否 | 1-600 | 指定页码范围 |
| callback | string | 否 | http://127.0.0.1/callback | 解析结果回调通知 URL |
| seed | string | 否 | abc** | 随机字符串，用于回调通知签名 |
| extra_formats | [string] | 否 | ["docx","html"] | 额外导出格式 |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "batch_id": "2bb2f0ec-a336-4a0a-b61a-241afaf9cc87",
    "file_urls": [
        "https://***"
    ]
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

### 2.2 URL 批量上传解析

#### 接口信息
- **URL**: `POST /extract/task/batch`
- **Content-Type**: `application/json`
- **Authorization**: `Bearer {your_token}`
- **限制**: 单次申请不能超过 200 个文件

#### Python 示例

```python
import requests

url = 'https://mineru.net/api/v4/extract/task/batch'
header = {
    'Content-Type': 'application/json',
    "Authorization": "Bearer eyJ0eXBlIjoiSl...请填写准确的token！"
}
data = {
    "enable_formula": True,
    "language": "en",
    "enable_table": True,
    "files": [
        {"url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf", "is_ocr": True, "data_id": "abcd"}
    ]
}

try:
    response = requests.post(url, headers=header, json=data)
    if response.status_code == 200:
        result = response.json()
        print('response success. result:{}'.format(result))
        if result["code"] == 0:
            batch_id = result["data"]["batch_id"]
            print('batch_id:{}'.format(batch_id))
        else:
            print('submit task failed,reason:{}'.format(result.msg))
    else:
        print('response not success. status:{} ,result:{}'.format(response.status_code, response))
except Exception as err:
    print(err)
```

#### CURL 示例

```bash
curl --location --request POST 'https://mineru.net/api/v4/extract/task/batch' \
--header 'Authorization: Bearer ***' \
--header 'Content-Type: application/json' \
--header 'Accept: */*' \
--data-raw '{
    "enable_formula": true,
    "language": "en",
    "enable_table": true,
    "files": [
        {"url":"https://cdn-mineru.openxlab.org.cn/demo/example.pdf", "is_ocr": true, "data_id": "abcd"}
    ]
}'
```

#### 请求参数说明

| 参数 | 类型 | 必选 | 示例 | 描述 |
|------|------|------|------|------|
| enable_formula | bool | 否 | true | 是否开启公式识别，默认 true |
| enable_table | bool | 否 | true | 是否开启表格识别，默认 true |
| language | string | 否 | ch | 指定文档语言，默认 ch |
| file.url | string | 是 | https://cdn-mineru.openxlab.org.cn/demo/example.pdf | 文件链接 |
| file.is_ocr | bool | 否 | true | 是否启动 OCR 功能，默认 false |
| file.data_id | string | 否 | abc** | 解析对象对应的数据 ID |
| file.page_ranges | string | 否 | 1-600 | 指定页码范围 |
| callback | string | 否 | http://127.0.0.1/callback | 解析结果回调通知 URL |
| seed | string | 否 | abc** | 随机字符串，用于回调通知签名 |
| extra_formats | [string] | 否 | ["docx","html"] | 额外导出格式 |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "batch_id": "2bb2f0ec-a336-4a0a-b61a-241afaf9cc87"
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

### 2.3 批量获取任务结果

#### 接口信息
- **URL**: `GET /extract-results/batch/{batch_id}`
- **Authorization**: `Bearer {your_token}`

#### Python 示例

```python
import requests

url = f'https://mineru.net/api/v4/extract-results/batch/{batch_id}'
header = {
    'Content-Type': 'application/json',
    "Authorization": "Bearer eyJ0eXBlIjoiSl...请填写准确的！"
}
res = requests.get(url, headers=header)
print(res.status_code)
print(res.json())
print(res.json()["data"])
```

#### CURL 示例

```bash
curl --location --request GET 'https://mineru.net/api/v4/extract-results/batch/{batch_id}' \
--header 'Authorization: Bearer *****' \
--header 'Accept: */*'
```

#### 响应参数说明

| 参数 | 类型 | 示例 | 说明 |
|------|------|------|------|
| code | int | 0 | 接口状态码，成功：0 |
| msg | string | ok | 接口处理信息，成功："ok" |
| trace_id | string | c876cd60b202f2396de1f9e39a1b0172 | 请求 ID |
| data.batch_id | string | 2bb2f0ec-a336-4a0a-b61a-241afaf9cc87 | batch_id |
| data.extract_result.file_name | string | demo.pdf | 文件名 |
| data.extract_result.state | string | done | 任务处理状态 |
| data.extract_result.full_zip_url | string | https://cdn-mineru.openxlab.org.cn/pdf/xxx.zip | 文件解析结果压缩包 |
| data.extract_result.err_msg | string | 文件格式不支持 | 解析失败原因 |
| data.extract_result.data_id | string | abc** | 解析对象对应的数据 ID |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "batch_id": "2bb2f0ec-a336-4a0a-b61a-241afaf9cc87",
    "extract_result": [
      {
        "file_name": "example.pdf",
        "state": "done",
        "err_msg": "",
        "full_zip_url": "https://cdn-mineru.openxlab.org.cn/pdf/018e53ad-d4f1-475d-b380-36bf24db9914.zip"
      },
      {
        "file_name": "demo.pdf",
        "state": "running",
        "err_msg": "",
        "extract_progress": {
          "extracted_pages": 1,
          "total_pages": 2,
          "start_time": "2025-01-20 11:43:20"
        }
      }
    ]
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

## 三、回调机制

### 3.1 回调接口要求

- 支持 POST 方法
- UTF-8 编码
- Content-Type: application/json
- 包含参数 checksum 和 content

### 3.2 签名验证

**checksum 生成规则：**
```
checksum = SHA256(用户UID + seed + content)
```

### 3.3 回调重试机制

- 返回 HTTP 200 表示接收成功
- 其他状态码视为接收失败
- 最多重复推送 5 次
- 5 次后仍失败则不再推送

## 四、常见错误码

| 错误码 | 说明 | 解决建议 |
|--------|------|----------|
| A0202 | Token 错误 | 检查 Token 是否正确，或者更换新 Token |
| A0211 | Token 过期 | 更换新 Token |
| -500 | 传参错误 | 请确保参数类型及 Content-Type 正确 |
| -10001 | 服务异常 | 请稍后再试 |
| -10002 | 请求参数错误 | 检查请求参数格式 |
| -60001 | 生成上传 URL 失败 | 请稍后再试 |
| -60002 | 获取匹配的文件格式失败 | 检查文件类型和后缀名 |
| -60003 | 文件读取失败 | 请检查文件是否损坏并重新上传 |
| -60004 | 空文件 | 请上传有效文件 |
| -60005 | 文件大小超出限制 | 检查文件大小，最大支持 200MB |
| -60006 | 文件页数超过限制 | 请拆分文件后重试 |
| -60007 | 模型服务暂时不可用 | 请稍后重试或联系技术支持 |
| -60008 | 文件读取超时 | 检查 URL 可访问性 |
| -60009 | 任务提交队列已满 | 请稍后再试 |
| -60010 | 解析失败 | 请稍后再试 |
| -60011 | 获取有效文件失败 | 请确保文件已上传 |
| -60012 | 找不到任务 | 请确保 task_id 有效且未删除 |
| -60013 | 没有权限访问该任务 | 只能访问自己提交的任务 |
| -60014 | 删除运行中的任务 | 运行中的任务暂不支持删除 |
| -60015 | 文件转换失败 | 可以手动转为 PDF 再上传 |
| -60016 | 文件转换失败 | 文件转换为指定格式失败，可以尝试其他格式导出或重试 |

## 五、最佳实践

### 5.1 Token 管理
- 定期检查 Token 有效性
- 及时更新过期的 Token
- 安全存储 Token，避免泄露

### 5.2 文件处理
- 确保文件格式正确
- 控制文件大小在 200MB 以内
- 检查文件页数不超过 600 页
- 对于大文件，考虑拆分处理

### 5.3 错误处理
- 实现完善的错误处理机制
- 根据错误码进行相应的重试策略
- 记录详细的错误日志便于排查

### 5.4 性能优化
- 使用批量接口处理多个文件
- 合理设置回调机制避免频繁轮询
- 考虑异步处理提高系统响应性

### 5.5 监控和日志
- 监控 API 调用频率和成功率
- 记录关键操作的 trace_id
- 定期检查解析任务状态

## 六、注意事项

1. **网络限制**: GitHub、AWS 等国外 URL 可能会请求超时
2. **文件上传**: 上传文件时无须设置 Content-Type 请求头
3. **自动提交**: 文件上传完成后，系统会自动扫描并提交解析任务
4. **链接有效期**: 申请的文件上传链接有效期为 24 小时
5. **批量限制**: 单次批量操作不能超过 200 个文件
6. **优先级**: 超过 2000 页的部分优先级会降低

---

本文档基于 MinerU API v4 版本编写，如有更新请参考官方最新文档。