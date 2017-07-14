#! /usr/bin/env python3
# coding:utf-8

'''
leaosunday <leaosunday25@gmail.com>
2017.06.13
'''

# from gevent import monkey
# monkey.patch_all()

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


class V2EX(object):
    def __init__(self, page=1):
        self.page = page
        self.resp = None
        self.max_page = 1
        self.base_url = 'https://www.v2ex.com/go/jobs'
        self.db = MongoClient().get_database('v2ex')
        self.col = self.db.get_collection('articles')

    @staticmethod
    def process_string(raw_string):
        text = ' '.join(raw_string.split())
        return text

    def get_max_page(self):
        r = self.resp
        tree = html.fromstring(r.text)
        max_page = tree.xpath('//div[@class="cell"]/table/tr/td[1]/a/text()')[-1]
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
            'Referer': 'https://www.v2ex.com/go/jobs/',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }

        try:
            resp = requests.get(self.base_url, headers=headers)
            self.resp = resp
        except Exception as e:
            print(e)
            return False
        else:
            if 'Access Denied' in resp.text:
                print('Access Denied')
                sys.exit(1)
            if resp.status_code != 200:
                print('code != 200')
                return False
            if '做有趣的有意义的事情。' not in resp.text:
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
            params = {'p': page}
            try:
                resp = requests.get(self.base_url, headers=headers, params=params)
            except Exception as e:
                print(e)
                sys.exit(1)
            else:
                if 'Access Denied' in resp.text:
                    print('Access Denied')
                    sys.exit(1)
                if resp.status_code != 200:
                    print('code != 200')
                    print(resp.status_code)
                    sys.exit(1)
                if '做有趣的有意义的事情。' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    sys.exit(1)

                tree = html.fromstring(resp.text)
                articles = tree.xpath('//div[@id="TopicsNode"]/div')
                print('count:', len(articles))
                for article in articles:
                    article = html.fromstring(html.tostring(article))

                    publish_time_str = article.xpath('//span[@class="small fade"]')[0].text_content().strip()
                    if '分钟' in publish_time_str or '秒' in publish_time_str or '小时' in publish_time_str:
                        publish_time = datetime.now().strftime('%Y-%m-%d')
                    elif '天前' in publish_time_str:
                        before_day = int(re.search(r'(\d+) 天前', publish_time_str).group(1))
                        publish_time = (datetime.now() - timedelta(days=before_day)).strftime('%Y-%m-%d')
                    else:
                        publish_time = publish_time_str.split()[2]
                    if '2017-06-13' in publish_time:
                        sys.exit(1)

                    href = article.xpath('//span[@class="item_title"]/a/@href')

                    title = title = article.xpath('//span[@class="item_title"]/a/text()')

                    if href and title:
                        href = 'https://www.v2ex.com' + href[0]
                        title = title[0].strip()
                    else:
                        break

                    id = re.sub('#.*', '', href.split('/')[-1])

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

                sleep_time = random.uniform(1, 2)
                print('sleep: {:.2f}'.format(sleep_time))
                time.sleep(sleep_time)
                # break ### for debug

        return True

    def get_comment(self, start):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://www.v2ex.com/go/jobs/',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }

        cursor = self.col.find({"status": "not_done"})
        i = 0
        for article in cursor:
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
                sys.exit(1)
            else:
                if 'Access Denied' in resp.text:
                    print('Access Denied')
                    return 'Access Denied'
                if resp.status_code != 200:
                    print('code:', resp.status_code)
                    print('href:', href)
                    if '50' in str(resp.status_code):
                        continue
                    sys.exit(1)
                if 'V2EX 是一个关于分享和探索的地方' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    print('href:', href)
                    return 'not in the right page'

                tree = html.fromstring(resp.text)
                try:
                    comment = tree.xpath('//div[@class="topic_content"]')[0]
                except:
                    self.col.remove({'id': id})
                    continue
                comment_str = self.process_string(comment.text_content())
                self.col.find_one_and_update(
                    {'id': id},
                    {'$set': {
                        'status': 'done',
                        'comment': comment_str
                    }}
                )
                m = self.col.find({'status': 'done'}).count()
                n = self.col.count()
                print('{} / {}, {:.1f}%'.format(m, n , 100*m/n))
                i += 1
                
                sleep_time = random.uniform(start, start+1)
                print('sleep: {:.2f}'.format(sleep_time))
                time.sleep(sleep_time)

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

    v2 = V2EX(page)
    v2.get_articles()

    print('delete progress')
    try:
        os.remove('.progress.json')
    except FileNotFoundError:
        pass
    print('done!')

def main_comment():
    sleep_time = 2
    v2 = V2EX()
    msg = v2.get_comment(sleep_time)
    while msg in ('Access Denied', 'not in the right page'):
        print('sleep 300 secs')
        time.sleep(300)
        sleep_time += 1
        v2 = V2EX()
        v2.get_comment(sleep_time)

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