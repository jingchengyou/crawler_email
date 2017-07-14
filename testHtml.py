import codecs
import requests
from bs4 import BeautifulSoup

resp = requests.get('http://www.newsmth.net/nForum/board/Career_Campus?ajax&p=1')
text = BeautifulSoup(resp.text, 'lxml')
with codecs.open('look.html', mode='w+', encoding='utf-8') as f:
    f.write(text.prettify())
