class Config:
    # refresh interval
    REFRESH_INTERVAL = 2

    # initial display
    DISPLAY_ON = True
    DISPLAY_DIM = False

    # trend settings
    TREND_INTERVAL = 15           # interval in minutes to test trends
    TREND_PRESSURE_LONG = False   # default True -> compare to yesterdays pressure, False -> compare to Interval ago
    TREND_MARGIN_PRESSURE = .005  # % difference to report full up or down swing
    TREND_MARGIN_HUMIDITY = .05   # % difference to report full up or down swing

    # local station info
    LOCAL_STATION_ID = "6100245999979349"
    LOCAL_STATION_TIMEZONE = "America/Eastern"

    # logging config
    LOGGING_DEBUG = False    # log on debug -->  if both set to false min
    LOGGING_INFO = True      # log on info  -->  level is warning
    LOGGING_BYTES = 20480    # bytes in log file before archive
    LOGGING_ROTATION = 3     # number of log files to archive
    LOGGING_PRINT = False    # set to true to print to console

    AUDIT_ON = False         # Return Audit Data if True
    AUDIT_DATA = None       # Audit data to be returned

    # daytime
    SUNRISE = 5
    SUNSET = 19

    # Weather Underground - Get Forecast Info - max of 500 times per day
    WU_GET_DATA = True
    WU_GET_INTERVAL = 1  # hours  -  current unused <<<<<<=========
    # WU_GET_URL = "http://api.wunderground.com/api/b70268c991a43e07/forecast/q/44.49,-80.04.json"
    WU_GET_URL = "http://api.wunderground.com/api/b70268c991a43e07/forecast/conditions/q/pws:MD3238.json"

    # Get Weather Station Data
    WS_GET_DATA = True
    WS_GET_INTERVAL = 2  # minutes
    WS_GET_URL = "http://192.168.0.99/weather/assets/ajax/aQueryCurrent.php"
    WS_ID = LOCAL_STATION_ID

    # Put Weather Station Control Data
    WS_PUT_DATA = True
    WS_PUT_URL = "http://192.168.0.99/weather/assets/ajax/aActionToControl.php"
    WS_ID = LOCAL_STATION_ID
