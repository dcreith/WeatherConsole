WeatherConsole
==============

WeatherConsole is a Python application making use of a 7" multi-touch screen to
display data from a DB and WeatherUnderground.

See the WeatherPi & WeatherServer repositories for complementary applications
that capture and log the data.

WeatherConsole (weather_console.py) was pulled together from various other Raspberry
Pi projects. The core function paints the screen and waits for touchscreen input while periodically querying for new data via web calls.

Yesterday's and Today's temperatures are pulled from the DB and graphed. Current
information (temperature, humidity, barometric pressure), overnight low, daytime
high are shown.

Forecasts are pulled from WeatherUnderground with the local wind direction and
speed. If WeatherUnderground information is not available it is left blank.


**Weather**
![Weather](images/WeatherConsole.jpg?raw=true "Weather")

**Console Control**
![Console Control](images/WeatherConsole_2.jpg?raw=true "Console")

**Station Control**
![StationControl](images/WeatherConsole_3.jpg?raw=true "Station")

**Prerequisites:**
 
Raspberry Pi (anything that supports the 7" multi touch screen)
7" Multi Touch Screen

**Setup**

7" Multi Touch Screen - plug in, get libs

Cron - see sample crontab, I reboot once a day to cover any interruptions

**Get repo:**

    git clone https://github.com/dcreith/WeatherConsole.git

**Usage:**

cd home/pi/weatherconsole

sudo python weather_console.py
