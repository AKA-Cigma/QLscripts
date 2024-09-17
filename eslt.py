#!/usr/bin/env python3
# coding: utf-8
'''
项目名称: AKA-Cigma / QLscripts
Author: AKA-Cigma
功能：恩山论坛自动签到
抓电脑网页端恩山论坛积分页面请求头的完整cookie填到环境变量'esltck'里，多账号&连接
Date: 2024/09/17
cron: 5 0 * * *
new Env('恩山论坛');
'''
import requests, json, time, os, sys
from lxml import etree
try:
    from notify import send
except:
    pass

accounts = os.getenv('esltck')

if accounts is None:
    print('未检测到esltck')
    exit(1)

accounts_list = accounts.split('&')
print(f"获取到 {len(accounts_list)} 个账号\n")

url = "https://www.right.com.cn/forum/home.php?mod=spacecp&ac=credit&op=log&suboperation=creditrulelog"

headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Connection' : 'keep-alive',
        'Host' : 'www.right.com.cn',
        'Upgrade-Insecure-Requests' : '1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language' : 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding' : 'gzip, deflate, br',
        'Cookie': ''
    }

result = []

for i, account in enumerate(accounts_list, start=1):
    print(f"=======开始执行账号{i}=======\n")

    headers['Cookie'] = account

    data = requests.get(url, headers=headers)
    if data and '每天登录' in data.text:
        result.append(f"账号{i}签到成功！\n")
        h = etree.HTML(data.text)
        signin_data = h.xpath('//tr[td[1]="每天登录"]/td[position() >= 2 and position() <= 6]/text()')
        if len(signin_data) == 5:
            result.append(f'签到总次数：{signin_data[0]}，签到周期次数：{signin_data[1]}，贡献：{signin_data[2]}，\
获得恩山币：{signin_data[3]}，最后签到时间：{signin_data[4]}\n')
        else:
            result.append(f'返回参数异常，可能是界面变更：{signin_data}\n')
    else:
        result.append(f"账号{i}签到失败：{data}\n")

try:
    send("恩山论坛签到",f"{''.join(result)}")
except Exception as e:
    print(f"消息推送失败：{e}！\n{result}\n")
