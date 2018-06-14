import requests
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.types import String
import sqlite3
from flask import Flask, session, redirect, url_for, escape, request, render_template, jsonify
import configparser
import logging

app = Flask(__name__)
Config = configparser.ConfigParser()

logging.basicConfig(format="%(asctime)s %(message)s",
                    datefmt="%d.%m.%Y %H:%M:%S")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# days since today to get tickets info
DAYS = 30


def setup_config():
    Config.read("config.ini")
    try:
        cfgfile = open("config.ini", 'r')
    except Exception as e:
        logger.info("Error: {}".format(e))
        logger.info("Creating config file")
        cfgfile = open("config.ini", 'w')
        Config.add_section('config')
        Config.set('config', 'api_key', "")
        Config.set('config', 'domain', "")

        Config.write(cfgfile)
        cfgfile.close()
        Config.read("config.ini")


def get_freshdesk():

    conn = sqlite3.connect("tickets.sqlite")
    cursor = conn.cursor()

    api_key = Config.get("config", "api_key")
    domain = Config.get("config", "domain")

    # api_key = "xIMlgSQNujg6Qt3Ja4Ur"
    # domain = "clconsult"
    password = "x"

    if api_key == "" or domain == "":
        return False
    # db = create_engine("sqlite:///tickets.db", echo=False)

    # Return the tickets that are new or opend & assigned to you
    # If you want to fetch all tickets remove the filter query param

    days_to_subtract = DAYS

    d = datetime.today() - timedelta(days=days_to_subtract)

    p1 = requests.get("https://" + domain + ".freshdesk.com/api/v2/tickets?updated_since=" + d.strftime("%Y-%m-%dT%H:%M:%SZ")
                      + "&per_page=100", auth=(api_key, password))

    p2 = requests.get("https://" + domain + ".freshdesk.com/api/v2/tickets?updated_since=" + d.strftime("%Y-%m-%dT%H:%M:%SZ")
                      + "&per_page=100&page=2", auth=(api_key, password))
    # read tickets page 1
    df1 = pd.read_json(p1.text)
    # read tickets page 2
    df2 = pd.read_json(p2.text)
    # concat dataframes
    df = pd.concat([df1, df2])

    # get clients
    r = requests.get("https://" + domain+".freshdesk.com/api/v2/companies?per_page=100", auth=(api_key, password))

    # read clients
    dfc = pd.read_json(r.text)

    # merge tables in dataframe
    tickets = pd.merge(df, dfc, how='inner', on=None, left_on='company_id', right_on='id',
                       left_index=False, right_index=False, sort=True)

    cols = tickets.dtypes[tickets.dtypes == 'object'].index
    type_mapping = {col: String for col in cols}

    cols_to_keep = ['created_at_x', 'name', 'type', 'subject', 'source']

    # tickets[cols_to_keep].to_sql('tickets', db, if_exists='replace', index=False, dtype=type_mapping)
    tickets[cols_to_keep].to_sql('tickets', conn, if_exists='replace')

    return True


def get_db():
    conn = sqlite3.connect("tickets.sqlite")
    cursor = conn.cursor()
    sql = "select name,count(*) from tickets group by name order by count(*) desc"
    cursor.execute(sql)

    results = cursor.fetchall()

    return results


@app.route('/', methods=['POST', 'GET'])
def index1(chartid='chart_ID',  chart_width=1000):

    tickets = get_db()

    series = ""
    x = 0
    total = 0

    for row in tickets:
        if x == 0:
            series += "{name: '" + row[0] + "' ,y: " + str(row[1]) + ", sliced: true, selected: true }, "
        else:
            series += "{name: '" + row[0] + "' ,y: " + str(row[1]) + "}, "
        x += 1
        total += row[1]

    series = "[{name: 'Clients', colorByPoint: true, data: [" + series + "] }]"

    # chart = {"renderTo": chartid, "type": chart_type, "height": chart_height}

    mydate = datetime.today() - timedelta(days=30)
    mydate2 = datetime.today()

    title = "QTD de Chamados por cliente"
    subtitle = "Período: " + mydate.strftime("%d/%m/%y") + " até " \
               + mydate2.strftime("%d/%m/%y") + " Total: " + str(total)
    xAxis=""

    return render_template('chart.html', chartID=chartid, series=series, title=title,
                           xAxis=xAxis, yAxis="Commits", yAxis2="Commits", subtitle=subtitle,
                           chartwd=chart_width, chart="0")


if __name__ == '__main__':
    setup_config()
    get_freshdesk()
    app.run()
