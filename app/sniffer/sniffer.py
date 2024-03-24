#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File  : sniffer.py
# Author: DaShenHan&道长-----先苦后甜，任凭晚风拂柳颜------
# Author's Blog: https://blog.csdn.net/qq_32394351
# Date  : 2024/3/24
# desc 利用selenium实现的简易播放地址嗅探器
# webdriver_manager 各个浏览器使用案例 https://blog.csdn.net/caixiangting/article/details/132049306

import ujson
from urllib.parse import urlparse
from time import time, sleep
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import re
import requests


class Sniffer:
    # 正则嗅探匹配表达式
    urlRegex: str = 'http((?!http).){12,}?\\.(m3u8|mp4|flv|avi|mkv|rm|wmv|mpg|m4a|mp3)\\?.*|http((?!http).){12,}\\.(m3u8|mp4|flv|avi|mkv|rm|wmv|mpg|m4a|mp3)|http((?!http).)*?video/tos*'
    urlNoHead: str = 'http((?!http).){12,}?(ac=dm&url=)'
    # 每次嗅探间隔毫秒
    delta: int = 250

    def __init__(self,
                 driver_path=None,
                 _type=0,
                 wait=5,
                 head_timeout=0.2,
                 timeout=10, user_agent=None, custom_regex=None):
        """
        初始化
        @param driver_path: 驱动器路径
        @param _type: 使用的浏览器 0:谷歌 1:edge
        @param wait:默认等待页面时间
        @param head_timeout:head请求超时
        @param timeout:嗅探超时
        @param user_agent:请求头
        @param custom_regex: 自定义嗅探正则
        """
        if driver_path is None:
            driver_path = r'C:\Users\dashen\.wdm\drivers\chromedriver\win64\123.0.6312.58\chromedriver-win32/chromedriver.exe'
        if user_agent is None:
            user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36'

        options = Options()
        # 无痕模式
        options.add_argument('--incognito')
        # 开启性能监听
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        options.add_experimental_option('perfLoggingPrefs', {'enableNetwork': True})
        # 忽略证书错误
        options.add_argument("--ignore-certificate-errors")
        # 禁止加载图片
        options.add_argument("--blink-settings=imagesEnabled=false")
        # 禁用不安全的外链
        options.add_argument("--no-displaying-insecure-content")
        # 跳过首次运行检查
        options.add_argument("--no-first-run")
        # 禁用扩展
        options.add_argument("--disable-extensions")
        # 允许Https加载http内容
        options.add_argument("--allow-running-insecure-content")
        # 规避自动化检测
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        # 规避滑块检测
        options.add_argument('--disable-blink-features=AutomationControlled')

        # 解决加载速度慢的问题
        options.page_load_strategy = 'none'
        # 模拟手机
        mobile_emulation = {'deviceName': 'iPhone 12 Pro'}
        options.add_experimental_option('mobileEmulation', mobile_emulation)
        # 启动时全屏
        # options.add_argument("--start-maximized")
        options.add_argument("profile-directory={profile}")
        # 不使用GPU，有的机器不支持GPU
        options.add_argument('--disable-gpu')
        # 使用无头模式，无 GUI的Linux服务器必须添加
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--headless")

        options.add_argument("--remote-debugging-port=9222")
        # 使用代理
        # options.add_argument('--proxy-server=http://127.0.0.1:7890')
        # 使用UA
        options.add_argument(f'user-agent={user_agent}')
        self.options = options
        self.wait = wait
        self.timeout = timeout
        self.head_timeout = head_timeout
        self.driver_path = driver_path
        self._type = _type
        self.custom_regex = custom_regex

        self.driver = self.init_driver()

    def init_driver(self):
        """
        初始化驱动程序
        @return:
        """
        _driver = None
        driver = None
        if self._type == 0:
            if self.driver_path == 'auto':
                self.driver_path = ChromeDriverManager().install()
            _driver = webdriver.Chrome
        elif self._type == 1:
            if self.driver_path == 'auto':
                self.driver_path = EdgeChromiumDriverManager().install()
            _driver = webdriver.Edge

        if _driver:
            service = ChromeService(self.driver_path)
            driver = _driver(service=service, options=self.options)
            driver.implicitly_wait(5)  # 隐式等待时间
            # 设置窗口大小
            driver.set_window_size(1, 0)

        return driver

    def setCookie(self, _dict):
        """
        设置cookie。可以在嗅探前或者获取源码前设置
        @param _dict:
        @return:
        """
        self.driver.add_cookie(_dict)

    def fetCodeByWebView(self, url):
        """
        利用webview请求得到渲染完成后的源码
        @param url: 待获取源码的url
        @return:
        """
        self.driver.get(url)
        content = self.driver.page_source
        url = self.driver.current_url
        return {'content': content, 'headers': {'location': url}}

    def snifferMediaUrl(self, playUrl, mode=0, custom_regex=None):
        """
        输入播放地址，返回嗅探到的真实视频链接
        @param playUrl: 播放网页地址
        @param mode: 模式:0 嗅探到一个就返回 1:在10秒内嗅探所有的返回列表
        @param custom_regex: 自定义嗅探正则
        @return:
        """
        if custom_regex is None:
            custom_regex = self.custom_regex
        realUrl = ''
        realUrls = []
        realHeaders = {}
        t1 = time()
        cost = 0
        self.driver.get(playUrl)
        while cost < self.timeout and (not realUrl or mode == 1):
            messages = []
            urls = []
            # 获取性能数据
            performance_logs = self.driver.get_log('performance')
            for entry in performance_logs:
                # 获取message的数据
                message = ujson.loads(entry.get('message')).get('message')
                if message.get('params') and message['params'].get('request'):
                    messages.append(message)
                    url = message['params']['request']['url']
                    method = message['params']['request']['method']
                    headers = message['params']['request']['headers']
                    urls.append(url)
                    if str(method).lower() == 'get' and str(url).startswith('http') and url != playUrl:
                        parsed_url = urlparse(url)
                        path = parsed_url.path
                        filename = str(path.split('/')[-1])
                        if ('.' not in filename and not re.search(self.urlNoHead, url, re.M | re.I)) or (
                                '.' in filename and len(filename) > 1 and not filename.split('.')[1]):
                            try:
                                r = requests.head(url=url, headers=headers, timeout=self.head_timeout)
                                rheaders = r.headers
                                if rheaders['Content-Type'] == 'application/octet-stream' and '.m3u8' in rheaders[
                                    'Content-Disposition']:
                                    realUrl = url

                                    if headers.get('Referer'):
                                        realHeaders['referer'] = headers['Referer']
                                    if headers.get('User-Agent'):
                                        realHeaders['user-agent'] = headers['User-Agent']
                                    if mode == 0:
                                        break
                                    else:
                                        realUrls.append({
                                            'url': realUrl,
                                            'headers': headers,
                                        })
                            except Exception as e:
                                print(f'head请求访问: {url} 发生了错误:{e}')

                    if custom_regex and re.search(custom_regex, url, re.M | re.I):
                        # print(message)
                        realUrl = url

                        if headers.get('Referer'):
                            realHeaders['referer'] = headers['Referer']
                        if headers.get('User-Agent'):
                            realHeaders['user-agent'] = headers['User-Agent']
                        if mode == 0:
                            break
                        else:
                            realUrls.append({
                                'url': realUrl,
                                'headers': headers,
                            })
                    if re.search(self.urlRegex, url, re.M | re.I):
                        if url.find('url=http') < 0 and url.find('v=http') < 0 and url.find('.css') < 0 and url.find(
                                '.html') < 0:
                            realUrl = url
                            if headers.get('Referer'):
                                realHeaders['referer'] = headers['Referer']
                            if headers.get('User-Agent'):
                                realHeaders['user-agent'] = headers['User-Agent']
                            if mode == 0:
                                break
                            else:
                                realUrls.append({
                                    'url': realUrl,
                                    'headers': headers,
                                })

            # print(len(urls), urls)
            sleep(round(self.delta / 1000, 2))
            t2 = time()
            cost = t2 - t1

        cost_str = str(round(cost * 1000, 2)) + 'ms'
        if mode == 0 and realUrl:
            return {'url': realUrl, 'headers': realHeaders, 'from': playUrl, 'cost': cost_str, 'code': 200,
                    'msg': '嗅探成功'}
        elif mode == 1 and realUrls:
            return {'urls': realUrls, 'code': 200, 'from': playUrl, 'cost': cost_str, 'msg': '嗅探成功'}
        else:
            return {'url': realUrl, 'headers': realHeaders, 'from': playUrl, 'cost': cost_str, 'code': 404,
                    'msg': '嗅探失败'}

    def close(self):
        """
        用完记得关闭驱动器
        @return:
        """
        self.driver.quit()


if __name__ == '__main__':
    t1 = time()
    url = 'https://www.cs1369.com/play/2-1-94.html'
    # url = 'https://v.qq.com/x/page/i3038urj2mt.html'
    # url = 'https://v.qq.com/x/page/i3038urj2mt.html'
    # url = 'http://www.mgtv.com/v/1/290346/f/3664551.html'
    browser = Sniffer(driver_path=None)
    # ret = browser.snifferMediaUrl(url)
    ret = browser.snifferMediaUrl('https://jx.jsonplayer.com/player/?url=https://m.iqiyi.com/v_1pj3ayb1n70.html')
    print(ret)
    ret = browser.snifferMediaUrl('https://jx.yangtu.top/?url=https://m.iqiyi.com/v_1pj3ayb1n70.html',
                                  custom_regex='http((?!http).){12,}?(download4|pcDownloadFile)')
    print(ret)
    browser.close()
    t2 = time()
    print(f'共计耗时:{round(t2 - t1, 2)}s')
