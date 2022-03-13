import urllib.request, json
import datetime
import sendgrid
import os
from os.path import exists



BASE_DATA_FILE = 'base_data.json'

DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

MONTH = '08'
YEAR = '2022'

CAMPSITES = {
  '232493': 'Fish Creek, Glacier NP',
  '251869': 'Many Glacier, Glacier NP',
  '232492': 'St. Mary, Glacier NP',
  '234791': 'Devil Creek, NEAR Glacier NP',
  '247663': 'Signal Mountain, Teton NP',
  '247664': 'Jenny Lake, Teton NP',
  '247785': 'Lizard Creek, Teton NP',
  '258830': 'Colter Bay, Teton NP'
}

DATES_INTERESTED = [
  '2022-08-17T00:00:00Z',
  '2022-08-18T00:00:00Z',
  '2022-08-19T00:00:00Z',
  '2022-08-20T00:00:00Z',
  '2022-08-21T00:00:00Z',
  '2022-08-22T00:00:00Z',
  '2022-08-23T00:00:00Z',
  '2022-08-24T00:00:00Z',
  '2022-08-25T00:00:00Z',
  '2022-08-26T00:00:00Z',
  '2022-08-27T00:00:00Z',
  '2022-08-28T00:00:00Z',
  '2022-08-29T00:00:00Z',
]

def send_email(subject, text):
  sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
  data = {
    "personalizations": [
      {
        "to": [
          {
            "email": "lrc3233@gmail.com"
          }
        ],
        "subject": subject
      }
    ],
    "from": {
      "email": "lrc3233@gmail.com"
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
  with open(BASE_DATA_FILE) as json_file:
    data = json.load(json_file)
    return data


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

  write_base(export_data)
  return email_text



gather_data(CAMPSITES, DATES_INTERESTED)
# send_email('ballet on the 7th?', gather_data(CAMPSITES, DATES_INTERESTED))

