import os
import re
from bs4 import BeautifulSoup
from pyppeteer import launch
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
from datetime import datetime, timedelta
import xml.dom.minidom
import xml.etree.ElementTree as ET
import asyncio
import requests

# 既存のXMLファイルから日付とタイトルの組み合わせを取得
def get_existing_schedules(file_name):
    existing_schedules = set()
    tree = ET.parse(file_name)
    root = tree.getroot()
    for item in root.findall(".//item"):
        date = item.find('pubDate').text
        title = item.find('title').text
        existing_schedules.add((date, title))
    return existing_schedules


async def main():

    # Discordのwebhook URLを環境変数から取得
    webhook_url = os.environ['WEBHOOK_URL']

    # 既存のXMLファイルがあれば、その情報を取得
    existing_file = 'Y_Sche.xml'
    existing_schedules = get_existing_schedules(existing_file) if os.path.exists(existing_file) else set()

    # 新規情報を保存するリスト
    new_schedules = []

    
    # 当月から今日から3ヶ月先までのyyyymmを生成
    start_date = datetime.today().replace(day=1)
    end_date = datetime.today() + timedelta(days=90)
    current_date = start_date
    schedules = []
    while current_date <= end_date:
        
        yyyymm = current_date.strftime('%Y%m')
        url = f"https://www.nogizaka46.com/s/n46/media/list?dy={yyyymm}&members={{%22member%22:[%2255387%22]}}"
        
        # Pyppeteerでブラウザを開く
        print('# Pyppeteerでブラウザを開く')
        browser = await launch(
            executablePath='/usr/bin/chromium-browser',
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu'
            ],
        )
        
        page = await browser.newPage()
        await page.goto(url)

        # ページのHTMLを取得
        print('# ページのHTMLを取得')
        html = await page.content()
        
        # BeautifulSoupで解析
        print('# BeautifulSoupで解析')
        soup = BeautifulSoup(html, 'html.parser')

        # スケジュール情報の取得
        print('# スケジュール情報の取得')
        day_schedules = soup.find_all('div', class_='sc--day')

        # 各スケジュールの情報を取得
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
                
            # 新規情報の確認
            if (date, title) not in existing_schedules: 
                new_schedules.append((date, title, url))



        
                
        # 次の月へ        
        current_date = (current_date + timedelta(days=31)).replace(day=1)
        if current_date.day != 1: # 月の最初の日ではない場合
            current_date = (current_date + timedelta(days=1)).replace(day=1) # 月を1つ進める
    
    # 新規情報があれば、Discordへ通知
    if new_schedules:
        # Discordへの通知処理
        pass
        
    # 既存のスケジュール情報もリスト形式に変換
    existing_schedules_list = [(date, title, '') for date, title in existing_schedules]

    # 既存の情報と新規情報を合わせる
    all_schedules = existing_schedules_list + new_schedules

    # 日付の降順にソート
    all_schedules.sort(key=lambda x: datetime.strptime(x[0], "%Y/%m/%d"), reverse=True)

    # RSSフィードを生成
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = "弓木奈於のスケジュール"
    SubElement(channel, "description").text = ""
    SubElement(channel, "link").text = ""
    for date, title, url in all_schedules:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = title
        SubElement(item, "link").text = url
        SubElement(item, "pubDate").text = date
    xml_str = xml.dom.minidom.parseString(tostring(rss)).toprettyxml(indent="   ")

    # ファイルに保存
    with open(existing_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)

# 非同期関数を実行
asyncio.get_event_loop().run_until_complete(main())
