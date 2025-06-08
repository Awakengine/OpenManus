# OpenManus Web UI

这是为OpenManus AI助手系统开发的现代化Web用户界面，提供了直观的聊天体验和完整的用户管理功能。

## 功能特性

### 🎯 核心功能
- **用户认证系统**: 安全的用户注册、登录和会话管理
- **对话管理**: 创建、管理和组织多个对话
- **实时聊天**: 与OpenManus AI助手进行实时对话
- **消息历史**: 完整的对话历史记录和搜索
- **响应式设计**: 支持桌面和移动设备

### 🛡️ 安全特性
- 密码哈希加密存储
- 会话管理和超时
- SQL注入防护
- XSS攻击防护

### 💾 数据存储
- SQLite数据库存储用户信息
- 完整的对话历史记录
- 消息时间戳和元数据
- 自动数据库初始化

## 安装和设置

### 1. 环境要求

- Python 3.12+
- OpenManus项目依赖
- Web UI额外依赖

### 2. 安装依赖

首先确保已安装OpenManus的基础依赖：

```bash
# 安装OpenManus基础依赖
pip install -r requirements.txt

# 安装Web UI额外依赖
pip install -r webui_requirements.txt
```

### 3. 配置OpenManus

确保OpenManus配置文件已正确设置：

```bash
# 复制配置文件模板
cp config/config.example.toml config/config.toml

# 编辑配置文件，设置LLM API密钥等
vim config/config.toml
```

配置示例：

```toml
[llm]
model = "gpt-4"
base_url = "https://api.openai.com/v1"
api_key = "your-api-key-here"
max_tokens = 4096
temperature = 0.7
api_type = "openai"
```

### 4. 启动Web UI

使用提供的启动脚本：

```bash
# 基本启动
python run_webui.py

# 自定义主机和端口
python run_webui.py --host 0.0.0.0 --port 8080

# 启用调试模式
python run_webui.py --debug

# 跳过配置检查（不推荐）
python run_webui.py --no-config-check
```

### 5. 访问Web界面

启动后，在浏览器中访问：

```
http://127.0.0.1:5000
```

## 使用指南

### 首次使用

1. **注册账户**
   - 访问注册页面
   - 填写用户名、邮箱和密码
   - 点击"创建账户"

2. **登录系统**
   - 使用注册的用户名和密码登录
   - 系统会自动跳转到主界面

3. **开始对话**
   - 点击"新建对话"按钮
   - 输入对话标题
   - 开始与OpenManus AI助手聊天

### 对话管理

- **创建新对话**: 点击侧边栏的"+"按钮
- **切换对话**: 点击侧边栏中的对话项
- **重命名对话**: 点击对话项的菜单按钮
- **删除对话**: 通过对话菜单删除不需要的对话

### 聊天功能

- **发送消息**: 在输入框中输入消息，按Enter或点击发送按钮
- **查看历史**: 所有消息都会自动保存和显示
- **格式支持**: 支持基本的Markdown格式（粗体、斜体、代码）

## 数据库结构

Web UI使用SQLite数据库存储数据，包含以下表：

### users表
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

### conversations表
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

### messages表
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

## 贡献和支持

如果您发现问题或有改进建议，请：

1. 查看现有的GitHub Issues
2. 创建新的Issue描述问题
3. 提交Pull Request贡献代码

## 许可证

本项目遵循与OpenManus主项目相同的许可证。