import urllib.request, json
import datetime
import sendgrid
import os
from os.path import exists
import psycopg2
import json

# CREATE TABLE availabilities (id serial PRIMARY KEY, availabilities TEXT);

BASE_DATA_FILE = 'base_data.json'

DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

MONTH = '08'
YEAR = '2022'

CAMPSITES = {
  '232493': 'Fish Creek, Glacier NP',
  '251869': 'Many Glacier, Glacier NP',
  '232492': 'St. Mary, Glacier NP',
  '234791': 'Devil Creek, NEAR Glacier NP',
  # '247663': 'Signal Mountain, Teton NP',
  # '247664': 'Jenny Lake, Teton NP',
  # '247785': 'Lizard Creek, Teton NP',
  # '258830': 'Colter Bay, Teton NP'
}

DATES_INTERESTED = [
  '2022-08-28T00:00:00Z',
]

db_host = os.environ.get('POSTGRES_HOST', 'oregon-postgres.render.com')
db_pw = os.environ.get('POSTGRES_PW')
conn = psycopg2.connect(f"dbname=camping_availability_3g5n user=camping_availability_user host={db_host} password={db_pw}")
cur = conn.cursor()

def send_email(subject, text):
  sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
  data = {
    "personalizations": [
      {
        "to": [
          {
            "email": os.environ.get('EMAIL_ADDRESS')
          }
        ],
        "subject": subject
      }
    ],
    "from": {
      "email": os.environ.get('EMAIL_ADDRESS')
    },
    "content": [
      {
        "type": "text/plain",
        "value": text
      }
    ]
  }
  sg.client.mail.send.post(request_body=data)


def write_base(data):
  with open(BASE_DATA_FILE, 'w') as outfile:
    json.dump(data, outfile)


def read_base():
  cur.execute('select availabilities from availabilities order by id desc limit 1;')
  record = cur.fetchone();
  if record:
    return json.loads(record[0])


def get_month_data_for_campsite(campground_id):
  with urllib.request.urlopen(
    f"https://www.recreation.gov/api/camps/availability/campground/{campground_id}/month?start_date={YEAR}-{MONTH}-01T00%3A00%3A00.000Z"
  ) as url:
    return json.loads(url.read().decode())['campsites']


def compare_availabilities(base_availabilities, head_availabilities, campground_name, campground_id):
  new_availibilities = []
  for campsite_id in base_availabilities.keys():
    site_available_dates = []
    for date in DATES_INTERESTED:
      base_site_avail = base_availabilities[campsite_id]['availabilities'].get(date)
      head_site_avail = head_availabilities[campsite_id]['availabilities'].get(date)

      if base_site_avail != head_site_avail and head_site_avail == 'Available':
        site_available_dates.append(date)

    new_avail = Availability(site_available_dates, head_availabilities[campsite_id], campground_name, campground_id)
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
    datetimes = [datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ') for date in self.available_dates]
    return [datetime.strftime('%b %d') for datetime in datetimes]

  def site_id(self):
    return self.site_data['campsite_id']

  def site_no(self):
    return self.site_data['site']

  def loop(self):
    return self.site_data['loop']

  def url(self):
    return f"https://www.recreation.gov/camping/campsites/{self.site_id()}"

  def email_line(self):
    dates = ', '.join(self.formatted_dates())
    return f"Campsite '{self.site_no()}' in loop {self.loop()} at {self.campground_name} is available for night of {dates}. {self.url()}"





def gather_data(campsites, dates_interested):
  email_text = []
  export_data = {}
  all_new_availabilities = []

  base_data = read_base()

  if base_data:
    for campground_id, campground_name in CAMPSITES.items():
      campsites_data = get_month_data_for_campsite(campground_id)
      export_data[campground_name] = campsites_data

      dates_available_for_sites = {}

      new_availibilities = compare_availabilities(base_data[campground_name], campsites_data, campground_name, campground_id)
      all_new_availabilities.extend(new_availibilities)


  if len(all_new_availabilities) > 0:
    send_email('new camping availabilites', '\n'.join([avail.email_line() for avail in all_new_availabilities]))
  else:
    print('not sending email')

  cur.execute("INSERT INTO availabilities (availabilities) VALUES (%s)", (json.dumps(export_data),))
  conn.commit()
  return email_text



gather_data(CAMPSITES, DATES_INTERESTED)
# send_email('ballet on the 7th?', gather_data(CAMPSITES, DATES_INTERESTED))

