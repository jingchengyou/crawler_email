#! /usr/bin/env python3
# coding:utf-8

'''
leaosunday <leaosunday25@gmail.com>
2017.06.28
http://bbs.whu.edu.cn/wForum/board.php?name=PartTimeJob
http://bbs.whu.edu.cn/wForum/board.php?name=Job
http://bbs.whu.edu.cn/wForum/board.php?name=JobInfo
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
        self.job_url = 'http://bbs.whu.edu.cn/wForum/board.php?name=Job'
        self.parttime_url = 'http://bbs.whu.edu.cn/wForum/board.php?name=PartTimeJob'
        self.jobinfo_url = 'http://bbs.whu.edu.cn/wForum/board.php?name=JobInfo'
        self.db = MongoClient().get_database('wuda')
        self.col = self.db.get_collection('articles')

    @staticmethod
    def process_string(raw_string):
        text = ' '.join(raw_string.split())
        return text

    def get_max_page(self):
        r = self.resp
        tree = html.fromstring(r.content)
        max_page = tree.xpath('//div[@align="right"]/a[last()-1]/b/text()')[0]
        self.max_page = int(max_page)
        print('max page:', self.max_page)

    def get_articles(self, plate):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch, br',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'http://bbs.whu.edu.cn/wForum/index.php',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }

        if plate == 'Job':
            self.base_url = self.job_url
        elif plate == 'JobInfo':
            self.base_url = self.jobinfo_url
        elif plate == 'PartTimeJob':
            self.base_url = self.parttime_url

        params = (('page', '1'),)
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
            if '快速搜索' not in resp.content.decode('GBK'):
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
            params = (('page', page),)
            try:
                resp = requests.get(self.base_url, headers=headers, params=params)
            except Exception as e:
                print(e)
                sys.exit(1)
            else:
                if resp.status_code != 200:
                    print('code != 200')
                    sys.exit(1)
                if '快速搜索' not in resp.content.decode('GBK'):
                    print('not in the right page')
                    print('current page:', resp.url)
                    sys.exit(1)

                tree = html.fromstring(resp.content)
                articles_str = tree.xpath('/html/body/table[6]/script')[0].text
                articles = articles_str.split('origin = ')
                articles.pop(0)
                print('count:', len(articles))
                for article in articles:
                    try:
                        title = re.search(r"writepost\(.*?'(.*?)'", article).group(1)
                    except AttributeError:
                        print(article)
                        traceback.print_exc()
                        time.sleep(1)
                        continue

                    id = re.search(r'new Post\((\d+),', article).group(1)
                    
                    href = 'http://bbs.whu.edu.cn/wForum/disparticle.php?boardName=' + str(plate) + '&ID=' + str(id)
                    
                    article_json = {
                        'id': id,
                        'href': href,
                        'title': title,
                        'status': 'not_done'
                    }
                    if not self.col.find_one({'id': id}):
                        self.col.insert_one(article_json)

        return True

    def get_comment(self):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch, br',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'http://bbs.whu.edu.cn/wForum/index.php',
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
                if '指定的版面不存在' in resp.content.decode('GBK'):
                    print('指定的版面不存在')
                    self.col.delete_one({'id': id})
                    continue
                if '论坛错误信息' in resp.content.decode('GBK'):
                    print('论坛错误信息')
                    self.col.delete_one({'id': id})
                    continue
                if '楼主' not in resp.content.decode('GBK'):
                    print('not in the right page')
                    print('current page:', resp.url)
                    print('href:', href)
                    sys.exit(1)

                tree = html.fromstring(resp.content)
                comment = tree.xpath('//td[@style="font-size:11pt;line-height:14pt;padding: 0px 5px;"]')[0]
                comment_str = self.process_string(comment.text_content())
                try:
                    publish_time = re.search(r'发信站: .*?\((.*?)\)',comment_str).group(1)
                except AttributeError:
                    print(href)
                    sys.exit(1)

                self.col.find_one_and_update(
                    {'id': id},
                    {'$set': {
                        'status': 'done',
                        'publish_time': publish_time,
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

    # bd.get_articles('Job')
    # print('delete progress')
    # try:
    #     os.remove('.progress.json')
    # except FileNotFoundError:
    #     pass

    # bd.get_articles('JobInfo')
    # print('delete progress')
    # try:
    #     os.remove('.progress.json')
    # except FileNotFoundError:
    #     pass

    bd.get_articles('PartTimeJob')
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
