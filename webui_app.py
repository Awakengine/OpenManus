#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenManus Web UI 应用程序

为 OpenManus AI 代理系统提供 Web 界面，支持 SQLite 数据库
用于用户管理和对话历史记录。
"""

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.agent.manus import Manus
from app.config import config
from app.logger import logger
from app.schema import Message, Role


class DatabaseManager:
    """管理用户和对话的 SQLite 数据库操作。"""

    def __init__(self, db_path: str = "openmanus_webui.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """初始化数据库并创建所需的表。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 用户表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """
            )

            # 如果角色列不存在则添加（用于现有数据库）
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
                conn.commit()
            except sqlite3.OperationalError:
                # 列已存在
                pass

            # 注意：已移除自动创建admin默认管理员用户的逻辑
            # 系统将只保留awakengine作为超级管理员账户

            # 检查 awakengine 用户是否存在并设置为超级管理员
            cursor.execute(
                "SELECT id, role FROM users WHERE username = ?", ("awakengine",)
            )
            awakengine_user = cursor.fetchone()

            if awakengine_user:
                if awakengine_user[1] != "super_admin":
                    cursor.execute(
                        "UPDATE users SET role = 'super_admin' WHERE username = ?",
                        ("awakengine",),
                    )
                    conn.commit()
                    logger.info("已将 awakengine 用户更新为超级管理员角色")
            else:
                # 如果 awakengine 用户不存在，则创建为超级管理员
                awakengine_password_hash = generate_password_hash("awakengine123")
                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        "awakengine",
                        "awakengine@openmanus.local",
                        awakengine_password_hash,
                        "super_admin",
                    ),
                )
                conn.commit()
                logger.info(
                    "已创建 awakengine 超级管理员用户: username=awakengine, password=awakengine123"
                )

            # 检查 admin 用户是否存在并创建为超级管理员
            cursor.execute(
                "SELECT id, role FROM users WHERE username = ?", ("admin",)
            )
            admin_user = cursor.fetchone()

            if admin_user:
                if admin_user[1] != "super_admin":
                    cursor.execute(
                        "UPDATE users SET role = 'super_admin' WHERE username = ?",
                        ("admin",),
                    )
                    conn.commit()
                    logger.info("已将 admin 用户更新为超级管理员角色")
            else:
                # 如果 admin 用户不存在，则创建为超级管理员
                admin_password_hash = generate_password_hash("admin123")
                cursor.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        "admin",
                        "admin@openmanus.local",
                        admin_password_hash,
                        "super_admin",
                    ),
                )
                conn.commit()
                logger.info(
                    "已创建 admin 超级管理员用户: username=admin, password=admin123"
                )

            # 对话表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """
            )

            # 消息表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    tool_call_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            """
            )

            conn.commit()

    def create_user(self, username: str, email: str, password: str) -> bool:
        """创建新用户账户。"""
        try:
            password_hash = generate_password_hash(password)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, password_hash),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """验证用户凭据。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, password_hash, role FROM users WHERE username = ? AND is_active = 1",
                (username,),
            )
            user = cursor.fetchone()

            if user and check_password_hash(user[3], password):
                # 更新最后登录时间
                cursor.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                    (user[0],),
                )
                conn.commit()

                return {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "role": user[4],
                }
        return None

    def create_conversation(self, user_id: int, title: str) -> str:
        """创建新对话。"""
        conversation_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
                (conversation_id, user_id, title),
            )
            conn.commit()
        return conversation_id

    def get_user_conversations(self, user_id: int) -> List[Dict]:
        """获取用户的所有对话。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            )
            conversations = cursor.fetchall()

            return [
                {
                    "id": conv[0],
                    "title": conv[1],
                    "created_at": conv[2],
                    "updated_at": conv[3],
                }
                for conv in conversations
            ]

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[str] = None,
        tool_call_id: Optional[str] = None,
    ):
        """将消息保存到数据库。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (conversation_id, role, content, tool_calls, tool_call_id) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role, content, tool_calls, tool_call_id),
            )

            # 更新对话时间戳
            cursor.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,),
            )
            conn.commit()

    def get_conversation_messages(self, conversation_id: str) -> List[Dict]:
        """获取对话的所有消息。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content, tool_calls, tool_call_id, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp",
                (conversation_id,),
            )
            messages = cursor.fetchall()

            return [
                {
                    "role": msg[0],
                    "content": msg[1],
                    "tool_calls": json.loads(msg[2]) if msg[2] else None,
                    "tool_call_id": msg[3],
                    "timestamp": msg[4],
                }
                for msg in messages
            ]

    def get_all_users(self) -> List[Dict]:
        """获取所有用户（仅管理员）。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, role, created_at, last_login, is_active FROM users ORDER BY created_at DESC"
            )
            users = cursor.fetchall()

            return [
                {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "role": user[3],
                    "created_at": user[4],
                    "last_login": user[5],
                    "is_active": bool(user[6]),
                }
                for user in users
            ]

    def update_user_role(self, user_id: int, role: str) -> bool:
        """更新用户角色（仅管理员）。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET role = ? WHERE id = ?", (role, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def update_user_status(self, user_id: int, is_active: bool) -> bool:
        """更新用户活跃状态（仅管理员）。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET is_active = ? WHERE id = ?", (is_active, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def delete_user(self, user_id: int) -> bool:
        """删除用户及所有相关数据（仅管理员）。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 获取用户的对话
                cursor.execute(
                    "SELECT id FROM conversations WHERE user_id = ?", (user_id,)
                )
                conversation_ids = [row[0] for row in cursor.fetchall()]

                # 删除用户所有对话的消息
                for conv_id in conversation_ids:
                    cursor.execute(
                        "DELETE FROM messages WHERE conversation_id = ?", (conv_id,)
                    )

                # 删除对话
                cursor.execute(
                    "DELETE FROM conversations WHERE user_id = ?", (user_id,)
                )

                # 删除用户
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

                conn.commit()
                return True
        except Exception:
            return False

    def create_user_with_role(
        self, username: str, email: str, password: str, role: str = "user"
    ) -> bool:
        """创建带有指定角色的新用户账户。"""
        try:
            password_hash = generate_password_hash(password)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (username, email, password_hash, role),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def reset_user_password(self, user_id: int, new_password: str) -> bool:
        """重置用户密码。"""
        try:
            password_hash = generate_password_hash(new_password)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (password_hash, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户信息。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, email, password_hash, role, created_at, last_login, is_active FROM users WHERE id = ?",
                (user_id,),
            )
            user = cursor.fetchone()

            if user:
                return {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "password_hash": user[3],
                    "role": user[4],
                    "created_at": user[5],
                    "last_login": user[6],
                    "is_active": bool(user[7]),
                }
        return None

    def update_user_email(self, user_id: int, email: str) -> bool:
        """更新用户邮箱。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET email = ? WHERE id = ?", (email, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False

    def update_user_password(self, user_id: int, new_password: str) -> bool:
        """更新用户密码。"""
        try:
            password_hash = generate_password_hash(new_password)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (password_hash, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False

    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码。"""
        return check_password_hash(password_hash, password)

    def get_user_details(self, user_id: int) -> Optional[Dict]:
        """获取用户详细信息。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, username, email, role, created_at, last_login, is_active,
                   (SELECT COUNT(*) FROM conversations WHERE user_id = ?) as conversation_count,
                   (SELECT COUNT(*) FROM messages WHERE conversation_id IN
                    (SELECT id FROM conversations WHERE user_id = ?)) as message_count
                   FROM users WHERE id = ?""",
                (user_id, user_id, user_id),
            )
            user = cursor.fetchone()

            if user:
                return {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "role": user[3],
                    "created_at": user[4],
                    "last_login": user[5],
                    "is_active": bool(user[6]),
                    "conversation_count": user[7],
                    "message_count": user[8],
                }
        return None

    def batch_delete_users(self, user_ids: List[int]) -> int:
        """批量删除用户。"""
        success_count = 0
        for user_id in user_ids:
            if self.delete_user(user_id):
                success_count += 1
        return success_count

    def batch_update_user_status(self, user_ids: List[int], is_active: bool) -> int:
        """批量更新用户状态。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" * len(user_ids))
                cursor.execute(
                    f"UPDATE users SET is_active = ? WHERE id IN ({placeholders})",
                    [is_active] + user_ids,
                )
                conn.commit()
                return cursor.rowcount
        except Exception:
            return 0

    def get_system_stats(self) -> Dict:
        """获取系统统计信息。"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 用户统计
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
            active_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'super_admin'")
            super_admin_users = cursor.fetchone()[0]

            # 对话统计
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total_conversations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]

            # 最近活跃用户
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE last_login > datetime('now', '-7 days')"
            )
            recent_active_users = cursor.fetchone()[0]

            return {
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "inactive": total_users - active_users,
                    "admin": admin_users,
                    "super_admin": super_admin_users,
                    "recent_active": recent_active_users,
                },
                "conversations": {"total": total_conversations},
                "messages": {"total": total_messages},
            }


class OpenManusWebUI:
    """主要的 Web UI 应用程序类。"""

    def __init__(self):
        self.app = Flask(__name__)
        self.app.secret_key = "openmanus-webui-secret-key-change-in-production"
        self.db = DatabaseManager()
        self.agent_instances = {}  # 存储每个会话的代理实例

        self.setup_routes()

    def setup_routes(self):
        """设置 Flask 路由。"""

        @self.app.route("/")
        def index():
            # 首页显示简介页面，不需要登录
            return render_template("intro.html")

        @self.app.route("/chat")
        def chat():
            # 聊天页面，支持游客模式
            return render_template("chat.html")

        @self.app.route("/demo")
        def demo():
            # 重定向到聊天页面的游客模式
            return redirect(url_for("chat", guest="true"))

        @self.app.route("/login", methods=["GET", "POST"])
        def login():
            if request.method == "POST":
                data = request.get_json()
                username = data.get("username")
                password = data.get("password")

                user = self.db.authenticate_user(username, password)
                if user:
                    session["user_id"] = user["id"]
                    session["username"] = user["username"]
                    session["role"] = user["role"]
                    return jsonify({"success": True})
                else:
                    return jsonify({"success": False, "error": "用户名或密码错误"})

            return render_template("login.html")

        @self.app.route("/register", methods=["GET", "POST"])
        def register():
            if request.method == "POST":
                data = request.get_json()
                username = data.get("username")
                email = data.get("email")
                password = data.get("password")

                if self.db.create_user(username, email, password):
                    return jsonify({"success": True})
                else:
                    return jsonify({"success": False, "error": "用户名或邮箱已存在"})

            return render_template("register.html")

        @self.app.route("/logout")
        def logout():
            session.clear()
            return redirect(url_for("login"))

        @self.app.route("/settings")
        def settings():
            """设置页面"""
            if "user_id" not in session:
                return redirect(url_for("login"))
            return render_template("settings.html")

        @self.app.route("/api/profile", methods=["GET"])
        def get_profile():
            """获取用户个人信息"""
            if "user_id" not in session:
                return jsonify({"error": "未认证"}), 401

            user = self.db.get_user_by_id(session["user_id"])
            if user:
                return jsonify(
                    {
                        "success": True,
                        "user": {
                            "username": user["username"],
                            "email": user["email"],
                            "role": user["role"],
                        },
                    }
                )
            else:
                return jsonify({"error": "用户不存在"}), 404

        @self.app.route("/api/profile", methods=["PUT"])
        def update_profile():
            """更新用户个人信息"""
            if "user_id" not in session:
                return jsonify({"error": "未认证"}), 401

            data = request.get_json()
            email = data.get("email")
            current_password = data.get("currentPassword")
            new_password = data.get("newPassword")

            if not email:
                return jsonify({"error": "邮箱不能为空"}), 400

            # 验证当前密码
            user = self.db.get_user_by_id(session["user_id"])
            if not user:
                return jsonify({"error": "用户不存在"}), 404

            if not self.db.verify_password(current_password, user["password_hash"]):
                return jsonify({"error": "当前密码错误"}), 400

            # 更新邮箱
            if not self.db.update_user_email(session["user_id"], email):
                return jsonify({"error": "邮箱更新失败，可能已被其他用户使用"}), 400

            # 如果提供了新密码，则更新密码
            if new_password:
                if len(new_password) < 6:
                    return jsonify({"error": "新密码长度至少6位"}), 400

                if not self.db.update_user_password(session["user_id"], new_password):
                    return jsonify({"error": "密码更新失败"}), 500

            return jsonify({"success": True})

        @self.app.route("/api/conversations")
        def get_conversations():
            if "user_id" not in session:
                return jsonify({"error": "未认证"}), 401

            conversations = self.db.get_user_conversations(session["user_id"])
            return jsonify({"success": True, "conversations": conversations})

        @self.app.route("/api/conversations", methods=["POST"])
        def create_conversation():
            if "user_id" not in session:
                return jsonify({"error": "未认证"}), 401

            # 支持both JSON and form data
            if request.is_json:
                data = request.get_json()
                title = data.get("title", "New Conversation")
            else:
                title = request.form.get("title", "New Conversation")

            conversation_id = self.db.create_conversation(session["user_id"], title)
            return jsonify({"success": True, "conversation_id": conversation_id, "title": title})

        @self.app.route("/api/conversations/<conversation_id>/messages")
        def get_messages(conversation_id):
            if "user_id" not in session:
                return jsonify({"error": "未认证"}), 401

            messages = self.db.get_conversation_messages(conversation_id)
            return jsonify(messages)

        @self.app.route("/api/chat", methods=["POST"])
        def api_chat():
            if "user_id" not in session:
                return jsonify({"success": False, "message": "请先登录"})

            message = request.form.get("message")
            conversation_id = request.form.get("conversation_id")

            if not message:
                return jsonify({"success": False, "message": "消息不能为空"})

            try:
                # 如果没有提供conversation_id，创建新对话
                if not conversation_id:
                    conversation_id = self.db.create_conversation(
                        session["user_id"],
                        f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    )

                # 保存用户消息
                self.db.save_message(conversation_id, "user", message)

                # 调用OpenManus代理
                response = asyncio.run(
                    self.process_with_agent(message, conversation_id)
                )

                # 保存助手回复
                self.db.save_message(conversation_id, "assistant", response)

                return jsonify(
                    {
                        "success": True,
                        "response": response,
                        "conversation_id": conversation_id,
                    }
                )

            except Exception as e:
                logger.error(f"Chat error: {e}")
                return jsonify({"success": False, "message": "处理消息时发生错误"})

        @self.app.route("/api/chat-guest", methods=["POST"])
        def api_chat_guest():
            """游客聊天API，不保存对话记录"""
            message = request.form.get("message")

            if not message:
                return jsonify({"success": False, "message": "消息不能为空"})

            try:
                # 调用OpenManus代理
                response = asyncio.run(self.process_with_agent(message, None))

                return jsonify({"success": True, "response": response})

            except Exception as e:
                logger.error(f"Guest chat error: {e}")
                return jsonify({"success": False, "message": "处理消息时发生错误"})

        @self.app.route("/api/check-auth", methods=["GET"])
        def api_check_auth():
            """检查用户登录状态"""
            return jsonify(
                {
                    "authenticated": "user_id" in session,
                    "username": session.get("username", ""),
                    "role": session.get("role", "user"),
                    "user_id": session.get("user_id", ""),
                }
            )

        # 管理员路由
        @self.app.route("/admin")
        def admin_panel():
            """管理员面板"""
            if not self.is_admin():
                return redirect(url_for("login"))
            return render_template("admin.html")

        @self.app.route("/admin/users", methods=["GET"])
        def admin_get_users():
            """获取所有用户（管理员）"""
            if not self.is_admin():
                return jsonify({"error": "权限不足"}), 403

            users = self.db.get_all_users()
            return jsonify({"users": users})

        @self.app.route("/admin/users/<int:user_id>/role", methods=["PUT"])
        def admin_update_user_role(user_id):
            """更新用户角色（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"error": "权限不足"}), 403

            data = request.get_json()
            role = data.get("role")

            if role not in ["user", "admin", "super_admin"]:
                return jsonify({"error": "无效的角色"}), 400

            if self.db.update_user_role(user_id, role):
                return jsonify({"success": True})
            else:
                return jsonify({"error": "更新失败"}), 500

        @self.app.route("/admin/users/<int:user_id>/status", methods=["PUT"])
        def admin_update_user_status(user_id):
            """更新用户状态（管理员）"""
            if not self.is_admin():
                return jsonify({"error": "权限不足"}), 403

            data = request.get_json()
            is_active = data.get("is_active")

            if self.db.update_user_status(user_id, is_active):
                return jsonify({"success": True})
            else:
                return jsonify({"error": "更新失败"}), 500

        @self.app.route("/admin/users/<int:user_id>", methods=["DELETE"])
        def admin_delete_user(user_id):
            """删除用户（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"error": "权限不足"}), 403

            # 不能删除自己
            if user_id == session.get("user_id"):
                return jsonify({"error": "不能删除自己"}), 400

            if self.db.delete_user(user_id):
                return jsonify({"success": True})
            else:
                return jsonify({"error": "删除失败"}), 500

        @self.app.route("/admin/users", methods=["POST"])
        def admin_create_user():
            """创建用户（管理员）"""
            if not self.is_admin():
                return jsonify({"error": "权限不足"}), 403

            data = request.get_json()
            username = data.get("username")
            email = data.get("email")
            password = data.get("password")
            role = data.get("role", "user")

            if not all([username, email, password]):
                return jsonify({"error": "用户名、邮箱和密码不能为空"}), 400

            if role not in ["user", "admin", "super_admin"]:
                return jsonify({"error": "无效的角色"}), 400

            # 只有超级管理员可以创建管理员和超级管理员
            if role in ["admin", "super_admin"] and not self.is_super_admin():
                return jsonify({"error": "权限不足，无法创建管理员用户"}), 403

            if self.db.create_user_with_role(username, email, password, role):
                return jsonify({"success": True})
            else:
                return jsonify({"error": "创建用户失败，用户名或邮箱可能已存在"}), 400

        @self.app.route("/admin/users/<int:user_id>/reset-password", methods=["PUT"])
        def admin_reset_password(user_id):
            """重置用户密码（管理员）"""
            if not self.is_admin():
                return jsonify({"error": "权限不足"}), 403

            data = request.get_json()
            new_password = data.get("new_password")

            if not new_password:
                return jsonify({"error": "新密码不能为空"}), 400

            if self.db.reset_user_password(user_id, new_password):
                return jsonify({"success": True})
            else:
                return jsonify({"error": "重置密码失败"}), 500

        @self.app.route("/admin/users/<int:user_id>/details", methods=["GET"])
        def admin_get_user_details(user_id):
            """获取用户详细信息（管理员）"""
            if not self.is_admin():
                return jsonify({"error": "权限不足"}), 403

            user = self.db.get_user_details(user_id)
            if user:
                return jsonify(user)
            else:
                return jsonify({"error": "用户不存在"}), 404

        @self.app.route("/admin/users/batch", methods=["POST"])
        def admin_batch_user_operation():
            """批量用户操作（管理员）"""
            if not self.is_admin():
                return jsonify({"error": "权限不足"}), 403

            data = request.get_json()
            operation = data.get("operation")
            user_ids = data.get("user_ids", [])

            if not user_ids:
                return jsonify({"error": "请选择要操作的用户"}), 400

            # 检查是否包含当前用户
            current_user_id = session.get("user_id")
            if current_user_id in user_ids:
                return jsonify({"error": "不能对自己执行批量操作"}), 400

            if operation == "delete":
                if not self.is_super_admin():
                    return jsonify({"error": "只有超级管理员可以批量删除用户"}), 403
                deleted_count = self.db.batch_delete_users(user_ids)
                return jsonify({"success": True, "affected_count": deleted_count})

            elif operation == "activate":
                updated_count = self.db.batch_update_user_status(user_ids, True)
                return jsonify({"success": True, "affected_count": updated_count})

            elif operation == "deactivate":
                updated_count = self.db.batch_update_user_status(user_ids, False)
                return jsonify({"success": True, "affected_count": updated_count})

            else:
                return jsonify({"error": "无效的操作"}), 400

        @self.app.route("/admin/stats", methods=["GET"])
        def admin_get_stats():
            """获取系统统计信息（管理员）"""
            if not self.is_admin():
                return jsonify({"error": "权限不足"}), 403

            stats = self.db.get_system_stats()
            return jsonify(stats)

        @self.app.route("/admin/config", methods=["GET"])
        def admin_get_configs():
            """获取所有配置文件列表（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"error": "权限不足"}), 403

            try:
                import os
                config_dir = os.path.join(os.path.dirname(__file__), "config")
                files = []
                
                if os.path.exists(config_dir):
                    for filename in os.listdir(config_dir):
                        if filename.endswith(('.toml', '.json')):
                            files.append(filename)
                
                return jsonify({"files": sorted(files)})
            except Exception as e:
                return jsonify({"error": f"获取配置文件列表失败: {str(e)}"}), 500

        @self.app.route("/admin/config/<filename>", methods=["GET"])
        def admin_get_config(filename):
            """获取配置文件内容（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"error": "权限不足"}), 403

            try:
                import os
                config_dir = os.path.join(os.path.dirname(__file__), "config")
                config_file = os.path.join(config_dir, filename)

                # 安全检查：确保文件在配置目录内
                if not os.path.abspath(config_file).startswith(
                    os.path.abspath(config_dir)
                ):
                    return jsonify({"error": "无效的文件路径"}), 400

                if not os.path.exists(config_file):
                    return jsonify({"error": "配置文件不存在"}), 404

                with open(config_file, "r", encoding="utf-8") as f:
                    content = f.read()

                return jsonify({"filename": filename, "content": content})
            except Exception as e:
                return jsonify({"error": f"读取配置文件失败: {str(e)}"}), 500

        @self.app.route("/admin/config/<filename>", methods=["PUT"])
        def admin_update_config(filename):
            """更新配置文件（超级管理员）"""
            if not self.is_super_admin():
                return jsonify({"error": "权限不足"}), 403

            try:
                import os
                config_dir = os.path.join(os.path.dirname(__file__), "config")
                config_file = os.path.join(config_dir, filename)

                # 安全检查：确保文件在配置目录内
                if not os.path.abspath(config_file).startswith(
                    os.path.abspath(config_dir)
                ):
                    return jsonify({"error": "无效的文件路径"}), 400

                data = request.get_json()

                if filename.endswith(".toml"):
                    # 对于TOML文件，直接保存文本内容
                    content = data.get("content", "")
                    with open(config_file, "w", encoding="utf-8") as f:
                        f.write(content)
                elif filename.endswith(".json"):
                    # 对于JSON文件，保存JSON格式
                    content = data.get("content", {})
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)
                else:
                    return jsonify({"error": "不支持的文件格式"}), 400

                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": f"保存配置失败: {str(e)}"}), 500

    def is_admin(self) -> bool:
        """检查当前用户是否为管理员或超级管理员"""
        user_role = session.get("role", "user")
        return user_role in ["admin", "super_admin"]

    def is_super_admin(self) -> bool:
        """检查当前用户是否为超级管理员"""
        user_role = session.get("role", "user")
        return user_role == "super_admin"

    async def process_with_agent(
        self, message: str, conversation_id: str = None
    ) -> str:
        """Process user message with OpenManus agent."""
        try:
            # Get or create agent instance for this session
            session_id = session.get("user_id", "guest")
            if session_id not in self.agent_instances:
                self.agent_instances[session_id] = await Manus.create()

            agent = self.agent_instances[session_id]

            # Load conversation history only if conversation_id is provided
            if conversation_id:
                messages = self.db.get_conversation_messages(conversation_id)

                # Convert to OpenManus message format
                agent.memory.clear()
                for msg in messages[
                    :-1
                ]:  # Exclude the last message (current user input)
                    agent.memory.add_message(
                        Message(
                            role=msg["role"],
                            content=msg["content"],
                            tool_calls=msg.get("tool_calls"),
                            tool_call_id=msg.get("tool_call_id"),
                        )
                    )

            # Process the message
            await agent.run(message)

            # Get the last assistant message
            last_message = agent.memory.get_messages()[-1]
            return last_message.content or "抱歉，我无法生成回复。"

        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            return f"处理您的请求时遇到错误：{str(e)}"

    def run(self, host="127.0.0.1", port=8080, debug=True):
        """Run the Flask application."""
        logger.info(f"Starting OpenManus Web UI on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    webui = OpenManusWebUI()
    webui.run()
