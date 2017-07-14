#! /usr/bin/env python3
# coding:utf-8

'''
leaosunday <leaosunday25@gmail.com>
2017.04.26
'''

# http://bbs.scut.edu.cn/classic/content.jsp?forumID=484 勤助与兼职信息
# http://bbs.scut.edu.cn/classic/content.jsp?forumID=477 就业与人才市场

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

class MuMian(object):
    def __init__(self, page=1):
        self.page = page
        self.max_page = 1
        self.resp = None
        self.base_url = 'http://bbs.scut.edu.cn/classic/content.jsp?forumID=477'
        self.db = MongoClient().get_database('mumian')
        self.col = self.db.get_collection('articles')

    @staticmethod
    def process_string(raw_string):
        text = ' '.join(raw_string.split())
        return text

    def get_max_page(self):
        r = self.resp
        tree = html.fromstring(r.text)
        max_page_str = tree.xpath('//td[@class="pageNum"]/span/text()')[0]
        max_page = max_page_str.split('/')[-1]
        self.max_page = int(max_page)
        print('max page:', self.max_page)

    def get_articles(self):
        headers = {
            'Pragma': 'no-cache',
            'Origin': 'http://bbs.scut.edu.cn',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.104 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Referer': 'http://bbs.scut.edu.cn/classic/content.jsp',
            'Connection': 'keep-alive',
        }
        cookies = {
            'JSESSIONID': '17AB4013BC4AF3A15A4DA6C875DB5D61.bbs3',
            'Hm_lvt_1b8bfc0b7ec122196182060235a6f104': '1498012281',
            'Hm_lpvt_1b8bfc0b7ec122196182060235a6f104': '1498038661',
        }
        try:
            resp = requests.get(self.base_url, headers=headers)
            self.resp = resp
        except Exception as e:
            traceback.print_exc()
            return False
        else:
            if resp.status_code != 200:
                print('code != 200', resp.status_code)
                return False
            if '收藏本版' not in resp.text:
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
            data = [
                ('pageNum', str(page)),
                ('forumID', '477'),
                ('goPage', ''),
                ('goPage2', ''),
            ]
            url = 'http://bbs.scut.edu.cn/classic/content.jsp'
            while True:
                try:
                    resp = requests.post(url, headers=headers, cookies=cookies, data=data)
                except Exception as e:
                    traceback.print_exc()
                    sys.exit(1)
                else:
                    if resp.status_code != 200:
                        print('code != 200', resp.status_code)
                        sys.exit(1)
                    if '收藏本版' not in resp.text:
                        print('not in the right page')
                        print('current page:', resp.url)
                        sys.exit(1)

                    tree = html.fromstring(resp.text)
                    articles = tree.xpath('//table[@class="listTable"]/tr')
                    print('count:', len(articles))
                    for i, article in enumerate(articles):
                        if i == 0:
                            continue
                        article = html.fromstring(html.tostring(article))

                        publish_time = article.xpath('//td[4]/p[@class="content_p02"]/text()')[0].strip()

                        href = article.xpath('//td[3]/a/@href')
                        title = article.xpath('//td[3]/a/text()')
                        if href and title:
                            href = href[0].strip()
                            title = title[0].strip()
                        else:
                            break
                        id = re.search(r'threadID=(\d+)&', href).group(1)
                        href = 'http://bbs.scut.edu.cn/classic/' + href
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
                break

        return True

    def get_comment(self):
        headers = {
            'Pragma': 'no-cache',
            'Origin': 'http://bbs.scut.edu.cn',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.104 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Referer': 'http://bbs.scut.edu.cn/classic/content.jsp',
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
                # if '抱歉，本帖要求阅读权限' in resp.text:
                #     print('no authority')
                #     print('href:', href)
                #     self.col.delete_one({'href': href})
                #     i += 1
                #     continue
                # if '没有权限访问该版块' in resp.text:
                #     print('no authority')
                #     print('href:', href)
                #     self.col.delete_one({'href': href})
                #     i += 1
                #     continue
                # if resp.url == 'http://bbs.scut.edu.cn/classic/index.jsp':
                #     print('article not exist')
                #     print('href:', href)
                #     self.col.delete_one({'href': href})
                #     i += 1
                #     continue
                if '楼主' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    print('href:', href)
                    self.col.delete_one({'id': id})
                    continue

                tree = html.fromstring(resp.text)
                comment = tree.xpath('//div[@class="contentWrap"]/div[@class="content"]')[0]
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

    mm = MuMian(page)
    mm.get_articles()

    print('delete progress')
    try:
        os.remove('.progress.json')
    except FileNotFoundError:
        pass
    print('done!')

def main_comment():
    greenlets = []
    for i in range(20):
        mm = MuMian()
        greenlets.append(gevent.spawn(mm.get_comment))
    gevent.joinall(greenlets)

if __name__ == '__main__':
    args = sys.argv
    if len(args) != 2:
        print('need choice')
    elif args[1] == 'href':
        main()
    elif args[1] == 'comment':
        main_comment()
