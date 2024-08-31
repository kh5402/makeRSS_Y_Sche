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
from html import unescape as html_unescape
from urllib.parse import urlparse, parse_qs

# 既存のXMLファイルから情報取得
def get_existing_schedules(file_name):
    existing_schedules = set()
    try:
        tree = ET.parse(file_name)
        root = tree.getroot()
        for item in root.findall(".//item"):
            date = item.find('pubDate').text
            title = html_unescape(item.find('title').text)
            url = html_unescape(item.find('link').text)
            category = item.find('category').text
            start_time = item.find('start_time').text
            existing_schedules.add((date, title, url, category, start_time))
    except FileNotFoundError:
        print(f"File not found: {file_name}")
    except ET.ParseError:
        print(f"Error parsing XML file: {file_name}")
    return existing_schedules

# URLが可変する部分を除外してURLを確認する
def extract_url_part(url):
    parsed_url = urlparse(url)
    path = parsed_url.path.split("/")[-1]  # /103002 や /102232 を取得
    query = parse_qs(parsed_url.query)
    unique_part = f"{path}_{query.get('pri1', [''])[0]}_{query.get('wd00', [''])[0]}_{query.get('wd01', [''])[0]}_{query.get('wd02', [''])[0]}"
    return unique_part

async def main():
    # Discordのwebhook URLを環境変数から取得
    # webhook_url = os.environ['WEBHOOK_URL']

    # 既存のXMLファイルがあれば、その情報を取得
    existing_file = 'Y_Sche.xml'
    existing_schedules = get_existing_schedules(existing_file)

    # 後で重複チェックするときの為の一覧
    existing_schedules_check = {(date, extract_url_part(url)) for date, _, url, _, _ in existing_schedules}

    # 新規情報を保存するリスト
    new_schedules = []

    # 先月の1日から3ヶ月先までのyyyymmを生成
    start_date = (datetime.today().replace(day=1) - timedelta(days=1)).replace(day=1)
    end_date = start_date + timedelta(days=90)
    current_date = start_date

    try:
        # Pyppeteerでブラウザを開く
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
            defaultViewport=None,
            userDataDir='./user_data',
            logLevel='INFO'  # ログレベルを上げる
        )
        print(f"Chromium launched successfully: {browser}")

        while current_date <= end_date:
            yyyymm = current_date.strftime('%Y%m')
            url = f"https://www.nogizaka46.com/s/n46/media/list?dy={yyyymm}&members={{%22member%22:[%2255387%22]}}"
            print(f"Fetching URL: {url}")

            page = await browser.newPage()
            print(f"Page created: {page}")

            response = await page.goto(url)
            print(f"Navigated to URL: {url}, Status: {response.status}")

            # **1. ウェブサイトの構造変更の確認:**
            print(f"HTML Content: {await page.content()}")  # HTML コンテンツを出力

            # ページの読み込みが完了するまで待機
            await page.waitForNavigation()

            # ページのHTMLを取得
            html = await page.content()

            # BeautifulSoupで解析
            soup = BeautifulSoup(html, 'html.parser')

            # スケジュール情報の取得
            day_schedules = soup.find_all('div', class_='sc--day')

            # 各スケジュールの情報を取得
            for day_schedule in day_schedules:
                date_tag = day_schedule.find('div', class_='sc--day__hd js-pos a--tx')
                if date_tag is None:
                    continue
                date = f"{yyyymm[:4]}/{yyyymm[4:]}/{date_tag.find('p', class_='sc--day__d f--head').text}"

                schedule_links = day_schedule.find_all('a', class_='m--scone__a hv--op')

                for link in schedule_links:
                    title = re.search(r'<p class="m--scone__ttl">(.*?)</p>', str(link.find('p', class_='m--scone__ttl')))
                    if title:
                        title = title.group(1)
                    else:
                        title = ""
                    title_tag = link.find('p', class_='m--scone__ttl')
                    if title_tag:
                        title = title_tag.get_text()
                    title = html_unescape(str(title))

                    url = link['href']
                    url = html_unescape(str(url))

                    category = link.find('p', class_='m--scone__cat__name').text
                    start_time_tag = link.find('p', class_='m--scone__start')
                    start_time = start_time_tag.text if start_time_tag else ''

                    # 新規情報の確認 URLは変わるので日付とタイトルだけで確認
                    extracted_url = extract_url_part(url)
                    try:
                        datetime.strptime(date, "%Y/%m/%d")  # ここで日付のフォーマットをチェック
                        if (date, extracted_url) not in existing_schedules_check:
                            new_schedules.append((date, title, url, category, start_time))
                            print(f"新規情報を追加: {date, title, url, category, start_time}")  # ここで新規情報を出力
                    except ValueError:
                        print(f"新規情報の日付のフォーマットがおかしいから、このデータはスキップするで！日付: {date}")

            # 次の月へ
            current_date = (current_date + timedelta(days=31)).replace(day=1)
            if current_date.day != 1:  # 月の最初の日ではない場合
                current_date = (current_date + timedelta(days=1)).replace(day=1)  # 月を1つ進める

    except Exception as e:
        print(f"Error occurred during browser operation: {e}")

    finally:
        if browser:
            await browser.close()
            print("Chromium closed.")

    # ... (Discordへの通知, RSSフィードの生成, ファイルへの保存) ...

# 非同期関数を実行
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
