
from os.path import join as osjoin
from os import chdir
import pyproj
import sys
import ntpath
import glob
from itertools import chain
from PIL.ExifTags import TAGS
from PIL import Image
import csv
from datetime import datetime as dt

def multiple_file_types(*patterns):
    """ get around Python's lack of regex support in glob/iglob """
    return chain.from_iterable(glob.iglob(pattern) for pattern in patterns)


def path_leaf(path):
    """ guaranteed filename from path; works on Win / OSX / *nix """
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


def latlon(path):
    """
    returns a dict of lat, lon, alt, filename values, given
    an input file path as string
    example: latlong("path/to/file") or latlon(variable)
    """
    img = Image.open(path)
    info = img._getexif()
    filename = path_leaf(path)
    # build a dict of decoded exif keys and values
    decoded = dict((TAGS.get(key, key), value) for key, value in info.items())
    #print(decoded['GPSInfo'].keys())
    info = {
        "filename": filename,
        "lat": None,
        "lon": None,
        "timestamp": None,
        "altitude": None,
        "direction": None,
        "directiontype": None,
        "orientation": None
    }
    # ensure that this photo contains GPS data, or return an empty dict:
    if not decoded.get('GPSInfo'):
        return info
    lat = [float(x) / float(y) for x, y in decoded['GPSInfo'][2]]
    lon = [float(x) / float(y) for x, y in decoded['GPSInfo'][4]]
    try:
        alt = float(decoded['GPSInfo'][6][0]) / float(decoded['GPSInfo'][6][1])
    except:
        #alt not exist
        #print("no altitude info:{}".format(filename))
        alt = 'unknown'
    direction = float(decoded['GPSInfo'][17][0]) / float(decoded['GPSInfo'][17][1])
    directiontype = decoded['GPSInfo'][16]
    timestamp = decoded['DateTimeOriginal']
    orientation = decoded['Orientation']
    # assign values to dict
    info['filename'] = filename
    info['lat'] = (lat[0] + lat[1] / 60)
    info['lon'] = (lon[0] + lon[1] / 60)
    info['timestamp'] = dt.strptime(
        timestamp,
        "%Y:%m:%d %H:%M:%S").strftime("%Y/%m/%d %H:%M:%S")
    info['altitude'] = alt
    info['direction'] = direction
    info['directiontype'] = directiontype
    info['orientation'] = orientation
    # corrections if necessary
    if decoded['GPSInfo'][1] == "S":
        info['lat'] *= -1
    if decoded['GPSInfo'][3] == "W":
        info['lon'] *= -1
    # if we're below sea level, the value's negative
    try:
        if decoded['GPSInfo'][5] == 1:
            info['altitude'] *= -1
    except:
        print("no alt reference:{}".format(filename))
        
    z, l, x, y = project(info['lon'], info['lat'])
    easting = x
    northing = y
    info['utm_zone'] = z + l
    info['Easting'] = x
    info['Northing'] = y
    
    return info


def write_csv(photofolder, csv_file="fileinfo.csv"):
    """ coroutine for writing dicts to a CSV as rows """
    header_written = False
    nowtime = dt.now().strftime('%Y%m%d_%H%M%S_')
    csv_path = osjoin(photofolder, nowtime + csv_file)
    # create a CSV writer object
    with open(csv_path, "w") as f:
        while True:
            data = (yield)
            # don't bother writing anything unless we have GPS data
            if data['lat']:
                dw = csv.DictWriter(f, sorted(data.keys()))
                if not header_written:
                    dw.writeheader()
                    header_written = True
                dw.writerow(data)
        
                
# end - from process_exif.py

def copy_exifresults(photofolder):
    """Copies image metadata to csv
    
    Arguments:
        photofolder {folder path} -- [folder path of photos, csv will be saved to this folder]
    """
    print("Getting a list of all jpg files in the current dir...")
    
    # change current directory
    chdir(photofolder)
    images = multiple_file_types("*.jpg", "*.JPG", "*.jpeg", "*.JPEG")
    
    
    try:
        # initialise a CSV writer coroutine
        output = write_csv(photofolder)
        output.next()
        # pipe each GPS-data-containing dict from the generator to the CSV writer
        print("writing to CSV...")
        [output.send(data) for data in (latlon(image) for image in images)]
    except IOError:
        print(
            """
            There was a read/write error. Ensure that you have read and write
            permissions for the current directory
            """
        )
    finally:
    
        sys.exit(1)
        AddMessage("And we're done.")
        output.close()
        
    return output
    
# https://gist.github.com/twpayne/4409500
def zone(coordinates):
    if 56 <= coordinates[1] < 64 and 3 <= coordinates[0] < 12:
        return 32
    if 72 <= coordinates[1] < 84 and 0 <= coordinates[0] < 42:
        if coordinates[0] < 9:
            return 31
        elif coordinates[0] < 21:
            return 33
        elif coordinates[0] < 33:
            return 35
        return 37
    return int((coordinates[0] + 180) / 6) + 1

def letter(coordinates):
    return 'CDEFGHJKLMNPQRSTUVWXX'[int((coordinates[1] + 80) / 8)]


def project(coordinates):
    z = zone(coordinates)
    l = letter(coordinates)
    if z not in _projections:
        _projections[z] = pyproj.Proj(proj='utm', zone=z, ellps='WGS84')
    x, y = _projections[z](coordinates[0], coordinates[1])
    if y < 0:
        y += 10000000
    return z, l, x, y


def unproject(z, l, x, y):
    if z not in _projections:
        _projections[z] = pyproj.Proj(proj='utm', zone=z, ellps='WGS84')
    if l < 'N':
        y -= 10000000
    lng, lat = _projections[z](x, y, inverse=True)
    return (lng, lat)

def makexyfrom(csv_path):
    
    output_layer = csv_path.replace('.csv', '_lyr')
    saved_Layer = csv_path.replace('.csv', '.lyr')
    MakeXYEventLayer_management(csv_path, output_layer, )

photofolder = ''
csv_path = copy_exifresults(photofolder)
    