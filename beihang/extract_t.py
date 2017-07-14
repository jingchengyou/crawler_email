#! /usr/bin/env python3
# coding:utf-8

# from gevent import monkey
# monkey.patch_all()

# import gevent
import re
import time
from pymongo import MongoClient
from pprint import pprint

def main():
    db = MongoClient().get_database('beihang')
    col = db.get_collection('articles')

    total = col.count()
    i = 1
    while True:
        document = col.find_one({'status': 'done'})
        if not document:
           break
        try:
            id = document['id']
        except:
            print(document)
            _id = document['_id']
            col.find_one_and_update({'_id':_id}, {'$set':{'status': 'fail'}})
            continue
        try:
            text = document['comment']
            href = document['href']
        except:
            print(id)
            col.find_one_and_update(
                {'id': id},
                {'$set': {
                    'status': 'not_done'
                }}
            )
            continue
        contact = {}

        # phone
        tele_pattern = re.compile(r'0\d{2,3}-\d{7,8}|0\d{2,3}\d{7,8}|1[358]\d{9}|147\d{8}')
        t = re.search(tele_pattern, text)
        if t:
            contact['phone'] = t.group()

        # email
        control = True
        if control:
            email_pattern = r'([A-Z_a-z_0-9.-]{1,64}@[a-z0-9-]{1,200}.{1,5}[a-z]{1,6})'
            e = re.search(email_pattern, text)
            if e:
                contact['email'] = e.group(1)
                control = False
        
        if control:
            email_pattern = r'([A-Z_a-z_0-9.-]{1,64}#[a-z0-9-]{1,200}.{1,5}[a-z]{1,6})'
            e = re.search(email_pattern, text)
            if e:
                contact['email'] = e.group(1).replace('#', '@')
                print(e.group(1))
                control = False

        if control:
            email_pattern = r'([A-Z_a-z_0-9.-]{1,64} # [a-z0-9-]{1,200}.{1,5}[a-z]{1,6})'
            e = re.search(email_pattern, text)
            if e:
                contact['email'] = e.group(1).replace(' # ', '@')
                print(e.group(1))
                control = False

        if control:
            email_pattern = r'([A-Z_a-z_0-9.-]{1,64} At [a-z0-9-]{1,200}.{1,5}[a-z]{1,6})'
            e = re.search(email_pattern, text)
            if e:
                contact['email'] = e.group(1).replace(' At ', '@')
                print(e.group(1))
                control = False

        if control:
            email_pattern = r'([A-Z_a-z_0-9.-]{1,64}##[a-z0-9-]{1,200}.{1,5}[a-z]{1,6})'
            e = re.search(email_pattern, text)
            if e:
                contact['email'] = e.group(1).replace('##', '@')
                print(e.group(1))
                control = False

        if control:
            email_pattern = r'([A-Z_a-z_0-9.-]{1,64}#_#[a-z0-9-]{1,200}.{1,5}[a-z]{1,6})'
            e = re.search(email_pattern, text)
            if e:
                contact['email'] = e.group(1).replace('#_#', '@')
                print(e.group(1))
                control = False

        if control:
            email_pattern = r'([A-Z_a-z_0-9.-]{1,64} AT [a-z0-9-]{1,200}.{1,5}[a-z]{1,6})'
            e = re.search(email_pattern, text)
            if e:
                contact['email'] = e.group(1).replace(' AT ', '@')
                print(e.group(1))
                control = False

        if contact:
            # time.sleep(0.2)
            print('{} / {}, {:.2f}%'.format(i, total, 100*i/total))
            pprint(contact)
            # time.sleep(1) 
            col.find_one_and_update(
                {'id': id},
                {'$set': {
                    'contact': contact,
                    'status': 'fetched'
                }}
            )
        else:
            col.find_one_and_update(
                {'id': id},
                {'$set': {
                    'contact': {},
                    'status': 'fetched'
                }}
            )

        i += 1

if __name__ == '__main__':
    # greenlets = []
    # for i in range(10):
    #     greenlets.append(gevent.spawn(main))
    # gevent.joinall(greenlets)
    main()
