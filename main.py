#!/usr/bin/python
# -*- coding: UTF-8 -*-
import requests
from bs4 import BeautifulSoup as bs
import pandas as pd
from datetime import datetime
import pymysql
import re
import json

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    with open('config.json', 'r') as f:
        config = json.load(f)

    home_url = 'https://boottent.sayun.studio/camps'
    page = requests.get(home_url)
    soup = bs(page.text, 'html.parser')

    pattern = '/_next/static/[\w-]+/\w+Manifest.js'
    tmp_list = soup.find_all('script')
    match = ''
    for tmp in tmp_list:
        if re.match(pattern=pattern, string=tmp['src']) is not None:
            match = re.match(pattern=pattern, string=tmp['src']).string
            break
    code = match.split('/')[3]

    request_url = f'https://boottent.sayun.studio/_next/data/{code}/camps.json'
    page = requests.get(request_url)

    data = page.json()

    item_keys = ['brandName', 'company', 'batchName', 'title', 'keywords', 'tags', 'regDate', 'regEndDate', 'startDate',
                 'endDate', 'batchId', 'campId']

    df_data = pd.DataFrame.from_dict(data['pageProps']['data'])

    df_data = df_data[item_keys]

    df_data['srcLink'] = df_data['campId'] + "_" + df_data['batchId']
    df_data.drop(['batchId', 'campId'], axis=1, inplace=True)

    df_data.columns = ['bootcamp_name', 'company', 'generation', 'title', 'tech_stack', 'field', 'reg_start_date',
                       'reg_end_date', 'camp_start_date', 'camp_end_date', 'src_link']

    df_data['apply_link'] = None

    """ 필요한 리스트 거르기"""
    df_data = df_data[df_data['reg_end_date'] > datetime.now().strftime('%Y-%m-%d %H:%M:%S')].sort_values(
        'reg_end_date')

    db = pymysql.connect(host=config['MYSQL']['HOST'], port=config['MYSQL']['PORT'], user=config['MYSQL']['USER'], passwd=config['MYSQL']['PASSWORD'], db=config['MYSQL']['DB'], charset=config['MYSQL']['CHARSET'])

    bootcamp_list_sql = """
        select name, id from bootcamp where status='WAITING' and type='BOOTCAMP';
    """

    field_list_sql = """
        select name, id from bootcamp where status='WAITING' and type='DEV_FIELD';
    """

    try:
        cursor = db.cursor()
        cursor.execute(bootcamp_list_sql)
        result = cursor.fetchall()

    finally:
        db.close()

    for bootcamp, id in result:

        bootcamp_series = df_data[
            df_data['bootcamp_name'].replace(r"\s", "", regex=True).str.contains(re.sub(r"\s", "", bootcamp.upper()),
                                                                                 case=False)]

        if bootcamp_series.empty:
            break

        for index, row in bootcamp_series.iterrows():
            url_response = requests.request(method='GET',
                                            url=f"https://boottent.sayun.studio/camps/{row['src_link']}")
            url_soup = bs(url_response.text, 'html.parser')

            dom = url_soup.select_one(
                '#__next > div > section > main > div.camp_container__3lIZ3.container > div:nth-child(1) > div.camp_layer1__y_wsY > div')

            asdf = url_soup.select_one('#__NEXT_DATA__')

            asdf_json = json.loads(asdf.text)
            apply_url = asdf_json['props']['pageProps']['camp']['campUrl']

            origin_data = df_data.iloc[index].squeeze()
            origin_data.drop('src_link', inplace=True)
            origin_data['apply_link'] = apply_url
            origin_data['id'] = id
            origin_data['reg_start_date'] = datetime.strptime(origin_data['reg_start_date'],
                                                              '%Y-%m-%d %H:%M').date().strftime('%Y-%m-%d')
            origin_data['reg_end_date'] = datetime.strptime(origin_data['reg_end_date'],
                                                            '%Y-%m-%d %H:%M').date().strftime('%Y-%m-%d')

            print(origin_data)

            headers = {'Content-Type': 'application/json; charset=utf-8'}

            res = requests.request(method='POST',
                                   headers=headers,
                                   url='http://'+config['SERVER']['HOST']+':'+config['SERVER']['PORT']+'/api/v1/mails/subscribes',
                                   data=origin_data.to_json())
