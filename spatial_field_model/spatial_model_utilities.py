# -*- coding: utf-8 -*-
"""
Created on Sun Oct 28 18:14:57 2012

@author: martin
"""

import numpy as np
import os.path
import netCDF4
import matplotlib.pyplot as plt
import codecs
import re
from datetime import datetime, timedelta
import unicodedata


def equilibrium_moisture(P, Q, T):

    # saturated vapor pressure (at each location, size n x 1)
    Pws = np.exp(54.842763 - 6763.22/T - 4.210 * np.log(T) + 0.000367*T + np.tanh(0.0415*(T - 218.8)) 
        * (53.878 - 1331.22/T - 9.44523 * np.log(T) + 0.014025*T))
      
    # water vapor pressure (at each location, size n x 1)
    Pw = P * Q / (0.622 + (1 - 0.622) * Q)
    
    # relative humidity (percent, at each location, size n x 1)
    H = 100 * Pw / Pws;
    
    # drying/wetting fuel equilibrium moisture contents (location specific,
    # n x 1)
    Ed = 0.924*H**0.679 + 0.000499*np.exp(0.1*H) + 0.18*(21.1 + 273.15 - T)*(1 - np.exp(-0.115*H))
    Ew = 0.618*H**0.753 + 0.000454*np.exp(0.1*H) + 0.18*(21.1 + 273.15 - T)*(1 - np.exp(-0.115*H))

    # remap values
    return Ed * 0.01, Ew * 0.01
    

def render_spatial_field(m, lon, lat, field, title):
    """
    Render a geo field over a basemap.  However the standard basemap
    does not seem to have sufficient resolution.
    TODO: can I obtain more detailed topography?
    """
    dx = (np.max(lon) - np.min(lon)) / 5
    dy = (np.max(lat) - np.min(lat)) / 5
    lat_rng = (np.min(lat), np.max(lat))
    lon_rng = (np.min(lon), np.max(lon))
    m.drawparallels(np.arange(lat_rng[0],lat_rng[1], dy))
    m.drawmeridians(np.arange(lon_rng[0],lon_rng[1], dx))
    m.drawcoastlines()
#    imf = m.transform_scalar(field.ravel(), lon.ravel(), lat.ravel(), lon.shape[0], lat.shape[1])
    x, y = m(lon, lat)
    m.pcolormesh(x, y, field, alpha = 0.6, edgecolor = 'none')
#    m.imshow(imf)
    plt.axis('equal')
    plt.title(title)


def load_wrf_data(data_file,
                  var_names = ['T2', 'Q2', 'PSFC', 'XLAT', 'XLONG', 'RAINNC', 'Times']):
    """
    Load required variables from the file data_file.  A list of variables
    is either supplied or the default list is used which contains the following
    variables: 'T2', 'Q2', 'PSFC', 'XLAT', 'XLONG', 'RAINNC', 'Times'
    """
    v = {}
    d = netCDF4.Dataset(os.path.join(data_file))
    for vname in var_names:
        v[vname] = d.variables[vname][:,...]
    d.close()
    
    # recode times into datetime objects
    if v.has_key('Times'):
        t = v['Times']
        tp = []
        for tm in t:
            tp.append(datetime.strptime(''.join(tm), '%Y-%m-%d_%H:%M:%S'))
        v['Times'] = tp

    return v


def load_station_data(station_file):
    """
    Load all available fuel moisture data from the station information.
    """
    f = codecs.open(station_file, 'r', encoding = 'utf-8')
    station_data = {}
    station_data['name'] = f.readline().strip()

    # next line is location string, not interesting    
    f.readline()
    
    # next 2 lines are lattitude & longitude
    lat_lon_re = re.compile("\D+(\d{2,3})\D+(\d{2})\D+(\d{2})")

    l = f.readline()
    mo = lat_lon_re.match(l)
    lat_info = map(lambda x: int(x), mo.groups())
    station_data['lat'] = lat_info[0] + lat_info[1] / 60.0 + lat_info[2] / 3600.0

    l = f.readline()
    mo = lat_lon_re.match(l)
    lon_info = map(lambda x: int(x), mo.groups())
    station_data['lon'] = -(lon_info[0] + lon_info[1] / 60.0 + lon_info[2] / 3600.0)
    
    # read lines 5 through 14
    for i in range(5,8):
        f.readline()

    moisture = {}
    rh = {}
    rain = {}
    temp = {}
    fuel_temp = {}
    while True:

        # read in and parse date
        l = f.readline()
        date = datetime.strptime(l.strip(), '%B %d, %Y')
        
        # read lines until a line starts with daily
        while l[0] < '0' or l[0] > '9' and len(l) > 0:
            l = f.readline()
            
        if len(l) == 0:
            break
        
        while l[0] >= '0' and l[0] <= '9' and len(l) > 0:
            fields = filter(lambda x: len(x) > 0, l.split('\t'))
            time = datetime.strptime(fields[0], "%I %p")
            timed = timedelta(0, time.hour * 3600)
            mtime = date + timed
            if len(fields) != 12:
                print fields
            temp[mtime] = float(fields[5])
            fuel_temp[mtime] = float(fields[6])
            moisture[mtime] = float(fields[7])
            rh[mtime] = float(fields[8])
            rain[mtime] = float(fields[11])
            l = f.readline()
        
        while l[:5] != 'Daily' and len(l) > 0:
            l = f.readline()
            
        if len(l) == 0:
            break
                
    station_data['fuel_moisture'] = moisture
    station_data['relative_humidity'] = rh
    station_data['rain'] = rain
    station_data['T'] = temp
    station_data['fuel_T'] = fuel_temp
    
    f.close()
    
    return station_data
    

def find_closest_grid_point(slon, slat, glon, glat):
    """
    Finds the closest grid piont to the given station longitude/lattitude.
    """
    closest = np.argmin((slon - glon)**2 + (slat - glat)**2)
    return np.unravel_index(closest, glon.shape)


def match_stations_to_gridpoints(sts, lon, lat):
    """
    Finds the nearest grid point for each station and stores it in the station dictionary.
    The nearest grid point is stored as the value of 'nearest_grid_point'.
    """
    for s in sts.values():
        i, j = find_closest_grid_point(s['lon'], s['lat'], lon, lat)
        s['nearest_grid_point'] = (i,j)
        

def load_stations_from_files(station_data_dir, station_list):
    """
    Loads station data from files given to me by AK and stores all station data
    in a dictionary indexed by station file names.
    
        stations = load_stations_from_files(station_data_dir, station_list)
    
    """
    stations = {}
    for s in station_list:
        st = load_station_data(os.path.join(station_data_dir, s))
        stations[s] = st

    return stations


def match_sample_times(tm1, tm2):
    """
    Match times assuming both times are sorted datetime arrays.  Returns
    the matching times and the indices of the matching times in the first
    and in the second array.
    
       isect, indx1, indx2 = match_sample_times(tm1, tm2) 
        
    """
    i, j = 0, 0
    isect = []
    indx1 = []
    indx2 = []
    while i < len(tm1) and j < len(tm2):
        while i < len(tm1) and tm1[i] < tm2[j]:
            i += 1
        while j < len(tm2) and i < len(tm1) and tm1[i] > tm2[j]:
            j += 1
        if i < len(tm1) and j < len(tm2) and tm1[i] == tm2[j]:
            isect.append(tm1[i])
            indx1.append(i)
            indx2.append(j)
            i += 1
            j += 1
            
    return isect, indx1, indx2