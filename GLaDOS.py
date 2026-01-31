#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
项目名称: AKA-Cigma / QLscripts
Author: Gemini & AKA-Cigma
功能：GLaDOS自动签到、积分查询、自动积分兑换
抓电脑网页端GLaDOS签到页面请求头的完整cookie填到环境变量'GR_COOKIE'里，多账号&连接或者新建
默认500积分换100天，要改的话环境变量GR_COOKIE在账号cookie后#连接：100-100积分换10天，200-200积分换30天，500-500积分换100天，off-关闭自动兑换
示例：koa:sess=...#off&koa:sess=...#500&koa:sess=...
Date: 2026/01/31
cron: 40 0,12 * * *
new Env('GLaDOS');
"""

import requests
import json
import os
import logging
import datetime
import time
from typing import Dict, List, Optional, Tuple, Any

# 尝试加载 notify
try:
    from notify import send
except:
    pass

# ================= 配置与常量 =================

# 环境变量名
ENV_COOKIES_KEY = "GR_COOKIE"

# API URLs
CHECKIN_URL = "https://glados.cloud/api/user/checkin"
STATUS_URL = "https://glados.cloud/api/user/status"
POINTS_URL = "https://glados.cloud/api/user/points"
EXCHANGE_URL = "https://glados.cloud/api/user/exchange"

# Request Headers
HEADERS_TEMPLATE = {
    'referer': 'https://glados.cloud/console/checkin',
    'origin': "https://glados.cloud",
    'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36",
    'content-type': 'application/json;charset=UTF-8'
}

# 兑换计划映射
# Key: 用户在环境变量中配置的值 (#100, #off 等)
# Value: API 需要的 planType (None 表示不兑换)
PLAN_MAP = {
    "100": "plan100",
    "200": "plan200",
    "500": "plan500",
    "off": None
}

# 积分需求表
EXCHANGE_POINTS = {"plan100": 100, "plan200": 200, "plan500": 500}

# ================= 日志设置 =================

def beijing_time_converter(timestamp):
    utc_dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
    beijing_dt = utc_dt.astimezone(beijing_tz)
    return beijing_dt.timetuple()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
root_logger = logging.getLogger()
for handler in root_logger.handlers:
    if hasattr(handler, 'formatter') and handler.formatter is not None:
        handler.formatter.converter = beijing_time_converter

logger = logging.getLogger(__name__)

# ================= 核心功能函数 =================

def get_accounts() -> List[Dict[str, Any]]:
    """
    获取并解析 GR_COOKIE，支持多账号及独立配置
    格式: Cookie字符串#配置码
    配置码: 100/200/500/off, 默认500
    """
    raw_cookies_env = os.environ.get(ENV_COOKIES_KEY)
    
    if not raw_cookies_env:
        logger.error(f"环境变量 '{ENV_COOKIES_KEY}' 未设置，请在环境变量中添加 Cookie。")
        return []

    # 分割多个账号
    raw_list = []
    if '&' in raw_cookies_env:
        raw_list = raw_cookies_env.split('&')
    elif '\n' in raw_cookies_env:
        raw_list = raw_cookies_env.split('\n')
    else:
        raw_list = [raw_cookies_env]

    accounts = []
    for raw_item in raw_list:
        if not raw_item.strip():
            continue
            
        # 解析 Cookie 和 配置后缀
        parts = raw_item.split('#')
        cookie_str = parts[0].strip()
        config_code = parts[1].strip() if len(parts) > 1 else "500" # 默认为 500
        
        # 映射配置码到实际计划
        plan = PLAN_MAP.get(config_code, "plan500") # 如果填了未知的，默认 plan500
        if config_code == "off":
            plan = None

        if cookie_str:
            accounts.append({
                'cookie': cookie_str,
                'plan': plan,
                'config_code': config_code
            })

    logger.info(f"已获取并解析 Env 环境 Cookie，共 {len(accounts)} 个账号。")
    return accounts

def make_request(url: str, method: str, headers: Dict[str, str], data: Optional[Dict] = None, cookies: str = "") -> Optional[requests.Response]:
    """
    发送网络请求，包含重试机制
    """
    session_headers = headers.copy()
    session_headers['cookie'] = cookies
    
    max_retries = 3
    delay = 2

    for attempt in range(1, max_retries + 1):
        try:
            if method.upper() == 'POST':
                response = requests.post(url, headers=session_headers, data=json.dumps(data), timeout=10)
            elif method.upper() == 'GET':
                response = requests.get(url, headers=session_headers, timeout=10)
            else:
                return None

            if response.ok:
                return response
            else:
                logger.warning(f"请求 {url} 失败 (第 {attempt}/{max_retries} 次)，状态码 {response.status_code}。")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求异常 (第 {attempt}/{max_retries} 次): {e}")

        # 如果不是最后一次尝试，等待后重试
        if attempt < max_retries:
            time.sleep(delay)
    
    logger.error(f"请求 {url} 超过最大重试次数，已放弃。")
    return None

def checkin_and_process(cookie: str, exchange_plan: Optional[str]) -> Tuple[str, str, str, str, str, str]:
    """执行单个账号的签到、查询和兑换流程"""
    
    status_msg = "签到失败"
    points_gained = "0"
    remaining_days = "未知"
    remaining_points = "未知"
    exchange_msg = "无兑换"
    email = "未知账号"
    
    # 1. 签到
    checkin_response = make_request(CHECKIN_URL, 'POST', HEADERS_TEMPLATE, {"token": "glados.cloud"}, cookies=cookie)
    if not checkin_response:
        return status_msg, points_gained, remaining_days, remaining_points, "接口请求失败", email

    try:
        checkin_data = checkin_response.json()
        response_message = checkin_data.get('message', '')
        points_gained = str(checkin_data.get('points', 0))

        if "Checkin! Got" in response_message:
            status_msg = f"签到成功 +{points_gained}"
        elif "Checkin Repeats!" in response_message:
            status_msg = "重复签到"
            points_gained = "0"
        else:
            status_msg = f"签到异常: {response_message}"
    except json.JSONDecodeError:
        status_msg = "响应解析失败"

    # 2. 获取状态 (剩余天数 和 Email)
    status_response = make_request(STATUS_URL, 'GET', HEADERS_TEMPLATE, cookies=cookie)
    if status_response:
        try:
            status_data = status_response.json()
            email = status_data.get('data', {}).get('email', '未知账号')
            
            left_days = status_data.get('data', {}).get('leftDays')
            if left_days is not None:
                remaining_days = f"{int(float(left_days))}天"
        except Exception:
            remaining_days = "天数获取失败"
            logger.error("解析状态数据失败")

    # 3. 获取积分
    points_response = make_request(POINTS_URL, 'GET', HEADERS_TEMPLATE, cookies=cookie)
    current_points_numeric = 0
    if points_response:
        try:
            points_data = points_response.json()
            points_float = points_data.get('points')
            if points_float is not None:
                current_points_numeric = int(float(points_float))
                remaining_points = f"{current_points_numeric}积分"
        except Exception:
            remaining_points = "积分获取失败"

    # 4. 自动兑换 (仅当 exchange_plan 不为 None 时执行)
    if exchange_plan:
        required_points = EXCHANGE_POINTS.get(exchange_plan, 500)
        if current_points_numeric >= required_points:
            logger.info(f"积分充足 ({current_points_numeric}/{required_points})，尝试执行兑换: {exchange_plan}")
            exchange_response = make_request(EXCHANGE_URL, 'POST', HEADERS_TEMPLATE, {"planType": exchange_plan}, cookies=cookie)
            if exchange_response:
                try:
                    ex_data = exchange_response.json()
                    if ex_data.get('code') == 0:
                        exchange_msg = f"兑换成功({exchange_plan})"
                    else:
                        exchange_msg = f"兑换失败:{ex_data.get('message')}"
                except:
                    exchange_msg = "兑换响应异常"
        else:
            exchange_msg = "积分不足"
    else:
        exchange_msg = "已设为不兑换"

    return status_msg, points_gained, remaining_days, remaining_points, exchange_msg, email

def format_notification(results: List[Dict[str, str]]) -> Tuple[str, str]:
    """格式化通知内容"""
    success_count = sum(1 for r in results if "成功" in r['status'] or "重复" in r['status'])
    
    title = f"GLaDOS签到: 成功{success_count}/共{len(results)}"
    
    content_lines = []
    for i, res in enumerate(results, 1):
        line = (
            f"账号: {res['email']}\n"
            f"状态: {res['status']}\n"
            f"天数: {res['days']} | 积分: {res['points_total']}\n"
            f"兑换: {res['exchange']}\n"
            f"----------------"
        )
        content_lines.append(line)
    
    return title, "\n".join(content_lines)

# ================= 主程序 =================

def main():
    logger.info("脚本开始运行...")
    
    accounts = get_accounts()
    if not accounts:
        return

    results = []
    
    for idx, account in enumerate(accounts, 1):
        logger.info(f"=== 正在处理第 {idx} 个账户 ===")
        cookie = account['cookie']
        exchange_plan = account['plan']
        config_code = account['config_code']

        # 使用掩码打印 Cookie 日志，避免泄露
        masked_cookie = cookie[:10] + "******" + cookie[-10:] if len(cookie) > 20 else "******"
        logger.info(f"Cookie: {masked_cookie}")
        logger.info(f"兑换配置: {config_code} -> {exchange_plan if exchange_plan else '不兑换'}")
        
        status, points, days, points_total, exchange, email = checkin_and_process(cookie, exchange_plan)
        
        display_name = email if email != "未知账号" else f"Account_{idx}"
        logger.info(f"账号: {display_name} | 结果: {status}, 剩余: {days}")
        
        results.append({
            'status': status,
            'points': points,
            'days': days,
            'points_total': points_total,
            'exchange': exchange,
            'email': email
        })
        
        # 避免请求过于频繁
        if idx < len(accounts):
            time.sleep(2)

    # 生成通知内容
    title, content = format_notification(results)
    print(f"\n{title}\n{content}")
    
    # 推送消息
    try:
        send(title, content)
    except Exception as e:
        print(f"消息推送失败：{e}！\n{content}\n")

if __name__ == '__main__':
    main()
