#!/usr/bin/env python
import argparse
import astral
import datetime
import json
import io
import logging
import picamera
import sched
import time
import tempfile
import tweepy

logger = logging.getLogger(__name__)
scheduler = sched.scheduler(time.time, time.sleep)
locinfo = ('San Francisco', 'California', 37.765712, -122.446216, 'America/Los_Angeles', 100)
events_of_interest = ('dawn', 'sunrise', 'noon', 'sunset', 'dusk')
secrets = json.load(open('.secrets.json', 'r'))
auth = tweepy.OAuthHandler(secrets['consumer_key'], secrets['consumer_secret'])
auth.set_access_token(secrets['access_token'], secrets['access_secret'])
twitter_api = tweepy.API(auth)

def delay_from_now(ts):
    return max(0, ts - time.time())

def schedule_event(utc_time_secs, priority, fn, argtuple):
    logging.info('scheduling event %s (args: %s) at %d', fn, argtuple, utc_time_secs)
    scheduler.enter(delay_from_now(utc_time_secs), priority, fn, argtuple)

def post_tweet(image_path, event):
    twitter_api.update_with_media(image_path, status='Another beautiful %s' % event)

def capture_image(event):
    logging.info('taking a picture of: %s', event)
    with picamera.PiCamera() as camera:
        camera.resolution = (1280, 720)
        camera.start_preview()
        # camera.exposure_compensation = 2
        #camera.exposure_mode = 'spotlight'
        camera.meter_mode = 'matrix'
        #camera.image_effect = 'gpen'
        # Give the camera some time to adjust to conditions
        time.sleep(1)
        with tempfile.NamedTemporaryFile(suffix='.png') as fp:
            camera.capture(fp.name, format='png')
            camera.stop_preview()
            post_tweet(fp.name, event)

def schedule_events(test_mode=False):
    location = astral.Location(info=locinfo)
    logging.info('scheduling events for: %s', location)

    schedule_date = datetime.datetime.today()
    while scheduler.empty():
        suntimes = location.sun(local=True, date=schedule_date)
        for i, event in enumerate(events_of_interest):
            event_date = suntimes[event]
            utc_time_secs = time.mktime(event_date.utctimetuple())
            if (utc_time_secs < time.time()):
                logging.info('skipping event before now')
                continue
            if test_mode:
                utc_time_secs = time.time() + 3 + i
            schedule_event(utc_time_secs, 1, capture_image, (event,))
        schedule_date += datetime.timedelta(days=1)

    # Schedule a re-run of this function 1 second after the last event.
    shortly_after = scheduler.queue[-1].time + 1
    schedule_event(shortly_after, 2, schedule_events, (test_mode,))

def main():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('requests').setLevel(logging.CRITICAL)
    logging.getLogger('tweepy.cache').setLevel(logging.CRITICAL)
    logging.getLogger('tweepy.binder').setLevel(logging.CRITICAL)
    
    parser = argparse.ArgumentParser(description='Take some pictures of the sun')
    parser.add_argument('-t', '--testmode', action='store_true', help='runs the program in test mode')
    args = parser.parse_args()
    schedule_events(test_mode=args.testmode)
    scheduler.run()
    
if __name__ == '__main__':
    main()
