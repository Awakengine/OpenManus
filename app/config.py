import json
import threading
import tomllib
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = get_project_root()
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


class LLMSettings(BaseModel):
    model: str = Field(..., description="模型名称")
    base_url: str = Field(..., description="API 基础 URL")
    api_key: str = Field(..., description="API 密钥")
    max_tokens: int = Field(4096, description="每个请求的最大令牌数")
    max_input_tokens: Optional[int] = Field(
        None,
        description="所有请求使用的最大输入令牌数（None 表示无限制）",
    )
    temperature: float = Field(1.0, description="采样温度")
    api_type: str = Field(..., description="Azure、Openai 或 Ollama")
    api_version: str = Field(..., description="如果是 AzureOpenai 则为 Azure Openai 版本")


class ProxySettings(BaseModel):
    server: str = Field(None, description="代理服务器地址")
    username: Optional[str] = Field(None, description="代理用户名")
    password: Optional[str] = Field(None, description="代理密码")


class SearchSettings(BaseModel):
    engine: str = Field(default="Google", description="LLM 使用的搜索引擎")
    fallback_engines: List[str] = Field(
        default_factory=lambda: ["DuckDuckGo", "Baidu", "Bing"],
        description="主搜索引擎失败时尝试的备用搜索引擎",
    )
    retry_delay: int = Field(
        default=60,
        description="所有引擎都失败后重试前等待的秒数",
    )
    max_retries: int = Field(
        default=3,
        description="所有引擎都失败时重试的最大次数",
    )
    lang: str = Field(
        default="en",
        description="搜索结果的语言代码（例如：en、zh、fr）",
    )
    country: str = Field(
        default="us",
        description="搜索结果的国家代码（例如：us、cn、uk）",
    )


class BrowserSettings(BaseModel):
    headless: bool = Field(False, description="是否在无头模式下运行浏览器")
    disable_security: bool = Field(
        True, description="禁用浏览器安全功能"
    )
    extra_chromium_args: List[str] = Field(
        default_factory=list, description="传递给浏览器的额外参数"
    )
    chrome_instance_path: Optional[str] = Field(
        None, description="要使用的 Chrome 实例路径"
    )
    wss_url: Optional[str] = Field(
        None, description="通过 WebSocket 连接到浏览器实例"
    )
    cdp_url: Optional[str] = Field(
        None, description="通过 CDP 连接到浏览器实例"
    )
    proxy: Optional[ProxySettings] = Field(
        None, description="浏览器的代理设置"
    )
    max_content_length: int = Field(
        2000, description="内容检索操作的最大长度"
    )


class SandboxSettings(BaseModel):
    """执行沙箱的配置"""

    use_sandbox: bool = Field(False, description="是否使用沙箱")
    image: str = Field("python:3.12-slim", description="基础镜像")
    work_dir: str = Field("/workspace", description="容器工作目录")
    memory_limit: str = Field("512m", description="内存限制")
    cpu_limit: float = Field(1.0, description="CPU 限制")
    timeout: int = Field(300, description="默认命令超时时间（秒）")
    network_enabled: bool = Field(
        False, description="是否允许网络访问"
    )


class MCPServerConfig(BaseModel):
    """单个 MCP 服务器的配置"""

    type: str = Field(..., description="服务器连接类型（sse 或 stdio）")
    url: Optional[str] = Field(None, description="SSE 连接的服务器 URL")
    command: Optional[str] = Field(None, description="stdio 连接的命令")
    args: List[str] = Field(
        default_factory=list, description="stdio 命令的参数"
    )


class MCPSettings(BaseModel):
    """MCP（模型上下文协议）的配置"""

    server_reference: str = Field(
        "app.mcp.server", description="MCP 服务器的模块引用"
    )
    servers: Dict[str, MCPServerConfig] = Field(
        default_factory=dict, description="MCP 服务器配置"
    )

    @classmethod
    def load_server_config(cls) -> Dict[str, MCPServerConfig]:
        """从 JSON 文件加载 MCP 服务器配置"""
        config_path = PROJECT_ROOT / "config" / "mcp.json"

        try:
            config_file = config_path if config_path.exists() else None
            if not config_file:
                return {}

            with config_file.open() as f:
                data = json.load(f)
                servers = {}

                # 遍历配置文件中的 MCP 服务器
                for server_id, server_config in data.get("mcpServers", {}).items():
                    servers[server_id] = MCPServerConfig(
                        type=server_config["type"],
                        url=server_config.get("url"),
                        command=server_config.get("command"),
                        args=server_config.get("args", []),
                    )
                return servers
        except Exception as e:
            raise ValueError(f"加载 MCP 服务器配置失败: {e}")


class AppConfig(BaseModel):
    """应用程序配置类"""
    llm: Dict[str, LLMSettings]
    sandbox: Optional[SandboxSettings] = Field(
        None, description="沙箱配置"
    )
    browser_config: Optional[BrowserSettings] = Field(
        None, description="浏览器配置"
    )
    search_config: Optional[SearchSettings] = Field(
        None, description="搜索配置"
    )
    mcp_config: Optional[MCPSettings] = Field(None, description="MCP 配置")

    class Config:
        arbitrary_types_allowed = True


class Config:
    """配置管理器（单例模式）"""
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        """确保单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化配置管理器"""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._config = None
                    self._load_initial_config()
                    self._initialized = True

    @staticmethod
    def _get_config_path() -> Path:
        """获取配置文件路径"""
        root = PROJECT_ROOT
        config_path = root / "config" / "config.toml"
        if config_path.exists():
            return config_path
        example_path = root / "config" / "config.example.toml"
        if example_path.exists():
            return example_path
        raise FileNotFoundError("在配置目录中未找到配置文件")

    def _load_config(self) -> dict:
        """加载配置文件"""
        config_path = self._get_config_path()
        with config_path.open("rb") as f:
            return tomllib.load(f)

    def _load_initial_config(self):
        """加载初始配置"""
        raw_config = self._load_config()
        base_llm = raw_config.get("llm", {})
        llm_overrides = {
            k: v for k, v in raw_config.get("llm", {}).items() if isinstance(v, dict)
        }

        # 设置默认的 LLM 配置
        default_settings = {
            "model": base_llm.get("model"),
            "base_url": base_llm.get("base_url"),
            "api_key": base_llm.get("api_key"),
            "max_tokens": base_llm.get("max_tokens", 4096),
            "max_input_tokens": base_llm.get("max_input_tokens"),
            "temperature": base_llm.get("temperature", 1.0),
            "api_type": base_llm.get("api_type", ""),
            "api_version": base_llm.get("api_version", ""),
        }

        # 处理浏览器配置
        browser_config = raw_config.get("browser", {})
        browser_settings = None

        if browser_config:
            # 处理代理设置
            proxy_config = browser_config.get("proxy", {})
            proxy_settings = None

            if proxy_config and proxy_config.get("server"):
                proxy_settings = ProxySettings(
                    **{
                        k: v
                        for k, v in proxy_config.items()
                        if k in ["server", "username", "password"] and v
                    }
                )

            # 过滤有效的浏览器配置参数
            valid_browser_params = {
                k: v
                for k, v in browser_config.items()
                if k in BrowserSettings.__annotations__ and v is not None
            }

            # 如果有代理设置，添加到参数中
            if proxy_settings:
                valid_browser_params["proxy"] = proxy_settings

            # 只有在有有效参数时才创建 BrowserSettings
            if valid_browser_params:
                browser_settings = BrowserSettings(**valid_browser_params)

        # 处理搜索配置
        search_config = raw_config.get("search", {})
        search_settings = None
        if search_config:
            search_settings = SearchSettings(**search_config)
            
        # 处理沙箱配置
        sandbox_config = raw_config.get("sandbox", {})
        if sandbox_config:
            sandbox_settings = SandboxSettings(**sandbox_config)
        else:
            sandbox_settings = SandboxSettings()

        # 处理 MCP 配置
        mcp_config = raw_config.get("mcp", {})
        mcp_settings = None
        if mcp_config:
            # 从 JSON 加载服务器配置
            mcp_config["servers"] = MCPSettings.load_server_config()
            mcp_settings = MCPSettings(**mcp_config)
        else:
            mcp_settings = MCPSettings(servers=MCPSettings.load_server_config())

        config_dict = {
            "llm": {
                "default": default_settings,
                **{
                    name: {**default_settings, **override_config}
                    for name, override_config in llm_overrides.items()
                },
            },
            "sandbox": sandbox_settings,
            "browser_config": browser_settings,
            "search_config": search_settings,
            "mcp_config": mcp_settings,
        }

        self._config = AppConfig(**config_dict)

    @property
    def llm(self) -> Dict[str, LLMSettings]:
        """获取 LLM 配置"""
        return self._config.llm

    @property
    def sandbox(self) -> SandboxSettings:
        """获取沙箱配置"""
        return self._config.sandbox

    @property
    def browser_config(self) -> Optional[BrowserSettings]:
        """获取浏览器配置"""
        return self._config.browser_config

    @property
    def search_config(self) -> Optional[SearchSettings]:
        """获取搜索配置"""
        return self._config.search_config

    @property
    def mcp_config(self) -> MCPSettings:
        """获取 MCP 配置"""
        return self._config.mcp_config

    @property
    def workspace_root(self) -> Path:
        """获取工作区根目录"""
        return WORKSPACE_ROOT

    @property
    def root_path(self) -> Path:
        """Get the root path of the application"""
        return PROJECT_ROOT


config = Config()
