import urllib.request
import json
import datetime
# import sendgrid
import os
from os.path import exists
import psycopg2
import json
from sendgrid.helpers.mail import Mail, To
from sendgrid import SendGridAPIClient
import time
import requests
from dotenv import load_dotenv
load_dotenv()


DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

MONTH = '08'
YEAR = '2024'

CAMPSITES = {
    # '232781': 'Hume Lake, Sequoia NP',
    # '233363': 'Eshom, Sequoia NP',
    # '232782': 'Princess, NEAR Sequoia NP',
    # '232785': 'Stony Creek, NEAR Sequoia NP',
    # '256932': 'Big Meadows, NEAR Sequoia NP',
    # '10124502': 'Azalea, Sequoia NP',
    # '251363': 'Ten Mile, NEAR Sequoia NP',
    # '10044710': 'Atwell Mill, Sequoia NP, up windy road',
    # '249979': 'Potwisha, Sequoia NP',
    # '232461': 'Lodgepole, Sequoia NP',
    # '253917': 'Sentinel Campground, Sequoia NP',
    '10083831': 'Porcupine Flat, Yosemite NP',
    '232447': 'Upper pines, Yosemite NP',
    '232450': 'Lower Pines, Yosemite NP',
    '232449': 'North Pines, Yosemite NP',
    # '232254': 'Pinecrest, NEAR yosemite',
    '232451': 'Crane Flat, Yosemite NP',
    # '233772': 'Diamond O, NEAR yosemite',
    # '245552': 'Beardsley, NEAR yosemite',
    # '245558': 'Dardanelle, NEAR yosemite',
    # '10083845': 'Tamarack Flats, Yosemite NP',
    # '234752': 'Sunset, Sequoia NP',
}

DATES_INTERESTED = [
    # '2024-08-13T00:00:00Z',
    # '2024-08-14T00:00:00Z',
    # '2024-08-15T00:00:00Z',
    # '2024-08-16T00:00:00Z',
    '2024-08-17T00:00:00Z',
    # '2024-08-18T00:00:00Z',
    # '2024-08-19T00:00:00Z',
]

is_prod = os.environ.get('POSTGRES_HOST')
db_name = os.getenv('DB_NAME')
db_user = os.getenv('USER_NAME')
db_host = os.getenv('DB_HOST')
db_pw = os.getenv('POSTGRES_PW')

conn = psycopg2.connect(
    f"dbname={db_name} user={db_user} host={db_host} password={db_pw}")
cur = conn.cursor()


def send_slack_notif(message):
    slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    headers = {'Content-type': 'application/json'}
    data = {"text": message}
    response = requests.post(slack_webhook_url, headers=headers, json=data)


def read_base():
    cur.execute(
        'select availabilities from availabilities order by id desc limit 1;')
    record = cur.fetchone()
    if record:
        return json.loads(record[0])


def get_month_data_for_campsite(campground_id):
    try:
        with urllib.request.urlopen(
            f"https://www.recreation.gov/api/camps/availability/campground/{campground_id}/month?start_date={YEAR}-{MONTH}-01T00%3A00%3A00.000Z"
        ) as url:
            return json.loads(url.read().decode())['campsites']
    except Exception as e:
        try:
            error = e.read().decode()
            json.loads(error)
            raise Exception(f"Error: {error}")
        except:
            raise Exception(f"Error: {e}")


def compare_availabilities(base_availabilities, head_availabilities, campground_name, campground_id):
    new_availibilities = []
    for campsite_id in base_availabilities.keys():
        site_available_dates = []
        for date in DATES_INTERESTED:
            base_site_avail = base_availabilities[campsite_id]['availabilities'].get(
                date)
            head_site_avail = head_availabilities[campsite_id]['availabilities'].get(
                date)
            if base_site_avail != head_site_avail and head_site_avail == 'Available':
                site_available_dates.append(date)

        new_avail = Availability(
            site_available_dates, head_availabilities[campsite_id], campground_name, campground_id)

        if 'group' in new_avail.loop() or 'Group' in new_avail.loop():
            continue

        if len(site_available_dates) == 0:
            continue

        new_availibilities.append(new_avail)

    return new_availibilities


class Availability:
    def __init__(self, available_dates, site_data, campground_name, campground_id):
        self.available_dates = available_dates
        self.site_data = site_data
        self.campground_name = campground_name
        self.campground_id = campground_id

    def formatted_dates(self):
        datetimes = [datetime.datetime.strptime(
            date, '%Y-%m-%dT%H:%M:%SZ') for date in self.available_dates]
        return [datetime.strftime('%b %d') for datetime in datetimes]

    def site_id(self):
        return self.site_data['campsite_id']

    def site_no(self):
        return self.site_data['site']

    def loop(self):
        return self.site_data['loop']

    def url(self):
        start_date = self.available_dates[0]
        formatted_start_date = datetime.datetime.strptime(
            start_date, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
        return f"https://www.recreation.gov/camping/campsites/{self.site_id()}?startDate={formatted_start_date}"

    def email_line(self):
        dates = ', '.join(self.formatted_dates())
        return f" Campsite '{self.site_no()}' in loop {self.loop()} at {self.campground_name} is available for night of {dates}. {self.url()}"

# For single campsite data: https://ridb.recreation.gov/api/v1/campsites/10174601


def gather_data(campsites, dates_interested):
    email_text = []
    export_data = {}
    all_new_availabilities = []
    base_data = read_base()
    if base_data:
        for campground_id, campground_name in campsites.items():
            campsites_data = get_month_data_for_campsite(campground_id)
            export_data[campground_name] = campsites_data

            if (campground_name in base_data):
                new_availibilities = compare_availabilities(
                    base_data[campground_name], campsites_data, campground_name, campground_id)
                all_new_availabilities.extend(new_availibilities)
            else:
                base_data[campground_name] = campsites_data

            time.sleep(3)

    if len(all_new_availabilities) > 0:
        send_slack_notif(message='\n'.join(
            [avail.email_line() for avail in all_new_availabilities]))
    else:
        print('not sending email')

    cur.execute("INSERT INTO availabilities (availabilities) VALUES (%s)",
                (json.dumps(export_data),))
    conn.commit()
    return email_text


if __name__ == "__main__":
    gather_data(CAMPSITES, DATES_INTERESTED)
