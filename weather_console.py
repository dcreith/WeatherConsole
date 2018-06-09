#!/usr/bin/python
'''*****************************************************************************************************************
    Pi Weather Console v1.0

    Weather Console

********************************************************************************************************************'''

from __future__ import print_function

import datetime
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import time
import math
import cPickle as pickle
import errno
import fnmatch
import json
from urllib import urlencode
import urllib2
import pygame
from pygame.locals import *
from ft5406 import Touchscreen, TS_PRESS, TS_RELEASE, TS_MOVE, TOUCH_X, TOUCH_Y


# from config import Config
mypath = os.path.abspath(__file__)  # Find the full path of this python script
baseDir = os.path.dirname(mypath)   # get the path location only (excluding script name)
baseFileName = os.path.splitext(os.path.basename(mypath))[0]
progName = os.path.basename(__file__)

# Check for config.py variable file to import and error out if not found.
configFilePath = os.path.join(baseDir, "config.py")
if not os.path.exists(configFilePath):
    print("ERROR - %s File Not Found. Cannot Import Configuration Variables." % ( configFilePath ))
    quit()
else:
    # Read Configuration variables from config.py file
    print("INFO  - Import Configuration Variables from File %s" % ( configFilePath ))
    from config import *


# set up logging
logFilePath = os.path.join(baseDir, baseFileName + ".log")

logger = logging.getLogger('weather_pi')
if Config.LOGGING_DEBUG:
    logger.setLevel(logging.DEBUG)
elif Config.LOGGING_INFO:
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.WARNING)
handler = RotatingFileHandler(logFilePath, maxBytes=Config.LOGGING_BYTES, backupCount=Config.LOGGING_ROTATION)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# ============================================================================
# Constants
# ============================================================================
size = width, height = 800, 480

GO=True
REBOOT=False
SHUTDOWN=False

DIM = 2
STANDARD_PRESSURE=1013.25
DEGREES= u'\N{DEGREE SIGN}'
DEGREES= u"\u2103"
DEGREES= u'\xb0'

ARROW={}
ARROW['LEFT']=u"\u2190"
ARROW['UP']=u"\u2191"
ARROW['RIGHT']=u"\u2192"
ARROW['DOWN']=u"\u2193"
ARROW['NORTHWEST']=u"\u2196"
ARROW['NORTHEAST']=u"\u2197"
ARROW['SOUTHEAST']=u"\u2198"
ARROW['SOUTHWEST']=u"\u2199"
ARROW['DASH']="--"

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

# UI classes ---------------------------------------------------------------

# Icon is a very simple bitmap class, just associates a name and a pygame
# image (PNG loaded from icons directory) for each.
# There isn't a globally-declared fixed list of Icons.  Instead, the list
# is populated at runtime from the contents of the 'icons' directory.

class Icon:

    def __init__(self, name):
      self.name = name
      try:
        self.bitmap = pygame.image.load(os.path.join(iconPath , str(name+'.png')))
      except:
        pass

# Button is a simple tappable screen region.  Each has:
#  - bounding rect ((X,Y,W,H) in pixels)
#  - optional background color and/or Icon (or None), always centered
#  - optional foreground Icon, always centered
#  - optional single callback function
#  - optional single value passed to callback
# Occasionally Buttons are used as a convenience for positioning Icons
# but the taps are ignored.  Stacking order is important; when Buttons
# overlap, lowest/first Button in list takes precedence when processing
# input, and highest/last Button is drawn atop prior Button(s).  This is
# used, for example, to center an Icon by creating a passive Button the
# width of the full screen, but with other buttons left or right that
# may take input precedence (e.g. the Effect labels & buttons).
# After Icons are loaded at runtime, a pass is made through the global
# buttons[] list to assign the Icon objects (from names) to each Button.

class ScreenButton:

    def __init__(self, rect, **kwargs):
      self.rect     = rect # Bounds
      self.color    = None # Background fill color, if any
      self.iconBg   = None # Background Icon (atop color fill)
      self.iconFg   = None # Foreground Icon (atop background)
      self.bg       = None # Background Icon name
      self.fg       = None # Foreground Icon name
      self.callback = None # Callback function
      self.value    = None # Value passed to callback
      for key, value in kwargs.iteritems():
        if   key == 'color': self.color    = value
        elif key == 'bg'   : self.bg       = value
        elif key == 'fg'   : self.fg       = value
        elif key == 'cb'   : self.callback = value
        elif key == 'value': self.value    = value

    def selected(self, pos):
      x1 = self.rect[0]
      y1 = self.rect[1]
      x2 = x1 + self.rect[2] - 1
      y2 = y1 + self.rect[3] - 1
      if ((pos[0] >= x1) and (pos[0] <= x2) and
          (pos[1] >= y1) and (pos[1] <= y2)):
        if self.callback:
          if self.value is None: self.callback()
          else:                  self.callback(self.value)
        return True
      return False

    def draw(self, screen):
      if self.color:
        screen.fill(self.color, self.rect)
      if self.iconBg:
        screen.blit(self.iconBg.bitmap,
          (self.rect[0]+(self.rect[2]-self.iconBg.bitmap.get_width())/2,
           self.rect[1]+(self.rect[3]-self.iconBg.bitmap.get_height())/2))
      if self.iconFg:
        screen.blit(self.iconFg.bitmap,
          (self.rect[0]+(self.rect[2]-self.iconFg.bitmap.get_width())/2,
           self.rect[1]+(self.rect[3]-self.iconFg.bitmap.get_height())/2))

    def setBg(self, name):
      if name is None:
        self.iconBg = None
      else:
        for i in icons:
          if name == i.name:
            self.iconBg = i
            break

def textIt(screen, text, position, size, color, fnt=None):
    # font = pygame.font.Font(fnt, size)
    if fnt is None:fnt='arial'
    font = pygame.font.SysFont(fnt, size)
    text = font.render(text, 1, color)
    textpos = text.get_rect()
    textpos.centerx, textpos.centery = position
    screen.blit(text, textpos)

def emptyCallback(n):
    infoMsg("d","emptyCallback %s" % n)

def touch_handler(event, touch):
    global activeScreen
    if event == TS_RELEASE:
        for b in buttons[activeScreen]:
            if b.selected((touch.x,touch.y)):
                # print (where(touch.x,touch.y))
                break

def infoMsg(lvl,msg):
    if (Config.LOGGING_PRINT): print(msg)
    if (lvl=='d'):
        logger.debug(msg)
    elif (lvl=='w'):
        logger.warning(msg)
    elif (lvl=='e'):
        logger.error(msg)
    elif (lvl=='c'):
        logger.critical(msg)
    else:
        logger.info(msg)

def backlight(n):         # toggle the screen backlight on and off
    global backlightState
    if backlightState==0:
        # set backlight off
        backlightState=1
        os.system("echo 1 > /sys/class/backlight/rpi_backlight/bl_power")
    else:
        # set backlight on
        backlightState=0
        os.system("echo 0 > /sys/class/backlight/rpi_backlight/bl_power")

def colour_set(s):
    global BLACK, WHITE, RED, GREEN, BLUE, GREY
    global palette
    palette=s
    infoMsg("d","colour_set==>"+palette)
    if s=="bright":
        BLACK = (0, 0, 0)
        WHITE = (255, 255, 255)
        RED =   (255, 0, 0)
        GREEN = (0, 255, 0)
        BLUE =  (0, 0, 255)
        GREY =  (80, 80, 80)
    elif s=="dim":
        BLACK = (0, 0, 0)
        WHITE = (224, 224, 224)
        RED =   (210, 40, 40)
        GREEN = (0, 153, 76)
        BLUE =  (51, 153, 255)
        GREY =  (96, 96, 96)
    elif s=="cool":
        BLACK = (20, 20, 20)
        WHITE = (236, 236, 236)
        RED =   (229, 64, 40)
        GREEN = (97, 174, 36)
        BLUE =  (0, 161, 203)
        GREY =  (97, 97, 97)
    elif s=="warm":
        BLACK = (20, 20, 20)
        WHITE = (255, 250, 250)
        RED =   (220, 20, 60)
        GREEN = (0, 255, 0)
        BLUE =  (123, 104, 238)
        GREY =  (105, 105, 105)
    else:
        BLACK = (0, 0, 0)
        WHITE = (255, 255, 255)
        RED =   (255, 0, 0)
        GREEN = (0, 255, 0)
        BLUE =  (0, 0, 255)
        GREY =  (80, 80, 80)

def goto_screen(n):
    # go to screen n
    global activeScreen
    activeScreen=n

def screen_on(n):
    # global ManualBrightness
    # set to main screen (0) from blank screen (10)
    goto_screen(n)
    cycle_brightness(n)

def app_Off(n):
    global running, REBOOT, SHUTDOWN
    if (n==0):
        running = False
    elif (n==1):
        running = False
        REBOOT = True
    elif (n==2):
        running = False
        SHUTDOWN = True

def toggle_screen(on=True):
    # infoMsg("d","toggle_screen on==>"+str(on))
    try:
        if on:
            os.system("echo 0 > /sys/class/backlight/rpi_backlight/bl_power")
        else:
            os.system("echo 1 > /sys/class/backlight/rpi_backlight/bl_power")
    except:
        infoMsg("w",".....Unable To Set Screen On Or Off")

def set_brightness(n):
    if n<0 or n>255: n=100
    # infoMsg("d","set_brightness n==>"+str(n))
    statement="echo "+str(n)+"  > /sys/class/backlight/rpi_backlight/brightness"
    try:
        os.system(statement)
    except:
        infoMsg("w",".....Unable to reset screen brightness to "+str(n))

def cycle_brightness(n):
    global State, DIM, ManualBrightness
    # ManualBrightness=True
    # infoMsg("d","cycle_brightness before=DIM=>"+str(DIM))
    if DIM==0:
        DIM = 4
        set_brightness(State['Brightness4'])
        toggle_screen(True)
    elif DIM==4:
        DIM = 3
        set_brightness(State['Brightness3'])
    elif DIM==3:
        DIM = 2
        set_brightness(State['Brightness2'])
    elif DIM==2:
        DIM = 1
        set_brightness(State['Brightness1'])
    elif DIM==1:
        DIM = 0
        toggle_screen(False)
        goto_screen(10)
    else:
        # this should never happen
        infoMsg("w","cycle_brightness in the else DIM==>"+str(DIM))
        DIM = 3
        set_brightness(State['Brightness3'])
        toggle_screen(True)
    # infoMsg("d","cycle_brightness after=DIM=>"+str(DIM))

def determine_brightness(n):
    global State, DIM, ManualBrightness
    # infoMsg("d","determine_brightness State==>"+str(State))
    screenOn=True
    Brightness=State['Brightness1']

    if n==State['Night'] or n>State['Night'] or n<State['Sunrise']:
        # infoMsg("d","determine_brightness /nighttime n==>"+str(n))
        DIM = 1
        screenOn=False
        Brightness=State['Brightness1']
    if n==State['Sunrise'] or n>State['Sunrise']:
        # ManualBrightness=False
        # infoMsg("d","determine_brightness /daytime n==>"+str(n))
        DIM = 3
        screenOn=True
        Brightness=State['Brightness3']
    # if ManualBrightness==False:
    if n==State['Sunset'] or n>State['Sunset']:
        # infoMsg("d","determine_brightness /evening n==>"+str(n))
        DIM = 2
        screenOn=True
        Brightness=State['Brightness2']

    # infoMsg("d","determine_brightness Brightness=s=>"+str(Brightness))

    statement="echo "+str(Brightness)+"  > /sys/class/backlight/rpi_backlight/brightness"
    try:
        os.system(statement)
        if screenOn:
            os.system("echo 0 > /sys/class/backlight/rpi_backlight/bl_power")
        else:
            os.system("echo 1 > /sys/class/backlight/rpi_backlight/bl_power")
    except:
        infoMsg("w",".....Unable to reset screen brightness to "+str(n))

    # infoMsg("d","determine_brightness Brightness=l=>"+str(Brightness))

def station_action(n):
    global activeScreen, WS_State
    # toggle the Dim, Display, ColdFrame and WU Upload
    # infoMsg("d","station_action=n=>"+str(n))
    WS_State['Status']='Stale'
    if n==1:
        if WS_State["DisplayDim"]==1:
            actionID=20
        else:
            actionID=19
    elif n==2:
        if WS_State["DisplayOn"]==1:
            actionID=22
        else:
            actionID=21
    elif n==3:
        if WS_State["ColdFrameOn"]==1:
            actionID=26
        else:
            actionID=25
    elif n==4:
        if WS_State["WUUpload"]==0:
            actionID=27
        else:
            actionID=28
    else:
        actionID = n
    # infoMsg("d","station_action=a=>"+str(actionID))
    success=False
    if Config.WS_PUT_DATA:
        # infoMsg("i","WS PUT Query...")
        # infoMsg("i","Config.WS_PUT_URL==>"+str(Config.WS_PUT_URL))
        system_data = {"_sid": str(Config.WS_ID),"_id": str(actionID)}
        try:
            upload_url = Config.WS_PUT_URL + "?" + urlencode(system_data)
            infoMsg("i","upload_url==>"+str(upload_url))
            response = urllib2.urlopen(upload_url)
            rtn_control = json.load(response)
            infoMsg("i","response==>"+str(rtn_control))
            if ("Status" in rtn_control):
                infoMsg("i","Status==>>"+str(rtn_control["Status"]))
                if (rtn_control["Status"]==0):
                    success=True
        except:
            infoMsg("w",".....Failed Putting Instructions To Station")
            infoMsg("w",".....Exception:"+str(sys.exc_info()))
            infoMsg("w",".....WS_PUT_URL:"+str(Config.WS_PUT_URL))

    return success

def current_Observation(e):
    epoch_time = int(time.time())
    currency = epoch_time - (6*60*60)  # 6 hours in seconds
    current=False
    try:
        if (epoch_time>int(e)): current=True
    except:
        infoMsg("w",".....Current epoch=>"+str(currency))

    return current

def parseRawObservations(data):
    global ws_CurrentConditionsSet
    global ws_ForecastSet

    current={}
    try:
        rawObservations=data["current_observation"]
        if current_Observation(rawObservations["observation_epoch"]):
            current['windspeed']=int(round(float(rawObservations['wind_kph']),0))
            current['windgusts']=int(round(float(rawObservations['wind_gust_kph']),0))
            current['winddirection']=rawObservations['wind_dir']
            current['windcardinal']=rawObservations['wind_degrees']
            current['temperature']=int(round(float(rawObservations['temp_c']),0))
            current['dewpoint']=int(round(float(rawObservations['dewpoint_c']),0))
            current['humidity']=0
            current['pressure']=int(round(float(rawObservations['pressure_mb']),0))
            ws_CurrentConditionsSet=True
        else:
            infoMsg("w","Current conditions are stale")
    except:
        infoMsg("w",".....Failed getting current conditions")

    # infoMsg("d","from current current="+str(ws_CurrentConditionsSet))
    # infoMsg("d","from current forecast="+str(ws_ForecastSet))

    return current

def parseRawForecasts(data,current):
    global ws_CurrentConditionsSet
    global ws_ForecastSet
    fcst_date = datetime.datetime.now()
    fcst_day = fcst_date.strftime("%A")
    # fcst_date = date.today()
    # fcst_day = calendar.day_name[my_date.weekday()]

    forecast={}
    rtn={}
    rtn['current']=current
    try:
        rawForecast=data["forecast"]
        # infoMsg("d","rawForecast="+str(rawForecast))
        for i in range(0,4):
            ws_ForecastSet=True
            fcst={}
            fcst['weekday'] = rawForecast['simpleforecast']['forecastday'][i]['date']['weekday']
            fcst['weekday_short'] = rawForecast['simpleforecast']['forecastday'][i]['date']['weekday_short']

            fcst['high'] = rawForecast['simpleforecast']['forecastday'][i]['high']['celsius']
            fcst['low'] = rawForecast['simpleforecast']['forecastday'][i]['low']['celsius']

            fcst['sky'] = rawForecast['simpleforecast']['forecastday'][i]['icon']
            fcst['pop'] = rawForecast['simpleforecast']['forecastday'][i]['pop']

            fcst['maxwind'] = rawForecast['simpleforecast']['forecastday'][i]['maxwind']['kph']
            fcst['maxdirection'] = rawForecast['simpleforecast']['forecastday'][i]['maxwind']['dir']
            fcst['maxcardinal'] = rawForecast['simpleforecast']['forecastday'][i]['maxwind']['degrees']

            fcst['avgwind'] = rawForecast['simpleforecast']['forecastday'][i]['avewind']['kph']
            fcst['avgdirection'] = rawForecast['simpleforecast']['forecastday'][i]['avewind']['dir']
            fcst['avgcardinal'] = rawForecast['simpleforecast']['forecastday'][i]['avewind']['degrees']
            # infoMsg("d","fcst ==>%s %s" % (str(fcst['weekday_short']),str(fcst['sky'])))
            forecast[i]=fcst
            if i==0 and ws_CurrentConditionsSet==False:
                current['windspeed']=int(round(float(fcst['avgwind']),0))
                current['windgusts']=int(round(float(fcst['maxwind']),0))
                current['winddirection']=fcst['avgdirection']
                current['windcardinal']=fcst['avgcardinal']
                rtn['current']=current
                ws_CurrentConditionsSet=True
            # infoMsg("d","forecast="+str(forecast))
        #
        # test forecast[0] fcst['weekday'] against todays day
        # if no match then set forecast false
        #
        if forecast[0]['weekday']!=fcst_day:
            infoMsg("w","weekday 0=>"+str(forecast[0]['weekday']))
            infoMsg("w","fcst_day =>"+str(fcst_day))
        # if forecast[0]['weekday']!=fcst_day:
        #     ws_ForecastSet=False
        # from datetime import date
        # >>> import calendar
        # 'Wednesday'
        #
    except:
        ws_ForecastSet=False
        infoMsg("w",".....Failed getting forecast conditions")

    rtn['forecast']=forecast

    return rtn

def determine_Trend(s, data):
    global State, trending, ARROW, calcTrend

    # def get_smooth(x):
    # # do we have the t object?
    # if not hasattr(get_smooth, "t"):
    #     # then create it
    #     get_smooth.t = [x, x, x]
    # # manage the rolling previous values
    # get_smooth.t[2] = get_smooth.t[1]
    # get_smooth.t[1] = get_smooth.t[0]
    # get_smooth.t[0] = x
    # # average the three last temperatures
    # xs = (get_smooth.t[0] + get_smooth.t[1] + get_smooth.t[2]) / 3
    # return xs

    k='TrendMargin'+str(s)
    r=''
    if (trending[s]>-99):
        # test if current value is outside boundaries
        # if it is then set indicator and capture current
        # for future(next) comparison
        trendMargin=data[s]*State[k]
        topBoundry=trending[s]+trendMargin
        bottomBoundry=trending[s]-trendMargin
        if (data[s]<bottomBoundry):
            infoMsg("d","Down ==> %s c=%s l=%s m=%s" % (str(s),str(data[s]),str(trending[s]),str(trendMargin)))
            r=ARROW['DOWN']
            trending[s]=data[s]
        elif (data[s]>topBoundry):
            infoMsg("d","Up ==> %s c=%s l=%s m=%s" % (str(s),str(data[s]),str(trending[s]),str(trendMargin)))
            r=ARROW['UP']
            trending[s]=data[s]
        elif (data[s]<trending[s]):
            infoMsg("d","SE ==> %s c=%s l=%s m=%s" % (str(s),str(data[s]),str(trending[s]),str(trendMargin)))
            r=ARROW['SOUTHEAST']
            trending[s]=data[s]
        elif (data[s]>trending[s]):
            infoMsg("d","NE ==> %s c=%s l=%s m=%s" % (str(s),str(data[s]),str(trending[s]),str(trendMargin)))
            r=ARROW['NORTHEAST']
            trending[s]=data[s]
        else:
            infoMsg("d","Steady ==> %s c=%s l=%s m=%s" % (str(s),str(data[s]),str(trending[s]),str(trendMargin)))
            r=ARROW['RIGHT']
    else:
        # initial set to trending value
        trending[s]=data[s]

    return r

def validateNumericListData(data,key):
    # infoMsg("d","validateNumericListData key:"+str(key))
    # infoMsg("d","validateNumericListData data:"+str(data))
    r=0
    try:
        dataExists=data[key]
    except KeyError as err:
        infoMsg("w",".....Bad key from query:"+key+"==>"+data[key])
        infoMsg("w",".....                   :"+err)
        dataExists='None'
    # infoMsg("d","validateNumericListData dataExists:"+str(dataExists))
    if dataExists is None:
        r=''
    else:
        r=validateFloat(dataExists)
        r=validateInt(r)
    # infoMsg("d","validateNumericListData r:"+str(r))
    return r

def validateNumeric(n):
    # infoMsg("d","validateNumeric n:"+str(n))
    r=validateFloat(n)
    r=validateInt(r)
    # infoMsg("d","validateNumeric r:"+str(r))
    return r

def validateFloat(n):
    # infoMsg("d","validateFloat n:"+str(n))
    r=0
    try:
        r=round(float(n),0)
    except (TypeError, ValueError) as err:
        infoMsg("w",".....ValidateFloat - Bad data from query:"+data)
        infoMsg("w",".....                                   :"+err)
    # infoMsg("d","validateFloat r:"+str(r))
    return (r)

def validateInt(n):
    # infoMsg("d","validateInt n:"+str(n))
    r=0
    try:
        r=int(n)
    except (TypeError, ValueError) as err:
        infoMsg("w",".....ValidateInt - Bad data from query:"+data)
        infoMsg("w",".....                                   :"+err)
    # infoMsg("d","validateInt r:"+str(r))
    return (r)

def validateNumericArray(data):
    returnArray=list()
    for x in data:
        returnArray.append(validateNumeric(x))
    return returnArray

def saveState(s):
    global State
    State['Calling'] = s
    infoMsg("i","Pickling State==> %s" % str(State))
    try:
      outfile = open('State.pkl', 'wb')
      # Use a dictionary (rather than pickling 'raw' values) so
      # the number & order of things can change without breaking.
      pickle.dump(State, outfile)
      outfile.close()
    except:
      infoMsg("w",".....Unable to Save State")

def loadState():
    global State
    try:
      infile = open('State.pkl', 'rb')
      State= pickle.load(infile)
      infile.close()
      infoMsg("i","Getting State==> %s" % str(State))
    except:
      infoMsg("w",".....State File Not Found")

def line_chart(x, y, w, h, datapoints, mmlist, xscale=None, linecolour=None, boxcolour=None, fontcolour=None, showmid=None, showscale=None, hatch=None, polygone=False):
    scaleFontSize=50
    scaleXOffset=20
    scaleYOffset=15
    scaleZOffset=15
    scaleMidLineColour=BLUE

    if len(datapoints)<2:return

    try:
        closed=False
        scalePad=1
        # infoMsg("d","datapoints==> %s" % str(datapoints))
        # infoMsg("d","mmlist======> %s" % str(mmlist))
        if mmlist is None: mmlist=datapoints
        if xscale is None: xscale=len(datapoints)
        if linecolour is None: linecolour=RED
        if fontcolour is None: fontcolour=WHITE

        xstep=math.trunc(w/xscale)
        xstart=math.trunc(((w-(xstep*xscale))/2)+x)
        ymin = (min(mmlist) - scalePad)
        ymax = (max(mmlist) + scalePad)
        yrange = ymax - ymin
        ystep = math.trunc((h)/yrange)

        chartbottom = (y+h)+(ystep*scalePad)
        # if boxcolour is not None: pygame.draw.rect(screen, boxcolour,  (x,  y,  w, h), 1)
        if boxcolour is not None: pygame.draw.line(screen, fontcolour, (x,y),(x,chartbottom),1)
        if boxcolour is not None: pygame.draw.line(screen, fontcolour, (x,chartbottom),(x+w,chartbottom),1)

        pointlist = []
        for i in range(len(datapoints)):
            ystart = math.trunc(y + (ystep*2) + ((math.fabs(ymax)-datapoints[i]) * ystep))
            sl = []
            sl.append(xstart)
            sl.append(ystart)
            pointlist.append(sl)
            xstart=xstart+xstep

        # determine where the middle is (use 0 if some values are +0 & some -0)
        if (ymin<0 and ymax>0):
            # zline=math.trunc((ymax+2)*ystep)
            midY=math.trunc(h/2)
            zline=math.trunc((ymax+(scalePad*2))*ystep)
            midScaleValue=str(0)
            scaleMidLineColour=WHITE
            if (midY>zline):
                scaleZOffset=-15
        else:
            zline=math.trunc(h/2)
            midScaleValue=str(math.trunc(ymin+(ymax-ymin)/2))

        # comment these statements out to always show a value on the midscale line
        # if showscale=='All':
        #     if ((zline+scaleFontSize)>(ymax-scaleFontSize)):
        #         showscale='Ends'
        #     if ((zline-scaleFontSize)<(ymin+scaleFontSize)):
        #         showscale='Ends'

        hatchmax=xstep
        if showscale=='All' or showscale=='Ends':
            hatchmax=(xstep*2)
            textIt(screen, str(math.trunc(int(ymax))), ((x+scaleXOffset),y+scaleYOffset), scaleFontSize, fontcolour, "futura")     #top scale value
            textIt(screen, str(math.trunc(int(ymin))), ((x+scaleXOffset),(chartbottom)-scaleYOffset), scaleFontSize, fontcolour, "futura") #bottom scale value

        if showscale=='All' or showscale=='Mid':
            textIt(screen, midScaleValue, ((x+scaleXOffset),(y+zline)-scaleZOffset), scaleFontSize, fontcolour, "futura") # mid scale value

        dohatch=False
        if hatch is None:hatch='None'
        if hatch=='In':
            hatchvoffset=-10
            dohatch=True
        elif hatch=='Out':
            hatchmax=0
            hatchvoffset=10
            dohatch=True

        if dohatch:
            i=1
            for m in range((x+xstep), (x+w-hatchmax), xstep):
                textIt(screen, str(i), (m,chartbottom+hatchvoffset), 20, fontcolour, "futura")
                pygame.draw.line(screen, fontcolour, (m,chartbottom),(m,chartbottom-3),1)
                i+=1

        # mid line
        if showmid==True:
            pygame.draw.line(screen, scaleMidLineColour, (x,y+zline),(x+w,y+zline),1)

        # chart line
        if polygone==True:
            pygame.draw.polygon(screen, linecolour, pointlist, 0)
        else:
            pygame.draw.lines(screen, linecolour, closed, pointlist, 5)
    except:
        infoMsg("w","*********************************************************")
        infoMsg("w","************ Failed Graph Build  ************************")
        infoMsg("w","*********************************************************")
        infoMsg("w","x=%s y=%s w=%s h=%s" % (str(x),str(y),str(w),str(h)))
        infoMsg("w","datapoints=> %s" % str(datapoints))
        infoMsg("w","mmlist=====> %s" % str(mmlist))
        infoMsg("w","xscale=====> %s" % str(xscale))
        infoMsg("w","linecolour=> %s boxcolour=> %s fontcolour=> %s" % (str(linecolour),str(boxcolour),str(fontcolour)))
        infoMsg("w","showscale=> %s hatch=> %s polygone=> %s" % (str(showscale),str(hatch),str(polygone)))
        infoMsg("w","*-------------------------------------------------------*")
        infoMsg("w","pointlist==> %s" % str(pointlist))
        infoMsg("w","linecolour=> %s" % str(linecolour))
        infoMsg("w","closed=====> %s" % str(closed))
        infoMsg("w","*********************************************************")

def set_background():
    global background_image
    # define the screen background from the image
    if background_image is None or background_image.get_height() < 480: # Letterbox, clear background
      screen.fill(0)
    if background_image:
      screen.blit(background_image,
        ((800 - background_image.get_width() ) / 2,
         (480 - background_image.get_height()) / 2))

def main():
    # global last_temp
    # global GO, REBOOT, SHUTDOWN, NOTICE
    global State, WS_State
    global running, activeScreen
    global palette, refresh
    global DEGREES
    global ws_CurrentConditionsSet
    global ws_ForecastSet
    global trending, trend, calcTrend
    global DIM

    palette="warm"
    colour_set(palette)

    # initialize the lastMinute variable to the current time to start
    last_minute = datetime.datetime.now().minute
    # on startup, just use the previous minute as lastMinute
    last_minute -= 1
    if last_minute == 0:
        last_minute = 59
    last_second = -1
    last_minute = -1
    last_hour = -1

    ws_ForecastSet=False
    ws_CurrentConditionsSet=False

    # infinite loop to continuously check weather values
    infoMsg("i","Start Loop...")
    while running:
        ws_NewData=False

        for event in pygame.event.get():
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                infoMsg("i","Capture event==>>"+str(event.type))
                ts.stop()
                sys.exit()

        # get the current minute, hour and second
        current_minute = datetime.datetime.now().minute
        current_hour = datetime.datetime.now().hour
        current_second = datetime.datetime.now().second

        if current_hour != last_hour:

            determine_brightness(current_hour)

            ws_Currency=False
            ws_Accuracy=False

            if Config.WU_GET_DATA:
                    ws_CurrentConditionsSet=False
                    ws_ForecastSet=False
                    # infoMsg("i","WU Query...")
                    # infoMsg("d","Config.WU_GET_URL==>"+str(Config.WU_GET_URL))
                    try:
                        upload_url = Config.WU_GET_URL
                        response = urllib2.urlopen(upload_url)
                        rtn_control = json.load(response)
                        infoMsg("w","response:"+str(rtn_control))
                        infoMsg("w","Setting Current Observations And Forecasts...")
                        current=parseRawObservations(rtn_control)
                        observations=parseRawForecasts(rtn_control,current)
                        current=observations['current']
                        forecast=observations['forecast']
                        if Config.AUDIT_ON: Config.AUDIT_DATA=forecast
                        infoMsg("w","current:"+str(current))
                        infoMsg("w","forecast:"+str(forecast))
                    except:
                        infoMsg("w",".....Failed getting Weather Underground data")
                        infoMsg("w",".....Exception:"+str(sys.exc_info()))
                        infoMsg("w",".....WU_GET_URL:"+str(Config.WU_GET_URL))

            last_hour = current_hour


        if current_minute != last_minute:
            # reset last_minute to the current_minute
            # get info from db
            ws_Currency=False
            ws_Accuracy=False

            if Config.WS_GET_DATA:
                if (last_minute < 0) or (current_minute == 0) or ((current_minute % State['GetInterval']) == 0):
                    # infoMsg("d","Server Query...")
                    system_data = {"si": str(Config.WS_ID)}
                    if Config.AUDIT_ON:
                        if Config.AUDIT_DATA is not None:
                            system_data = {"si": str(Config.WS_ID), "audit": str(Config.AUDIT_DATA)}
                            Config.AUDIT_DATA = None
                    try:
                        upload_url = Config.WS_GET_URL + "?" + urlencode(system_data)
                        # infoMsg("d","upload_url==>"+str(upload_url))
                        response = urllib2.urlopen(upload_url)
                        rtn_control = json.load(response)
                        # infoMsg("d","response==>"+str(rtn_control))
                        if ("Status" in rtn_control):
                            if (rtn_control["Status"]==0):
                                ws_NewData=True
                                settingsData=''
                                if "Settings" in rtn_control:
                                    # infoMsg("d","Settings==>>"+str(rtn_control["Settings"]))
                                    settingsData=rtn_control["Settings"]
                                if "Currency" in rtn_control:
                                    if rtn_control["Currency"]=="OK":
                                        ws_Currency=True
                                    else:
                                        infoMsg("w","Data From Station Is Stale, Settings:%s" % str(settingsData))
                                if "Accuracy" in rtn_control:
                                    if rtn_control["Accuracy"]=="OK":ws_Accuracy=True
                                if "Current" in rtn_control:
                                    # infoMsg("d","Current==>>"+str(rtn_control["Current"]))
                                    currentData=rtn_control["Current"]
                                if "Graph" in rtn_control:
                                    graphData=rtn_control["Graph"]
                                    if "Hours" in graphData:
                                        graphXScale=graphData["Hours"]
                                    if "Yesterday" in graphData:
                                        yesterdaysRawDataPoints=graphData["Yesterday"]
                                    if "Today" in graphData:
                                        todaysRawDataPoints=graphData["Today"]
                                    if "ColdFrame" in graphData:
                                        coldframeRawDataPoints=graphData["ColdFrame"]
                                if "YesterdaysPressure" in rtn_control:
                                    yesterdaysPressure=rtn_control["YesterdaysPressure"]
                                if "Last7Temperature" in rtn_control:
                                    last7Temperature=rtn_control["Last7Temperature"]
                                    if "DOW" in last7Temperature:
                                        last7DOW=last7Temperature["DOW"]
                                    if "Low" in last7Temperature:
                                        last7TemperatureLow=last7Temperature["Low"]
                                    if "High" in last7Temperature:
                                        last7TemperatureHigh=last7Temperature["High"]
                                if "Last7ColdFrame" in rtn_control:
                                    last7ColdFrame=rtn_control["Last7ColdFrame"]
                                    if "Low" in last7ColdFrame:
                                        last7ColdFrameLow=last7ColdFrame["Low"]
                                    if "High" in last7ColdFrame:
                                        last7ColdFrameHigh=last7ColdFrame["High"]
                                if "Last7Pressure" in rtn_control:
                                    last7Pressure=rtn_control["Last7Pressure"]
                                    if "DOM" in last7Pressure:
                                        last7DOM=last7Pressure["DOM"]
                                    if "Low" in last7Pressure:
                                        last7PressureLow=last7Pressure["Low"]
                                    if "High" in last7Pressure:
                                        last7PressureHigh=last7Pressure["High"]
                            elif (rtn_control["Status"]==1):
                                infoMsg("i","WS Query Status:%s" % str(rtn_control["Status"]))
                                infoMsg("i","upload_url==>"+str(upload_url))
                                infoMsg("i","response==>"+str(rtn_control))

                            else:
                                infoMsg("i","WS Query Status:%s" % str(rtn_control["Status"]))
                                infoMsg("i","upload_url==>"+str(upload_url))
                                infoMsg("i","response==>"+str(rtn_control))
                        else:
                            infoMsg("i","WS Query Status Not Returned")
                            infoMsg("i","upload_url==>"+str(upload_url))
                            infoMsg("i","response==>"+str(rtn_control))
                    except:
                        infoMsg("w",".....WS Upload Exception:%s" % str(sys.exc_info()[0]))
                        infoMsg("w",".....WS URL             :%s" % str(Config.WS_GET_URL))
                        infoMsg("w",".....WS String          :%s" % str(urlencode(system_data)))

                    if ws_NewData:
                        WS_State['Status']='Fresh'
                        WS_State['DisplayDim']=validateNumericListData(settingsData,'DisplayDim')
                        WS_State['DisplayOn']=validateNumericListData(settingsData,'DisplayOn')
                        WS_State['ColdFrameOn']=validateNumericListData(settingsData,'ColdFrameOn')
                        WS_State['WUUpload']=validateNumericListData(settingsData,'WUUpload')
                        WS_State['Updated']=currentData,'Updated'
                        localData={}
                        localData['Temperature']=validateNumericListData(currentData,'Temperature')
                        localData['ColdFrameTemperature']=validateNumericListData(currentData,'ColdFrameTemperature')
                        localData['DayTime']=validateNumericListData(currentData,'DayTime')
                        localData['OverNight']=validateNumericListData(currentData,'OverNight')
                        localData['RelativeHumidity']=validateNumericListData(currentData,'RelativeHumidity')
                        localData['DewPoint']=validateNumericListData(currentData,'DewPoint')
                        localData['Pressure']=validateNumericListData(currentData,'Pressure')
                        localData['UVIndex']=validateNumericListData(currentData,'UVIndex')

                        if ws_Currency==False:
                            localData['Temperature']=validateNumericListData(current,'temperature')
                            localData['RelativeHumidity']=validateNumericListData(current,'humidity')
                            localData['DewPoint']=validateNumericListData(current,'dewpoint')
                            localData['Pressure']=validateNumericListData(current,'pressure')
                            localData['OverNight']=''
                            localData['ColdFrameTemperature']=''
                            localData['DayTime']=''

                        # infoMsg("d","yesterdaysRawDataPoints:%s" % str(yesterdaysRawDataPoints))
                        yesterdaysDataPoints=validateNumericArray(yesterdaysRawDataPoints)
                        # infoMsg("d","todaysRawDataPoints:%s" % str(todaysRawDataPoints))
                        todaysDataPoints=validateNumericArray(todaysRawDataPoints)
                        # infoMsg("d","coldframeRawDataPoints:%s" % str(coldframeRawDataPoints))
                        coldframeDataPoints=validateNumericArray(coldframeRawDataPoints)
                        # infoMsg("d","yesterdaysDataPoints:%s" % str(yesterdaysDataPoints))
                        # infoMsg("d","todaysDataPoints:%s" % str(todaysDataPoints))
                        # infoMsg("d","coldframeDataPoints:%s" % str(coldframeDataPoints))

                        # L7TemperatureLowDataPoints=validateNumericArray(yesterdaysRawDataPoints)
                        # L7TemperatureHighDataPoints=validateNumericArray(yesterdaysRawDataPoints)
                        # L7ColdFrameLowDataPoints=validateNumericArray(yesterdaysRawDataPoints)
                        # L7ColdFrameHighDataPoints=validateNumericArray(yesterdaysRawDataPoints)
                        # L7PressureLowDataPoints=validateNumericArray(yesterdaysRawDataPoints)
                        # L7PressureHighDataPoints=validateNumericArray(yesterdaysRawDataPoints)

                Config.AUDIT_DATA = None

            last_minute = current_minute

        if ((current_minute == 0) or ((current_minute % State['TrendInterval']) == 0)):
            if calcTrend:
                calcTrend=False
                trend['Pressure']=determine_Trend('Pressure',localData)
                trend['RelativeHumidity']=determine_Trend('RelativeHumidity',localData)
        else:
            calcTrend=True

                                    # default screen is show temperature basic (screen 0)
        if activeScreen==1:         # activeScreen==1 --> station control
            refresh=True
            screen.fill((0, 0, 0))
            set_background()
            displayDim='Bright'
            displayOn='Off'
            coldFrameOn='Off'
            WUUpload='Off'
            stateColour=BLACK
            if WS_State['Status']=='Stale':stateColour=RED
            if WS_State['DisplayDim']==1:displayDim='Dim'
            if WS_State['DisplayOn']==1:displayOn='On'
            if WS_State['ColdFrameOn']==1:coldFrameOn='On'
            if WS_State['WUUpload']>0:WUUpload=str(WS_State['WUUpload'])+" Min"
            textIt(screen, displayDim,    (250,130), 30, stateColour, "arial")
            textIt(screen, displayOn,     (250,220), 30, stateColour, "arial")
            textIt(screen, coldFrameOn,   (550,130), 30, stateColour, "arial")
            textIt(screen, WUUpload,      (550,220), 30, stateColour, "arial")
            textIt(screen, "Station",     (400,50),  80, BLACK, "arial")
        elif activeScreen==2:       # activeScreen==2 --> console control
            refresh=True
            screen.fill((0, 0, 0))
            set_background()
            textIt(screen, "Console",    (400,50), 80, BLACK, "arial")
        elif activeScreen==10:      # activeScreen==10 --> blank screen with big button
            refresh=True
            screen.fill((0, 0, 0))
        else:                       # activeScreen==0 --> weather console
            if ws_NewData or refresh:
                # infoMsg("d","ws_NewData:%s" % str(ws_NewData))
                refresh=False
                screen.fill((0, 0, 0))
                # draw lines, circles, etc.
                pygame.draw.line(screen, BLUE, (210,10),(210,80),1)
                pygame.draw.line(screen, BLUE, (10,90),(790,90),1)
                pygame.draw.circle(screen, BLUE, (710,235), 130, 4)
                # helvetica futura calibri optima regular arial
                # headings
                textIt(screen, "Cold",        (250,20), 15, WHITE, "arial")
                textIt(screen, "Frame",       (250,40), 15, WHITE, "arial")
                textIt(screen, "Daytime",     (330,20), 15, WHITE, "arial")
                textIt(screen, "High",        (330,40), 15, WHITE, "arial")
                textIt(screen, "Overnight",   (415,20), 15, WHITE, "arial")
                textIt(screen, "Low",         (415,40), 15, WHITE, "arial")
                textIt(screen, "Dew",         (500,20), 15, WHITE, "arial")
                textIt(screen, "Point",       (500,40), 15, WHITE, "arial")
                textIt(screen, "Wind",        (615,20), 15, WHITE, "arial")
                textIt(screen, "KPH",         (615,40), 15, GREY, "arial")
                textIt(screen, "Direction",   (740,20), 15, WHITE, "arial")
                # textIt(screen, str(DIM),         (740,40), 15, GREY, "arial")
                # data
                # infoMsg("d","data:%s" % str(localData))
                useColour=WHITE
                if ws_Currency==False:useColour=RED
                # concatenate trend info
                # pressure_string=str(localData['Pressure'])+" mb "
                # humidity_string=str(localData['RelativeHumidity'])+"% "
                pressure_string=str(localData['Pressure'])+" mb "+trend['Pressure']
                humidity_string=str(localData['RelativeHumidity'])+"% "+trend['RelativeHumidity']

                textIt(screen, str(localData['Temperature']),         (710,235),140,   useColour, "arial")
                textIt(screen, str(localData['ColdFrameTemperature']),(250,70),  40,   WHITE, "arial")
                textIt(screen, str(localData['DayTime']),             (330,70),  40,   WHITE, "arial")
                textIt(screen, str(localData['OverNight']),           (415,70),  40,   WHITE, "arial")
                textIt(screen, str(localData['DewPoint']),            (500,70),  40,   WHITE, "arial")
                # textIt(screen, humidity_string,                       (710,155),  30,  GREEN, "arial")
                # textIt(screen, pressure_string,                       (710,315),  30,  GREEN, "arial")
                textIt(screen, str(localData['RelativeHumidity'])+"%",(710,158),  30,  GREEN, "arial")
                textIt(screen, str(localData['Pressure'])+" mb",      (710,312),  30,  GREEN, "arial")
                # textIt(screen, trend['RelativeHumidity'],             (780,155),  30,  WHITE, "arial")
                # textIt(screen, trend['Pressure'],                     (780,315),  30,  WHITE, "arial")
                textIt(screen, trend['RelativeHumidity'],             (710,131),  30,  WHITE, "arial")
                textIt(screen, trend['Pressure'],                     (710,339),  30,  WHITE, "arial")
                # today's temperature graph
                mmlist=yesterdaysDataPoints+todaysDataPoints+coldframeDataPoints
                # infoMsg("d","mmlist:%s" % str(mmlist))
                # fullscreen_message(screen, 'that', WHITE)
                #           x   y   w   h  data array (must be full polygon (reverse second half points) if polygon is True)
                #           |   |   |   |  |                all data to be graphed (empty uses datalist)
                #           |   |   |   |  |                    | (used to determin min/max)
                #           |   |   |   |  |                    |     x scale max (empty to calc it)
                #           |   |   |   |  |                    |     |   line colour
                #           |   |   |   |  |                    |     |   |    box colour
                #           |   |   |   |  |                    |     |   |    |     font colour
                #           |   |   |   |  |                    |     |   |    |     |    show mid line
                #           |   |   |   |  |                    |     |   |    |     |    |    show y scale (All,Ends,Mid)
                #           |   |   |   |  |                    |     |   |    |     |    |    |    show x hatch marks (In,Out,None)
                #           |   |   |   |  |                    |     |   |    |     |    |    |    |       show as filled polygon
                #           |   |   |   |  |                    |     |   |    |     |    |    |    |       |
                line_chart(10,105,520,220,yesterdaysDataPoints,mmlist,23,BLUE,GREY,WHITE,True,'All','Out',False)
                line_chart(10,105,520,220,todaysDataPoints,mmlist,23,RED)
                line_chart(10,105,520,220,coldframeDataPoints,mmlist,23,GREEN)

                if ws_CurrentConditionsSet:
                    # infoMsg("d","ws_CurrentConditionsSet:%s" % str(ws_CurrentConditionsSet))
                    textIt(screen, str(current['winddirection']), (740,70),40,WHITE, "arial")
                    if current['windspeed']>0 and current['windgusts']>0:
                        textIt(screen, str(current['windspeed'])+"G"+str(current['windgusts']), (615,70),40,WHITE, "arial")
                    elif current['windspeed']>0:
                        textIt(screen, str(current['windspeed']), (615,70),40,WHITE, "arial")
                    elif current['windgusts']>0:
                        textIt(screen, str(current['windspeed'])+"G"+str(current['windgusts']), (615,70),40,WHITE, "arial")

                if ws_ForecastSet:
                    # infoMsg("d","ws_ForecastSet:%s" % str(ws_ForecastSet))
                    xpoint = [10, 160, 310, 460, 610]
                    for f in forecast:
                        # infoMsg("d","f %s in forecast==>>%s" % (str(f),str(forecast)))
                        try:
                            icon=forecastIcons[forecast[f]['sky']]
                            # infoMsg("d","icon==>>"+forecast[f]['sky'])
                        except:
                            infoMsg("w",".....Icon Unknown ==>> "+str(forecast[f]['sky']))
                            icon=forecastIcons['unknown']

                        screen.blit(icon,(xpoint[f],405))

                        textIt(screen, str(forecast[f]['weekday']), ((xpoint[f]+60),385),  20,   WHITE, "arial")
                        textIt(screen, str(forecast[f]['high'])+"/"+str(forecast[f]['low']), ((xpoint[f]+100),415),  20,   WHITE, "arial")
                        textIt(screen, "POP", ((xpoint[f]+100),435),  15,   WHITE, "arial")
                        textIt(screen, str(forecast[f]['pop'])+"%", ((xpoint[f]+100),455),  20,   WHITE, "arial")
                    # else:
                    #     textIt(screen, str(forecast[f]['weekday']), ((xpoint[f]+60),385),  20,   WHITE, "arial")

            if current_second != last_second:
                # infoMsg("d","reset time==>>"+str(current_second))
                last_second = current_second
                if current_minute<10:
                    show_minute='0'+str(current_minute)
                else:
                    show_minute=str(current_minute)

                screen.fill((0, 0, 0),(1,1,200,85))
                textIt(screen, str(current_hour)+":"+str(show_minute), (110,50), 60, WHITE, "arial")

        # infoMsg("d","draw buttons")
        for i,b in enumerate(buttons[activeScreen]):
            # print("drawing button %s ===>> %s" % (str(i),str(b)))
            b.draw(screen)

        # infoMsg("d","flip screen / short wait....")
        pygame.display.flip()
        time.sleep(0.01)

    ts.stop()

def reboot_now():
    infoMsg("i","Reboot On Request")
    os.system('reboot')

def shutdown_now():
    infoMsg("i","Shutdown On Request")
    os.system('shutdown -h now')

# http://api.wunderground.com/api/b70268c991a43e07/geolookup/q/44.5,-80.02.json
# http://api.wunderground.com/api/b70268c991a43e07/forecast/q/44.49,-80.04.json
# ============================================================================
# Start Start Start Start Start Start Start Start Start Start Start Start
# ============================================================================
infoMsg("i","..............................")
infoMsg("i","..............................")
infoMsg("i","...Weather Console Starting...")
infoMsg("i","..............................")
infoMsg("i","..............................")

# console state
State= {'Calling': 'init',
        'Brightness1': 10,
        'Brightness2': 20,
        'Brightness3': 60,
        'Brightness4': 200,
        'RefreshInterval': 2,
        'Units': 'SI',
        'Sunrise': 7,
        'Sunset': 19,
        'Night': 1,
        'TrendInterval': 5,
        'TrendMarginPressure': .05,
        'TrendMarginRelativeHumidity': .005}

# weather station state
WS_State= {'Status': 'Stale',
        'Updated': 'Unknown',
        'DisplayDim': 0,
        'DisplayOn': 0,
        'ColdFrameOn': 0,
        'WUUpload': 0}

infoMsg("i","Load Icons")

infoMsg("i","Loading Icons...")
iconPath      = 'icons' # Subdirectory containing UI bitmaps (PNG format)

# forecastIcons = [] # This list gets populated at startup
#
# # Load all icons at startup.
# for file in os.listdir(iconPath):
#   if fnmatch.fnmatch(file, '*.png'):
#     forecastIcons.append(Icon(file.split('.')[0]))
infoMsg("i","pygame.image.get_extended()"+str(pygame.image.get_extended()))
infoMsg("i","os.getcwd()"+str(os.getcwd()))

forecastIcons = {'unknown': pygame.image.load(os.path.join(iconPath , 'wi-na.png')),
            'chanceflurries': pygame.image.load(os.path.join(iconPath , 'wi-day-snow.png')),
            'chancerain': pygame.image.load(os.path.join(iconPath , 'wi-day-rain.png')),
            'chancesleet': pygame.image.load(os.path.join(iconPath , 'wi-day-sleet.png')),
            'chancesnow': pygame.image.load(os.path.join(iconPath , 'wi-day-snow.png')),
            'chancestorms': pygame.image.load(os.path.join(iconPath , 'wi-day-thunderstorm.png')),
            'chancetstorms': pygame.image.load(os.path.join(iconPath , 'wi-day-thunderstorm.png')),
            'clear': pygame.image.load(os.path.join(iconPath , 'wi-day-sunny.png')),
            'cloudy': pygame.image.load(os.path.join(iconPath , 'wi-cloudy.png')),
            'flurries': pygame.image.load(os.path.join(iconPath , 'wi-snow.png')),
            'fog': pygame.image.load(os.path.join(iconPath , 'wi-fog.png')),
            'hazy': pygame.image.load(os.path.join(iconPath , 'wi-day-haze.png')),
            'mostlycloudy': pygame.image.load(os.path.join(iconPath , 'wi-cloudy.png')),
            'partlycloudy': pygame.image.load(os.path.join(iconPath , 'wi-day-cloudy.png')),
            'mostlysunny': pygame.image.load(os.path.join(iconPath , 'wi-day-cloudy.png')),
            'partlysunny': pygame.image.load(os.path.join(iconPath , 'wi-day-cloudy.png')),
            'rain': pygame.image.load(os.path.join(iconPath , 'wi-rain.png')),
            'sleet': pygame.image.load(os.path.join(iconPath , 'wi-sleet.png')),
            'snow': pygame.image.load(os.path.join(iconPath , 'wi-snow.png')),
            'sunny': pygame.image.load(os.path.join(iconPath , 'wi-day-sunny.png')),
            'tstorms': pygame.image.load(os.path.join(iconPath , 'wi-storm-showers.png')),
            'nt_chanceflurries': pygame.image.load(os.path.join(iconPath , 'wi-night-snow.png')),
            'nt_chancerain': pygame.image.load(os.path.join(iconPath , 'wi-night-rain.png')),
            'nt_chancesleet': pygame.image.load(os.path.join(iconPath , 'wi-night-sleet.png')),
            'nt_chancesnow': pygame.image.load(os.path.join(iconPath , 'wi-night-snow.png')),
            'nt_chancestorms': pygame.image.load(os.path.join(iconPath , 'wi-night-storm-showers.png')),
            'nt_chancetstorms': pygame.image.load(os.path.join(iconPath , 'wi-night-storm-showers.png')),
            'nt_clear': pygame.image.load(os.path.join(iconPath , 'wi-night-clear.png')),
            'nt_cloudy': pygame.image.load(os.path.join(iconPath , 'wi-night-cloudy.png')),
            'nt_flurries': pygame.image.load(os.path.join(iconPath , 'wi-night-snow.png')),
            'nt_fog': pygame.image.load(os.path.join(iconPath , 'wi-night-fog.png')),
            'nt_hazy': pygame.image.load(os.path.join(iconPath , 'wi-night-fog.png')),
            'nt_mostlycloudy': pygame.image.load(os.path.join(iconPath , 'wi-night-cloudy.png')),
            'nt_partlycloudy': pygame.image.load(os.path.join(iconPath , 'wi-night-partly-cloudy.png')),
            'nt_mostlysunny': pygame.image.load(os.path.join(iconPath , 'wi-night-partly-cloudy.png')),
            'nt_partlysunny': pygame.image.load(os.path.join(iconPath , 'wi-night-partly-cloudy.png')),
            'nt_rain': pygame.image.load(os.path.join(iconPath , 'wi-night-showers.png')),
            'nt_sleet': pygame.image.load(os.path.join(iconPath , 'wi-night-rain.png')),
            'nt_snow': pygame.image.load(os.path.join(iconPath , 'wi-night-snow.png')),
            'nt_sunny': pygame.image.load(os.path.join(iconPath , 'wi-stars.png')),
            'nt_tstorms': pygame.image.load(os.path.join(iconPath , 'wi-night-thunderstorm.png'))}

infoMsg("i","Define Buttons...")
buttons = [
# TODO this stuff
  # Screen mode 0 is main view screen of current status
  [ScreenButton((710,380, 80, 80),  bg='box80',  fg='sun-4-64',     cb=cycle_brightness,value=0),
   ScreenButton((620,380, 80, 80),  bg='box80',  fg='services-64',  cb=goto_screen,     value=1),
   ScreenButton((580,105,260,260),                                  cb=emptyCallback,   value=2),
   ScreenButton((  0,105,520,240),                                  cb=emptyCallback,   value=3)],

  # Screen 1 for station control
  [ScreenButton(( 10,390,180, 80),  bg='shutdown',  cb=station_action,value=16),
   ScreenButton((200,390,180, 80),  bg='restart',   cb=station_action,value=17),
   ScreenButton((390,390,180, 80),  bg='off',       cb=station_action,value=18),
   ScreenButton((610, 10,180, 80),  bg='console',   cb=goto_screen,  value=2),
   ScreenButton(( 10,100,180, 80),  bg='dim180',    cb=station_action,value=1),
   ScreenButton(( 10,190,180, 80),  bg='display180',cb=station_action,value=2),
   ScreenButton((610,100,180, 80),  bg='coldframe', cb=station_action,value=3),
   ScreenButton((610,190,180, 80),  bg='wuupload',  cb=station_action,value=4),
   ScreenButton((610,390,180, 80),  bg='done',      cb=goto_screen,  value=0)],

  # Screen 2 for console control
  [ScreenButton((390,390,180, 80),  bg='off',       cb=app_Off,       value=0),
   ScreenButton((200,390,180, 80),  bg='restart',   cb=app_Off,       value=1),
   ScreenButton(( 10,390,180, 80),  bg='shutdown',  cb=app_Off,       value=2),
   ScreenButton((610,390,180, 80),  bg='done',      cb=goto_screen,   value=1)],

  # Screen mode 3 is interesting facts
  [ScreenButton((610,390,180, 80),  bg='done',                      cb=goto_screen,     value=0)],

  # Screen mode 4 is chart choser
  [ScreenButton((610,390,180, 80),  bg='done',                      cb=goto_screen,     value=0),
   ScreenButton((580,105,260,100),                                  cb=emptyCallback,   value=2),
   ScreenButton((580,205,260,100),                                  cb=emptyCallback,   value=2),
   ScreenButton((580,305,260,100),                                  cb=emptyCallback,   value=2)],

  # Screen mode 5 is interesting facts
  [ScreenButton((610,390,180, 80),  bg='done',                      cb=goto_screen,     value=0)],
  # Screen mode 6 is interesting facts
  [ScreenButton((610,390,180, 80),  bg='done',                      cb=goto_screen,     value=0)],
  # Screen mode 7 is interesting facts
  [ScreenButton((610,390,180, 80),  bg='done',                      cb=goto_screen,     value=0)],
  # Screen mode 8 is interesting facts
  [ScreenButton((610,390,180, 80),  bg='done',                      cb=goto_screen,     value=0)],

  # Screen 9 for numeric input
  [ScreenButton((  0,  0,320, 60), color=GREEN, bg='box'),
   ScreenButton((180,120, 60, 60), color=GREEN, bg='0',         cb=emptyCallback, value=20),
   ScreenButton((  0,180, 60, 60), color=GREEN, bg='1',         cb=emptyCallback, value=21),
   ScreenButton((120,180, 60, 60), color=GREEN, bg='3',         cb=emptyCallback, value=23),
   ScreenButton(( 60,180, 60, 60), color=GREEN, bg='2',         cb=emptyCallback, value=22),
   ScreenButton((  0,120, 60, 60), color=GREEN, bg='4',         cb=emptyCallback, value=24),
   ScreenButton(( 60,120, 60, 60), color=GREEN, bg='5',         cb=emptyCallback, value=25),
   ScreenButton((120,120, 60, 60), color=GREEN, bg='6',         cb=emptyCallback, value=26),
   ScreenButton((  0, 60, 60, 60), color=GREEN, bg='7',         cb=emptyCallback, value=27),
   ScreenButton(( 60, 60, 60, 60), color=GREEN, bg='8',         cb=emptyCallback, value=28),
   ScreenButton((120, 60, 60, 60), color=GREEN, bg='9',         cb=emptyCallback, value=29),
   ScreenButton((240,120, 80, 60), color=GREEN, bg='clear',     cb=emptyCallback, value=30),
   ScreenButton((180,180,140, 60), color=GREEN, bg='update',    cb=emptyCallback, value=32),
   ScreenButton((180, 60,140, 60), color=GREEN, bg='cancel',    cb=emptyCallback, value=31)],

  # Screen mode 10 blank screen with full screen button
  [ScreenButton((  0,  0,800,480),                              cb=screen_on,     value=0)],
   ]

infoMsg("i","Initializing Configuration")

# make sure we don't have a REFRESH_INTERVAL > 60
if (Config.REFRESH_INTERVAL is None) or (Config.REFRESH_INTERVAL > 60):
    infoMsg("w","The application's 'REFRESH_INTERVAL' cannot be empty or greater than 60")
    sys.exit(1)
if (Config.WS_GET_INTERVAL is None) or (Config.WS_GET_INTERVAL > 60) or (Config.WS_GET_INTERVAL < 1):
    infoMsg("w","The application's 'WS_GET_INTERVAL' cannot be empty, less than 1 or greater than 60")
    sys.exit(1)
# if (Config.WU_GET_INTERVAL is None) or (Config.WU_GET_INTERVAL > 60) or (Config.WU_GET_INTERVAL < 1):
#     infoMsg("w","The application's 'WU_GET_INTERVAL' cannot be empty, less than 1 or greater than 60")
#     sys.exit(1)

infoMsg("i","LOCAL_STATION_ID===========>"+Config.LOCAL_STATION_ID)
infoMsg("i","LOCAL_STATION_TIMEZONE=====>"+Config.LOCAL_STATION_TIMEZONE)

infoMsg("i","SUNRISE====================>"+str(Config.SUNRISE))
infoMsg("i","SUNSET=====================>"+str(Config.SUNSET))

infoMsg("i","REFRESH_INTERVAL===========>"+str(Config.REFRESH_INTERVAL))
infoMsg("i","DISPLAY_ON=================>"+str(Config.DISPLAY_ON))
infoMsg("i","DISPLAY_DIM================>"+str(Config.DISPLAY_DIM))
infoMsg("i","TREND_INTERVAL=============>"+str(Config.TREND_INTERVAL))
infoMsg("i","TREND_PRESSURE_LONG========>"+str(Config.TREND_PRESSURE_LONG))
infoMsg("i","TREND_MARGIN_PRESSURE======>"+str(Config.TREND_MARGIN_PRESSURE))
infoMsg("i","TREND_MARGIN_HUMIDITY======>"+str(Config.TREND_MARGIN_HUMIDITY))

infoMsg("i","WS_GET_DATA================>"+str(Config.WS_GET_DATA))
infoMsg("i","WS_GET_INTERVAL============>"+str(Config.WS_GET_INTERVAL))
infoMsg("i","WS_GET_URL=================>"+Config.WS_GET_URL)

infoMsg("i","WS_PUT_DATA================>"+str(Config.WS_PUT_DATA))
infoMsg("i","WS_PUT_URL=================>"+Config.WS_PUT_URL)

infoMsg("i","WU_GET_DATA================>"+str(Config.WU_GET_DATA))
infoMsg("i","WU_GET_INTERVAL============>"+str(Config.WU_GET_INTERVAL))
infoMsg("i","WU_GET_URL=================>"+Config.WU_GET_URL)

infoMsg("i","AUDIT_ON===================>"+str(Config.AUDIT_ON))
infoMsg("i","AUDIT_DATA=================>"+str(Config.AUDIT_DATA))

infoMsg("i","Successfully Set Configuration Values")

State['GetInterval']=Config.WS_GET_INTERVAL
State['RefreshInterval']=Config.REFRESH_INTERVAL
State['Sunrise']=Config.SUNRISE
State['Sunset']=Config.SUNSET
State['TrendInterval']=Config.TREND_INTERVAL
State['TrendMarginPressure']=Config.TREND_MARGIN_PRESSURE
State['TrendMarginRelativeHumidity']=Config.TREND_MARGIN_HUMIDITY

infoMsg("i","Load Saved State")

loadState()

infoMsg("i","State (Post Load)")
infoMsg("i","  Brightness1...................%s" % str(State['Brightness1']))
infoMsg("i","  Brightness2...................%s" % str(State['Brightness2']))
infoMsg("i","  Brightness3...................%s" % str(State['Brightness3']))
infoMsg("i","  Brightness4...................%s" % str(State['Brightness4']))
infoMsg("i","  RefreshInterval...............%s" % str(State['RefreshInterval']))
infoMsg("i","  Units.........................%s" % str(State['Units']))
infoMsg("i","  Sunrise.......................%s" % str(State['Sunrise']))
infoMsg("i","  Sunset........................%s" % str(State['Sunset']))
infoMsg("i","  Night.........................%s" % str(State['Night']))
infoMsg("i","  TrendInterval.................%s" % str(State['TrendInterval']))
infoMsg("i","  TrendMarginPressure...........%s" % str(State['TrendMarginPressure']))
infoMsg("i","  TrendMarginRelativeHumidity...%s" % str(State['TrendMarginRelativeHumidity']))

infoMsg("i","Initializing Pygame")

pygame.init()
screen = pygame.display.set_mode(size, pygame.FULLSCREEN)
pygame.mouse.set_visible(False)

# Load all icons at startup.
icons = [] # This list gets populated at startup

infoMsg("i","Loading Icons...")
for file in os.listdir(iconPath):
  if fnmatch.fnmatch(file, '*.png'):
    icons.append(Icon(file.split('.')[0]))

# Assign Icons to Buttons, now that they're loaded
infoMsg("i","Assigning Buttons...")
for s in buttons:        # For each screenful of buttons...
  for b in s:            #  For each button on screen...
    for i in icons:      #   For each icon...
      if b.bg == i.name: #    Compare names; match?
        b.iconBg = i     #     Assign Icon to Button
        b.bg     = None  #     Name no longer used; allow garbage collection
      if b.fg == i.name:
        b.iconFg = i
        b.fg     = None

infoMsg("i","Loading Background...")
# background_image = pygame.image.load('icons/iceberg.png')
background_image = pygame.image.load('icons/flower.png')
# background_image = pygame.image.load('icons/deathvalley.png')
# background_image = pygame.image.load('icons/pipstone.png')

infoMsg("i","Initializing Touch Screen")

ts = Touchscreen()
for touch in ts.touches:
    touch.on_press = touch_handler
    touch.on_release = touch_handler
    touch.on_move = touch_handler

ts.run()

running = True
refresh = True
activeScreen = 0

ws_CurrentConditionsSet = False
ws_ForecastSet = False

trending={}
trending['Pressure']=-99
trending['RelativeHumidity']=-99
trend={}
trend['Pressure']='?'
trend['RelativeHumidity']='?'
calcTrend=True
# trend['Pressure']=ARROW['Dash']
# trend['RelativeHumidity']=ARROW['Dash']

current_hour = datetime.datetime.now().hour
determine_brightness(current_hour)

infoMsg("i","Initialization complete!")

# Go main
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting application\n")
        sys.exit(0)

    # clean up here
    saveState('__main__')

    if (SHUTDOWN):
        infoMsg("i","Shutdown....")
        shutdown_now()

    if (REBOOT):
        infoMsg("i","Reboot....")
        reboot_now()

    sys.exit(0)
