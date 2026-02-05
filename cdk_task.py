#!/usr/bin/python
# coding=utf-8
import os
import sys
import requests
import time
from loguru import logger

# 日志格式优化
logger.remove()
logger.add(sys.stdout, level='INFO', format="<white>[{time:HH:mm:ss} INF]</white> {message}")

try:
    import notify
except ImportError:
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
                    self.results.append(f"抽卡: 成功")
            else:
                logger.info(f"抽卡次数不足({free_rem})，跳过")
        except Exception: pass

    def lucky_wheel(self):
        """大转盘：循环执行5次"""
        try:
            logger.info("开始执行大转盘任务 (5次)...")
            prizes = []
            for i in range(5):
                # 根据抓包信息，接口地址为 /api/wheel
                url = f'https://{self.domain}/api/wheel'
                # 抓包显示为 POST 且 Content-Length 为 0
                resp = requests.post(url, headers=self.headers, json={}, timeout=15).json()
                
                if resp.get("success"):
                    # 匹配响应结构中的 prize.name
                    prize = resp.get("data", {}).get("prize", {}).get("name", "未知")
                    logger.info(f"第 {i+1} 次转盘成功: {prize}")
                    prizes.append(prize)
                    time.sleep(3) # 账号内转动延迟
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
                "amountUsd": 5, # 默认5额度，不需卡片ID
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
    # 允许通过命令行指定任务类型
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
        
        # 按参数执行任务逻辑
        if task_arg in ["draw", "all"]: cdk.card_draw()
        if task_arg in ["wheel", "all"]: cdk.lucky_wheel()
        if task_arg in ["throw", "all"]: cdk.drift_throw()
        if task_arg in ["pick", "all"]: cdk.drift_pick()
        
        if cdk.results: summary.append(f"账号 {i}: " + " | ".join(cdk.results))
        
        # 账号间延迟，防止触发风控
        if i < len(accounts) - 1:
            time.sleep(5)

    # 简报发送逻辑
    if notify and summary and task_arg in ["all", "draw", "wheel"]:
        notify.send("CDK 任务简报", "\n".join(summary))

if __name__ == "__main__":
    main()