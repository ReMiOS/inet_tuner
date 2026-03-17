#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import html
import socket
import sqlite3
import requests
import datetime
import configparser
import argparse
import logging
from logging.handlers import RotatingFileHandler
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from lxml import etree

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import urllib3
urllib3.disable_warnings( urllib3.exceptions.InsecureRequestWarning )
urllib3.disable_warnings( urllib3.exceptions.HeaderParsingError )

# retry voor requests session
http_connect_timeout = 5
http_response_timeout = 10
requests_retries = 3
if requests_retries:
    from urllib3.util.retry import Retry

# ===========================
# CONFIG
# ===========================
script_file = os.path.abspath( __file__ )
progdir, filename = os.path.split( script_file )
script_name = os.path.splitext( filename )[0]
CONFIG_FILE = os.path.join( progdir, f'{script_name}.ini' )

# ==============================
# COMMAND LINE OPTIES
# ==============================
parser = argparse.ArgumentParser( description='Denon / Marantz internet stream tuner',formatter_class=argparse.RawTextHelpFormatter )
parser.add_argument( '-d', '--debug', default=False,  action='store_true', help='Extra debuggging info' )
parser.add_argument( '-s', '--screen', default=False,  action='store_true', help='Logging to console' )
args = parser.parse_args()

# ===========================
# LOGGING
# ===========================
logfile = os.path.join( progdir , f'{script_name}.log' )

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Rotating file handler
file_handler = RotatingFileHandler(
    logfile,
    maxBytes=5_000_000,  # 5 MB
    backupCount=5,
    encoding='utf-8'
)

file_handler.setLevel( logging.INFO )
formatter = logging.Formatter( '%(asctime)s - %(levelname)s - %(message)s' )
file_handler.setFormatter( formatter )

# Handler toevoegen
logger.addHandler( file_handler )
if args.screen:
    # Console handler
    console_handler = logging.StreamHandler( sys.stdout )
    console_handler.setLevel( logging.INFO )
    console_handler.setFormatter( formatter )

    logger.addHandler( console_handler )

# Test logging
logger.info( 'Applicatie gestart' )
        
# ===========================
# STREAMER ENDPOINTS
# ===========================
STREAMER_API_ENDPOINT = 'http://{}/goform/AppCommand.xml'
FAVORITE_API_ENDPOINT = 'http://{}/goform/formiPhoneAppFavorite_Call.xml?{}'
STATUS_API_ENDPOINT = 'http://{}/goform/formNetAudio_StatusXml.xml'
DEVICEINFO_API_ENDPOINT = 'http://{}/goform/Deviceinfo.xml'
NETINPUT_API_ENDPOINT = 'http://{}/goform/formiPhoneAppDirect.xml?SIIRADIO'
        
# ===========================
# DATABASE HELPERS
# ===========================
DB_FILE = 'stations.db'
API_ALL = 'https://all.api.radio-browser.info/json/stations'
API_LASTCHANGE = 'https://all.api.radio-browser.info/json/stations/lastchange'
API_TOPVOTE = 'https://all.api.radio-browser.info/json/stations/topvote'
API_TOPCLICK = 'https://all.api.radio-browser.info/json/stations/topclick'
API_LASTCLICK = 'https://all.api.radio-browser.info/json/stations/lastclick'
API_BY_UUID = 'https://all.api.radio-browser.info/json/stations/byuuid/{}'

# ===========================
# MIME TYPES
# ===========================
valid_mime_types = [

    # algemene audio
    'audio',
    'mpeg',
    'aac',
    'ogg',
    'stream',
    'audio/',
    
    # mp3 / mpeg
    'audio/mpeg',
    'audio/mp3',
    'audio/x-mpeg',
    'audio/mpeg3',

    # AAC
    'audio/aac',
    'audio/aacp',
    'audio/x-aac',

    # OGG
    'audio/ogg',
    'application/ogg',

    # Opus
    'audio/opus',

    # WAV
    'audio/wav',
    'audio/x-wav',

    # FLAC
    'audio/flac',
    'audio/x-flac',

    # WebM audio
    'audio/webm',

    # Icecast / Shoutcast
    'audio/aacp',
    'audio/x-scpls',
    'audio/x-mpegurl',

    # playlists
    'application/vnd.apple.mpegurl',
    'application/x-mpegurl',
    'application/mpegurl',
    'application/vnd.apple.mpegurl.audio',

    # HLS
    'application/x-mpegurl',
    'application/vnd.apple.mpegurl',

    # DASH
    'application/dash+xml',

    # generiek (sommige streams doen dit fout)
    'application/octet-stream',
    'binary/octet-stream',

    # sommige Icecast servers
    'audio/stream',
    'audio/x-stream',

    # edge cases
    'application/audio',
]

thread_local = {}

class Display: 
    def __init__( self, station=None ):
        self.station = station
        self.action = None
        self.value = None 
    def __repr__( self ):
        return str( self.__dict__ )
        
def send_xml( ip, xml_data ):
    session = get_session()
    headers = { 'Content-Type': 'application/json' }
    session.headers.update( headers )

    api_url = STREAMER_API_ENDPOINT.format( ip )
    response = api_call( session, api_url, 'POST', xml_data=xml_data )
    
    if response and isinstance( response, requests.Response ):
        status_code = response.status_code
        response_text = response.text
        try:
            parser = etree.XMLParser( recover=True )
            root = etree.fromstring( response.text.encode(), parser )
            cmd = root.findtext( './/cmd' )
            result = 'OK' if cmd and cmd.strip().upper() == 'OK' else 'MISLUKT'
        except etree.ParseError:
            result = 'ONGELDIGE XML'
    else:
        status_code = None
        result = 'MISLUKT'
        response_text = None
        
    return status_code, result, response_text

# ---- XML Building ----
def build_xml(cmd_name, **kwargs):

    # Bouwt een XML string met cmd_name en optionele extra velden.
    # kwargs = dictionary van extra tags en hun waarden
    # Zorgt voor correcte linefeeds.

    xml  = f'''<?xml version="1.0" encoding="utf-8"?>\n<tx>\n'''
    xml += f'''  <cmd id="1">{cmd_name}</cmd>\n'''
    
    for key, value in kwargs.items():
        if isinstance( value, str ):
            value = value.replace( '&', '&amp;' )  # ampersand escapen
        xml += f'''  <{key}>{value}</{key}>\n'''
    xml += '''</tx>'''
    return xml.encode( 'utf-8' )

def build_play_xml(title, url, mime):
    return build_xml( 'SetvTunerPlay', title=title, url=url, mime=mime )

def build_get_favorites_xml():
    return build_xml( 'GetSystemFavoriteList' )

def build_set_favorite_xml(num):
    return build_xml( 'SetAddToSystemFavorite', value=num )
    
def create_connection( db_file=DB_FILE ):
    conn = sqlite3.connect( db_file, timeout=30 )
    conn.execute( 'PRAGMA journal_mode=WAL;' )
    conn.execute( 'PRAGMA synchronous=NORMAL;' )
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-200000;")
    return conn

def get_session( retries = requests_retries ):    
    if 'session' not in thread_local:
        session = requests.Session()
        if retries:
            # ---- Retry strategy ----
            # timeout     = hoe lang ik wacht op antwoord
            # backoff     = hoe lang ik wacht vóór ik opnieuw probeer
            # retries     = hoe vaak ik het probeer

            backoff: float = 1.0    # 1s, 2s, 4s ( 1.0 x 2^n (n=0,1,2,3,4... bij retry=1,2,3,4,5....))
            retry_strategy = Retry(
                total=retries,
                connect=retries,
                read=retries,
                status=retries,
                backoff_factor=backoff,
                status_forcelist=[ 500, 502, 503, 504 ], # Bij deze HTTP statuscodes mag automatisch een retry gebeuren. 500=Internal Server Error /502=Bad Gateway / 503=Service Un>
                allowed_methods=[ 'GET', 'POST' ],
                raise_on_status=False,
            )

            adapter = requests.adapters.HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=10,
                pool_maxsize=10,
            )

            session.mount( 'http://', adapter )
            session.mount( 'https://', adapter )
        
        thread_local["session"] = session
    return thread_local["session"]
    
# ICD REST API aanroep
def rest_api( session, request_url, request_type, xml_data=None, timeout=5 ):
    try:
        # POST
        if request_type == 'POST':
            response = session.post( request_url, data=xml_data, timeout = timeout )
        # GET
        elif request_type == 'GET':
            response = session.get( request_url, timeout = timeout )
        # DELETE
        elif request_type == 'DELETE':
            response = session.delete( request_url, timeout = timeout )
        # onbekend
        else:
            return None, None, 'Unknown request type, check error log'
        # controleer HTTP status

        if isinstance( response, requests.Response ):
            response.raise_for_status()
            http_code = response.status_code
        else:
            return None, None

    except requests.exceptions.HTTPError as err:
        if args.debug:
            logging.error( f'''HTTP Error: {err}''' )
        http_code = err.response.status_code
        return err.response, http_code        # Return error
    except requests.exceptions.ConnectionError as err:
       if args.debug:
           logging.error( f'''Connection Error: {err}''' )
       return err, None       # Return error
    except requests.exceptions.Timeout as err:
        if args.debug:
            logging.error( f'''Timeout Error: {err}''' )
        logging.error( f'''ERR {err}''' )
        return err, None       # Return error
    except requests.exceptions.RequestException as err:
       if args.debug:
           logging.error( f'''General Error: {err}''' )
       return err, None       # Return error
       
    return response, http_code

# Controleer REST-API response
def check_response( response, http_code, req ):
    # Check status code
    
    if http_code == None:
        logging.error( f'''REST-API {req} request mislukt HTTP {http_code}''' )
    elif http_code >= 200 and http_code < 300:
        try:
            if response.headers.get( 'Content-Type' ) == 'application/json':
                json_data = {}
                json_data = response.json()
                logging.debug( 'REST-API {} request geslaagd'.format( req ) )
                return json_data
        except Exception as exc:
            if args.debug:
                logging.error( f'Exception ocurred: {str(exc)}', exc_info=True )
           
        logging.debug( 'REST-API {} request geslaagd'.format( req ) )
    else: # REST API error: 30-400 = HTTP Redirect request error / 400-500 = REST API request error / 500-600 = Internal server error
        logging.error( f'''REST-API {req} request mislukt HTTP {http_code}''' )
        return None
    return response
    
def api_call( api_session, url, methode, xml_data=None ):
    try:
        # Ophalen gegevens        
        response, http_code = rest_api( api_session, url, methode, xml_data=xml_data, timeout=http_response_timeout )
        json_data = check_response( response, http_code, methode )
       
        if json_data:
            return json_data
        elif isinstance( json_data, list ) and len( json_data ) ==0:
            logging.warning( f'⚠ API URL {url} bevat geen data' )
            return None
        else:
            logging.warning( f'⚠ API URL {url} is offline' )
            return None
        
    except Exception as exc:        
        logging.error( f'Exception ocurred: {str(exc)}', exc_info=True )
        return None
       
def get_station_from_db(database, station_id, legacy):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    
    cursor.execute( '''
        SELECT s.name, COALESCE(NULLIF(s.url_resolved, ''), s.url), c.Name
        FROM stations s
        LEFT JOIN codecs c ON s.IDCodec = c.IDCodec
        WHERE s.IDStation = ?
    ''', ( station_id, ) )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise Exception( 'Station niet gevonden' )
    
    name, url, codec = row
    if not url:
        raise Exception( 'Geen URL gevonden' )
        
    if legacy:
        url = url.replace( 'https://', 'http://' )
        if codec:
            codec = codec.replace( 'AAC+', 'AAC' )
    if not codec:
        codec = 'MP3'
    return name, url, codec
    
def get_or_create_id( cursor, table, name_field, value ):
    if not value:
        return None
    value = value.strip()
    id_columns = {
        'countries': 'IDCountry',
        'languages': 'IDLanguage',
        'codecs': 'IDCodec',
        'tags': 'IDTag'
    }
    id_column = id_columns[ table ]
    cursor.execute( f'SELECT {id_column} FROM {table} WHERE {name_field} = ?', ( value, ))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute( f'INSERT INTO {table} ({name_field}) VALUES (?)', ( value, ))
    return cursor.lastrowid

def insert_station( cursor, station ):
    stationuuid = station.get( 'stationuuid' )
    name = station.get( 'name', '' ).strip()
    url = station.get( 'url' )
    url_resolved = station.get( 'url_resolved' )
    homepage = station.get( 'homepage' )
    favicon = station.get( 'favicon' )
    votes = station.get( 'votes', 0 )
    bitrate = station.get( 'bitrate', 0 )
    lastcheckok = station.get( 'lastcheckok', 0 )
    lastcheckoktime = station.get( 'lastcheckoktime' )
    # lastchecktime = station.get( 'lastchecktime' )
    lastchecktime = datetime.datetime.now().strftime( "%Y-%m-%d %H:%M:%S" )
    geo_lat = station.get( 'geo_lat' )
    geo_long = station.get( 'geo_long' )
    id_country = get_or_create_id( cursor, 'countries', 'Name', station.get( 'country' ))
    id_language = get_or_create_id( cursor, 'languages', 'Name', station.get( 'language' ))
    id_codec = get_or_create_id( cursor, 'codecs', 'Name', station.get( 'codec' ))
    cursor.execute( """
        INSERT INTO stations (
            stationuuid, name, url, url_resolved, homepage, favicon,
            IDCountry, IDLanguage, votes, IDCodec, bitrate,
            lastcheckok, lastcheckoktime, lastchecktime, geo_lat, geo_long
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        stationuuid, name, url, url_resolved, homepage, favicon,
        id_country, id_language, votes, id_codec,
        bitrate, lastcheckok, lastcheckoktime, lastchecktime,
        geo_lat, geo_long
    ))
    if args.debug:
        app.log( f'Station {name} met URL {url} toegevoegd (uuid ={stationuuid})' )
    return cursor.lastrowid

def update_station( cursor, station ):
    stationuuid = station.get( 'stationuuid' )
    name = station.get( 'name', '' ).strip()
    url = station.get( 'url' )
    url_resolved = station.get( 'url_resolved' )
    homepage = station.get( 'homepage' )
    favicon = station.get( 'favicon' )
    votes = station.get( 'votes', 0 )
    bitrate = station.get( 'bitrate', 0 )
    lastcheckok = station.get( 'lastcheckok', 0 )
    lastcheckoktime = station.get( 'lastcheckoktime' )
    # lastchecktime = station.get( 'lastchecktime' )
    lastchecktime = datetime.datetime.now().strftime( "%Y-%m-%d %H:%M:%S" )
    geo_lat = station.get( 'geo_lat' )
    geo_long = station.get( 'geo_long' )
    id_country = get_or_create_id( cursor, 'countries', 'Name', station.get( 'country' ))
    id_language = get_or_create_id( cursor, 'languages', 'Name', station.get( 'language' ))
    id_codec = get_or_create_id( cursor, 'codecs', 'Name', station.get( 'codec' ))
    cursor.execute("""
        UPDATE stations SET
            name = ?, url = ?, url_resolved = ?, homepage = ?, favicon = ?,
            IDCountry = ?, IDLanguage = ?, votes = ?, IDCodec = ?,
            bitrate = ?, lastcheckok = ?, lastcheckoktime = ?, lastchecktime = ?,
            geo_lat = ?, geo_long = ?
        WHERE stationuuid = ?
    """, (
        name, url, url_resolved, homepage, favicon,
        id_country, id_language, votes, id_codec,
        bitrate, lastcheckok, lastcheckoktime, lastchecktime,
        geo_lat, geo_long, stationuuid
    ))
    cursor.execute( 'SELECT IDStation FROM stations WHERE stationuuid = ?', ( stationuuid, ) )
    row = cursor.fetchone()
    if args.debug:
        app.log( f'Station {name} bijgewerkt (uuid ={stationuuid})' )
    return row[0] if row else None
    
def update_station_lastchecktime_by_uuid( cursor, uuid ):
    cursor.execute("""
        UPDATE stations
        SET lastchecktime = datetime( 'now', 'localtime' )
        WHERE stationuuid = ?
    """, ( uuid, ))
    if args.debug:
        logging.info( f'Station lastchecktime bijgewerkt (uuid ={uuid})' )
        
def sync_tags( cursor, id_station, tags_string ):
    cursor.execute( 'DELETE FROM stationstags WHERE IDStation = ?', ( id_station, ) )
    if not tags_string:
        return
    tag_list = [t.strip() for t in tags_string.split( ',' ) if t.strip()]
    for tag in tag_list:
        id_tag = get_or_create_id(cursor, 'tags', 'Name', tag)
        cursor.execute( 'INSERT INTO stationstags (IDStation, IDTag) VALUES (?, ?)', ( id_station, id_tag ) )


def fetch_all_stations(api_url): 
    session = get_session()
    return api_call( session, api_url, 'GET' )

def fetch_station_by_uuid( uuid ):
    try:
        if False:
            if 'session' not in thread_local:
                session = get_session()
                thread_local[ 'session' ] = session
            session = thread_local[ 'session' ]
        session = get_session()
        url = API_BY_UUID.format( uuid )        
        data = api_call( session, url, 'GET' )
        
        return data[0] if data else None
    except Exception as exc:        
        logging.error( f'Exception ocurred: {str(exc)}', exc_info=True )
        return None

def _tcp_check( host, port, timeout=3 ):
    try:
        # -------------------------
        # 1. DNS check
        # -------------------------
        ip = socket.gethostbyname( host )
        if not ip:
            return False

        # -------------------------
        # 2. TCP connect check
        # -------------------------
        sock = socket.create_connection(( ip, port ), timeout=timeout )
        sock.close()
        
        return True
    except Exception:
        return False

def is_stream_url_alive( url, timeout=8 ):
    """
    Controleert of een audiostream URL bereikbaar is.
    Werkt met Icecast, Shoutcast, MP3 streams en HLS.

    Returns True als de stream reageert.
    """

    if not url:
        return False

    try:
        parsed = urlparse(url)

        host = parsed.hostname
        port = parsed.port

        if not port:
            port = 443 if parsed.scheme == "https" else 80
            
        # -------------------------
        # Snelle TCP connect check
        # -------------------------
        if not _tcp_check( host, port ):
            logging.info( f'Controle URL {url} Server {host}:{port} reageert niet op TCP check' )
            return False

        # -------------------------
        # 3. HTTP request
        # -------------------------
        session = get_session()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (RadioStreamValidator)",
            "Accept": "*/*",
            "Icy-MetaData": "1",
            "Connection": "keep-alive",
        }
        
        session.headers.update( headers )
        
        try:
            response = session.get(
                url,
                timeout = ( http_connect_timeout, http_response_timeout),
                stream=True,
                allow_redirects=True
            )
        except requests.exceptions.SSLError:            
            # fallback bij broken TLS
            logging.info( f'Controle URL {url} TLS certificaat mislukt probeer fallback' )
            response = requests.get(
                url,
                timeout = ( http_connect_timeout, http_response_timeout),
                stream=True,
                allow_redirects=True,
                verify=False
            )

        if response.status_code >= 400:
            logging.warning( f'Bad HTTP status: {response.status_code}' )
            return False
            
        # geldige HTTP status
        if not ( 200 <= response.status_code < 400 ):
            logging.warning( f'Bad HTTP status: {response.status_code}' )
            return False

        # -------------------------
        # 4. Check content-type
        # -------------------------
        content_type = response.headers.get( 'content-type', '' ).lower()
        logging.info( f'URL {url} is een {content_type} stream ' )

        if any( v in content_type for v in valid_mime_types ):
            return True

        # -------------------------
        # 5. fallback: lees eerste bytes
        # -------------------------
        chunk = next( response.iter_content(1024), None )

        if chunk:
            return True

        return False

    except Exception as exc:
        logging.error( f'Stream check failed for {url}: {exc}' )
        return False
        
def delete_station_by_uuid( cursor, uuid ):
    try:

        # IDStation ophalen
        cursor.execute( 'SELECT IDStation FROM stations WHERE stationuuid = ?', ( uuid, ) )
        row = cursor.fetchone()

        if not row:
            return f'{uuid} - al verwijderd'

        id_station = row[0]

        # Eerst tags verwijderen ( foreign key veilig)
        cursor.execute( 'DELETE FROM stationstags WHERE IDStation = ?', ( id_station, ) )

        # Daarna station verwijderen
        cursor.execute( 'DELETE FROM stations WHERE IDStation = ?', ( id_station, ) )

        return f'{uuid} VERWIJDERD'

    except Exception as e:
        logging.error( 'Exeception occured', exc_info=True )
        return f'FOUT bij verwijderen {uuid}: {e}'
        
def safe_delete_station( cursor, uuid, stream_url ):
    if not is_stream_url_alive( stream_url ):
        return delete_station_by_uuid( cursor, uuid )
    
    update_station_lastchecktime_by_uuid( cursor, uuid )
    return f'{uuid} niet verwijderd (stream leeft nog)'

def update_station_worker( uuid, stop_event=None ):
    
    conn = None
    
    # check stop-event bij start
    if stop_event and stop_event.is_set():
        return f'{uuid} update overgeslagen (gestopt)'

    try:
        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute( 'SELECT url FROM stations WHERE stationuuid = ?', ( uuid, ) )
        row = cursor.fetchone()
        current_url = row[0] if row else None

        # Fetch station data
        station = fetch_station_by_uuid( uuid )

        if stop_event and stop_event.is_set():
            return f'{uuid} update overgeslagen (gestopt)'

        if not station:
            return safe_delete_station( cursor, uuid, current_url )
           
        id_station = update_station( cursor, station )

        if stop_event and stop_event.is_set():
            return f'{uuid} update overgeslagen (gestopt)'
            
        if id_station:
            sync_tags( cursor, id_station, station.get( 'tags', '' ) )

        return f'''{station.get( 'name', uuid )} OK'''

    except Exception as e:
        return f'FOUT bij {uuid}: {e}'

    finally:
        conn.commit()
        conn.close()

# ===========================
# GUI
# ===========================
class StreamerGUI:
    def __init__( self, root):
        self.root = root
        self.root.title( 'iNetTuner' )
        self.root.iconbitmap( os.path.join( progdir, 'inet_tuner.ico' ) )
        
        # Scherm info ophalen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = 900
        height = 950
        x = int(( screen_width / 2 ) - (width / 2 ))
        y = int(( screen_height / 2 ) - (height / 2 ))
        self.root.geometry( f'{width}x{height}+{x}+{y}' )

        self.ip_var = tk.StringVar()
        self.db_var = tk.StringVar( value=DB_FILE )
        self.legacy_var = tk.BooleanVar( value=True )
        self.update_checkbox_var = tk.BooleanVar( value=True )
        self.status_var = tk.StringVar( value='Gereed' )
        
        self.build_ui()
        self.load_config()
        self.update_thread = None
        self.streamer_found = False

        # Variabele voor after-id 
        self.update_model_name_title()
        self.root.after( 2000, self.update_now_playing ) # eenmaling uitvoeren na 2000ms
        self._debounce_after_id = None
        # Trace IP-adres
        self.ip_var.trace_add( 'write', self.on_ip_change )
        
        # Stop-event voor update threads
        self.stop_update_event = threading.Event()
        
        self.root.protocol( 'WM_DELETE_WINDOW', self.on_close )


    def on_ip_change( self, *args ):
        # Cancel eventuele geplande update
        if self._debounce_after_id is not None:
            self.root.after_cancel( self._debounce_after_id )

        # Plan update na 10.000ms
        self._debounce_after_id = self.root.after( 10000, self.update_model_name_title )
        
               
    def update_model_name_title( self ):

        ip = self.ip_var.get().strip()   # <-- in main thread ophalen

        if not ip or ip == getattr( self, '_last_ip', None):
            return
            
        self._last_ip = ip

        def worker(ip):
            found = False
            try:
                url = DEVICEINFO_API_ENDPOINT.format( ip )
                session = get_session()
                response = session.get(url, timeout=(http_connect_timeout, http_response_timeout))
                
                response.raise_for_status()
                try:
                    parser = etree.XMLParser( recover=True )
                    root_xml = etree.fromstring( response.text.encode(), parser )
                except etree.ParseError:
                    model_name = 'Not Recognized'
                model_name = root_xml.findtext( 'ModelName', default='iNetTuner' )
                found = bool( model_name )
                self.log( f'Found streamer {model_name}' )
                self.root.after(0, lambda: self.root.title( f'iNetTuner - {model_name}' ))

            except Exception as exc:
                self.root.title( f'iNetTuner' )
                self.root.after(0, lambda: self.log( f'No streamer found on {ip}' ))
                if args.debug:
                    logging.error( f'Kon ModelName niet ophalen: {exc}' )
            # Sla de status op
            self.streamer_found = found

        threading.Thread(target=worker, args=(ip,), daemon=True).start()

    def update_now_playing( self ):
        ip = self.ip_var.get().strip()

        # Stop als geen streamer
        if not ip or not getattr( self, 'streamer_found', False ):
            if args.debug:
                self.log( 'Geen streamer gevonden, skip Now Playing update' )
            self.root.after( 5000, self.update_now_playing )
            return
            
        def worker(ip):
            try:
                url = STATUS_API_ENDPOINT.format( ip )

                session = get_session()
                response = session.get(
                    url,
                    timeout=(http_connect_timeout, http_response_timeout)
                )
                response.raise_for_status()
                
                display = Display( )
                try:
                    parser = etree.XMLParser( recover=True )
                    root_xml = etree.fromstring( response.text.encode(), parser )
                    values = [v.text or '' for v in root_xml.findall( './/szLine/value' )]
                except etree.ParseError:
                    if args.debug:
                        logging.warning( f'Invalid Text {response.text}' )
                    values = []

                # html.unescape( val ) # vertaal &apos; => ' /  &amp; => &
                display.action = html.unescape( values[0] ) if len( values ) > 0 else ''
                display.value = html.unescape( values[1] ) if len( values ) > 1 else ''
                display.station = html.unescape( values[2] ) if len( values ) > 2 else ''

                
                track = display.value if display.value else display.action

                # GUI update via main thread
                self.root.after(
                    0,
                    lambda: self.update_now_playing_display( display, track )
                )

            except Exception as e:
                logging.error( f'Kon Now Playing niet ophalen: {e}' )

        threading.Thread( target=worker, args=( ip, ), daemon=True ).start()

        # elke 5000 milliseconden opnieuw ophalen (na elke update eenmalig opnieuw plannen)
        self.root.after( 5000, self.update_now_playing )
    
    def update_now_playing_display( self, display, track ):
        self.station_var.set( display.station )

        spacer = '     '

        if getattr( self, 'current_track', None ) != track:
            self.current_track = track
            if display.action != display.value and display.station:
                self.log( f'{display.action}: {display.station} - {track}' )
            elif display.action != display.value:
                self.log( f'{display.action}: {track}' )
            else:
                self.log( f'{display.action}' )
                
            # dubbele tekst voor continu scrollen
            self.loop_text = track + spacer + track + spacer
            self.now_canvas.itemconfig( self.now_text, text=self.loop_text)
            self.now_canvas.update_idletasks()

            # breedte van eerste kopie
            bbox = self.now_canvas.bbox( self.now_text)
            self.first_width = (bbox[2] - bbox[0]) / 2

            # scroll starten of blijven lopen
            if not hasattr( self, 'scroll_x' ):
                self.scroll_x = 0
            self.start_scroll()

    def start_scroll( self ):            
        # scroll_step al actief? niet opnieuw starten
        if hasattr( self, 'scroll_job' ) and self.scroll_job:
            return
        self.scroll_step()
        
    def scroll_step( self ):
        speed = 1
        self.scroll_x = getattr( self, 'scroll_x', 0)

        # scroll naar links of naar rechts
        self.scroll_x += speed
        # self.scroll_x -= speed

        # modulo reset → vloeiende loop zonder springen
        self.scroll_x %= self.first_width

        self.now_canvas.coords( self.now_text, -self.scroll_x, 11)

        # blijf scrollen
        self.scroll_job = self.now_canvas.after(30, self.scroll_step)
    
    def load_config( self ):
        config = configparser.ConfigParser()
        if os.path.exists( CONFIG_FILE ):
            config.read( CONFIG_FILE )
            self.ip_var.set( config.get( 'settings', 'ip', fallback='' ) )
            self.db_var.set( config.get( 'settings', 'database', fallback=DB_FILE ))
            self.legacy_var.set( config.getboolean( 'settings','legacy', fallback=True ))
            self.update_checkbox_var.set( config.getboolean( 'settings','update_db', fallback=True ))

    def save_config( self ):
        config = configparser.ConfigParser()
        config[ 'settings' ] = {
            'ip': self.ip_var.get(),
            'database': self.db_var.get(),
            'legacy': str( self.legacy_var.get()),
            'update_db': str( self.update_checkbox_var.get())
        }
        with open(CONFIG_FILE, 'w' ) as f:
            config.write( f)

    def on_close( self ):
        # Stop update threads
        if self.update_thread and self.update_thread.is_alive():
            self.stop_update_event.set()
            self.update_thread.join(timeout=5 )  # wacht max 5 seconden
        self.save_config()
        self.root.destroy()

    def build_ui( self ):

        # ==========================
        # INSTELLINGEN FRAME
        # ==========================
        top = ttk.LabelFrame( self.root, text='Instellingen' )
        top.pack( fill='x', padx=10, pady=5 )

        # kolommen layout
        top.columnconfigure( 0, weight=0 )
        top.columnconfigure( 1, weight=0 )
        top.columnconfigure( 2, weight=0 )
        top.columnconfigure( 3, weight=0 )
        top.columnconfigure( 4, weight=1 )

        # =============================
        # IP ADRES
        # =============================

        ttk.Label( top, text='IP Adres:' ).grid(
            row=0, column=0, padx=5, pady=5, sticky='w' )

        ttk.Entry( top, textvariable=self.ip_var, width=20).grid(
            row=0, column=1, padx=5, pady=5, sticky='w' )

        ttk.Checkbutton(
            top,
            text = 'Legacy Mode',
            variable = self.legacy_var
        ).grid(
            row=0, column=2, padx=5, pady=5, sticky='w' )

        # =============================
        # DATABASE
        # =============================

        ttk.Label( top, text='Database:' ).grid(
            row=1, column=0, padx=5, pady=5, sticky='w' )

        ttk.Entry(top, textvariable=self.db_var, width=20).grid(
            row=1, column=1, padx=5, pady=5, sticky='w' )

        ttk.Button(
            top,
            text = 'Bladeren',
            command = self.select_db
        ).grid(
            row=1, column=2, padx=5, pady=5, sticky='w'
        )

        # =============================
        # NOW PLAYING DISPLAY
        # =============================

        display_frame = ttk.Frame( top )
        display_frame.grid(
            row=0,
            column=4,
            rowspan=2,
            padx=10,
            pady=4,
            sticky='e'
        )

        DISPLAY_W = 260
        DISPLAY_H = 22

        # -----------------------------
        # Zendernaam
        # -----------------------------

        self.station_var = tk.StringVar()

        self.station_entry = tk.Entry(
            display_frame,
            textvariable=self.station_var,
            width=1,
            justify='center',
            state='readonly',
            relief='sunken'
        )

        self.station_entry.grid(
            row=0,
            column=0,
            ipadx=DISPLAY_W//2,
            ipady=2,
            sticky='ew',
            pady=(0,4)
        )

        # -----------------------------
        # Scroll display
        # -----------------------------

        self.now_canvas = tk.Canvas(
            display_frame,
            width=DISPLAY_W,
            height=DISPLAY_H,
            bd=1,
            relief='sunken',
            highlightthickness=0
        )

        self.now_canvas.grid(
            row=1,
            column=0,
            sticky='ew'
        )

        self.now_text = self.now_canvas.create_text(
            DISPLAY_W,
            DISPLAY_H//2,
            anchor='w',
            text='',
            font=( 'Segoe UI', 9 )
        )
        
        # ==========================
        # ACTIES FRAME
        # ==========================
        actions = ttk.LabelFrame( self.root, text='Acties' )
        actions.pack( fill='x', padx=10, pady=5 )

        # Zorg dat rechter kolom ruimte krijgt
        actions.columnconfigure( 0, weight=1 )
        actions.columnconfigure( 1, weight=1 )

        # ==========================
        # ACTIES LINKER GEDEELTE 
        # ==========================
        left = ttk.Frame( actions )
        left.grid( row=0, column=0, sticky='w' )
        
        ttk.Label( left, text='Station ID:' ).grid( row=0, column=0 )
        self.station_entry = ttk.Entry( left, width=10 )
        self.station_entry.grid( row=0, column=1 )

        ttk.Button( left, text='Speel Station', command=self.play_station ).grid( row=0, column=2, padx=5 )
        ttk.Button( left, text='Input NET', command=self.set_input_net ).grid( row=0, column=4, padx=5 )
        ttk.Button( left, text='Lijst Favorieten', command=self.get_favorites ).grid( row=0, column=3, padx=5 )

        ttk.Label( left, text='Favoriet Nr:' ).grid( row=1, column=0 )
        self.fav_entry = ttk.Entry( left, width=10 )
        self.fav_entry.grid( row=1, column=1 )

        ttk.Button( left, text='Instellen', command=self.set_favorite ).grid( row=1, column=2, padx=5 )
        ttk.Button( left, text='Favoriet Kiezen', command=self.call_favorite ).grid( row=1, column=3, padx=5 )

        # ==========================
        # ACTIES RECHTER GEDEELTE (Database Update)
        # ==========================
        right = ttk.Frame( actions )
        right.grid(row=0, column=1, sticky='ne' )  # rechts boven uitlijnen

        # Zorg dat alles links in dit frame uitlijnt
        right.columnconfigure(0, weight=1)

        self.update_button = ttk.Button(
            right,
            text='Database Update',
            command=self.toggle_update_database,
            width=20
        )
        self.update_button.grid( row=0, column=0, sticky='w', padx=5 )

        ttk.Checkbutton(
            right,
            text='Vernieuwen db-entries via api.radio-browser.info',
            variable=self.update_checkbox_var
        ).grid( row=1, column=0, sticky='w', padx=5 )

        # ==========================
        # FAVORIETENLIJST
        # ==========================
        fav_frame = ttk.LabelFrame( self.root,text='Favorieten' )
        fav_frame.pack( fill='both',expand=True,padx=10,pady=5 )
        self.fav_tree = ttk.Treeview( fav_frame, columns=( 'no','name' ), show='headings' )
        self.fav_tree.heading( 'no',text='Nr', anchor='w' )
        self.fav_tree.heading( 'name',text='Naam', anchor='w' )
        self.fav_tree.column( 'no', width=50, anchor='w' )
        self.fav_tree.column( 'name', width=250, anchor='w' )
        self.fav_tree.pack( fill='both',expand=True )
        self.fav_tree.bind( '<Double-1>', self.on_fav_double )

        # ==========================
        # ZOEKBALK 
        # ==========================
        searchbar_frame = ttk.LabelFrame( self.root, text='Zoeken' )
        searchbar_frame.pack( fill='x', padx=10, pady=5 )

        ttk.Label( searchbar_frame, text='Zoek station:' ).pack( side='left', padx=5 )

        self.search_entry = ttk.Entry( searchbar_frame, width=40 )
        self.search_entry.pack( side='left', padx=5 )

        ttk.Button(
            searchbar_frame,
            text='Zoeken',
            command=self.search_stations
        ).pack(side='left', padx=5 )
        self.search_entry.bind( '<Return>', lambda event: self.search_stations())

        # ==========================
        # ZOEKRESULTATEN
        # ==========================
        search_frame = ttk.LabelFrame( self.root,text='Zoekresultaten' )
        search_frame.pack( fill='both',expand=True,padx=10,pady=5 )
        self.search_tree = ttk.Treeview( search_frame, columns=( 'id','name','url','mime' ), show='headings' )
        self.search_tree.heading( 'id',text='ID', anchor='w' )
        self.search_tree.heading( 'name',text='Naam', anchor='w' )
        self.search_tree.heading( 'url',text='URL', anchor='w' )
        self.search_tree.heading( 'mime',text='MIME', anchor='w' )
        self.search_tree.column( 'id',width=50, anchor='w' )
        self.search_tree.column( 'name',width=250, anchor='w' )
        self.search_tree.column( 'url',width=300, anchor='w' )
        self.search_tree.column( 'mime',width=80, anchor='w' )
        self.search_tree.pack( fill='both',expand=True )
        self.search_tree.bind( '<Double-1>', self.on_search_double )

        # ==========================
        # LOG
        # ==========================
        log_frame = ttk.LabelFrame( self.root,text='Log' )
        log_frame.pack( fill='both',expand=True,padx=10,pady=5 )
        self.log_text = tk.Text( log_frame,height=6 )
        self.log_text.pack( fill='both',expand=True )

        self.progress = ttk.Progressbar( self.root, orient='horizontal', mode='determinate' )
        self.progress.pack( fill='x', padx=10, pady=5 )

        self.statusbar = ttk.Label( self.root,textvariable=self.status_var,relief='sunken',anchor='w' )
        self.statusbar.pack( fill='x',side='bottom' )

    def log( self,text):
        logging.info( text )
        self.log_text.insert( tk.END,text+'\n' )
        self.log_text.see( tk.END )

    def set_status( self,text):
        logging.info( f'Status: {text}' )
        self.status_var.set( text )
        self.root.update_idletasks()

    def select_db( self ):
        file = filedialog.askopenfilename( initialdir=progdir, filetypes=[( 'SQLite DB','*.db' )] )
        if file:
            self.db_var.set( file )
    
    def set_input_net(self):
        try:
            ip = self.ip_var.get().strip()

            # Stop als geen streamer
            if not ip or not getattr( self, 'streamer_found', False ):
                if args.debug:
                    self.log( 'Geen streamer gevonden, skip set Input Net/USB' )
                return
            
            session = get_session()
            url = NETINPUT_API_ENDPOINT.format( ip )
            response = api_call( session, url, 'GET' )
            
            self.set_status( f'Input NET/USB ingesteld' )
            self.log( f'Input NET/USB ingesteld' )
            
        except Exception as e:
            self.log( f'Fout bij Input NET: {e}' )
    
    def play_station( self ):
        try:
            ip = self.ip_var.get()
            # Stop als geen streamer
            if not ip or not getattr( self, 'streamer_found', False ):
                if args.debug:
                    self.log( 'Geen streamer gevonden, skip Play Station' )
                return
                
            station_id = int( self.station_entry.get())
            name, url, codec = get_station_from_db( self.db_var.get(), station_id, self.legacy_var.get())
            xml = build_play_xml( name, url, codec )
            status, result, response = send_xml( ip, xml )
            self.log( f'Speelt: {name} URL={url} MIME={codec}' )
            self.log( f'Status: {status} - {result}' )
            self.set_status( f'Speelt: {name}' )
        except Exception as e:
            messagebox.showerror( 'Fout',str(e))

    def get_favorites( self ):
        try:
            ip = self.ip_var.get()
            
            # Stop als geen streamer
            if not ip or not getattr( self, 'streamer_found', False ):
                if args.debug:
                    self.log( 'Geen streamer gevonden, skip Get Favorites' )
                return                
                
            xml = build_get_favorites_xml()
            status, result, response = send_xml( ip, xml )
            if status == 200:
                self.log( f'Status: OK ({status})' )
            else:
                self.log( f'Status: {status}' )
            if response:
                self.fav_tree.delete(*self.fav_tree.get_children())            
                
                parser = etree.XMLParser( recover=True )
                root = etree.fromstring( response.encode(), parser )
           
                favorites = root.findall( './/favorite' )
                for fav in favorites:
                    no = fav.findtext( 'No','' )
                    name = fav.findtext( 'ItemName','(leeg)' )
                    
                    self.fav_tree.insert( '', 'end', values=(no,name))
                self.set_status( 'Favorieten geladen' )
            else:
                self.set_status( 'Favorieten ophalen mislukt' )
        except Exception as e:
            messagebox.showerror( 'Fout',str(e))

    def set_favorite( self ):
        try:
            ip = self.ip_var.get()
            # Stop als geen streamer
            if not ip or not getattr( self, 'streamer_found', False ):
                if args.debug:
                    self.log( 'Geen streamer gevonden, skip Set Favorite Station' )
                return
                
            num = int( self.fav_entry.get())
            xml = build_set_favorite_xml( num )
            status, result, response = send_xml( ip, xml )
            self.log( f'Favoriet ingesteld op {num}' )
            self.get_favorites()
        except Exception as e:
            messagebox.showerror( 'Fout',str(e))

    def call_favorite( self ):
        try:
            session = get_session()
            ip = self.ip_var.get()
            
            # Stop als geen streamer
            if not ip or not getattr( self, 'streamer_found', False ):
                if args.debug:
                    self.log( 'Geen streamer gevonden, skip Play Favorite Station' )
                return
                
            num = str( int( self.fav_entry.get())).zfill( 2 )
            url = FAVORITE_API_ENDPOINT.format( ip, num )
            response = api_call( session, url, 'GET' )
            
            self.set_status( f'Favoriet kanaal {num} gekozen' )
            self.log( f'Favoriet kanaal {num} gekozen' )
        except Exception as e:
            messagebox.showerror( 'Fout',str(e))

    def on_fav_double( self,event):
        item = self.fav_tree.selection()
        if item:
            values = self.fav_tree.item(item)['values']
            self.fav_entry.delete(0,tk.END)
            self.fav_entry.insert(0, values[0])
            self.call_favorite()

    def search_stations( self ):
        try:
            query = self.search_entry.get().strip()
            if not query:
                return
            self.search_tree.delete(*self.search_tree.get_children())
            conn = create_connection( self.db_var.get())
            cursor = conn.cursor()
            parts = query.upper().split()
            like_clause = '%' + '%'.join(parts) + '%'
            SQL = f'''SELECT s.IDStation, s.name, COALESCE(s.url_resolved,s.url), c.Name
                      FROM stations s
                      LEFT JOIN codecs c ON s.IDCodec = c.IDCodec
                      WHERE UPPER(s.name) LIKE '{like_clause}'
                      ORDER BY s.lastcheckoktime DESC'''
            cursor.execute(SQL)
            for row in cursor.fetchall():
                self.search_tree.insert( '', 'end', values=row )
            conn.close()
            self.set_status( f'''Zoekresultaten voor '{query}' geladen''' )
        except Exception as e:
            messagebox.showerror( 'Fout',str(e) )

    def on_search_double( self,event):
        item = self.search_tree.selection()
        if item:
            values = self.search_tree.item(item)[ 'values' ]
            self.station_entry.delete(0,tk.END)
            self.station_entry.insert(0, values[0])
            self.play_station()

               
    def update_database( self ):
        try:
            # Eerst nieuwe stations importeren
            self.import_new_stations()
            self.log( 'Database update gestart...' )        
            self.set_status( 'Database update gestart...' )

            if not self.update_checkbox_var.get():
                self.log( 'Multi-threaded update niet geselecteerd, geen update uitgevoerd' )
                self.set_status( 'Database update voltooid (geen update)' )
                self.update_button.config( text='Database Update' )
                return

            # Multi-threaded update oudere stations
            self.update_all_stations_thread()

        except Exception as e:
            self.log( f'Fout in update_database: {e}' )
            self.update_button.config( text='Database Update' )
            
    def toggle_update_database( self ):
        # Controleer of er een actieve thread is en alive
        if self.update_thread and self.update_thread.is_alive():
            # Stop de update
            self.stop_update_event.set()
            self.update_button.config( text='Database Update' )
            self.set_status( 'Database update wordt gestopt...' )
            self.log( 'Stop signaal verzonden...' )
        else:
            # Start een nieuwe update
            self.stop_update_event.clear()  # ✅ reset event bij starten
            self.update_button.config( text='Stop Update' )
            self.update_thread = threading.Thread( target=self.update_database, daemon=True )
            self.update_thread.start()

    def import_new_stations( self ):
        try:
            conn = create_connection( self.db_var.get())
            cursor = conn.cursor()
            # ---- Eerst nieuwe stations importeren ----

            self.log( 'Importeren van nieuwe stations gestart...' )
            self.set_status( 'Importeren nieuwe stations...' )

            for api_url in [ API_ALL, API_LASTCHANGE, API_TOPVOTE, API_TOPCLICK, API_LASTCLICK ]:
                self.log( f'Importeren van {api_url} ...' )                
                stations = fetch_all_stations(api_url)
                inserted = 0
                for station in stations:
                    uuid = station.get( 'stationuuid' )
                    name = station.get( 'name', '' ).strip()
                    url = station.get( 'url' )
                    
                    cursor.execute( 'SELECT 1 FROM stations WHERE stationuuid = ?', ( uuid, ) )
                    if cursor.fetchone():
                        id_station = update_station( cursor, station )
                    else:
                        id_station = insert_station( cursor, station )
                        inserted += 1
                        
                    sync_tags( cursor, id_station, station.get( 'tags','' ) )

                conn.commit()
                self.log( f'{inserted} nieuwe stations toegevoegd van {api_url}' )
            self.log( 'Importeren nieuwe stations voltooid' )
            conn.close()
        except Exception as e:
            self.log( f'Fout bij importeren nieuwe stations: {e}' )
            
            
    def run_update_thread( self ):
        t = threading.Thread( target=self.update_all_stations_thread )
        t.start()

    def update_all_stations_thread( self ):
        conn = create_connection( self.db_var.get() )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT stationuuid 
            FROM stations
            WHERE lastchecktime IS NULL 
            OR lastchecktime <= datetime('now', '-2 months')
        """)
        uuids = [ row[0] for row in cursor.fetchall() ]
        conn.close()

        total = len( uuids )
        self.progress[ 'maximum' ] = total
        self.progress[ 'value' ] = 0
        completed = 0

        self.log( f'{total} stations worden bijgewerkt...' )

        with ThreadPoolExecutor( max_workers=18 ) as executor:
            # Stop-event meegeven aan elke worker
            futures = { executor.submit( update_station_worker, uuid, self.stop_update_event ): uuid for uuid in uuids }

            for future in as_completed( futures ):
                if self.stop_update_event.is_set():
                    self.log( 'Update gestopt door gebruiker' )
                    self.set_status( 'Database update gestopt' )
                    break

                result = future.result()
                completed += 1
                self.log( f'[{completed}/{total}] {result}' )
                self.progress[ 'value' ] = completed
                self.set_status( f'Update voortgang: {completed}/{total}' )

        self.update_button.config( text='Database Update' )
        if not self.stop_update_event.is_set():
            self.set_status( 'Database update voltooid' )
            self.log( 'Database update voltooid' )

# ===========================
# START APP
# ===========================
if __name__ == '__main__':
    root = tk.Tk()
    app = StreamerGUI( root )
    root.mainloop()