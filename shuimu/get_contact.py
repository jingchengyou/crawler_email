#! /usr/bin/env python3
# coding:utf-8

import time
from pymongo import MongoClient

def main():
    db = MongoClient().get_database('shuimu')
    col = db.get_collection('articles')

    cursor = col.find({'status': 'fetched'})
    total = cursor.count()
    i = 1
    exist_emails = []
    for doc in cursor:
        contact = doc['contact']

        # email
        emails = contact.get('email')
        if emails:
            emails = [email.split()[0] for email in emails if email]
            remaining_emails = []
            for email in emails:
                if email in exist_emails:
                    continue
                else:
                    remaining_emails.append(email)
                    exist_emails.append(email)
        else:
            continue
        if remaining_emails:
            email_str = '/'.join(remaining_emails)
        else:
            continue

        # phone
        phones = contact.get('phone')
        if phones:
            phone_str = '/'.join(phones)
        else:
            phone_str = None

        # title
        title = doc['title'].replace(' ', '').replace('\n', ',').replace('\r', '')

        # publish_time
        publish_time = doc['publishTime']

        # href
        href = doc['href']

        # type
        if 'Career_Campus' in href:
            type = '校园招聘'
        elif 'Career_Upgrade' in href:
            type = '社会招聘'
        elif 'ExecutiveSearch' in href:
            type = '猎头招聘'

        data_str = '{}\t{}\t{}\t{}\t{}\n'.format(
            email_str, phone_str, publish_time, title, type
        )
        print(data_str)
        print('{} / {}, {:.2f}%'.format(i, total, 100*i/total))
        i += 1
        with open('./format_data.txt', 'a+') as f:
            f.write(data_str)

if __name__ == '__main__':
    main()
