# LM Studio 集成指南

本文档介绍如何将 LM Studio 与 OpenManus ChatUI 集成使用。

## LM Studio 简介

LM Studio 是一个本地运行大语言模型的桌面应用程序，它提供了与 OpenAI API 兼容的接口，使得现有的 OpenAI 客户端可以无缝切换到本地模型。

## 支持的 API 接口

LM Studio 提供以下 OpenAI 兼容的 API 接口：

- `GET /v1/models` - 获取可用模型列表
- `POST /v1/chat/completions` - 聊天完成接口
- `POST /v1/embeddings` - 文本嵌入接口
- `POST /v1/completions` - 文本完成接口

## 配置步骤

### 1. 启动 LM Studio 服务器

1. 打开 LM Studio 应用程序
2. 在左侧面板选择一个模型并加载
3. 切换到 "Local Server" 标签页
4. 点击 "Start Server" 启动本地服务器
5. 默认服务器地址为：`http://localhost:1234`

### 2. 配置 OpenManus ChatUI

创建配置文件 `config/config.toml`，参考以下示例：

```toml
[llm]
api_type = 'openai'                    # 使用 OpenAI 兼容 API
model = "your-model-name"              # LM Studio 中加载的模型名称
base_url = "http://localhost:1234/v1"  # LM Studio API 端点
api_key = "lm-studio"                  # API 密钥（本地服务可以是任意字符串）
max_tokens = 4096                      # 最大令牌数
temperature = 0.7                      # 温度参数

# 可选：如果模型支持视觉功能
[llm.vision]
api_type = 'openai'
model = "your-vision-model-name"
base_url = "http://localhost:1234/v1"
api_key = "lm-studio"
max_tokens = 4096
temperature = 0.7
```

### 3. 获取模型名称

可以通过以下方式获取 LM Studio 中可用的模型名称：

```bash
curl http://localhost:1234/v1/models
```

或者在 LM Studio 的 "Local Server" 页面查看当前加载的模型名称。

## 使用说明

### 模型选择

- 确保在 LM Studio 中已经下载并加载了所需的模型
- 配置文件中的 `model` 字段应该与 LM Studio 中显示的模型名称完全一致
- 支持同时配置文本模型和视觉模型（如果可用）

### 性能优化

1. **硬件要求**：
   - 推荐使用具有足够 VRAM 的 GPU
   - 确保有足够的系统内存

2. **模型设置**：
   - 根据硬件性能选择合适大小的模型
   - 调整 `max_tokens` 参数以平衡性能和输出长度
   - 根据需要调整 `temperature` 参数控制输出的随机性

### 故障排除

1. **连接问题**：
   - 确保 LM Studio 服务器正在运行
   - 检查防火墙设置是否阻止了本地连接
   - 验证端口 1234 是否可用

2. **模型问题**：
   - 确认模型已在 LM Studio 中正确加载
   - 检查模型名称是否与配置文件中的名称匹配
   - 验证模型是否支持所需的功能（如聊天、嵌入等）

3. **性能问题**：
   - 监控系统资源使用情况
   - 考虑降低 `max_tokens` 值
   - 尝试使用更小的模型

## 高级配置

### 自定义端口

如果 LM Studio 使用非默认端口，请相应更新 `base_url`：

```toml
base_url = "http://localhost:YOUR_PORT/v1"
```

### 网络访问

如果需要从其他机器访问 LM Studio 服务器：

1. 在 LM Studio 中配置服务器监听所有接口
2. 更新配置文件中的 `base_url`：

```toml
base_url = "http://YOUR_SERVER_IP:1234/v1"
```

### 代理设置

如果需要通过代理访问，可以在配置文件中添加代理设置：

```toml
[browser.proxy]
server = "http://proxy-server:port"
username = "proxy-username"
password = "proxy-password"
```

## 示例配置文件

完整的配置示例请参考：`config/config.example-model-lmstudio.toml`

## 注意事项

1. LM Studio 是本地运行的服务，确保有足够的硬件资源
2. 模型加载可能需要一些时间，特别是大型模型
3. 本地模型的响应速度取决于硬件性能
4. 某些高级功能可能需要特定的模型支持
5. 定期更新 LM Studio 以获得最新功能和性能改进

## 支持的模型类型

- 文本生成模型（如 Llama、Mistral、CodeLlama 等）
- 多模态模型（支持图像和文本的模型）
- 代码生成模型
- 对话模型

根据具体需求选择合适的模型，并确保模型与 OpenAI API 格式兼容。