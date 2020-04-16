"""
    Send SMA values influxdb

    2018-12-28 Tommi2Day

    Configuration:
    pip3 install influxdb datetime

    [SMA-EM]
    # serials of sma-ems the daemon should take notice
    # seperated by space
    serials=30028xxx
    # features could filter serials to, but wouldn't see serials if these serials was not defines in SMA-EM serials
    # list of features to load/run
    features=influxdb

    [FEATURE-influxdb]
    # symcon
    host=influxdb
    port=8086
    db=SMA
    measurement=SMAEM
    timeout=5
    user=
    password=
    fields=pconsume,psupply,p1consume,p2consume,p3consume,p1supply,p2supply,p3supply

    # How frequently to send updates over (defaults to 20 sec)
    min_update=30

    debug=0
    pvmeasurement=SMAWR
    pvvields=AC Power,AC Voltage,grid frequency,DC Power,DC input voltage,daily yield,total yield


"""

import urllib.request,urllib.error
import json
import time
import platform
import datetime
from influxdb import InfluxDBClient
from influxdb.client import InfluxDBClientError


influx_last_update = 0
influx_debug=0

def run(emparts,config):
    global influx_last_update
    global influx_debug

    # Only update every X seconds
    if time.time() < influx_last_update + int(config.get('min_update', 20)):
        if (influx_debug > 1):
            print("InfluxDB: data skipping")
        return

    # db connect
    db = config.get('db', 'SMA')
    host = config.get('host', 'influxdb')
    port = int(config.get('port', 8086))
    ssl = bool(config.get('ssl', 'false'))
    timeout = int(config.get('timeout', 5))
    user = config.get('user', None)
    password = config.get('password',None )
    mesurement= config.get('measurement','SMAEM' )
    fields = config.get('fields', 'pconsume,psupply')
    pvfields=eval(config.get('pvfields'))
    influx=None
    #connect to db, create one if needed
    try:
        influx = InfluxDBClient(host=host, port=port, ssl=ssl, verify_ssl=ssl, username=user, password=password, timeout=timeout)
        dbs = influx.get_list_database()
        if influx_debug>1:
            print(dbs)
        if not {"name": db} in dbs:
            print(db + ' not in list, create')
            influx.create_database(db)

        influx.switch_database(db)
        if influx_debug > 1:
            print("Influxdb connected to '%s' @ '%s'(%s)" % (str(user), host, db))

    except InfluxDBClientError as e:
        if influx_debug > 0:
            print("InfluxDB:  Connect Error to '%s' @ '%s'(%s)" % (str(user), host, db))
            print(format(e))
        return
    except Exception as e:
        if influx_debug > 0:
            print("InfluxDB: Error while connecting to '%s' @ '%s'(%s)" % (str(user), host, db))
            print(e)
        return





    myhostname = platform.node()
    influx_last_update = time.time()
    now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    #last aupdate
    influx_last_update = time.time()
    serial = emparts['serial']

    #data fields
    data={}
    for f in fields.split(','):
        data[f] = emparts[f]

    # data point
    influx_data = {}
    influx_data['measurement'] = mesurement
    influx_data['time'] = now
    influx_data['tags']={}
    influx_data['tags']["serial"]=serial
    pvpower=0
    pbattery=0
    try:
        from features.pvdata import pv_data

        for inv in pv_data:
            if inv.get("DeviceClass") == "Solar Inverter":
                pvpower += inv.get("AC Power")
            elif inv.get("DeviceClass") == "Battery Inverter":
                pbattery += inv.get("AC Power")

        if pvpower is None: pvpower=0
        pconsume = emparts.get('pconsume', 0)
        psupply = emparts.get('psupply', 0)
        pusage = pvpower + pconsume - psupply
        data['pbattery'] = pbattery
        data['pvpower'] = pvpower
        data['pusage'] = pusage
    except:
        pass

    influx_data['fields'] = data
    points = [influx_data]

    # send it
    try:
        influx.write_points(points, time_precision='s', protocol='json')
    except InfluxDBClientError as e:
        if influx_debug > 0:
            print('InfluxDBError: %s' %(format(e)))
            print("InfluxDB failed data:" + format(time.strftime("%H:%M:%S", time.localtime(influx_last_update))),
                  format(points))
        pass

    else:
        if influx_debug > 0:
            print("InfluxDB: em data published %s:%s" % (
            format(time.strftime("%H:%M:%S", time.localtime(influx_last_update))), format(points)))

    pvmeasurement=config.get('pvmeasurement')
    if None in [pvfields,pv_data,pvmeasurement]: return

    influx_data = []
    datapoint={
            'measurement': pvmeasurement,
            'time': now,
            'tags': {},
            'fields': {}
            }
    taglist = ['serial', 'DeviceID', 'Device Name']
    tags = {}
    fields = {}
    for inv in pv_data:
        for t in taglist:
            tags[t] = inv.get(t)
            inv.pop(t)

        # only if we have values
        if pvpower is not None:
            for f in pvfields:
                fields[f] = inv.get(f)
        datapoint['tags'] = tags.copy()
        datapoint['fields'] = fields.copy()
        influx_data.append(datapoint.copy())

    points=influx_data

    #send it
    try:
        influx.write_points(points, time_precision='s', protocol='json')
    except InfluxDBClientError as e:
        if influx_debug > 0:
            print('InfluxDBError: %s' % (format(e)))
            print("InfluxDB failed pv data:"+format(time.strftime("%H:%M:%S", time.localtime(influx_last_update))), format(points))
        pass

    else:
        if influx_debug > 0:
            print("InfluxDB: pv data published %s:%s" % (format(time.strftime("%H:%M:%S", time.localtime(influx_last_update))),format(points)))


def stopping(emparts,config):
    pass

def config(config):
    global influx_debug
    influx_debug=int(config.get('debug', 0))
    print('influxdb: feature enabled')
