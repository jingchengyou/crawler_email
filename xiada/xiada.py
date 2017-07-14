#! /usr/bin/env python3
# coding:utf-8

'''
leaosunday <leaosunday25@gmail.com>
2017.06.28
'''

# http://bbs.xmu.edu.cn/bbsdoc.php?board=Office

from gevent import monkey
monkey.patch_all()

import gevent
import requests
import time
import json
import sys
import os
import traceback
import re
from pprint import pprint
from lxml import html
from datetime import datetime
from pymongo import MongoClient

class Beiyouren(object):
    def __init__(self, page=1):
        self.page = page
        self.max_page = 312
        self.resp = None
        self.base_url = 'http://bbs.xmu.edu.cn/bbsdoc.php?board=Office'
        self.db = MongoClient().get_database('xiada')
        self.col = self.db.get_collection('articles')
        self.text = ''

    @staticmethod
    def process_string(raw_string):
        text = ' '.join(raw_string.split())
        return text

    # def get_max_page(self):
    #     r = self.resp
    #     tree = html.fromstring(r.text)
    #     max_page = tree.xpath('//li[@class="page-normal"]/a/text()')[-2]
    #     self.max_page = int(max_page)
    #     print('max page:', self.max_page)

    def get_articles(self):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'http://bbs.xmu.edu.cn/bbsdoc.php?board=Office',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }

        # params = {'page': 1}
        # try:
        #     resp = requests.get(self.base_url, headers=headers, params=params)
        #     self.resp = resp
        # except Exception as e:
        #     traceback.print_exc()
        #     return False
        # else:
        #     if resp.status_code != 200:
        #         print('code != 200')
        #         return False
        #     if '今日帖数' not in resp.text:
        #         print('not in the right page')
        #         print('current page:', resp.url)
        #         return False

        #     self.get_max_page()
            
        # for page in range(self.page, self.max_page+1):
        for page in range(self.page, self.max_page+1):
            print('\ngo to page:', page)
            with open('.progress.json', 'w+') as f:
                json.dump({
                    'page': page
                }, f)
            params = {'page': page}
            try:
                resp = requests.get(self.base_url, headers=headers, params=params)
                self.text = resp.content.decode('GB18030', 'ignore')
            except Exception:
                traceback.print_exc()
                sys.exit(1)
            else:
                if resp.status_code != 200:
                    print('code != 200')
                    sys.exit(1)
                if 'Office(工作人) 版' not in self.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    sys.exit(1)

                articles = [a for a in self.text.split(';') if a.startswith('\nc.o')]
                print('count:', len(articles))
                for article in articles:
                    article = article.strip()

                    title = article.split(',')[5].strip()
                    if 'Re:' in title:
                        continue

                    publish_time_str = re.search(r"',(\d+),'", article).group(1)
                    publish_time = datetime.fromtimestamp(int(publish_time_str)).strftime('%Y-%m-%d %H:%M:%S')

                    id = re.search(r'c\.o\((\d+),', article).group(1)

                    href = 'http://bbs.xmu.edu.cn/bbscon.php?bid=90&id=' + str(id)

                    article_json = {
                        'id': id,
                        'href': href,
                        'title': title,
                        'publishTime': publish_time,
                        'status': 'not_done'
                    }
                    if not self.col.find_one({'id': id}):
                        self.col.insert_one(article_json)

        return True

    def get_comment(self):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'http://bbs.xmu.edu.cn/bbsdoc.php?board=Office',
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
                self.text = resp.content.decode('GB18030', 'ignore')
            except Exception as e:
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
                if '文章不存在' in self.text:
                    print('article not exist')
                    print('href:', href)
                    self.col.delete_one({'href': href})
                    i += 1
                    continue
                if '阅读文章' not in self.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    print('href:', href)
                    sys.exit(1)

                comment = re.search(r"prints\('(.*?)'\);", self.text).group(1)
                comment_str = self.process_string(comment.replace('\\n', '').replace('\\r', ''))
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

    byr = Beiyouren(page)
    byr.get_articles()

    print('delete progress')
    try:
        os.remove('.progress.json')
    except FileNotFoundError:
        pass
    print('done!')

def main_comment():
    greenlets = []
    for i in range(20):
        byr = Beiyouren()
        greenlets.append(gevent.spawn(byr.get_comment))
    gevent.joinall(greenlets)

if __name__ == '__main__':
    args = sys.argv
    if len(args) != 2:
        print('need choice')
    elif args[1] == 'href':
        main()
    elif args[1] == 'comment':
        main_comment()
