#!/usr/bin/env python3
# coding:utf-8

"""
JobInfo(就业信息)爬取!
https://bbs.sjtu.edu.cn/bbsdoc?board=JobInfo

爬取内容：邮箱 电话 发帖时间 标题
主键：邮箱
爬取条件：相同邮箱，不同帖子，只取最新时间帖子

爬取步骤：
1 获取下一页url地址，并进入
2 进入每一条招聘信息
3 对招聘信息进行解析，取得邮箱，电话等四个信息，没有邮箱则直接退出
4 将爬取信息录入文件

数据存储形式：以dict的形式存入data.json
"""
import sys
import os
import re
import codecs
import datetime
import requests
from lxml import html
from bs4 import BeautifulSoup


class JobSearch(object):
    def __init__(self):
        self.base_url = "https://bbs.sjtu.edu.cn/bbsdoc?board=JobInfo"
        self.headers = {
            'User-Agent': ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                            '(KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'),
            'Referer': 'https://easy.lagou.com/im/chat/index.htm',
            'Upgrade-Insecure-Requests': '1',
            'Accept-Language': 'zh,zh-CN;q=0.8,en;q=0.6,zh-TW;q=0.4'
        }
        self.temp_data = []  # 仅将一个页面所有文章解析信息暂存列表中
        self.wrong_article_link = []  # 招聘信息不含email的文章链接

    @staticmethod
    def url_auto_minus(match):
        val = match.group()
        num = int(val) - 1
        if num:
            return str(num)
        else:
            sys.exit(0)

    def get_next_page(self, current_page_url):
        """
        获取下一页url地址
        :param current_page_url: 当前网页url地址
        :return: 下一页网页url地址
        """
        prefix_url = "https://bbs.sjtu.edu.cn/"  # 前缀url地址
        text = requests.get(current_page_url, headers=self.headers).text
        tree = html.fromstring(text)
        result = tree.xpath('/html/body/form/center/nobr/a[4]/@href')
        if len(result) >= 1:
            next_url = prefix_url + result[0]
        else:
            print("url地址捕获错误，当前网页地址为：")
            print(current_page_url)
            next_url = re.sub(r'\d+', self.url_auto_minus, current_page_url)
        return next_url

    def get_job_link(self, page_url):
        """
        输入网页url，反序输出该网页所有招聘信息url
        :param page_url: 网页url地址
        :return: 一个包含该网页所有招聘信息链接的列表
        """
        text = requests.get(page_url, headers=self.headers).text
        soup = BeautifulSoup(text, 'lxml')
        article_link = []
        job_link_pattern = re.compile(r'bbscon[?,]board[,=](JobInfo|JobForum)[,&]file')
        for link in soup.find_all('a'):
            temp = link.get('href')
            try:
                if re.match(job_link_pattern, temp).group():
                    article_link.append('https://bbs.sjtu.edu.cn/' + temp)
            except AttributeError:
                pass
        article_link.reverse()
        return article_link

    def article_parse(self, article_link):
        """
        输入招聘信息url，招聘信息解析,输出邮箱 发帖时间 标题 电话形成的列表
        :param article_link: 招聘信息链接
        :return: 一个字符串，按照右键，标题，时间，电话的顺序，以逗号为间隔组成
        """
        article_email = ''
        article_title = ''
        article_time = ''
        article_tel = ''

        target_article = ""
        time_string = ''

        text = requests.get(article_link, headers=self.headers).text
        target_article_list = html.fromstring(text).xpath('//pre/text()')
        for article in target_article_list:
            target_article += article
        # 邮件
        email_pattern = re.compile(r'[a-zA-Z0-9]+[.]?[\w]+@[0-9a-zA-z-]+[.][a-zA-z]+[.]?[a-zA-Z]*[.]?[a-zA-Z]*')
        try:
            article_email = re.search(email_pattern, target_article).group()
            print('$' * 5 + "邮件格式匹配成功" + '$' * 5)
        except AttributeError:
            print('-'*5 + "邮件格式匹配错误" + '-'*5)
            self.wrong_article_link.append(article_link)
            pass
        if not article_email:
            return   # 邮件为空，直接结束方法
        # 标题
        try:
            article_title = target_article.split('\n')[1].split(':')[1].strip()
            time_string = target_article.split('\n')[2]
        except TypeError:
            pass
        # 时间
        time_pattern = re.compile(r'[0-9]+')
        try:
            time_list = re.findall(time_pattern, time_string)
            if time_list[0] != "2017":
                sys.exit(0)
            if int(time_list[1]) <7 and int(time_list[2]) < 10:
                sys.exit(0)
            if len(time_list) >= 3:
                article_time = time_list[0] + '/' + time_list[1] + '/' + time_list[2] + " " + time_list[3] + ":" + \
                               time_list[
                                   4]
        except AttributeError:
            pass
        # 电话
        tel_pattern = re.compile(r'1\d{10}')
        try:
            article_tel = re.search(tel_pattern, target_article).group()
        except AttributeError:
            pass
        return article_email + ',' + article_title + ',' + article_time + ',' + article_tel

    def clear_same_email(self):
        """
        将一个页面中相同邮箱的帖子中，除去旧帖子，只保留最新的一个
        :return:
        """
        email_list = []
        index_list = []
        for post in self.temp_data:
            temp = post.split(',')
            if len(temp) >= 2:
                email_list.append(temp[0])
            else:
                email_list.append('')
        for i in range(0, len(email_list)):
            if email_list.index(email_list[i]) != i:
                index_list.append(i)
        index_list.reverse()
        if index_list:
            for n in index_list:
                del self.temp_data[n]
        return

    @staticmethod
    def new_file():
        """
        新建数据存储文件
        :return: 返回一个元组！第一个是数据存储文件名称，第二个是招聘信息不含email链接的文件名称
        """
        t_human = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        data_path = os.path.join(os.path.dirname(__file__), 'data/{}/'.format(t_human))
        if not os.path.exists(data_path):
            os.makedirs(data_path)
        data_file = os.path.join(data_path, 'data.txt')
        no_email_link_file = os.path.join(data_path, 'no_email_link.txt')
        return data_file, no_email_link_file

    def data_entry(self, text):
        """
        将爬取信息列表self.temp_data录入到text中
        :param text: 一个元组！包含数据存储文件名称，email匹配不成功文件名称
        :return:
        """
        # print(self.temp_data)
        try:
            with codecs.open(text[0], mode='a', encoding='utf-8') as f:
                for data in self.temp_data:
                    f.writelines(data + "\n")
            with codecs.open(text[1], mode='a', encoding='utf-8') as f:
                for link in self.wrong_article_link:
                    f.writelines(link + "\n")
        except UnicodeEncodeError:
            pass
        return

    def crawl(self, page_url, file, page_num=10):
        """
        爬虫程序！将各个函数联通起来
           page_num:最大爬去页面数
        :param page_url: 爬取页面地址
        :param file: 一个元组，含有数据存储文件名称、email匹配不成功链接文件名称
        :param page_num: 爬取网页数量，默认爬取10个
        :return:
        """
        total_job_link = 0  # 爬取的总招聘信息链接数量
        success_link = 0  # 含有email的招聘信息链接数量
        for i in range(0, page_num):
            print("*当前正在爬取的页面："+page_url)
            try:
                job_link = self.get_job_link(page_url)
                total_job_link += len(job_link)
                for link in job_link:
                    content = self.article_parse(link)
                    if content:
                        self.temp_data.append(content)
                        success_link += 1
                # self.temp_data列表长度达到10，就进行输出,然后清空列表
                if len(self.temp_data) >= 10:
                    self.clear_same_email()
                    self.data_entry(file)
                    self.temp_data = []
                    self.wrong_article_link = []
            except AttributeError:
                print("crawl出现错误，当前爬取页面为：")
                print(page_url)
                pass
            # page_url = self.get_next_page(page_url)
            page_url = re.sub(r'\d+', self.url_auto_minus, page_url)
        print('招聘信息总数：' + str(total_job_link))
        print('含有邮箱的招聘信息数目：' + str(success_link))
        if total_job_link:  # total_job_link不能为0
            success = success_link / total_job_link
        else:
            success = 0
        print('成功率：%.2f%%  :)' % (success * 100))
        return


def main():
    search = JobSearch()
    choice = input("请输入要爬取的BBS：就业信息（1） or 求职交流（2） \n")
    num = input("请输入要爬取的页数(默认5页）：\n")
    url = input("输入爬取页面url，或者 回车跳过选择默认")
    if int(num) <= 0 or not num.isdigit():
        print("对不起，您要求爬取的页数不符合要求！系统将默认爬取5页数据")
        num = 5
    else:
        num = int(num)

    if choice == "就业信息" or int(choice) == 1:
        print("*****就业信息正在爬取*****")
        search.base_url = "https://bbs.sjtu.edu.cn/bbsdoc?board=JobInfo"

    elif choice == "求职交流" or int(choice) == 2:
        print("*****求职交流正在爬取*****")
        search.base_url = "https://bbs.sjtu.edu.cn/bbsdoc?board=JobForum"

    else:
        print("请选择1 or 2")
        return
    if url:
        search.base_url = url
    else:
        pass

    search.crawl(search.base_url, search.new_file(), page_num=num)


if __name__ == '__main__':
    main()
