from pyproj import Proj, Transformer
import geohash2


# =========================
# 🔹 DMS → DD
# =========================
def dms_to_dd(deg, minutes, seconds, direction):
    dd = deg + minutes / 60 + seconds / 3600
    if direction in ['S', 'W']:
        dd = -dd
    return dd


# =========================
# 🔹 DD → DMS
# =========================
def dd_to_dms(dd):
    deg = int(dd)
    temp = abs(dd - deg) * 60
    minutes = int(temp)
    seconds = (temp - minutes) * 60
    return deg, minutes, seconds


# =========================
# 🔹 DD → DDM
# =========================
def dd_to_ddm(dd):
    deg = int(dd)
    minutes = (abs(dd) - abs(deg)) * 60
    return deg, minutes


# =========================
# 🔹 DDM → DD
# =========================
def ddm_to_dd(deg, minutes, direction):
    dd = deg + minutes / 60
    if direction in ['S', 'W']:
        dd = -dd
    return dd


# =========================
# 🔹 DD → UTM
# =========================
def dd_to_utm(lat, lon):
    zone = int((lon + 180) / 6) + 1
    proj = Proj(proj='utm', zone=zone, ellps='WGS84')
    x, y = proj(lon, lat)
    return zone, x, y


# =========================
# 🔹 UTM → DD
# =========================
def utm_to_dd(zone, x, y):
    proj = Proj(proj='utm', zone=zone, ellps='WGS84')
    lon, lat = proj(x, y, inverse=True)
    return lat, lon


# =========================
# 🔹 DD → Geohash
# =========================
def dd_to_geohash(lat, lon, precision=8):
    return geohash2.encode(lat, lon, precision=precision)


# =========================
# 🔹 Geohash → DD
# =========================
def geohash_to_dd(code):
    lat, lon = geohash2.decode(code)
    return lat, lon


# =========================
# 🔥 MAIN MENU
# =========================
def main():
    print("\n🌍 Coordinate Converter Calculator 🌍")
    print("--------------------------------------")
    print("1. DMS → DD")
    print("2. DD → DMS")
    print("3. DDM → DD")
    print("4. DD → DDM")
    print("5. DD → UTM")
    print("6. UTM → DD")
    print("7. DD → Geohash")
    print("8. Geohash → DD")

    choice = input("\nEnter choice: ")

    # =========================
    # 1. DMS → DD
    # =========================
    if choice == "1":
        deg = float(input("Degrees: "))
        minutes = float(input("Minutes: "))
        seconds = float(input("Seconds: "))
        direction = input("Direction (N/S/E/W): ")
        print("Result:", dms_to_dd(deg, minutes, seconds, direction))

    # =========================
    # 2. DD → DMS
    # =========================
    elif choice == "2":
        dd = float(input("Decimal Degrees: "))
        print("Result:", dd_to_dms(dd))

    # =========================
    # 3. DDM → DD
    # =========================
    elif choice == "3":
        deg = float(input("Degrees: "))
        minutes = float(input("Decimal Minutes: "))
        direction = input("Direction (N/S/E/W): ")
        print("Result:", ddm_to_dd(deg, minutes, direction))

    # =========================
    # 4. DD → DDM
    # =========================
    elif choice == "4":
        dd = float(input("Decimal Degrees: "))
        print("Result:", dd_to_ddm(dd))

    # =========================
    # 5. DD → UTM
    # =========================
    elif choice == "5":
        lat = float(input("Latitude: "))
        lon = float(input("Longitude: "))
        zone, x, y = dd_to_utm(lat, lon)
        print(f"Zone: {zone}, Easting: {x}, Northing: {y}")

    # =========================
    # 6. UTM → DD
    # =========================
    elif choice == "6":
        zone = int(input("Zone: "))
        x = float(input("Easting: "))
        y = float(input("Northing: "))
        lat, lon = utm_to_dd(zone, x, y)
        print(f"Latitude: {lat}, Longitude: {lon}")

    # =========================
    # 7. DD → Geohash
    # =========================
    elif choice == "7":
        lat = float(input("Latitude: "))
        lon = float(input("Longitude: "))
        print("Geohash:", dd_to_geohash(lat, lon))

    # =========================
    # 8. Geohash → DD
    # =========================
    elif choice == "8":
        code = input("Geohash: ")
        lat, lon = geohash_to_dd(code)
        print(f"Latitude: {lat}, Longitude: {lon}")

    else:
        print("Invalid choice!")


# Run program
if __name__ == "__main__":
    main()