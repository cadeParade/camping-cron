import urllib.request, json
import datetime

import sendgrid
import os



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

email_text = []


for campsite_id, campsite_name in CAMPSITES.items():
  with urllib.request.urlopen(
    f"https://www.recreation.gov/api/camps/availability/campground/{campsite_id}/month?start_date={YEAR}-{MONTH}-01T00%3A00%3A00.000Z"
  ) as url:
    data = json.loads(url.read().decode())['campsites']

    dates_available_for_sites = {}
    for site_id, site_data in data.items():
      site_availabilities = site_data['availabilities']
      for date in DATES_INTERESTED:
        if site_availabilities.get(date) == 'Available':
          if site_id in dates_available_for_sites:
            dates_available_for_sites[site_id].append(date)
          else:
            dates_available_for_sites[site_id] = [date]

    for id, entry in dates_available_for_sites.items():
      site = data[id]['site']
      loop = data[id]['loop']
      site_url = f"https://www.recreation.gov/camping/campsites/{id}"
      dt_times = [datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ') for date in entry]
      formatted_times = [date.strftime('%b %d') for date in dt_times]
      line = (f"Campsite '{site}' in loop {loop} at {CAMPSITES[campsite_id]} is available for night of {formatted_times}. (<a href='{site_url}'>link</a>)")
      email_text.append(line)
        # print(availabilities[date])
    # import ipdb; ipdb.set_trace()
    # print(data)

print(email_text)
  # "Campsite [site (c095)] [(id ___)] at [campsite name] is available for night of ________ "


sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
data = {
  "personalizations": [
    {
      "to": [
        {
          "email": "lrc3233@gmail.com"
        }
      ],
      "subject": "New campground availibilities"
    }
  ],
  "from": {
    "email": "lrc3233@gmail.com"
  },
  "content": [
    {
      "type": "text/plain",
      "value": '\n'.join(email_text)
    }
  ]
}
response = sg.client.mail.send.post(request_body=data)
print(response.status_code)
print(response.body)
print(response.headers)
