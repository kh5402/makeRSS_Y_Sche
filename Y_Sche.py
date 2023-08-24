from bs4 import BeautifulSoup
from pyppeteer import launch
import re
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
from datetime import datetime
import xml.dom.minidom

# 3ヶ月先までの日付でURLを生成
start_date = datetime.today().replace(day=1)
end_date = datetime.today() + timedelta(days=90)
current_date = start_date
schedules = []
while current_date <= end_date:
    yyyymm = current_date.strftime('%Y%m')
    url = f"https://www.nogizaka46.com/s/n46/media/list?dy={yyyymm}&members={{%22member%22:[%2255387%22]}}"
    browser = await launch()
    page = await browser.newPage()
    await page.goto(url)
    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    day_schedules = soup.find_all('div', class_='sc--day')
    for day_schedule in day_schedules:
        date_tag = day_schedule.find('div', class_='sc--day__hd js-pos a--tx')
        if date_tag is None:
            continue
        date = f"{yyyymm[:4]}/{yyyymm[4:]}/{date_tag.find('p', class_='sc--day__d f--head').text}"
        schedule_links = day_schedule.find_all('a', class_='m--scone__a hv--op')
        for link in schedule_links:
            title = re.search(r'<!--wovn-src:(.*?)-->', str(link.find('p', class_='m--scone__ttl'))).group(1)
            url = link['href']
            schedules.append((date, title, url))
    current_date += timedelta(days=30)

# 日付の降順にソート
schedules.sort(key=lambda x: datetime.strptime(x[0], "%Y/%m/%d"), reverse=True)

# RSSフィードを生成
rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")
SubElement(channel, "title").text = "弓木奈緒のスケジュール"
SubElement(channel, "description").text = ""
SubElement(channel, "link").text = ""
for date, title, url in schedules:
    item = SubElement(channel, "item")
    SubElement(item, "title").text = title
    SubElement(item, "link").text = url
    SubElement(item, "pubDate").text = date
xml_str = xml.dom.minidom.parseString(tostring(rss)).toprettyxml(indent="   ")

# ファイルに保存
with open('Y_Sche.xml', 'w', encoding='utf-8') as f:
    f.write(xml_str)
