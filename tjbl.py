#!/usr/bin/env python3
# coding: utf-8
'''
项目名称: AKA-Cigma / QLscripts
Author: AKA-Cigma
功能：唐久便利自动签到
抓手机端小程序签到请求头里面的authorization#accept-serial#User-Agent填到环境变量'tjblck'里，多账号&连接
Date: 2024/09/06
cron: 4 0 * * *
new Env('唐久便利');
'''
import requests
import os
import json
try:
    from notify import send
except:
    pass

accounts = os.getenv('tjblck')

if accounts is None:
    print('未检测到tjblck')
    exit(1)

accounts_list = accounts.split('&')
print(f"获取到 {len(accounts_list)} 个账号\n")

urls = ["https://api.xiantjbl.com/prod-api/user/score/userSignDay",
    "https://api.xiantjbl.com/prod-api/user/score/queryUserSignList?signMonth\u003d",
    "https://api.xiantjbl.com/prod-api/user/score/queryUserScoreItem",
]

headers = {
    "Host": "api.xiantjbl.com",
    "Connection": "keep-alive",
    "authorization": "",
    "charset": "utf-8",
    "accept-language": "zh",
    "User-Agent": "",
    "content-type": "application/json",
    "Accept-Encoding": "gzip,compress,br,deflate",
    "accept-serial": ""
  }

result = []

def request_json(url, headers):
    response = requests.get(url, headers=headers)
    raw_response = response.content.decode('utf-8')

    try:
        data = json.loads(raw_response)
        return data
    except json.JSONDecodeError:
        print("无法解析为JSON格式：\n")
        print(raw_response)
        return None


for i, account in enumerate(accounts_list, start=1):
    print(f"=======开始执行账号{i}=======\n")
    params_list = account.split('#')
    if len(params_list) != 3:
        result.append(f"参数数量错误！跳过账号{i}！\n")
        continue

    headers['authorization'] = params_list[0]
    headers['accept-serial'] = params_list[1]
    headers['User-Agent'] = params_list[2]

    data = request_json(urls[0], headers=headers)
    if data and data['msg'] == "操作成功":
        result.append(f"账号{i}签到成功！\n")
    else:
        result.append(f"账号{i}签到失败：{data}\n")

    data = request_json(urls[1], headers=headers)
    if data and data['msg'] == "操作成功":
        result.append(f"本月签到{data['data']['numCount']}次，共获得积分：{data['data']['scoreCount']}，")
    else:
        result.append(f"查询签到详情失败：{data}，")

    data = request_json(urls[2], headers=headers)
    if data and data['msg'] == "操作成功":
        result.append(f"当前账户总积分：{data['data']['totalScore']}，昵称：{data['data']['nickName']}\n")
    else:
        result.append(f"查询当前积分失败：{data}\n")

try:
    send("唐久便利签到",f"{''.join(result)}")
except Exception as e:
    print(f"消息推送失败：{e}！\n{result}\n")
