# -*- coding: utf-8 -*-
import os
import asyncio
import time
import feedparser
import requests
from datetime import datetime, timedelta
import botpy
from botpy import logging
from botpy.message import Message
from keep_alive import keep_alive

APPID = os.environ.get("QQ_APPID", "")
APPSECRET = os.environ.get("QQ_APPSECRET", "")
ADMIN_QQ = os.environ.get("ADMIN_QQ", "")
GROUP_ID = os.environ.get("GROUP_ID", "")
FORUM_URL = "https://shouyeren.discourse.group"
FORUM_RSS = FORUM_URL + "/latest.rss"

KEYWORD_REPLIES = {
    "论坛地址": "🌙 二中守夜人论坛：" + FORUM_URL + "
手机电脑都能打开，邮箱注册即可使用！",
    "论坛网址": "🌙 二中守夜人论坛：" + FORUM_URL + "
手机电脑都能打开，邮箱注册即可使用！",
    "官网": "🌙 二中守夜人论坛：" + FORUM_URL,
    "悬赏": "💰 悬赏市场在论坛的「悬赏市场」版块，发帖注明【悬赏】和报酬即可。",
    "表白": "💌 表白墙在论坛的「表白墙」版块，支持匿名发帖哦～",
    "规则": "📋 论坛规则：
1. 遵守法律法规和学校纪律
2. 尊重他人，禁止人身攻击
3. 悬赏交易自行核实
4. 表白墙禁止恶意攻击他人",
    "帮助": "🤖 我是守夜人论坛助手，你可以问我：
- 论坛地址
- 悬赏
- 表白
- 规则
- 最新帖子",
}

_log = logging.get_logger()
_sent_posts = set()
_group_openid = None
_admin_openid = None
message_count = 0
active_members = set()

class MyClient(botpy.Client):
    async def on_ready(self):
        _log.info("机器人登录成功！")
        asyncio.create_task(self.forum_monitor())
        asyncio.create_task(self.daily_summary())

    async def on_group_at_message_create(self, message):
        global message_count
        message_count += 1
        active_members.add(message.author.member_openid)
        content = message.content.strip()
        if message.mentions:
            for mention in message.mentions:
                content = content.replace("@" + mention.bot, "").strip()
        _log.info("收到群消息: " + content)
        reply = self.match_keyword(content)
        if reply:
            await message.reply(content=reply)
            return
        await message.reply(content="🤖 你好！我是守夜人论坛助手。
发送「帮助」查看我能做什么。")

    async def on_c2c_message_create(self, message):
        global message_count, _admin_openid
        message_count += 1
        content = message.content.strip()
        _log.info("收到私聊: " + content)
        if not _admin_openid:
            _admin_openid = message.author.user_openid
        response = self.handle_command(content, message.author.user_openid)
        await message.reply(content=response)

    def match_keyword(self, text):
        for keyword, reply in KEYWORD_REPLIES.items():
            if keyword in text:
                return reply
        return None

    def handle_command(self, cmd, user_openid):
        cmd = cmd.strip()
        if cmd in ["帮助", "help", "/help"]:
            return "📋 可用指令：
/统计 - 查看今日统计
/最新 - 查看论坛最新帖子
/群信息 - 查看群信息
/关键词 - 查看关键词列表
/发公告 [内容] - 往群里发公告（仅管理员）"
        elif cmd in ["/统计", "统计"]:
            return "📊 今日统计：
- 消息总数：" + str(message_count) + "条
- 活跃成员：" + str(len(active_members)) + "人
- 运行时间：" + self.get_uptime()
        elif cmd in ["/最新", "最新帖子", "/latest"]:
            return self.get_latest_posts()
        elif cmd in ["/关键词", "关键词"]:
            return "🔑 支持的关键词：
" + "、".join(KEYWORD_REPLIES.keys())
        elif cmd.startswith("/发公告"):
            if user_openid != _admin_openid:
                return "❌ 你没有权限执行此指令"
            content = cmd.replace("/发公告", "").strip()
            if not content:
                return "❌ 请输入公告内容"
            asyncio.create_task(self.send_group_message("📢 公告：
" + content))
            return "✅ 公告已发送到群里"
        elif cmd in ["/群信息", "/group"]:
            return "👥 群信息：
- 群号：" + (GROUP_ID or "未配置") + "
- 机器人状态：在线
- 今日消息：" + str(message_count) + "条"
        else:
            return "🤖 未知指令：" + cmd + "
发送「帮助」查看可用指令"

    def get_uptime(self):
        if not hasattr(self, "_start_time"):
            self._start_time = time.time()
        elapsed = time.time() - self._start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        return str(hours) + "小时" + str(minutes) + "分钟"

    def get_latest_posts(self, limit=5):
        try:
            feed = feedparser.parse(FORUM_RSS)
            if not feed.entries:
                return "❌ 暂时无法获取论坛帖子"
            posts = []
            for i, entry in enumerate(feed.entries[:limit]):
                posts.append(str(i+1) + ". " + entry.title + "
   " + entry.link)
            return "📰 论坛最新帖子：
" + "
".join(posts)
        except Exception as e:
            return "❌ 获取帖子失败：" + str(e)

    async def forum_monitor(self):
        _log.info("论坛监控已启动")
        try:
            feed = feedparser.parse(FORUM_RSS)
            for entry in feed.entries:
                _sent_posts.add(entry.link)
        except:
            pass
        while True:
            try:
                feed = feedparser.parse(FORUM_RSS)
                for entry in feed.entries[:3]:
                    if entry.link not in _sent_posts:
                        _sent_posts.add(entry.link)
                        msg = "📰 论坛新帖：
《" + entry.title + "》
" + entry.link
                        await self.send_group_message(msg)
                        _log.info("转发新帖: " + entry.title)
            except Exception as e:
                _log.error("论坛监控错误: " + str(e))
            await asyncio.sleep(300)

    async def daily_summary(self):
        _log.info("每日总结任务已启动")
        while True:
            now = datetime.now()
            target = now.replace(hour=22, minute=0, second=0, microsecond=0)
            if now > target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            if _admin_openid:
                summary = "📊 今日守夜人论坛总结
━━━━━━━━━━━━━
📅 日期：" + now.strftime("%Y-%m-%d") + "
💬 群消息总数：" + str(message_count) + "条
👥 活跃成员：" + str(len(active_members)) + "人
🤖 运行时长：" + self.get_uptime() + "
━━━━━━━━━━━━━
" + self.get_latest_posts(3)
                try:
                    await self.api.post_c2c_message(openid=_admin_openid, content=summary)
                    _log.info("每日总结已发送")
                except Exception as e:
                    _log.error("发送每日总结失败: " + str(e))
            global message_count, active_members
            message_count = 0
            active_members.clear()

    async def send_group_message(self, content):
        if not _group_openid:
            _log.warning("群openid未配置")
            return
        try:
            await self.api.post_group_message(group_openid=_group_openid, content=content)
        except Exception as e:
            _log.error("发送群消息失败: " + str(e))

if __name__ == "__main__":
    keep_alive()
    if not APPID:
        print("❌ 请配置 QQ_APPID 和 QQ_APPSECRET 环境变量！")
        exit(1)
    print("🚀 正在启动守夜人论坛QQ机器人...")
    print("论坛地址: " + FORUM_URL)
    try:
        intents = botpy.Intents(
            public_messages=True,
            c2c_group_at_messages=True,
            c2c_message=True,
        )
        client = MyClient(intents=intents)
        client.run(appid=APPID, secret=APPSECRET)
    except Exception as e:
        print("❌ 启动失败: " + str(e))
