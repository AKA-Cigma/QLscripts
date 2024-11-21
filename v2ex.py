#!/usr/bin/env python3
# coding: utf-8
'''
项目名称: AKA-Cigma / QLscripts
Author: AKA-Cigma
功能：v2ex论坛自动签到
抓电脑网页端v2ex论坛积分页面请求头的完整cookie填到环境变量'v2exck'里，多账号&连接
Date: 2024/10/31
cron: 9 8 * * *
new Env('v2ex');
'''
import requests, json, time, os, sys, re
from lxml import html
from datetime import datetime
try:
    from notify import send
except:
    pass

accounts = os.getenv('v2exck')

if accounts is None:
    print('未检测到v2exck')
    exit(1)

accounts_list = accounts.split('&')
print(f"获取到 {len(accounts_list)} 个账号\n")

urls = ['https://www.v2ex.com/mission/daily',
    'https://www.v2ex.com',
    'https://www.v2ex.com/balance',
]

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-CN,zh;q=0.9,zh-TW;q=0.8,en-US;q=0.7,en;q=0.6',
    'priority': 'u=0, i',
    'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
}

result = []

for i, account in enumerate(accounts_list, start=1):
    print(f"=======开始执行账号{i}=======\n")

    headers['Cookie'] = account

    data = requests.get(urls[0], headers=headers)
    if data and '每日登录奖励已领取' in data.text:
        result.append(f"账号{i}今日已签到！")
    elif data and '领取 X 铜币' in data.text:
        tree = html.fromstring(data.text)
        link = tree.xpath('//input[@class="super normal button"]/@onclick')
        match  = re.search(r"'/([^']+)'", link[0])
        if match:
            url = f"/{match.group(1)}"
        else:
            result.append(f"账号{i}未获取到签到链接：{link[0]}\n")
            continue

        data = requests.get(urls[1] + url, headers=headers)
        result.append(f"账号{i}已尝试签到！")
    else:
        result.append(f"账号{i}签到异常：{data}\n")

    data = requests.get(urls[2], headers=headers)
    if data and data.text:
        tree = html.fromstring(data.text)
        signin_time = tree.xpath('//table[@class="data"]/tr[2]/td[1]/small/text()')[0]
        time = datetime.fromisoformat(signin_time.replace(" +08:00", "")).date()
        today = datetime.now().date()
        if time == today:
            amount_value = tree.xpath('//table[@class="data"]/tr[2]/td[3]/span/strong/text()')
            result.append(f"今日签到成功，获得铜币：{amount_value[0]}\n")
        else:
            result.append(f"签到失败：{time}\n")

        # 查找账户余额区域
        balance_div = tree.xpath('//div[@class="balance_area bigger"]')
        if balance_div:
            balance_div = balance_div[0]  # 获取第一个匹配的余额区域

            # 提取数字和币种图片信息
            numbers = balance_div.xpath('text()')  # 提取文字部分（数字）
            image_sources = balance_div.xpath('.//img/@src')  # 提取图片路径

            # 初始化金银铜币
            gold, silver, bronze = 0, 0, 0

            # 遍历图片路径与数字对应
            index = 0
            for src in image_sources:
                while index < len(numbers) and not numbers[index].strip():
                    index += 1  # 跳过空白字符
                if index >= len(numbers):
                    break
                num = int(numbers[index].strip())  # 提取数字
                if "gold" in src:
                    gold = num
                elif "silver" in src:
                    silver = num
                elif "bronze" in src:
                    bronze = num
                index += 1

            result.append(f"金币数量：{gold}，银币数量：{silver}，铜币数量：{bronze}\n")
        else:
            result.append(f"获取余额异常：{data}\n")
    else:
        result.append(f"获取余额异常：{data}\n")

try:
    send("v2ex论坛签到",f"{''.join(result)}")
except Exception as e:
    print(f"消息推送失败：{e}！\n{result}\n")
