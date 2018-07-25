# Restartinator

### Overview

Restartinator is an automated power-cycler for your devices. It can monitor any
device that accepts TCP connections (for example one that serves web pages),
and will restart the device automatically if it is no longer reachable. This is
useful for devices that commonly lock up, such as routers, IP cameras, and
microcontroller projects. Email notifications can also optionally be sent.

In order to use Restartinator, you must have the device connected via a "smart
plug", which is used to switch power on and off. Currently, only the [TPLink
Kasa](https://www.tp-link.com/us/kasa-smart/kasa.html) series of smart plugs is
supported.

### Configuration

A JSON configuration file is used to specify the devices to monitor. The basic
layout of the file is as follows:

```
{
  "notifications": {
    "TYPE": {
      "PARAM1": "VALUE1",
      ...
    }
  },
  "devices": [
    {
      "PARAM1": "VALUE1",
      ...
    }
  ]
}
```

The `notifications` section only supports one type: `"email"`. This section
configures email notifications and accepts the following parameters:

* `smtp_host`: Hostname for SMTP server
* `smtp_user`: Username for SMTP server
* `smtp_password`: Password for SMTP server
* `use_ssl`: Set to 1 to use SSL to connect (optional, default = 0)
* `email_to`: Mailing list for notifications
* `email_from`: Sender address for notifications

The `devices` section contains a list of device configurations, each of which
accepts the following parameters:

* `name`: The display name, used for logging and notifications
* `host`: Hostname used for connections to check the device
* `port`: Port used for connections to check the device
* `plug_host`: Hostname for the smart plug that controls the device
* `boot_time`: The amount of time the device takes to restart, in seconds, from
  being power-cycled until it is ready to accept connections. This value
  depends on the type of device, an IP camera might take a minute or two to
  reboot for example. (optional, default = 300)
* `check_interval`: How often to check the device, in seconds. A few times per
  minute or less frequently is probably reasonable here, you don't want to
  flood the device with connections. (optional, default = 30)
* `retries`: Number of connection attempts to make before restarting the
  device (optional, default = 3)
* `cycle_time`: How long to wait, in seconds, between switching off the device
  and switching it on again. This again depends on the type of device, but the
  default of ten seconds should be enough for most devices to fully power down.
  (optional, default = 10)

### Installation

Installation is simple, just install the Python packages listed in
requirements.txt, create a config, and run Restartinator at boot time on a
reliable device.

For example, it can be installed in /opt and started with systemd. As root,
run:

```
pip3 install -r restartinator/requirements.txt
cp -R restartinator /opt
cp restartinator/sample.conf /etc/restartinator.conf
chmod 600 /etc/restartinator.conf
cat >/etc/systemd/system/restartinator.service <<<EOF
[Unit]
Description=restartinator

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/restartinator/restartinator.py /etc/restartinator.conf
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable restartinator
systemctl start restartinator
journalctl -u restartinator
```

### Todo

* Alternative monitoring methods: HTTP response code, ping, power usage (where
  supported by plug)
* Customizable notifications
* Scheduled reboot
* Support for more brands of smart plug
* Distributed monitoring?
