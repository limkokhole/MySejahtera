
# Note, run with python 3, not python 2.
import sys, time

import simplejson
import uuid, base64

import requests

import geopy
import geopy.distance

import webbrowser

direction_dict = {'west': 270, 'east': 90, 'north': 0, 'south': 180}

UA = 'Mozilla/5.0 (Linux; U; Android 2.2.1; en-us; Nexus One Build/FRG83) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1'
search_url = 'https://mysejahtera.malaysia.gov.my/register/api/nearby/hotspots?type=search'

max_radius_km = 1.00

fake_deviceId = str(uuid.uuid1())
fake_authToken = fake_deviceId
fake_bAth = base64.b64encode( (fake_deviceId + ':' + fake_authToken).encode() ).decode() # btoa() in js

# You don't encode space with %20 which causes HTTP 500 err
BASIC_AUTH = 'Basic ' + fake_bAth


def get_session():
    s = requests.Session()
    s.headers = {
        'User-Agent': UA,
        'Accept': 'application/json',
        'Accept-Charset': 'UTF-8',
        'Accept-Encoding': 'gzip',
        'Content-Type': 'application/json',
        'Content-Encoding': 'gzip',
        'Authorization': BASIC_AUTH,
        'Connection': 'Keep-Alive'
    }
    return s


def call_api(lat, lng, s):
    post_d = '[{"lat":' + str(lat) + ',"lng":' + str(lng) + ',"classification":"LOW_RISK_NS"}]'
    #print('post_d' + repr(post_d))
    while 1:
        try: # Normally is fast enough, so use 0.1 seconds timeout
            r = s.post(search_url, data=post_d, timeout=(0.1, 0.1))
            if r.status_code == 404:
                print(r.text)
                print('404 not found error. Abort.')
                sys.exit(1)
            elif r.status_code == 500:
                print(r.text)
                print('Server error. Abort.')
                sys.exit(1)
            else:
                j = r.json()
                #print(j)
                # {'hotSpots': [], 'zoneType': 'RED', 'messages': {'ms_MY': 'Hai {name}, terdapat 1 kes COVID-19 dalam lingkungan radius 1km dari lokasi ini yang dilaporkan dalam masa 14 hari yang lepas.', 'en_US': 'Hi {name}, there have been 1 reported case(s) of COVID-19 within a 1km radius from your searched location in the last 14 days.'}, 'note': None}
                msg = j.get('messages', {}).get('ms_MY', '')
                if 'tiada kes' in msg:
                    expect_case = 0
                else:
                    expect_case = int(msg.split(' kes ')[0].split(' terdapat ')[1])
                print('Case' + ('s' if expect_case > 1 else '') + ': ' + str(expect_case))
                break
        except (IndexError, simplejson.errors.JSONDecodeError):
            print(r.text)
            print('API error. Retry after 0.1 second. Or double check your post data.')
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            print('Network error. Retry after 0.1 second.')
        time.sleep(0.1)
    return expect_case


def get_1km_lat_long(lat, lng, move_direction, km):
    # Credit: https://stackoverflow.com/a/61460267/1074998

    #print('Adding from lat, long: ' + str(lat) + ', ' + str(lng))
    # Define starting point. Point(latitude=None, longitude=None, altitude=None)
    start = geopy.Point(lat, lng)

    # Define a general distance object, initialized with a distance of 1 km.
    d = geopy.distance.distance(kilometers = km)

    # Use the `destination` method with a bearing of 0 degrees (which is north)
    # in order to go from point `start` 1 km to north.
    # The output is 48 52m 0.0s N, 2 21m 0.0s E (or Point(48.861992239749355, 2.349, 0.0)).
    # A bearing of 90 degrees corresponds to East, 180 degrees is South, and so on.
    direction = direction_dict[move_direction]
    print('\nMove direction: ' + move_direction)
    p = d.destination(point=start, bearing=direction) # ret: point
    print('Increased to lat, long: ' + str(p.latitude) + ', ' + str(p.longitude))
    return p.latitude, p.longitude


def towards_quadrant(lng_case, lat_case, lat, lng, s, unit, count, until_case, major, perpendicular, nth_side):
    if perpendicular:
        head = ' [Real] [' + str(nth_side) + '/4] '
    else:
        head = ' [Preparing] [' + str(nth_side) + '/4] '

    if major:
        major_txt = '[Major]'
    else:
        major_txt = '[Minor]'

    arrow = ''
    if lng_case == 'east':
        vertical_prefix = '\t\t'
    else: # == 'west'
        vertical_prefix = ''
    if lat_case == 'north': # this should put on top, for towards_half no nid
        arrow+='\n' + vertical_prefix + '▲\n' + vertical_prefix + '▲\n' + vertical_prefix + '▲\n' + vertical_prefix + '|\n'
    if lng_case == 'east':
        arrow+='\n ----- ► ► ► ► ►\n'
    if lng_case == 'west':
        arrow+='\n◄ ◄ ◄ ◄ ◄ -----\n'
    if lat_case == 'south':
        arrow+='\n' + vertical_prefix + '|\n' + vertical_prefix + '▼\n' + vertical_prefix + '▼\n' + vertical_prefix + '▼\n'
    print(arrow)
    print('\n' + head + '[Quadrant] ' + major_txt + ' [ ' + str(count) + ' ] towards quadrant by ' + str(unit * 1000) + ' Meter')

    if (major and (count > 63)) or (not major and (count > 33)): #3(0.1, 0.01, 0.001) major + offset = 63 and 3 minor + offset = 33
        print(head + '[Quadrant] ' + major_txt + ' Possibly >1 hotspots around the area and not possible locate accurately. Abort.')
        sys.exit(1)
    prev_lat = lat
    prev_lng = lng
    lat, lng = get_1km_lat_long(lat, lng, lng_case, unit) # unit 0.001 means 1 Meter
    lat, lng = get_1km_lat_long(lat, lng, lat_case, unit)
    case = call_api(lat, lng, s)
    if case > 1: # "Must"(not optional) check in every step to avoid chance of outer 1 causes forward a bit. And it also help to stop early without solely rely on final distance.
        print(head + '[Quadrant] ' + major_txt + ' Possibly >1 hotspots around the area and not possible locate accurately. Abort.')
        sys.exit(1)
    elif case == until_case:

        #should't reverse both until_case and direction here since it use prev estimated lat/long

        print('\n ############# [Quadrant] Moved by ' + str(unit) + ' Completed #############')
        print(head + '[Quadrant] ' + major_txt + ' current lat/long at ' + str(prev_lat) + ', ' + str(prev_lng))
        if unit == 0.1:
            print(head + '[Quadrant] ' + major_txt + ' Recude to 10 Meters step, Hotspot center estimated at ' + str(prev_lat) + ', ' + str(prev_lng) + '\n')
            return towards_quadrant(lng_case, lat_case, prev_lat, prev_lng, s, 0.01, count+1, until_case, major, perpendicular, nth_side)
        elif unit == 0.01:
            print(head + '[Quadrant] ' + major_txt + ' Recude to 1 Meter step, Hotspot center estimated at ' + str(prev_lat) + ', ' + str(prev_lng) + '\n')
            return towards_quadrant(lng_case, lat_case, prev_lat, prev_lng, s, 0.001, count+1, until_case, major, perpendicular, nth_side)
        else:
            print(head + '[Quadrant] ' + ('Major' if major else 'Minor side') + ' located at ' + str(prev_lat) + ', ' + str(prev_lng))
            return prev_lat, prev_lng
    else:
        return towards_quadrant(lng_case, lat_case, lat, lng, s, unit, count+1, until_case, major, perpendicular, nth_side)


def towards_half(lng_case, lat_case, lat, lng, s, unit, orientation, count, until_case, major, perpendicular, nth_side):
    if perpendicular:
        head = ' [Real] [' + str(nth_side) + '/4] '
    else:
        head = ' [Preparing] [' + str(nth_side) + '/4] '

    if major:
        major_txt = '[Major]'
    else:
        major_txt = '[Minor]'

    arrow = ''
    if lng_case == 'east':
        arrow+='\n ----- ► ► ► ► ►\n'
    if lng_case == 'west':
        arrow+='\n◄ ◄ ◄ ◄ ◄ -----\n'
    if lat_case == 'north':
        arrow+='\n\t\t▲\n\t\t▲\n\t\t▲\n\t\t|\n'
    if lat_case == 'south':
        arrow+='\n\t\t|\n\t\t▼\n\t\t▼\n\t\t▼\n'
    print(arrow)
    print('\n' + head + '[Half] ' + major_txt + ' [ ' + str(count) + ' ] towards ' + orientation + ' by ' + str(unit * 1000) + ' Meter')

    if (major and (count > 63)) or (not major and (count > 33)): #3(0.1, 0.01, 0.001) major + offset = 63 and 3 minor + offset = 33
        print(head + '[Half] ' + major_txt + ' Possibly >1 hotspots around the area and not possible locate accurately. Abort.')
        sys.exit(1)
    prev_lat = lat
    prev_lng = lng
    if orientation == 'vertical':
        lat, lng = get_1km_lat_long(lat, lng, lat_case, unit) # unit 0.001 means 1 Meter
    else:
        lat, lng = get_1km_lat_long(lat, lng, lng_case, unit)
    case = call_api(lat, lng, s)
    if case > 1: # "Must"(not optional) check in every step to avoid chance of outer 1 causes forward a bit. And it also help to stop early without solely rely on final distance.
        print(head + '[Half] ' + major_txt + ' Possibly >1 hotspots around the area and not possible locate accurately. Abort.')
        sys.exit(1)
    elif case == until_case:

        #should't reveser both until_case and direction here since it use prev estimated lat/long

        print('\n ############# [Half] Moved by ' + str(unit) + ' Completed #############')
        print(head + '[Half] ' + major_txt + ' current lat/long at ' + str(prev_lat) + ', ' + str(prev_lng))
        if unit == 0.1:
            print(head + '[Half] ' + major_txt + ' Reduce to 10 Meters step, Hotspot center estimated at ' + str(prev_lat) + ', ' + str(prev_lng) + '\n')
            return towards_half(lng_case, lat_case, prev_lat, prev_lng, s, 0.01, orientation, count+1, until_case, major, perpendicular, nth_side)
        elif unit == 0.01:
            print(head + '[Half] ' + major_txt + ' Recude to 1 Meter step, Hotspot center estimated at ' + str(prev_lat) + ', ' + str(prev_lng) + '\n')
            return towards_half(lng_case, lat_case, prev_lat, prev_lng, s, 0.001, orientation, count+1, until_case, major, perpendicular, nth_side)
        else:
            print(head + '[Half] ' + ('Major' if major else 'Minor side') + ' located at ' + str(prev_lat) + ', ' + str(prev_lng))
            return prev_lat, prev_lng
    else:
        return towards_half(lng_case, lat_case, lat, lng, s, unit, orientation, count+1, until_case, major, perpendicular, nth_side)


def check_outer_km(lat, lng, s, unit, check_case_only):

    west_lat, west_lng = get_1km_lat_long(lat, lng, 'west', max_radius_km)
    west_case = call_api(west_lat, west_lng, s)

    east_lat, east_lng = get_1km_lat_long(lat, lng, 'east', max_radius_km)
    east_case = call_api(east_lat, east_lng, s)

    north_lat, north_lng = get_1km_lat_long(lat, lng, 'north', max_radius_km)
    north_case = call_api(north_lat, north_lng, s)

    south_lat, south_lng = get_1km_lat_long(lat, lng, 'south', max_radius_km)
    south_case = call_api(south_lat, south_lng, s)

    if not ((west_case <= 1) and (east_case <= 1) and (north_case <= 1) and (south_case <= 1)):
        print('\nThis lat/long can\'t be used since outer 1KM not all 1 or 0 case. Abort.')
        if not check_case_only:
            sys.exit(1)
    else:
        return west_case, east_case, north_case, south_case


def print_side_banner(major):
        if major:
            print('\n\n ############# Moving to major side ############# ')
        else:
            print('\n\n ############# Moving to minor side ############# ')


def calc_chord_center(input_lat, input_lng, minor_lat, minor_lng, major_lat, major_lng, s, perpendicular_orientation):
    center_lat = (minor_lat + major_lat) / 2.0
    center_lng = (minor_lng + major_lng) / 2.0

    # To ensure only 1 case round this area, double the km from 1km to 2km from center point.
    print('\n\n ############# Verify false positive ############# ')
    print('Chord center lat: ' + str(center_lat) + ' Long: ' + str(center_lng))
    # Should use geodesic instead of great_circle, since calc lat/long that time is .distance which used geodesic, or else the comparison inconsistent, https://stackoverflow.com/questions/19412462 , https://geopy.readthedocs.io/en/stable/#module-geopy.distance
    distance = geopy.distance.geodesic( (minor_lat, minor_lng), (major_lat, major_lng) ).km
    print('Diameter of hotspot chord circle in km: ' + str(distance))
    if distance > 2: # 1 km radius * 2 , no nid care for offset, and failed better than inaccurate.
        print('Distance is too long which possible caused by >1 cases round the area. Abort.')
        sys.exit(1)
    else:
        print('Distance valid so far.')
    lat = center_lat
    lng = center_lng
    # init for each major/minor, like main()
    unit = 0.1
    count = 1

    # Not do test case here and always try 2nd, and all major not big deal since got check max distance at the end
    # west_case, east_case, north_case, south_case = check_outer_km(lat, lng, s, 0.94) # Should < 1 unlikei main()

    if perpendicular_orientation in ('horizontal', 'vertical'):
        print_side_banner(True)
        if (perpendicular_orientation == 'horizontal'):
            minor_lat, minor_lng = towards_half('east', None, lat, lng, s, unit, 'horizontal', count, 0, True, True, 3) # major side
            major_lat, major_lng = towards_half('west', None, lat, lng, s, unit, 'horizontal', count, 0, True, True, 4) # major side
        elif (perpendicular_orientation == 'vertical'):
            minor_lat, minor_lng = towards_half(None, 'south', lat, lng, s, unit, 'vertical', count, 0, True, True, 3) # major side
            major_lat, major_lng = towards_half(None, 'north', lat, lng, s, unit, 'vertical', count, 0, True, True, 4) # major side
        calc_diameter_center(input_lat, input_lng, minor_lat, minor_lng, major_lat, major_lng)
 
    elif (perpendicular_orientation == 'east_south'):

        print_side_banner(True)
        minor_lat, minor_lng = towards_quadrant('west', 'north', lat, lng, s, unit, count, 0, True, True, 3) # major side
        major_lat, major_lng = towards_quadrant('east', 'south', lat, lng, s, unit, count, 0, True, True, 4) # major side

        calc_diameter_center(input_lat, input_lng, minor_lat, minor_lng, major_lat, major_lng)

    elif (perpendicular_orientation == 'east_north'):

        print_side_banner(True)
        minor_lat, minor_lng = towards_quadrant('west', 'south', lat, lng, s, unit, count, 0, True, True, 3) # major side
        major_lat, major_lng = towards_quadrant('east', 'north', lat, lng, s, unit, count, 0, True, True, 4) # major side

        calc_diameter_center(input_lat, input_lng, minor_lat, minor_lng, major_lat, major_lng)

    else: 
        print('[2nd, Quadrant !1] Possible not able calculate correctly. Abort.')


def calc_diameter_center(input_lat, input_lng, minor_lat, minor_lng, major_lat, major_lng):

    print('Minor: ' + str(minor_lat) + ',' + str(minor_lng))
    print('Major: ' + str(major_lat) + ',' + str(major_lng))
    center_lat = (minor_lat + major_lat) / 2.0
    center_lng = (minor_lng + major_lng) / 2.0

    # To ensure only 1 case round this area, double the km from 1km to 2km from center point.
    print('\n\n ############# Verify false positive ############# ')
    # Should use geodesic instead of great_circle, since calc lat/long that time is .distance which used geodesic, or else the comparison inconsistent, https://stackoverflow.com/questions/19412462 , https://geopy.readthedocs.io/en/stable/#module-geopy.distance
    distance = geopy.distance.geodesic( (minor_lat, minor_lng), (major_lat, major_lng) ).km
    print('Diameter of hotspot circle in km: ' + str(distance))
    if distance > 2: # 1 km radius * 2 , no nid care for offset, and failed better than inaccurate. 
        print('Distance is too long which possible caused by >1 cases round the area. Abort.')
    else:
        print('Distance is valid.')
        center_lat_str = str(center_lat) 
        center_lng_str = str(center_lng) 
        print('\n\n ############# Result ############# ')
        print('\nHotspot center probably located at ' + center_lat_str + ', ' + center_lng_str)
        print('You can double check (expected results: all 0s) by re-run this script with that lat/long.\n')
        # https://stackoverflow.com/a/25993441/1074998
        google_map_link = 'http://www.google.com/maps/place/' + center_lat_str + ',' + center_lng_str
        print('Google map link: ' + google_map_link)
        hotspot_circle_link = 'https://www.nanchatte.com/map/circleService-e.html?lat=' + center_lat_str + '&lng=' + center_lng_str + '&z=15&m=lat:' + center_lat_str + ',lng:' + center_lng_str + '&m=lat:' + center_lat_str + ',lng:' + center_lng_str + '&m=lat:' + str(input_lat) + ',lng:' + str(input_lng) + '&c=lat:' + center_lat_str + ',lng:' + center_lng_str + ',r:1000'
        print('Hotspot circle link: ' + hotspot_circle_link)
        # https://stackoverflow.com/a/832338/1074998
        webbrowser.open(google_map_link)
        webbrowser.open(hotspot_circle_link)


def main(lat, lng, s, west_case, east_case, north_case, south_case):

    # init for each major/minor
    unit = 0.1
    count = 1

    total_cases = west_case + east_case + north_case + south_case
    if total_cases in (0, 4):

        # ',<space>' to make it easier copy-paste to re-run with this script.
        print('[M 0/4] Hotspot center is nearby/same with input lat/long which located at ' + str(lat) + ', ' + str(lng))

    elif total_cases == 3: # Total 3: 3 sides are 1 but only 1 side is 0 is not make sense.

        print('[M 3] Hotspot center is weird but should nearby with input lat/long which located at ' + str(lat) + ', ' + str(lng))

    elif total_cases == 1:

        print_side_banner(True)
        if west_case == 1:
            minor_lat, minor_lng = towards_half('east', None, lat, lng, s, unit, 'horizontal', count, 0, False, False, 1) # minor side
            major_lat, major_lng = towards_half('west', None, lat, lng, s, unit, 'horizontal', count, 0, True, False, 2) # major side
            perpendicular_orientation = 'vertical'

        elif east_case == 1:
            minor_lat, minor_lng = towards_half('west', None, lat, lng, s, unit, 'horizontal', count, 0, False, False, 1) # minor side
            major_lat, major_lng = towards_half('east', None, lat, lng, s, unit, 'horizontal', count, 0, True, False, 2) # major side
            perpendicular_orientation = 'vertical'

        elif north_case == 1:
            minor_lat, minor_lng = towards_half(None, 'south', lat, lng, s, unit, 'vertical', count, 0, False, False, 1) # minor side
            major_lat, major_lng = towards_half(None, 'north', lat, lng, s, unit, 'vertical', count, 0, True, False, 2) # major side
            perpendicular_orientation = 'horizontal'

        elif south_case == 1:
            minor_lat, minor_lng = towards_half(None, 'north', lat, lng, s, unit, 'vertical', count, 0, False, False, 1) # minor side
            major_lat, major_lng = towards_half(None, 'south', lat, lng, s, unit, 'vertical', count, 0, True, False, 2) # major side
            perpendicular_orientation = 'horizontal'

        calc_chord_center(lat, lng, minor_lat, minor_lng, major_lat, major_lng, s, perpendicular_orientation)
        
    elif (east_case == 1) and (south_case == 1):

        print_side_banner(False)
        minor_lat, minor_lng = towards_quadrant('west', 'north', lat, lng, s, unit, count, 0, False, False, 1) # minor side

        print_side_banner(True)
        major_lat, major_lng = towards_quadrant('east', 'south', lat, lng, s, unit, count, 0, True, False, 2) # major side

        calc_chord_center(lat, lng, minor_lat, minor_lng, major_lat, major_lng, s, 'east_north')

    elif (east_case == 1) and (north_case == 1):

        print_side_banner(False)
        minor_lat, minor_lng = towards_quadrant('west', 'south', lat, lng, s, unit, count, 0, False, False, 1) # minor side

        print_side_banner(True)
        major_lat, major_lng = towards_quadrant('east', 'north', lat, lng, s, unit, count, 0, True, False, 2) # major side

        calc_chord_center(lat, lng, minor_lat, minor_lng, major_lat, major_lng, s, 'east_south')

    elif (west_case == 1) and (south_case == 1):

        print_side_banner(False)
        minor_lat, minor_lng = towards_quadrant('east', 'north', lat, lng, s, unit, count+1, 0, False, False, 1) # minor side

        print_side_banner(True)
        major_lat, major_lng = towards_quadrant('west', 'south', lat, lng, s, unit, count+1, 0, True, False, 2) # major side

        calc_chord_center(lat, lng, minor_lat, minor_lng, major_lat, major_lng, s, 'east_south')

    elif (west_case == 1) and (north_case == 1):

        print_side_banner(False)
        minor_lat, minor_lng = towards_quadrant('east', 'south', lat, lng, s, unit, count+1, 0, False, False, 1) # minor side

        print_side_banner(True)
        major_lat, major_lng = towards_quadrant('west', 'north', lat, lng, s, unit, count+1, 0, True, False, 2) # major side

        calc_chord_center(lat, lng, minor_lat, minor_lng, major_lat, major_lng, s, 'east_north')

    else: # e.g. west/east both 1 but south/north both 0 come here
        print('[M 2] Hotspot center is weird but should nearby with input lat/long which located at ' + str(lat) + ', ' + str(lng))
    

if __name__ == "__main__":

    lat = None
    lng = None
    import argparse
    parser = argparse.ArgumentParser(description='MySejahtera Hotspot Center Locator')
    parser.add_argument('-c', '--check-case', dest='check_case_only', action='store_true', help='Check cases of provided lat/long without continue to find hotspot.')
    #parser.add_argument('latlong', nargs='?', help='<Latitude>, <Longitude>')
    args, remaining  = parser.parse_known_args()
    # For `python3 hotspot_center_locator.py lat, lnt`, which ',' copy from google map place indicator menu item
    # I know why use "lng" instead of "long" bcoz `long` can be data type keyword
    if len(remaining) >= 2:
        lat = float(remaining[0].rstrip(','))
        lng = float(remaining[1])
    elif ( len(remaining) == 1 ) and (',' in remaining[0]):
        arg_split = remaining[0].split(',')
        lat = float(arg_split[0])
        lng = float(arg_split[1])

    s = get_session()

    while 1:

        if lat is not None and lng is not None: # else wait for input
            print('You provided lat: ' + str(lat) + ' lng: ' + str(lng))
            print('\n\n ############# Start center 1km verification ############# ')
            expect_case = call_api(lat, lng, s)
            print('\n\n ############# Done center 1km verification ############# ')

            if expect_case == 1:
    
                print('\n\n ############# Start outer 1km verification ############# ')
                west_case, east_case, north_case, south_case = check_outer_km(lat, lng, s, 1, args.check_case_only)
                print('\n\n ############# Done outer 1km verification ############# ')
                if not args.check_case_only:
                    print('Start with 100 Meter step')
                    main(lat, lng, s, west_case, east_case, north_case, south_case) # 0.1 means 100 Meters
                    break
            else:
                print('\nOnly if 1 case in current lat/long able to locate by this program. Abort.') # Not impossible(imagine it walk enitre Malaysia map), if it walk to form a big square map to collect all neighbour hotspots(no need entire Malaysia), or calc the circle radian accurately, with more API calls, which is complicated.
                if not args.check_case_only:
                    break

        try:
            reply = input('\nPlease paste <lat, long> OR type \'n\' to exit: ').strip()
        except EOFError: #when use -1 and < list_of_lines_file, last line will raise EOFError
            break
        if (reply and reply[0].lower() != 'n'):
            if ',' in reply:
                lat = float(reply.split(',')[0].strip())
                lng = float(reply.split(',')[1].strip())
            elif ' ' in reply:
                lat = float(reply.split(' ')[0].strip())
                lng = float(reply.split(' ')[1].strip())
            else:
                print('Invalid input. Abort.')
                break
        else:
            break



