#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenManus Web UI 启动器

此脚本用于启动 OpenManus Web UI 应用程序，并进行适当的配置。
提供了依赖检查、配置验证和环境设置等功能。
"""

import argparse
import os
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from webui_app import OpenManusWebUI
from app.logger import logger
from app.config import config


def check_dependencies():
    """检查是否安装了所有必需的依赖项。"""
    try:
        import flask
        import werkzeug

        logger.info("找到 Flask 依赖项")
    except ImportError as e:
        logger.error(f"缺少 Flask 依赖项: {e}")
        logger.error("请安装 Web UI 依赖项: pip install -r webui_requirements.txt")
        return False

    return True


def check_config():
    """检查 OpenManus 配置是否正确设置。"""
    config_file = project_root / "config" / "config.toml"

    if not config_file.exists():
        logger.warning(f"未找到配置文件: {config_file}")
        logger.warning(
            "请将 config/config.example.toml 复制到 config/config.toml 并进行配置"
        )
        return False

    try:
        # 测试配置是否可以加载
        _ = config.llm_config
        logger.info("配置加载成功")
        return True
    except Exception as e:
        logger.error(f"配置错误: {e}")
        return False


def setup_environment():
    """设置环境变量和路径。"""
    # 为 Flask 设置环境变量
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("FLASK_DEBUG", "1")

    # 确保工作区目录存在
    workspace_dir = project_root / "workspace"
    workspace_dir.mkdir(exist_ok=True)

    logger.info(f"工作区目录: {workspace_dir}")


def main():
    """Web UI 启动器的主入口点。"""
    parser = argparse.ArgumentParser(description="OpenManus Web UI 启动器")
    parser.add_argument(
        "--host", default="127.0.0.1", help="绑定的主机地址 (默认: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=5000, help="绑定的端口 (默认: 5000)"
    )
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--no-config-check", action="store_true", help="跳过配置检查")

    args = parser.parse_args()

    logger.info("正在启动 OpenManus Web UI...")

    # 检查依赖项
    if not check_dependencies():
        sys.exit(1)

    # 检查配置（除非跳过）
    if not args.no_config_check and not check_config():
        logger.warning("配置检查失败，但仍然继续...")
        logger.warning("没有正确配置，某些功能可能无法正常工作")

    # 设置环境
    setup_environment()

    try:
        # 创建并运行 Web UI
        webui = OpenManusWebUI()

        logger.info(f"Web UI 将在以下地址可用: http://{args.host}:{args.port}")
        logger.info("按 Ctrl+C 停止服务器")

        webui.run(host=args.host, port=args.port, debug=args.debug)

    except KeyboardInterrupt:
        logger.info("正在关闭 Web UI...")
    except Exception as e:
        logger.error(f"启动 Web UI 失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
