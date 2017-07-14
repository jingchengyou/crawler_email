#! /usr/bin/env python3
# coding:utf-8

'''
leaosunday <leaosunday25@gmail.com>
2017.04.26
'''

# http://zhixing.bjtu.edu.cn/forum-623-1.html ~ forum-623-156.html
# http://zhixing.bjtu.edu.cn/forum-624-1.html ~ forum-624-367.html

from gevent import monkey
monkey.patch_all()

import gevent
import requests
import time
import json
import sys
import os
import re
import traceback
from pprint import pprint
from lxml import html
from datetime import datetime
from pymongo import MongoClient

class Beijiaoda(object):
    def __init__(self, base_url='', page=1):
        self.page = page
        self.max_page = 1
        self.resp = None
        self.base_url = base_url
        # self.job_url = 'http://zhixing.bjtu.edu.cn/forum-623-1.html'
        # self.intern_url = 'http://zhixing.bjtu.edu.cn/forum-624-1.html'
        self.db = MongoClient().get_database('beijiaoda')
        self.col = self.db.get_collection('articles')

    @staticmethod
    def process_string(raw_string):
        text = raw_string.replace('\t', ' ').replace('\n', ' ')
        text = ' '.join(text.split())
        return text

    def get_max_page(self):
        r = self.resp
        tree = html.fromstring(r.text)
        max_page_str = tree.xpath('//div[@class="pg"]/a[@class="last"]/text()')[0]
        max_page = max_page_str.split()[-1]
        self.max_page = int(max_page)
        print('max page:', self.max_page)

    def get_articles(self):
        if '623' in self.base_url:
            topic = 623
        else:
            topic = 624
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }
        
        try:
            resp = requests.get(self.base_url, headers=headers)
            self.resp = resp
        except Exception as e:
            traceback.print_exc()
            return False
        else:
            if resp.status_code != 200:
                print('code != 200')
                return False
            if '全部主题' not in resp.text:
                print('not in the right page')
                print('current page:', resp.url)
                return False

            self.get_max_page()
            
        for page in range(self.page, self.max_page+1):
            print('\ngo to page:', page)
            with open('.progress.json', 'w+') as f:
                json.dump({
                    'page': page
                }, f)
            url = 'http://zhixing.bjtu.edu.cn/forum-{}-{}.html'.format(topic, page)
            try:
                # a = time.time()
                resp = requests.get(url, headers=headers)
                # b = time.time()
                # print(b-a)
            except Exception as e:
                print(e)
                sys.exit(1)
            else:
                if resp.status_code != 200:
                    print('code != 200')
                    sys.exit(1)
                if '全部主题' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    sys.exit(1)

                tree = html.fromstring(resp.text)
                articles = tree.xpath('//table[@summary="forum_{}"]/tbody[contains(@id, "normalthread")]/tr'.format(topic))
                print('count:', len(articles))
                for article in articles:
                    article = html.fromstring(html.tostring(article))

                    update_time = article.xpath('//td[@class="by"]/em/a/text()')[0].strip()
                    year = int(update_time.split('-')[0])
                    month = int(update_time.split('-')[1])
                    day = int(update_time.split('-')[2].split()[0])
                    if year != 2017:
                        return
                    if month <= 6 and day <= 24:
                        return

                    publish_time = article.xpath('//td[@class="by"]/em/span/text()')[0].strip()

                    try:
                        type = article.xpath('//th[@class="new"]/em/a/font/text()')[0].strip()
                        if type == '宣讲会':
                            continue
                    except IndexError:
                        type = None
                    href = article.xpath('//th[@class="new"]/a/@href')
                    title = article.xpath('//th[@class="new"]/a/text()')
                    if href and title:
                        href = href[0].strip()
                        title = title[0].strip()
                    else:
                        break
                    id = href.split('-')[1]
                    href = 'http://zhixing.bjtu.edu.cn/' + href
                    article_json = {
                        'id': id,
                        'type': type,
                        'href': href,
                        'title': title,
                        'publishTime': publish_time,
                        'status': 'not_done'
                    }
                    if not self.col.find_one({'id': id}):
                        self.col.insert_one(article_json)
                        # pprint(article_json)
                # break

        return True

    def get_comment(self):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }

        i = 0
        while True:
            article = self.col.find_one_and_update(
                {'status': 'not_done'},
                {'$set': {'status': 'ing'}}
            )
            if not article:
                break

            # article = self.col.find_one({'status': 'not_done'})
            href = article['href']
            id = article['id']
            try:
                resp = requests.get(href, headers=headers, timeout=60)
            except Exception as e:
                print(id)
                traceback.print_exc()
                # time.sleep(1)
                self.col.find_one_and_update(
                    {'id': id},
                    {'$set': {
                        'status': 'not_done',
                    }}
                )
                continue
            else:
                if resp.status_code != 200:
                    print('code:', resp.status_code)
                    print('href:', href)
                    if '50' in str(resp.status_code):
                        continue
                    sys.exit(1)
                if '抱歉，本帖要求阅读权限' in resp.text:
                    print('no authority')
                    print('href:', href)
                    self.col.delete_one({'href': href})
                    i += 1
                    continue
                if '没有权限访问该版块' in resp.text:
                    print('no authority')
                    print('href:', href)
                    self.col.delete_one({'href': href})
                    i += 1
                    continue
                if '该帖被管理员或版主屏蔽' in resp.text:
                    print('article not exist')
                    print('href:', href)
                    self.col.delete_one({'href': href})
                    i += 1
                    continue
                if '楼主' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    print('href:', href)
                    sys.exit(1)

                tree = html.fromstring(resp.text)
                comment = tree.xpath('//td[@class="t_f"]')[0]
                comment_str = self.process_string(comment.text_content())
                # print(comment_str)
                # time.sleep(10)
                self.col.find_one_and_update(
                    {'id': id},
                    {'$set': {
                        'status': 'done',
                        'comment': comment_str
                    }}
                )
                if i % 50 == 0:
                    m = self.col.find({'status': 'done'}).count()
                    m1 = self.col.find({'status': 'fetched'}).count()
                    n = self.col.count()
                    print('{} / {}, {:.1f}%'.format(m+m1, n , 100*(m+m1)/n))
                i += 1

def main():
    try:
        with open('.progress.json', 'r') as f:
            progress = json.load(f)
        print('load process')
        pprint(progress)
    except IOError:
        progress = None

    if progress:
        page = int(progress['page'])
    else:
        page = 1

    # bjd = Beijiaoda('http://zhixing.bjtu.edu.cn/forum-623-1.html', page)
    bjd = Beijiaoda('http://zhixing.bjtu.edu.cn/forum-624-1.html', page)
    bjd.get_articles()

    print('delete progress')
    try:
        os.remove('.progress.json')
    except FileNotFoundError:
        pass
    print('done!')

def main_comment():
    greenlets = []
    for i in range(20):
        bjd = Beijiaoda()
        greenlets.append(gevent.spawn(bjd.get_comment))
    gevent.joinall(greenlets)

if __name__ == '__main__':
    args = sys.argv
    if len(args) != 2:
        print('need choice')
    elif args[1] == 'href':
        main()
    elif args[1] == 'comment':
        main_comment()
