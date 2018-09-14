#!/usr/bin/env python3

import argparse
import collections
import enum
import email.mime.text
import json
import pyHS100
import smtplib
import socket
import sys
import time
import threading

class State(enum.Enum):
    AWAKE         = enum.auto()  # Device is up, keep checking
    POWERING_OFF  = enum.auto()  # Waiting for switch to power off
    POWER_OFF     = enum.auto()  # Switch is off
    POWERING_ON   = enum.auto()  # Waiting for switch to power on
    REBOOTING     = enum.auto()  # Waiting for device to power on

class NotifyState(enum.Enum):
    ONLINE  = enum.auto()
    OFFLINE = enum.auto()

EmailSettings = collections.namedtuple('EmailSettings',
                                       ['smtp_host', 'smtp_username',
                                        'smtp_password', 'use_ssl',
                                        'email_from', 'email_to'])

Device = collections.namedtuple('Device',
	                        ['name', 'host', 'port', 'plug_host',
                                 'boot_time', 'check_interval', 'retries',
                                 'cycle_time'])

SOCKET_TIMEOUT = 5

def log(template, device, **kwargs):
    kwargs['device'] = device
    print(('[{device.name}] '+template).format(**kwargs), file = sys.stderr)

def notify(config, template, device, **kwargs):
    if 'email' in config:
        try:
            email_cfg = config['email']
            kwargs['device'] = device

            message = email.mime.text.MIMEText('')
            message['Subject'] = '[restartinator] ' + template.format(**kwargs)
            message['From'] = email_cfg.email_from
            message['To'] = email_cfg.email_to

            sender = smtplib.SMTP_SSL if email_cfg.use_ssl else smtplib.SMTP

            smtp = sender(email_cfg.smtp_host, timeout = SOCKET_TIMEOUT)
            smtp.login(email_cfg.smtp_username,
                       email_cfg.smtp_password)
            smtp.send_message(message)
            smtp.quit()
        except Exception as e:
            log('Failed to send notification: {exception}',
                device = device,
                exception = e)

def monitorDevice(config, device):
    try:
        state = State.AWAKE
        next_state = state
        retries = 0
        notify_state = NotifyState.ONLINE

        while True:
            previous_state = state
            state = next_state

            if state == State.AWAKE:
                try:
                    host = socket.gethostbyname(device.host)
                    socket.create_connection((host, device.port),
                                             SOCKET_TIMEOUT).close()

                    if notify_state != NotifyState.ONLINE:
                        notify_state = NotifyState.ONLINE
                        notify(config,
                               '{device.name} is ONLINE',
                               device = device)

                    if previous_state != state.AWAKE or retries > 0:
                        log('Device is now up', device = device)

                    retries = 0
                except (socket.timeout, socket.error, ConnectionError):
                    log('No response, attempt {attempt}/{device.retries}',
                        device = device,
                        attempt = retries + 1)

                    retries = retries + 1
                    if retries >= device.retries:
                        if notify_state != NotifyState.OFFLINE:
                            notify_state = NotifyState.OFFLINE
                            notify(config,
                                   '{device.name} is OFFLINE',
                                   device = device)
                        next_state = State.POWERING_OFF
                        continue

                time.sleep(device.check_interval)

            elif state == State.POWERING_OFF:
                try:
                    host = socket.gethostbyname(device.plug_host)
                    pyHS100.SmartPlug(host).turn_off()
                    log('Powered off', device = device)
                    next_state = State.POWER_OFF
                except (pyHS100.SmartDeviceException, socket.error) as e:
                    log('Failed to power off: {exception}',
                        device = device,
                        exception = e)

                    # Sleep, unless this was caused by a timeout
                    if not isinstance(e.__cause__, socket.timeout):
                        time.sleep(SOCKET_TIMEOUT)

            elif state == State.POWER_OFF:
                log('Waiting {device.cycle_time} seconds for power cycle',
                    device = device)
                time.sleep(device.cycle_time)
                next_state = State.POWERING_ON

            elif state == State.POWERING_ON:
                try:
                    host = socket.gethostbyname(device.plug_host)
                    pyHS100.SmartPlug(host).turn_on()
                    log('Powered on', device = device)
                    next_state = State.REBOOTING
                except (pyHS100.SmartDeviceException, socket.error) as e:
                    log('Failed to power on: {exception}',
                        device = device,
                        exception = e)

                    # Sleep, unless this was caused by a timeout
                    if not isinstance(e.__cause__, socket.timeout):
                        time.sleep(SOCKET_TIMEOUT)

            elif state == State.REBOOTING:
                log('Waiting {device.boot_time} seconds for reboot',
                    device = device)
                time.sleep(device.boot_time)
                next_state = State.AWAKE
                retries = 0

    except Exception as e:
        log('Got exception while monitoring: {exception}',
            device = device,
            exception = e)

if len(sys.argv) < 2:
    sys.exit(1)

input = json.load(open(sys.argv[1]))

config = {}
for key, entry in input.get('notifications', {}).items():
    if key == 'email':
        config['email'] = EmailSettings(
            smtp_host = entry['smtp_host'],
            smtp_username = entry['smtp_username'],
            smtp_password = entry['smtp_password'],
            use_ssl = entry.get('use_ssl', 0),
            email_from = entry['email_from'],
            email_to = entry['email_to'])

devices = []
for entry in input.get('devices', []):
   devices.append(
       Device(name = entry['name'],
              host = entry['host'],
              port = int(entry['port']),
              plug_host = entry['plug_host'],
              boot_time = int(entry.get('boot_time', 300)),
              check_interval = int(entry.get('check_interval', 30)),
              retries = int(entry.get('retries', 3)),
              cycle_time = int(entry.get('cycle_time', 10))))

threads = []
for device in devices:
    thread = threading.Thread(target = monitorDevice, args = [config, device])
    thread.start()

if len(devices) == 0:
    print('No devices to monitor', file = sys.stderr)
else:
    print('Monitoring {} device(s)'.format(len(devices)),
          file = sys.stderr)

for thread in threads:
    thread.join()
