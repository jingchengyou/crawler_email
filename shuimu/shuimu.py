#! /usr/bin/env python3
# coding:utf-8

# http://www.newsmth.net/ 主页
# http://www.newsmth.net/nForum/board/Career_Campus?ajax&p=1 校园
# http://www.newsmth.net/nForum/board/Career_Upgrade?ajax&p=1 社会
# http://www.newsmth.net/nForum/board/ExecutiveSearch?ajax&p=1 猎头

from gevent import monkey
monkey.patch_all()

import gevent
import requests
import json
import sys
import os
from pprint import pprint
from lxml import html
from pymongo import MongoClient

class ShuiMu(object):
    def __init__(self, theme='Career_Campus', page=1):
        self.theme = theme
        self.page = page
        self.max_page = 1
        self.resp = None
        self.db = MongoClient().get_database('shuimu')
        self.col = self.db.get_collection('articles')

    @staticmethod
    def process_string(raw_string):
        text = raw_string.replace('\t', '').replace('\n', ' ')
        text = ' '.join(text.split())
        return text

    def get_max_page(self):
        r = self.resp
        tree = html.fromstring(r.text)
        max_page = tree.xpath('//li[@class="page-normal"]/a/text()')[-2]
        self.max_page = int(max_page)
        print('max page:', self.max_page)

    def get_articles(self):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
            'Accept': '*/*',
            'Referer': 'http://www.newsmth.net/nForum/',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        params = (('ajax', ''), ('p', '1'),)
        try:
            resp = requests.get('http://www.newsmth.net/nForum/board/'+self.theme, headers=headers, params=params)
            self.resp = resp
        except Exception as e:
            print(e)
            return False
        else:
            if resp.status_code != 200:
                print('code != 200')
                return False
            if '主题数' not in resp.text:
                print('not in the right page')
                print('current page:', resp.url)
                return False

            self.get_max_page()
        for page in range(self.page, self.max_page+1):
            print('go to page:', page, self.theme)
            with open(self.theme+'.progress.json', 'w+') as f:
                json.dump({
                    'theme': self.theme,
                    'page': page
                }, f)
            params = (('ajax', ''), ('p', page),)
            try:
                resp = requests.get('http://www.newsmth.net/nForum/board/'+self.theme, headers=headers, params=params)
            except Exception as e:
                print(e)
                sys.exit(1)
            else:
                if resp.status_code != 200:
                    print('code != 200')
                    sys.exit(1)
                if '主题数' not in resp.text:
                    print('not in the right page')
                    print('current page:', resp.url)
                    sys.exit(1)

                tree = html.fromstring(resp.text)
                articles = tree.xpath('//table[@class="board-list tiz"]/tbody/tr')
                # print('count:', len(articles))
                for article in articles:
                    article = html.fromstring(html.tostring(article))

                    href = article.xpath('//td[@class="title_9"]/a/@href')
                    title = title = article.xpath('//td[@class="title_9"]/a/text()')
                    if href and title:
                        href = href[0]
                        title = title[0]
                    else:
                        break
                    href = 'http://www.newsmth.net' + href
                    article_json = {
                        'href': href,
                        'title': title,
                        'status': 'not_done'
                    }
                    if not self.col.find_one({'href': href}):
                        self.col.insert_one(article_json)
                        # pprint(article_json)

        return True

    def get_comment(self):
        headers = {
            'Pragma': 'no-cache',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
            'Accept': '*/*',
            'Referer': 'http://www.newsmth.net/nForum/',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        params = (
            ('ajax', ''),
        )

        i = 0
        while True:
            article = self.col.find_one_and_update(
                {'status': 'not_done'},
                {'$set': {'status': 'ing'}}
            )
            # article = self.col.find_one({'status': 'not_done'})
            href = article['href']
            try:
                resp = requests.get(href, headers=headers, params=params)
            except Exception as e:
                print(e)
                sys.exit(1)
            else:
                if resp.status_code != 200:
                    print('code:', resp.status_code)
                    print('href:', href)
                    if '50' in str(resp.status_code):
                        continue
                    sys.exit(1)
                if '文章不存在' in resp.text:
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
                comment = tree.xpath('//td[@class="a-content"]/p')[0]
                comment_str = self.process_string(comment.text_content())
                self.col.find_one_and_update(
                    {'href': href},
                    {'$set': {
                        'status': 'done',
                        'comment': comment_str
                    }}
                )
                if i % 100 == 0:
                    m = self.col.find({'status': 'done'}).count()
                    n = self.col.count()
                    print('{} / {}, {:.1f}%'.format(m, n , 100*m/n))
                i += 1

def main():
    try:
        with open('.progress.json', 'r') as f:
            progress = json.load(f)
        print('load process')
        pprint(progress)
    except IOError:
        progress = ''

    themes = ['Career_Campus', 'Career_Upgrade', 'ExecutiveSearch']
    if progress:
        campus_page = int(progress['Career_Campus'])
        upgrade_page = int(progress['Career_Upgrade'])
        search_page = int(progress['ExecutiveSearch'])
    page_list = [campus_page, upgrade_page, search_page]

    greenlets = []
    i = 0
    for theme in themes:
        page = page_list[i]
        sm = ShuiMu(theme, page)
        greenlets.append(gevent.spawn(sm.get_articles))
        i += 1
        # if not result:
        #     print('something wrong, exit')
        #     sys.exit(1)
        # break ### for debug
    gevent.joinall(greenlets)

    print('delete progress')
    os.remove('.progress.json')
    print('done!')

def main_comment():
    greenlets = []
    for i in range(10):
        sm = ShuiMu()
        greenlets.append(gevent.spawn(sm.get_comment))
    gevent.joinall(greenlets)

if __name__ == '__main__':
    args = sys.argv
    if len(args) != 2:
        print('need choice')
    elif args[1] == 'href':
        main()
    elif args[1] == 'comment':
        main_comment()
