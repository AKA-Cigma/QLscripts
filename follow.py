#!/usr/bin/env python3
# coding: utf-8
"""
项目名称: AKA-Cigma / QLscripts
Author: AKA-Cigma
功能：Follow自动签到
抓Follow网页端的全部cookie填到环境变量'followck'里，多账号&连接
Date: 2024/10/24
cron: 8 8 * * *
new Env('Follow');
"""
from logging import exception

import requests
import time
import os
try:
    from notify import send
except:
    pass

accounts = os.getenv('followck')

if accounts is None:
    print('未检测到followck')
    exit(1)

accounts_list = accounts.split('&')
print(f"获取到 {len(accounts_list)} 个账号\n")

urls = ["https://api.follow.is/auth/csrf",
    "https://api.follow.is/wallets/transactions/claim-check",
    "https://api.follow.is/wallets/transactions/claim_daily",
    "https://api.follow.is/wallets",
    "https://api.follow.is/wallets/transactions?fromOrToUserId=",
]

headers = {
    'accept': '*/*',
    'accept-language': 'zh-CN,zh;q=0.9,zh-TW;q=0.8,en-US;q=0.7,en;q=0.6',
    'content-type': 'application/json',
    'origin': 'https://app.follow.is',
    'priority': 'u=1, i',
    'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
}

result = []

for i, account in enumerate(accounts_list, start=1):
    print(f"=======开始执行账号{i}=======\n")

    texts = []
    for s in account.split(";"):
        text = s.strip()
        if not text or text.startswith("authjs.callback-url=") or text.startswith("authjs.csrf-token="):
            continue

        texts.append(text)

    cleaned_cookie = "; ".join(texts)
    headers['cookie'] = cleaned_cookie
    session = requests.Session()
    session.headers.update(headers)
    try:
        data = session.get(urls[0])
        if data.text:
            xCsrfToken = data.json()['csrfToken']
            csrfToken = data.cookies.get_dict().get('authjs.csrf-token')
            callback = data.cookies.get_dict().get('authjs.callback-url')
        else:
            result.append(f"账号{i}未获取到xCsrfToken：{data}\n")
            continue

        headers['cookie'] = cleaned_cookie + "; authjs.callback-url=" + callback + "; authjs.csrf-token=" + csrfToken if callback and csrfToken else account
        headers['x-csrf-token'] = xCsrfToken or ''
        session.headers.update(headers)
        transactionHash = None

        data = session.get(urls[1])
        if data.text and data.json().get('data'):
            if not data.json()['data']:
                result.append(f"账号{i}今日已签到！")
            else:
                data = session.post(urls[2])
                if data.text and data.json()['code'] == 0:
                    result.append(f"账号{i}签到成功！")
                    transactionHash = data.json()['data']['transactionHash']
                    print("等待一分钟后刷新……")
                    time.sleep(60)
                else:
                    result.append(f"账号{i}签到失败：{data}，")
        else:
            result.append(f"账号{i}查询签到状态失败：{data}")

        data = session.get(urls[3])
        if data.text:
            userId = data.json()['data'][0]['userId']
            powerToken = int(data.json()['data'][0]['powerToken']) / (10 ** 18)
            result.append(f"总power：{powerToken}，")
        else:
            result.append(f"查询power总数失败：{data}\n")
            continue

        data = session.get(urls[4] + userId)
        if data.text:
            if transactionHash and data.json()['data'][0]['hash'] == transactionHash:
                result.append(f"签到校验成功！\n")
            elif transactionHash is None:
                result.append(f"仅在每天第一次签到校验结果。\n")
            else:
                result.append(f"签到校验失败：{data.json()['data'][0]['hash']}\n")
        else:
            result.append(f"签到校验失败：{data}\n")
    except Exception as e:
        result.append(f"出现未知错误：{e}即将进行下一账号\n")
    finally:
        session.close()

try:
    send("Follow签到",f"{''.join(result)}")
except Exception as e:
    print(f"消息推送失败：{e}！\n{result}\n")
