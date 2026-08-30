#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
项目名称: 妖狐吧签到
Author: Gemini & AKA-Cigma
功能：妖狐吧 APP 每日自动签到、金币钻石查询

环境变量说明:
抓安卓妖狐吧APP端签到请求的cookie、User-Agent、Body填到环境变量'YHB_COOKIE'里，多账号#连接或者新建
变量名: YHB_COOKIE
变量值格式: Cookie值@User-Agent@Body参数
示例: 
PHPSESSID=***@Mozilla/5.0 (Linux; Android 16...@uuid=***&name=***&password=***&username=***&device=android&max_loading_time=60&api_token=***

Date: 2026/08/30
cron: 1 0 * * *
new Env('妖狐吧签到');
"""

import requests
import json
import os
import logging
import datetime
import time
import sys
from typing import Dict, List, Optional, Tuple, Any

# 尝试加载 notify 推送模块
try:
    from notify import send
except Exception:
    def send(title, content):
        pass

# ================= 配置与常量 =================

ENV_COOKIES_KEY = "YHB_COOKIE"

# APP 端 API URL
FULI_URL = "https://shenmatk.com/api/fuli.php?act=getDaily&lang=cn&app_version=7.0.01"

# Request Headers (默认模板)
HEADERS_TEMPLATE = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Android WebView";v="150"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'user-agent': 'Mozilla/5.0 (Linux; Android 16; 2304FPN6DC Build/BP2A.250605.031.A3; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.181 Mobile Safari/537.36',
    'x-requested-with': 'com.phonegap.hello_world',
}

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

def get_accounts() -> List[Dict[str, str]]:
    """
    获取并解析 YHB_COOKIE 环境变量
    标准格式: Cookie值@User-Agent@Body参数
    多账号使用 '#' 或换行符 '\n' 分隔
    """
    raw_env = os.environ.get(ENV_COOKIES_KEY)
    
    if not raw_env:
        logger.error(f"环境变量 '{ENV_COOKIES_KEY}' 未设置，请在青龙面板中添加。")
        sys.exit(1)

    # 将 # 统一替换为换行符后按行切分账号
    raw_list = raw_env.replace('#', '\n').split('\n')

    accounts = []
    for idx, item in enumerate(raw_list, 1):
        item = item.strip()
        if not item:
            continue
        
        parts = item.split('@')
        
        # 校验 parts 数量，若小于或等于 2（即缺少 Cookie、UA 或 Body）则直接报错退出
        if len(parts) <= 2:
            logger.error(f"❌ 第 {idx} 个账号格式错误！期望格式为 'Cookie@User-Agent@Body'（必须包含至少2个'@'分隔符）。")
            logger.error(f"当前传入内容 parts 数量为 {len(parts)}，无法满足 3 项参数要求: {item}")
            logger.error("终止运行，请修改环境变量配置后重试。")
            sys.exit(1)

        cookie_str = parts[0].strip()
        ua_str = parts[1].strip()
        body_str = "@".join(parts[2:]).strip()  # 防止 body 内容里自带 @ 字符被误切分

        accounts.append({
            'cookie': cookie_str,
            'ua': ua_str,
            'body': body_str
        })

    logger.info(f"已成功解析并校验环境变量，共发现 {len(accounts)} 个格式正确的账号。")
    return accounts

def do_checkin(account: Dict[str, str]) -> Dict[str, Any]:
    """
    执行 APP 端单账号签到请求
    """
    headers = HEADERS_TEMPLATE.copy()
    
    if account['cookie']:
        headers['cookie'] = account['cookie']
    if account['ua']:
        headers['user-agent'] = account['ua']

    body_data = account['body']

    result_info = {
        'status': "签到失败",
        'msg': "",
        'money': "未知",
        'diamond': "未知"
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(FULI_URL, headers=headers, data=body_data, timeout=10)
            
            if response.ok:
                logger.info(f"接口原始响应内容: {response.text}")
                try:
                    data = response.json()

                    # 判断 Cookie/Session 或 Token 是否失效
                    if data.get('api_load_completed') == 0:
                        result_info['status'] = "账号参数已失效"
                        result_info['msg'] = "登录态失效，请重新抓取 APP 的 Cookie 和 Body"
                        return result_info

                    msg = data.get('msg') or data.get('error') or ''
                    success = data.get('success', 0)
                    money = data.get('money', '未知')
                    diamond = data.get('diamond', '未知')

                    # 补充从 result 子对象获取余额逻辑
                    if money == '未知' and 'result' in data:
                        money = data['result'].get('money_have', '未知')

                    result_info['msg'] = msg if msg else "签到成功"
                    result_info['money'] = str(money)
                    result_info['diamond'] = str(diamond)

                    if success == 1:
                        result_info['status'] = "签到成功"
                    else:
                        result_info['status'] = f"签到失败/重复(success={success})"

                    return result_info

                except json.JSONDecodeError:
                    result_info['msg'] = f"返回非 JSON 内容: {response.text[:100]}"
                    logger.error(f"解析响应失败，返回内容: {response.text}")
            else:
                logger.warning(f"请求失败 (第 {attempt}/{max_retries} 次)，状态码 {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求异常 (第 {attempt}/{max_retries} 次): {e}")

        if attempt < max_retries:
            time.sleep(2)

    return result_info

def format_notification(results: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    格式化通知消息
    """
    success_count = sum(1 for r in results if r['status'] == "签到成功")
    title = f"妖狐吧APP每日签到: 成功{success_count}/共{len(results)}"
    
    content_lines = []
    for i, res in enumerate(results, 1):
        line = (
            f"账号 [{i}]\n"
            f"结果: {res['status']}\n"
            f"提示: {res['msg']}\n"
            f"余额: 金币 {res['money']} | 钻石 {res['diamond']}\n"
            f"----------------"
        )
        content_lines.append(line)
    
    return title, "\n".join(content_lines)

# ================= 主程序 =================

def main():
    logger.info("开始执行 妖狐吧APP 每日福利签到...")
    
    accounts = get_accounts()
    if not accounts:
        return

    results = []
    
    for idx, acc in enumerate(accounts, 1):
        logger.info(f"=== 正在处理第 {idx} 个账户 ===")
        
        # 打印日志（掩码显示）
        masked_cookie = acc['cookie'][:10] + "******" if len(acc['cookie']) > 10 else "未配置Cookie"
        masked_ua = acc['ua'][:20] + "******" if len(acc['ua']) > 20 else "未配置UA"
        masked_body = acc['body'][:20] + "******" if len(acc['body']) > 20 else "未配置Body"
        
        logger.info(f"Cookie: {masked_cookie}")
        logger.info(f"User-Agent: {masked_ua}")
        logger.info(f"Body 载荷: {masked_body}")
        
        res = do_checkin(acc)
        logger.info(f"签到状态: {res['status']} | 消息: {res['msg']} | 金币: {res['money']} | 钻石: {res['diamond']}")
        
        results.append(res)
        
        if idx < len(accounts):
            time.sleep(2)

    # 汇总并发送推送
    title, content = format_notification(results)
    print(f"\n{title}\n{content}")
    
    try:
        send(title, content)
    except Exception as e:
        logger.error(f"消息推送失败：{e}")

if __name__ == '__main__':
    main()
