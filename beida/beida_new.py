#! /usr/bin/env python3
# coding:utf-8

'''
leaosunday <leaosunday25@gmail.com>
2017.06.05
https://bbs.pku.edu.cn/v2/thread.php?bid=845 job_post
https://bbs.pku.edu.cn/v2/thread.php?bid=896 intern
'''

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
from datetime import datetime, timedelta
from pymongo import MongoClient


class Beida(object):
    def __init__(self, page=1):
        self.page = page
        self.max_page = 1
        self.resp = None
        self.job_url = 'https://bbs.pku.edu.cn/v2/thread.php?bid=845'
        self.intern_url = 'https://bbs.pku.edu.cn/v2/thread.php?bid=896'
        self.db = MongoClient().get_database('beida')
        self.col = self.db.get_collection('articles')

    @staticmethod
    def process_string(raw_string):
        text = ' '.join(raw_string.split())
        return text

    def get_max_page(self):
        r = self.resp
        tree = html.fromstring(r.text)
        max_page_str = tree.xpath('//div[@id="board-body"]/div[@class="paging"]/div/text()')[-2]
        max_page = max_page_str.split()[-1]
        self.max_page = int(max_page)
        print('max page:', self.max_page)

    def get_articles(self, plate='job_post'):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch, br',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://bbs.pku.edu.cn/v2/thread.php?bid=845',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }

        if plate == 'job_post':
            self.base_url = self.job_url
            self.bid = '845'
        elif plate == 'intern':
            self.base_url = self.intern_url
            self.bid = '896'

        params = (('bid', self.bid), ('page', '1'),)
        try:
            resp = requests.get(self.base_url, headers=headers, params=params)
            self.resp = resp
        except Exception as e:
            traceback.print_exc()
            return False
        else:
            if resp.status_code != 200:
                print('code != 200')
                return False
            if '收藏本版' not in resp.content.decode():
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
            params = (('bid', self.bid), ('page', page),)
            try:
                resp = requests.get(self.base_url, headers=headers, params=params)
            except Exception as e:
                print(e)
                sys.exit(1)
            else:
                if resp.status_code != 200:
                    print('code != 200')
                    sys.exit(1)
                if '收藏本版' not in resp.content.decode():
                    print('not in the right page')
                    print('current page:', resp.url)
                    sys.exit(1)

                tree = html.fromstring(resp.content.decode())
                articles = tree.xpath('//div[@id="list-content"]/div[@class="list-item-topic list-item"]')
                print('count:', len(articles))
                for article in articles:
                    article = html.fromstring(html.tostring(article))

                    update_time = article.xpath('//div[@class="author l"]/div[@class="time"]/text()')[1].strip()
                    now = datetime.now()
                    if '昨天' in update_time:
                        update_time = (now - timedelta(days=1)).strftime('%Y-%m-%d')
                    elif '前天' in update_time:
                        update_time = (now - timedelta(days=2)).strftime('%Y-%m-%d')
                    elif '-' in update_time and '2016' in update_time:
                        pass
                    elif '-' in update_time and '2016' not in update_time:
                        update_time = '2017-' + update_time.split()[0]
                    else:
                        update_time = now.strftime('%Y-%m-%d')

                    year = int(update_time.split('-')[0])
                    month = int(update_time.split('-')[1])
                    day = int(update_time.split('-')[2])
                    if year != 2017:
                        return
                    if month <= 6 and day <= 24:
                        return

                    publish_time = article.xpath('//div[@class="author l"]/div[@class="time"]/text()')[0].strip()
                    now = datetime.now()
                    if '昨天' in publish_time:
                        publish_time = (now - timedelta(days=1)).strftime('%Y-%m-%d')
                    elif '前天' in publish_time:
                        publish_time = (now - timedelta(days=2)).strftime('%Y-%m-%d')
                    elif '-' in publish_time and '2016' in publish_time:
                        pass
                    elif '-' in publish_time and '2016' not in publish_time:
                        publish_time = '2017-' + publish_time.split()[0]
                    else:
                        publish_time = now.strftime('%Y-%m-%d')

                    href = article.xpath('//a[@class="link"]/@href')
                    title = article.xpath('//div[@class="title-cont l"]/div/text()')
                    if href and title:
                        href = href[0].strip()
                        title = title[0].strip().replace('\xa0', '')
                    else:
                        break
                    id = href.split('=')[-1]
                    href = 'https://bbs.pku.edu.cn/v2/' + href
                    article_json = {
                        'id': id,
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
            'Accept-Encoding': 'gzip, deflate, sdch, br',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://bbs.pku.edu.cn/v2/thread.php?bid=845',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }

        i = 0
        while True:
            article = self.col.find_one_and_update(
                {'status': 'not_done'},
                {'$set': {'status': 'ing'}}
            )
            if not article:
                break

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
                # if '抱歉，本帖要求阅读权限' in resp.content.decode():
                #     print('no authority')
                #     print('href:', href)
                #     self.col.delete_one({'href': href})
                #     i += 1
                #     continue
                # if '没有权限访问该版块' in resp.content.decode():
                #     print('no authority')
                #     print('href:', href)
                #     self.col.delete_one({'href': href})
                #     i += 1
                #     continue
                # if '该帖被管理员或版主屏蔽' in resp.content.decode():
                #     print('article not exist')
                #     print('href:', href)
                #     self.col.delete_one({'href': href})
                #     i += 1
                    # continue
                if '返回本版' not in resp.content.decode():
                    print('not in the right page')
                    print('current page:', resp.url)
                    print('href:', href)
                    sys.exit(1)

                tree = html.fromstring(resp.content.decode())
                comment = tree.xpath('//div[@class="content"]')[0]
                comment_str = self.process_string(comment.text_content())
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

    bd = Beida(page)
    bd.get_articles('job_post')
    print('delete progress')
    try:
        os.remove('.progress.json')
    except FileNotFoundError:
        pass

    bd.get_articles('intern')
    print('delete progress')
    try:
        os.remove('.progress.json')
    except FileNotFoundError:
        pass
    print('done!')

def main_comment():
    greenlets = []
    for i in range(20):
        bd = Beida()
        greenlets.append(gevent.spawn(bd.get_comment))
    gevent.joinall(greenlets)

if __name__ == '__main__':
    args = sys.argv
    if len(args) != 2:
        print('need choice')
    elif args[1] == 'href':
        main()
    elif args[1] == 'comment':
        main_comment()
