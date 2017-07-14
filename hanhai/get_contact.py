#! /usr/bin/env python3
# coding:utf-8

import time
from pymongo import MongoClient

def main():
    db = MongoClient().get_database('hanhai')
    col = db.get_collection('articles')

    cursor = col.find({"status":"fetched"})
    total = cursor.count()
    i = 1
    emails = []
    for doc in cursor:
        contact = doc['contact']
        email = contact.get('email')
        if email == None:
            continue
        else:
            email = email.split()[0]

        if email in emails:
            continue
        else:
            emails.append(email)

        phone = contact.get('phone')

        title = doc['title'].replace(' ', '')

        publish_time = doc['publishTime']

        href = doc['href']

        data_str = '{}\t{}\t{}\t{}\n'.format(
            email, phone, publish_time, title
        )
        print(data_str)
        print('{} / {}, {:.2f}%'.format(i, total, 100*i/total))
        i += 1
        with open('./format_data.txt', 'a+') as f:
            f.write(data_str)

if __name__ == '__main__':
    main()
