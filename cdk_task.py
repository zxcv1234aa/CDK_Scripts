#!/usr/bin/python
# coding=utf-8
import os
import sys
import requests
import time
from loguru import logger

# --- 修复路径问题：确保能找到青龙自带的 notify.py ---
# 将父目录和当前目录加入系统路径
current_path = os.path.dirname(os.path.abspath(__file__))
parent_path = os.path.dirname(current_path)
sys.path.append(current_path)
sys.path.append(parent_path)
# 针对青龙容器的标准路径
if os.path.exists('/ql/data/scripts'):
    sys.path.append('/ql/data/scripts')

# 日志格式优化
logger.remove()
logger.add(sys.stdout, level='INFO', format="<white>[{time:HH:mm:ss} INF]</white> {message}")

try:
    import notify
    logger.info("✅ 成功加载通知模块")
except ImportError:
    logger.warning("⚠️ 未找到 notify.py 模块，将仅通过控制台输出日志")
    notify = None

class CDKStation:
    def __init__(self, cookie_str, index):
        self.cookie = cookie_str.strip()
        self.index = index
        self.domain = 'cdk.hybgzs.com'
        self.headers = {
            'authority': self.domain,
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15',
            'origin': f'https://{self.domain}',
            'referer': f'https://{self.domain}/',
            'cookie': self.cookie
        }
        self.results = []

    def _get_bottle_usage(self):
        """获取漂流瓶状态"""
        try:
            url = f"https://{self.domain}/api/drift-bottle/settings"
            res = requests.get(url, headers=self.headers, timeout=10).json()
            if res.get("success"):
                return res.get("data", {}).get("usage", {})
        except Exception: return {}
        return {}

    def card_draw(self):
        """集换卡片：满足10次才执行"""
        try:
            status_url = f"https://{self.domain}/api/cards/draw/status"
            res_status = requests.get(status_url, headers=self.headers, timeout=10).json()
            free_rem = res_status.get("limits", {}).get("freeRemaining", 0)
            
            if free_rem >= 10:
                logger.info(f"抽卡次数充足({free_rem})，执行十连...")
                res = requests.post(f"https://{self.domain}/api/cards/draw", json={"count": 10}, headers=self.headers, timeout=10).json()
                if res.get("success"):
                    self.results.append("抽卡: 成功")
            else:
                logger.info(f"抽卡次数不足({free_rem})，跳过")
        except Exception: logger.error("抽卡任务异常")

    def lucky_wheel(self):
        """大转盘：循环执行5次"""
        try:
            logger.info("开始执行大转盘任务 (5次)...")
            prizes = []
            for i in range(5):
                url = f'https://{self.domain}/api/wheel'
                resp = requests.post(url, headers=self.headers, json={}, timeout=15).json()
                if resp.get("success"):
                    prize = resp.get("data", {}).get("prize", {}).get("name", "未知")
                    logger.info(f"第 {i+1} 次转盘成功: {prize}")
                    prizes.append(prize)
                    time.sleep(3)
                else:
                    err = resp.get("error", "次数耗尽或异常")
                    logger.info(f"转盘提前结束: {err}")
                    break
            if prizes:
                self.results.append(f"转盘: {', '.join(prizes)}")
        except Exception as e:
            logger.error(f"转盘任务异常: {str(e)}")

    def drift_throw(self):
        """漂流瓶：单次丢出 (5额度)"""
        usage = self._get_bottle_usage()
        if usage.get("throwRemaining", 0) <= 0:
            return logger.info("今日丢瓶子次数已用完")
        
        try:
            logger.info("执行单次丢瓶子...")
            payload = {
                "isAnonymous": True, 
                "noteContent": "愿生活明朗，万物可爱。", 
                "amountUsd": 5,
                "cardId": None, 
                "cardIsSP": False
            }
            res = requests.post(f"https://{self.domain}/api/drift-bottle/throw", json=payload, headers=self.headers, timeout=10).json()
            if res.get("success"):
                logger.info("丢瓶子成功 √")
                self.results.append("丢瓶子: 成功")
        except Exception: logger.error("丢瓶子任务异常")

    def drift_pick(self):
        """漂流瓶：单次捡起"""
        usage = self._get_bottle_usage()
        if usage.get("pickRemaining", 0) <= 0:
            return logger.info("今日捡瓶子次数已用完")

        try:
            logger.info("执行单次捡瓶子...")
            res = requests.post(f"https://{self.domain}/api/drift-bottle/pick", json={"scope": "world"}, headers=self.headers, timeout=10).json()
            if res.get("success"):
                bottle = res.get("data", {}).get("bottle", {})
                reward = f"额度{bottle.get('quotaAmount')}" if bottle.get('quotaAmount') else "祝福"
                logger.info(f"捡瓶子成功: {reward}")
                self.results.append(f"捡瓶子: {reward}")
        except Exception: logger.error("捡瓶子异常")

def main():
    task_arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    cookie_env = os.getenv("CDK_COOKIES", "")
    if not cookie_env: 
        logger.error("未发现环境变量 CDK_COOKIES")
        return

    accounts = [a for a in cookie_env.split('\n') if a.strip()]
    summary = []

    for i, ck in enumerate(accounts):
        logger.info(f"--- 开始处理 账号 {i} ---")
        cdk = CDKStation(ck, i)
        
        if task_arg in ["draw", "all"]: cdk.card_draw()
        if task_arg in ["wheel", "all"]: cdk.lucky_wheel()
        if task_arg in ["throw", "all"]: cdk.drift_throw()
        if task_arg in ["pick", "all"]: cdk.drift_pick()
        
        if cdk.results: 
            summary.append(f"【账号 {i}】: " + " | ".join(cdk.results))
        
        if i < len(accounts) - 1:
            time.sleep(5)

    # --- 修复通知判断逻辑 ---
    # 只要 notify 加载成功且有执行结果（summary不为空），就发送通知
    if notify and summary:
        logger.info("📡 正在发送推送通知...")
        notify.send("CDK 任务简报", "\n".join(summary))
    elif not notify:
        logger.warning("📢 推送跳过：未加载到 notify.py")
    elif not summary:
        logger.info("📢 推送跳过：本次运行无任何产出结果")

if __name__ == "__main__":
    main()
