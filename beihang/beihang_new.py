#! /usr/bin/env python3
# coding:utf-8

'''
leaosunday <leaosunday25@gmail.com>
2017.06.21
'''

# http://www.buaaer.com/bbs/forumdisplay.php?fid=36

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

class Beihang(object):
    def __init__(self, page=1):
        self.page = page
        self.max_page = 1
        self.resp = None
        self.text = ''
        self.base_url = 'http://www.buaaer.com/bbs/forumdisplay.php?fid=36'
        self.db = MongoClient().get_database('beihang')
        self.col = self.db.get_collection('articles')

    @staticmethod
    def process_string(raw_string):
        text = raw_string.replace('\t', ' ').replace('\n', ' ')
        text = ' '.join(text.split())
        return text

    def get_max_page(self):
        r = self.resp
        tree = html.fromstring(r.text)
        max_page_str = tree.xpath('//a[@class="p_pages"]/text()')[0].strip()
        max_page = max_page_str.split('/')[-1]
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
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }

        params = {'page': 1}
        try:
            resp = requests.get(self.base_url, headers=headers, params=params)
            self.resp = resp
            self.text = resp.content.decode('gbk')
        except Exception as e:
            traceback.print_exc()
            return False
        else:
            if resp.status_code != 200:
                print('code != 200')
                return False
            if '本版规则' not in self.text:
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
            params = {'page': page}
            try:
                # a = time.time()
                resp = requests.get(self.base_url, headers=headers, params=params)
                self.text = resp.content.decode('gbk')
                # b = time.time()
                # print(b-a)
            except Exception as e:
                print(e)
                sys.exit(1)
            else:
                if resp.status_code != 200:
                    print('code != 200')
                    sys.exit(1)
                if '本版规则' not in self.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    sys.exit(1)

                tree = html.fromstring(self.text)
                articles = tree.xpath('//form/div[@class="maintable"]/div[@class="spaceborder"]/table[@class="row"]/tr')
                print('count:', len(articles))
                for i, article in enumerate(articles):
                    if page == 1 and i == 0:
                        continue

                    article = html.fromstring(html.tostring(article))

                    try:
                        article.xpath('//td[@class="f_title"]')[0]
                    except IndexError:
                        print('f_title not exist')
                        # print(article.text_content())
                        # print(resp.url)
                        # time.sleep(2)
                        continue

                    update_time = article.xpath('//td[@class="f_last"]/span/a/text()')[0].strip()
                    year = update_time.split('-')[0]
                    month = int(update_time.split('-')[1])
                    day = int(update_time.split('-')[2].split()[0])
                    if year != '2017':
                        return
                    if month <= 4 and day <= 26:
                        return

                    publish_time = article.xpath('//td[@class="f_author"]/span/text()')[0].strip()

                    href = article.xpath('//td[@class="f_title"]/a/@href')
                    title = title = article.xpath('//td[@class="f_title"]/a/text()')
                    if href and title:
                        href = href[0].strip()
                        title = title[0].strip()
                    else:
                        print('href or title not exist')
                        break
                    id = re.search(r'tid=(\d+)&', href).group(1)
                    href = 'http://www.buaaer.com/bbs/' + href
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
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'http://bbs.cloud.icybee.cn/board/JobInfo',
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

            # article = self.col.find_one({'status': 'not_done'})
            href = article['href']
            id = article['id']
            try:
                resp = requests.get(href, headers=headers, timeout=60)
                self.text = resp.content.decode('gbk')
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
                if '未定义操作' in self.text:
                    print('article not exist')
                    print('href:', href)
                    self.col.delete_one({'href': href})
                    i += 1
                    continue
                if '内容自动屏蔽' in self.text:
                    print('article not exist')
                    print('href:', href)
                    self.col.delete_one({'href': href})
                    i += 1
                    continue
                if '使用道具' not in self.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    print('href:', href)
                    sys.exit(1)

                tree = html.fromstring(self.text)
                try:
                    comment = tree.xpath('//form/div[@class="spaceborder"][1]/table/tr/td[2]/table/tr[2]/td/div[2]')[0]
                except IndexError:
                    self.col.find_one_and_update(
                        {'id': id},
                        {'$set': {
                            'status': 'fail',
                            'comment': comment_str
                        }}
                    )
                    continue
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

    bh = Beihang(page)
    bh.get_articles()

    print('delete progress')
    try:
        os.remove('.progress.json')
    except FileNotFoundError:
        pass
    print('done!')

def main_comment():
    greenlets = []
    for i in range(20):
        bh = Beihang()
        greenlets.append(gevent.spawn(bh.get_comment))
    gevent.joinall(greenlets)

if __name__ == '__main__':
    args = sys.argv
    if len(args) != 2:
        print('need choice')
    elif args[1] == 'href':
        main()
    elif args[1] == 'comment':
        main_comment()
