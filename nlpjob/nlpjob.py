#! /usr/bin/env python3
# coding:utf-8

'''
leaosunday <leaosunday25@gmail.com>
2017.05.11
'''

# http://www.nlpjob.com/jobs/

from gevent import monkey
monkey.patch_all()

import gevent
import requests
import time
import json
import sys
import os
import traceback
from pprint import pprint
from lxml import html
from datetime import datetime
from pymongo import MongoClient

class Nlpjob(object):
    def __init__(self, page=1):
        self.page = page
        self.resp = None
        self.base_url = 'http://www.nlpjob.com/jobs/'
        self.db = MongoClient().get_database('nlpjob')
        self.col = self.db.get_collection('articles')

    @staticmethod
    def process_string(raw_string):
        text = ' '.join(raw_string.split())
        return text

    def get_articles(self):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'http://www.nlpjob.com/',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }   
        # for page in range(self.page, self.max_page+1):
        for page in range(self.page, 445): # TODO check if next page exist
            print('\ngo to page:', page)
            with open('.progress.json', 'w+') as f:
                json.dump({
                    'page': page
                }, f)
            params = {'p': page}
            try:
                a = time.time()
                resp = requests.get(self.base_url, headers=headers, params=params)
                b = time.time()
                print(b-a)
            except Exception as e:
                print(e)
                sys.exit(1)
            else:
                if resp.status_code != 200:
                    print('code != 200')
                    sys.exit(1)
                if '全部职位' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    sys.exit(1)

                tree = html.fromstring(resp.text)
                articles = tree.xpath('//div[contains(@class, "row")]')
                print('count:', len(articles))
                for article in articles:
                    article = html.fromstring(html.tostring(article))

                    publish_time = article.xpath('//span[@class="time-posted"]')[0].text_content().strip()

                    href = article.xpath('//span[@class="row-info"]/a/@href')

                    title = title = article.xpath('//span[@class="row-info"]/a/text()')

                    if href and title:
                        href = href[0]
                        title = title[0].strip()
                    else:
                        break

                    id = href.split('/')[4]

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
            'Referer': 'http://www.nlpjob.com/jobs/',
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
                if resp.status_code != 200:
                    print('code:', resp.status_code)
                    print('href:', href)
                    if '50' in str(resp.status_code):
                        continue
                    sys.exit(1)
                # if '文章不存在' in resp.text:
                #     print('article not exist')
                #     print('href:', href)
                #     self.col.delete_one({'href': href})
                #     i += 1
                #     continue
                if '申请人' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    print('href:', href)
                    sys.exit(1)

                tree = html.fromstring(resp.text)
                try:
                    comment = tree.xpath('//div[@id="job-description"]')[0]
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
                    m1 = self.col.find({'status': 'fetched'}).count()
                    n = self.col.count()
                    print('{} / {}, {:.1f}%'.format(m+m1, n , 100*(m+m1)/n))
                i += 1
                # break

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

    nj = Nlpjob(page)
    nj.get_articles()

    print('delete progress')
    try:
        os.remove('.progress.json')
    except FileNotFoundError:
        pass
    print('done!')

def main_comment():
    greenlets = []
    for i in range(20):
        nj = Nlpjob()
        greenlets.append(gevent.spawn(nj.get_comment))
    gevent.joinall(greenlets)

if __name__ == '__main__':
    args = sys.argv
    if len(args) != 2:
        print('need choice')
    elif args[1] == 'href':
        main()
    elif args[1] == 'comment':
        main_comment()
