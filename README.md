# OpenManus

<div align="center">

[![GitHub stars](https://img.shields.io/github/stars/MannaandPoem/OpenManus.svg?style=social&label=Star)](https://github.com/MannaandPoem/OpenManus)
[![GitHub forks](https://img.shields.io/github/forks/MannaandPoem/OpenManus.svg?style=social&label=Fork)](https://github.com/MannaandPoem/OpenManus)
[![GitHub watchers](https://img.shields.io/github/watchers/MannaandPoem/OpenManus.svg?style=social&label=Watch)](https://github.com/MannaandPoem/OpenManus)
[![GitHub followers](https://img.shields.io/github/followers/MannaandPoem.svg?style=social&label=Follow)](https://github.com/MannaandPoem)

</div>

**OpenManus** 是一个开源的多模态AI代理系统，能够通过自然语言与计算机进行交互。

**OpenManus** 集成了 [Computer Use](https://www.anthropic.com/news/3-5-models-and-computer-use)、[Browser Use](https://github.com/gregpr07/browser-use)、[MCP](https://github.com/modelcontextprotocol/python-sdk) 等前沿技术，让用户能够用自然语言控制计算机完成各种复杂任务。

## ✨ 核心特性

### 🤖 多模态AI代理
- **Computer Use**: 能够看到屏幕并执行点击、输入、滚动等操作
- **Browser Use**: 自动化网页导航、表单填写、数据提取
- **Code Execution**: 执行Python、JavaScript等多种编程语言代码
- **File Operations**: 创建、编辑、整理和分析文件

### 🌐 现代化Web界面
- **用户认证**: 安全的登录和用户管理系统
- **对话历史**: 持久化的聊天记录和对话管理
- **实时聊天**: 响应式的聊天界面
- **文件管理**: 拖拽上传文件功能
- **设置管理**: 直观的配置面板

### 🛠️ 开发者友好
- **MCP集成**: 基于Model Context Protocol的可扩展工具系统
- **插件架构**: 轻松添加自定义工具和代理
- **多LLM支持**: 支持OpenAI、Anthropic、Ollama等多种模型
- **高度可配置**: 丰富的配置选项和自定义能力

### 🔧 内置工具
- **Python执行器**: 代码执行和调试
- **浏览器自动化**: Web任务自动化
- **文件编辑器**: 文本文件编辑和操作
- **搜索功能**: 网络搜索和数据收集
- **终端访问**: 系统命令执行

## 🚀 快速开始

### 环境要求

- **Python**: 3.12 或更高版本
- **操作系统**: Windows、macOS、Linux
- **内存**: 建议 4GB 以上
- **存储**: 至少 2GB 可用空间

### 安装方式

#### 方式一：使用 conda（推荐）

```bash
# 克隆项目
git clone https://github.com/MannaandPoem/OpenManus.git
cd OpenManus

# 创建并激活虚拟环境
conda create -n openmanus python=3.12
conda activate openmanus

# 安装依赖
pip install -r requirements.txt
```

#### 方式二：使用 uv（更快）

```bash
# 安装 uv
pip install uv

# 克隆项目
git clone https://github.com/MannaandPoem/OpenManus.git
cd OpenManus

# 使用 uv 安装依赖
uv pip install -r requirements.txt
```

### 配置设置

1. **复制配置文件**：
```bash
cp config/config.example.toml config/config.toml
```

2. **编辑配置文件**，设置您的 LLM API 密钥：

**Anthropic Claude 示例**：
```toml
[llm]
model = "claude-3-7-sonnet-20250219"
base_url = "https://api.anthropic.com/v1/"
api_key = "YOUR_API_KEY"  # 替换为您的实际 API 密钥
max_tokens = 8192
temperature = 0.0
```

**LM Studio 本地模型示例**：
```toml
[llm]
api_type = 'openai'
model = "your-model-name"              # LM Studio 中加载的模型名称
base_url = "http://localhost:1234/v1"  # LM Studio API 端点
api_key = "lm-studio"                  # 本地服务可以是任意字符串
max_tokens = 4096
temperature = 0.7
```

> 💡 **提示**: 更多配置示例请参考 `config/` 目录下的示例文件，包括 Azure OpenAI、Ollama 等配置。
> 📖 **LM Studio 详细配置**: 请参考 [LM Studio 集成指南](docs/LM_STUDIO_INTEGRATION.md)

支持的 LLM 提供商：
- **Anthropic Claude**: claude-3-7-sonnet, claude-3-haiku 等
- **OpenAI**: gpt-4o, gpt-4o-mini 等
- **Azure OpenAI**: 企业级 OpenAI 服务
- **Ollama**: 本地部署的开源模型
- **LM Studio**: 本地运行的大语言模型，提供 OpenAI 兼容 API
- **Amazon Bedrock**: AWS 托管的 AI 服务

### 🚀 命令行界面

直接在命令行中运行 OpenManus：

```bash
python main.py
```

然后在终端中输入您的想法，让 OpenManus 为您实现！

### 🌐 Web 用户界面

启动更友好的 Web 界面：

```bash
python run_webui.py
```

然后在浏览器中访问 `http://localhost:5000`，享受现代化的 Web 界面：
- 用户认证和注册
- 持久化对话历史
- 实时聊天界面
- 文件上传和管理
- 配置设置

### 🔧 高级用法

**MCP 工具版本**：
```bash
python run_mcp.py
```

**多代理流程（实验性）**：
```bash
python run_flow.py
```

## 📖 使用示例

### 代码开发
```
"帮我创建一个Python网络爬虫，用于从电商网站提取产品信息"
```

### 数据分析
```
"分析这个CSV文件，并创建一个显示销售趋势的可视化图表"
```

### Web自动化
```
"访问GitHub，搜索Python机器学习项目，并总结前5个结果"
```

### 文件操作
```
"整理我的下载文件夹，按文件类型分类并生成摘要报告"
```

### 系统管理
```
"检查系统性能，生成资源使用报告"
```

## 🛠️ 高级配置

### MCP 服务器配置

OpenManus 支持 Model Context Protocol (MCP) 服务器，可以扩展更多功能：

```bash
# 启动 MCP 服务器
python run_mcp_server.py

# 在另一个终端运行 MCP 客户端
python run_mcp.py
```

### 浏览器配置

配置浏览器自动化功能：

```toml
[browser]
headless = false  # 是否无头模式
timeout = 30      # 超时时间（秒）
viewport_width = 1280
viewport_height = 720
```

### 搜索引擎配置

```toml
[search]
engine = "Google"  # 主搜索引擎
fallback_engines = ["DuckDuckGo", "Baidu", "Bing"]
max_retries = 3
```

## 🏗️ 项目架构

### 核心组件

```
OpenManus/
├── app/
│   ├── agent/             # AI 代理核心
│   │   ├── manus.py      # 主代理类
│   │   └── flow.py       # 多代理流程
│   ├── tool/             # 工具系统
│   │   ├── base.py       # 工具基类
│   │   ├── browser.py    # 浏览器工具
│   │   ├── file.py       # 文件操作工具
│   │   └── search.py     # 搜索工具
│   ├── mcp/              # MCP 协议支持
│   └── config.py         # 配置管理
├── webui/                # Web 界面
│   ├── static/           # 静态资源
│   ├── templates/        # HTML 模板
│   └── app.py           # Web 应用
├── main.py              # 命令行入口
├── run_webui.py         # Web UI 启动
├── run_mcp.py           # MCP 客户端
└── config.example.toml  # 配置示例
```

### 工具系统

OpenManus 采用模块化的工具系统：

- **文件工具**: 文件读写、目录操作、文件搜索
- **浏览器工具**: 网页访问、元素交互、截图
- **搜索工具**: 多引擎搜索、结果聚合
- **系统工具**: 命令执行、进程管理
- **MCP 工具**: 外部服务集成

### 数据库结构

Web UI使用SQLite数据库存储数据，包含以下表：

#### users表
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);
```

#### conversations表
```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

#### messages表
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    tool_call_id TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
);
```

## API接口

Web UI提供以下REST API接口：

### 认证接口
- `POST /login` - 用户登录
- `POST /register` - 用户注册
- `GET /logout` - 用户登出

### 对话接口
- `GET /api/conversations` - 获取用户的所有对话
- `POST /api/conversations` - 创建新对话
- `GET /api/conversations/<id>/messages` - 获取对话消息

### 聊天接口
- `POST /api/chat` - 发送消息并获取AI回复

## 自定义和扩展

### 修改样式

编辑 `templates/base.html` 中的CSS样式来自定义界面外观。

### 添加新功能

1. 在 `webui_app.py` 中添加新的路由
2. 在相应的HTML模板中添加前端界面
3. 使用JavaScript处理用户交互

### 集成其他AI模型

修改 `webui_app.py` 中的 `process_with_agent` 方法来集成其他AI模型或服务。

## 故障排除

### 常见问题

1. **配置文件错误**
   ```
   错误: Configuration file not found
   解决: 确保 config/config.toml 文件存在并正确配置
   ```

2. **依赖缺失**
   ```
   错误: Missing Flask dependencies
   解决: pip install -r webui_requirements.txt
   ```

3. **数据库权限问题**
   ```
   错误: Permission denied to create database
   解决: 确保当前目录有写权限
   ```

4. **端口被占用**
   ```
   错误: Address already in use
   解决: 使用 --port 参数指定其他端口
   ```

### 调试模式

启用调试模式获取更详细的错误信息：

```bash
python run_webui.py --debug
```

### 日志查看

检查控制台输出和日志文件来诊断问题。

## 安全注意事项

1. **生产环境部署**
   - 更改默认的Flask secret key
   - 使用HTTPS协议
   - 配置防火墙规则
   - 定期备份数据库

2. **密码安全**
   - 使用强密码
   - 定期更换密码
   - 启用会话超时

3. **数据保护**
   - 定期备份SQLite数据库
   - 限制数据库文件访问权限
   - 考虑加密敏感数据

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. **Fork 项目**
2. **创建功能分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add some AmazingFeature'`)
4. **推送到分支** (`git push origin feature/AmazingFeature`)
5. **创建 Pull Request**

### 开发环境设置

```bash
# 克隆项目
git clone https://github.com/Awakengine/OpenManus.git
cd OpenManus

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest

# 代码格式化
black .
flake8 .
```

### 代码规范

- 遵循 PEP 8 Python 代码规范
- 使用类型提示
- 编写单元测试
- 添加适当的文档字符串

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

感谢所有为 OpenManus 项目做出贡献的开发者和用户！

## 📞 联系我们

- **GitHub Issues**: [提交问题](https://github.com/Awakengine/OpenManus/issues)
- **讨论区**: [GitHub Discussions](https://github.com/Awakengine/OpenManus/discussions)
- **邮箱**: your-email@example.com

---

⭐ 如果这个项目对您有帮助，请给我们一个 Star！