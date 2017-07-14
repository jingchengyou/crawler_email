#! /usr/bin/env python3
# coding:utf-8

'''
leaosunday <leaosunday25@gmail.com>
2017.05.15
'''

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
import random
from pprint import pprint
from lxml import html
from datetime import datetime, timedelta
from pymongo import MongoClient


class ITpub(object):
    def __init__(self, page=1):
        self.page = page
        self.resp = None
        self.base_url = 'http://www.itpub.net/forum-11-{}.html'
        self.db = MongoClient().get_database('itpub')
        self.col = self.db.get_collection('articles')

    @staticmethod
    def process_string(raw_string):
        text = ' '.join(raw_string.split())
        return text

    def get_max_page(self):
        r = self.resp
        tree = html.fromstring(r.text)
        max_page_str = tree.xpath('//a[@class="last"]/text()')[0]
        max_page = max_page_str.split()[-1]
        self.max_page = int(max_page)
        print('max page:', self.max_page)

    def get_articles(self):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'http://www.itpub.net/forum-11-1.html',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }

        try:
            resp = requests.get(self.base_url.format(1), headers=headers)
            self.resp = resp
        except Exception as e:
            print(e)
            return False
        else:
            if resp.status_code != 200:
                print('code != 200')
                return False
            if '职位搜索' not in resp.text:
                print('not in the right page')
                print('current page:', resp.url)
                return False

            self.get_max_page()

        for page in range(self.page, 11):
            print('\ngo to page:', page)
            with open('.progress.json', 'w+') as f:
                json.dump({
                    'page': page
                }, f)
            try:
                resp = requests.get(self.base_url.format(page), headers=headers)
            except Exception as e:
                print(e)
                sys.exit(1)
            else:
                if resp.status_code != 200:
                    print('code != 200')
                    sys.exit(1)
                if '职位搜索' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    sys.exit(1)

                tree = html.fromstring(resp.text)
                articles = tree.xpath('//table[@id="threadlisttableid"]/tbody[contains(@id, "normalthread")]')
                print('count:', len(articles))
                for article in articles:
                    # print(html.tostring(article))
                    article = html.fromstring(html.tostring(article))

                    publish_time = article.xpath('//td[@class="by cc"]/em/span')[0].text_content().strip()

                    if publish_time:
                        p = publish_time.split('-')
                        year = p[0]
                        month = p[1]
                        day = p[2]
                        if year != '2017':
                            continue
                        if int(month) < 5 and int(day) < 14:
                            continue
                    else:
                        continue

                    href = article.xpath('//th[@class="new"]/a[2]/@href')
                    if not href:
                        href = article.xpath('//th[@class="common"]/a[2]/@href')

                    title = article.xpath('//th[@class="new"]/a[2]/text()')
                    if not title:
                        title = article.xpath('//th[@class="common"]/a[2]/text()')

                    if href and title:
                        href = 'http://www.itpub.net/' + href[0]
                        title = title[0].strip()
                    else:
                        break

                    id = href.split('-')[1]

                    article_json = {
                        'id': id,
                        'href': href,
                        'title': title,
                        'publishTime': publish_time,
                        'status': 'not_done'
                    }
                    # pprint(article_json)

                    if not self.col.find_one({'id': id}):
                        self.col.insert_one(article_json)

                        # sleep_time = random.uniform(1, 2)
                        # print('sleep: {:.2f}'.format(sleep_time))
                        # time.sleep(sleep_time)
                        # break ### for debug

        return True

    def get_comment(self):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'http://www.itpub.net/forum-11-1.html',
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
                traceback.print_exc()
                self.col.find_one_and_update(
                    {'id': id},
                    {'$set': {
                        'status': 'not_done',
                    }}
                )
                continue
            else:
                if '没有找到帖子' in resp.text or '抱歉，本帖要求阅读权限' in resp.text:
                    self.col.remove({'id': id})
                    continue
                if resp.status_code != 200:
                    print('code:', resp.status_code)
                    print('href:', href)
                    if '50' in str(resp.status_code):
                        continue
                    sys.exit(1)
                if '本版精华' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    print('href:', href)
                    print(resp.text)
                    sys.exit(1)

                tree = html.fromstring(resp.text)
                try:
                    comment = tree.xpath('//div[contains(@class, "t_f") '
                                         'or contains(@class, "rwdn") '
                                         'or contains(@class, "pcbs")]/table/tr/td')[0]
                except:
                    print('something wrong', href)
                    sys.exit(1)
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
                    n = self.col.count()
                    print('{} / {}, {:.1f}%'.format(m, n, 100 * m / n))
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

    ip = ITpub(page)
    ip.get_articles()

    print('delete progress')
    try:
        os.remove('.progress.json')
    except FileNotFoundError:
        pass
    print('done!')


def main_comment():
    greenlets = []
    for i in range(20):
        ip = ITpub()
        greenlets.append(gevent.spawn(ip.get_comment))
    gevent.joinall(greenlets)


if __name__ == '__main__':
    try:
        args = sys.argv
        if len(args) != 2:
            print('need choice')
        elif args[1] == 'href':
            main()
        elif args[1] == 'comment':
            main_comment()
    except KeyboardInterrupt:
        sys.exit('KeyboardInterrupt')