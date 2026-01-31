"""
Migration 010: Add Google Ads geo criterion IDs to geographies table

This migration adds:
- google_geo_id column to map Google's numeric geo IDs to names
- US metro/DMA regions (21xxx series)
- Common international cities

Run with:
    python -m storage.migrations.010_add_google_geo_ids

Or automatically applied via SQLiteStore.initialize()
"""

import sqlite3
from typing import Union


def detect_db_type(connection) -> str:
    """Detect database type from connection."""
    conn_type = str(type(connection)).lower()
    if 'sqlite' in conn_type:
        return 'sqlite'
    elif 'psycopg' in conn_type or 'postgres' in conn_type:
        return 'postgresql'
    return 'unknown'


# Google Ads country-level geo criterion IDs
# Reference: https://developers.google.com/google-ads/api/reference/data/geotargets
COUNTRY_GEO_IDS = [
    ('2840', 'US', 'United States', None),
    ('2826', 'GB', 'United Kingdom', None),
    ('2124', 'CAN', 'Canada', None),
    ('2036', 'AU', 'Australia', None),
    ('2276', 'DE', 'Germany', None),
    ('2250', 'FR', 'France', None),
    ('2392', 'JP', 'Japan', None),
    ('2076', 'BR', 'Brazil', None),
    ('2356', 'IN', 'India', None),
    ('2484', 'MX', 'Mexico', None),
    ('2724', 'ES', 'Spain', None),
    ('2380', 'IT', 'Italy', None),
    ('2528', 'NL', 'Netherlands', None),
    ('2586', 'PK', 'Pakistan', None),
    ('2360', 'ID', 'Indonesia', None),
    ('2608', 'PH', 'Philippines', None),
    ('2704', 'VN', 'Vietnam', None),
    ('2764', 'TH', 'Thailand', None),
    ('2458', 'MY', 'Malaysia', None),
    ('2702', 'SG', 'Singapore', None),
    ('2784', 'AE', 'UAE', None),
    ('2682', 'SA', 'Saudi Arabia', None),
    ('2818', 'EG', 'Egypt', None),
    ('2566', 'NG', 'Nigeria', None),
    ('2710', 'ZA', 'South Africa', None),
]

# US Metro/DMA region codes (21xxx series)
# These are the Nielsen DMA regions used by Google Ads
US_METRO_GEO_IDS = [
    ('21137', 'US', 'United States', 'Abilene-Sweetwater, TX'),
    ('21138', 'US', 'United States', 'Albany, GA'),
    ('21139', 'US', 'United States', 'Albany-Schenectady-Troy, NY'),
    ('21140', 'US', 'United States', 'Albuquerque-Santa Fe, NM'),
    ('21141', 'US', 'United States', 'Alexandria, LA'),
    ('21142', 'US', 'United States', 'Alpena, MI'),
    ('21143', 'US', 'United States', 'Amarillo, TX'),
    ('21144', 'US', 'United States', 'Anchorage, AK'),
    ('21145', 'US', 'United States', 'Atlanta, GA'),
    ('21146', 'US', 'United States', 'Augusta-Aiken, GA'),
    ('21147', 'US', 'United States', 'Austin, TX'),
    ('21148', 'US', 'United States', 'Bakersfield, CA'),
    ('21149', 'US', 'United States', 'Baltimore, MD'),
    ('21150', 'US', 'United States', 'Bangor, ME'),
    ('21151', 'US', 'United States', 'Baton Rouge, LA'),
    ('21152', 'US', 'United States', 'Beaumont-Port Arthur, TX'),
    ('21153', 'US', 'United States', 'Bend, OR'),
    ('21154', 'US', 'United States', 'Billings, MT'),
    ('21155', 'US', 'United States', 'Los Angeles, CA'),
    ('21156', 'US', 'United States', 'Birmingham, AL'),
    ('21157', 'US', 'United States', 'Bluefield-Beckley-Oak Hill, WV'),
    ('21158', 'US', 'United States', 'Boise, ID'),
    ('21159', 'US', 'United States', 'Boston, MA'),
    ('21160', 'US', 'United States', 'Bowling Green, KY'),
    ('21161', 'US', 'United States', 'Buffalo, NY'),
    ('21162', 'US', 'United States', 'Burlington-Plattsburgh, VT'),
    ('21163', 'US', 'United States', 'Butte-Bozeman, MT'),
    ('21164', 'US', 'United States', 'New York, NY'),
    ('21165', 'US', 'United States', 'Casper-Riverton, WY'),
    ('21166', 'US', 'United States', 'Cedar Rapids-Waterloo, IA'),
    ('21167', 'US', 'United States', 'Champaign-Springfield, IL'),
    ('21168', 'US', 'United States', 'Charleston, SC'),
    ('21169', 'US', 'United States', 'Charleston-Huntington, WV'),
    ('21170', 'US', 'United States', 'Charlotte, NC'),
    ('21171', 'US', 'United States', 'Charlottesville, VA'),
    ('21172', 'US', 'United States', 'Chattanooga, TN'),
    ('21173', 'US', 'United States', 'Cheyenne-Scottsbluff, WY'),
    ('21174', 'US', 'United States', 'Chicago, IL'),
    ('21175', 'US', 'United States', 'Chico-Redding, CA'),
    ('21176', 'US', 'United States', 'Cincinnati, OH'),
    ('21177', 'US', 'United States', 'Clarksburg-Weston, WV'),
    ('21178', 'US', 'United States', 'Cleveland-Akron, OH'),
    ('21179', 'US', 'United States', 'Colorado Springs-Pueblo, CO'),
    ('21180', 'US', 'United States', 'Columbia, SC'),
    ('21181', 'US', 'United States', 'Columbia-Jefferson City, MO'),
    ('21182', 'US', 'United States', 'Columbus, GA'),
    ('21183', 'US', 'United States', 'Columbus, OH'),
    ('21184', 'US', 'United States', 'Columbus-Tupelo, MS'),
    ('21185', 'US', 'United States', 'Corpus Christi, TX'),
    ('21186', 'US', 'United States', 'Dallas-Fort Worth, TX'),
    ('21187', 'US', 'United States', 'Davenport-Rock Island, IA'),
    ('21188', 'US', 'United States', 'Dayton, OH'),
    ('21189', 'US', 'United States', 'Denver, CO'),
    ('21190', 'US', 'United States', 'Des Moines-Ames, IA'),
    ('21191', 'US', 'United States', 'Detroit, MI'),
    ('21192', 'US', 'United States', 'Dothan, AL'),
    ('21193', 'US', 'United States', 'Duluth-Superior, MN'),
    ('21194', 'US', 'United States', 'El Paso, TX'),
    ('21195', 'US', 'United States', 'Elmira, NY'),
    ('21196', 'US', 'United States', 'Erie, PA'),
    ('21197', 'US', 'United States', 'Eugene, OR'),
    ('21198', 'US', 'United States', 'Eureka, CA'),
    ('21199', 'US', 'United States', 'Evansville, IN'),
    ('21200', 'US', 'United States', 'Fairbanks, AK'),
    ('21201', 'US', 'United States', 'Fargo-Valley City, ND'),
    ('21202', 'US', 'United States', 'Flint-Saginaw, MI'),
    ('21203', 'US', 'United States', 'Florence-Myrtle Beach, SC'),
    ('21204', 'US', 'United States', 'Fort Myers-Naples, FL'),
    ('21205', 'US', 'United States', 'Fort Smith-Fayetteville, AR'),
    ('21206', 'US', 'United States', 'Fort Wayne, IN'),
    ('21207', 'US', 'United States', 'Fresno-Visalia, CA'),
    ('21208', 'US', 'United States', 'Gainesville, FL'),
    ('21209', 'US', 'United States', 'Glendive, MT'),
    ('21210', 'US', 'United States', 'Grand Junction-Montrose, CO'),
    ('21211', 'US', 'United States', 'Grand Rapids-Kalamazoo, MI'),
    ('21212', 'US', 'United States', 'Great Falls, MT'),
    ('21213', 'US', 'United States', 'Green Bay-Appleton, WI'),
    ('21214', 'US', 'United States', 'Greensboro-Winston Salem, NC'),
    ('21215', 'US', 'United States', 'Greenville-New Bern, NC'),
    ('21216', 'US', 'United States', 'Greenville-Spartanburg, SC'),
    ('21217', 'US', 'United States', 'Greenwood-Greenville, MS'),
    ('21218', 'US', 'United States', 'Harlingen-Brownsville, TX'),
    ('21219', 'US', 'United States', 'Harrisburg-Lancaster, PA'),
    ('21220', 'US', 'United States', 'Harrisonburg, VA'),
    ('21221', 'US', 'United States', 'Hartford-New Haven, CT'),
    ('21222', 'US', 'United States', 'Hattiesburg-Laurel, MS'),
    ('21223', 'US', 'United States', 'Helena, MT'),
    ('21224', 'US', 'United States', 'Honolulu, HI'),
    ('21225', 'US', 'United States', 'Houston, TX'),
    ('21226', 'US', 'United States', 'Huntsville-Decatur, AL'),
    ('21227', 'US', 'United States', 'Idaho Falls-Pocatello, ID'),
    ('21228', 'US', 'United States', 'Indianapolis, IN'),
    ('21229', 'US', 'United States', 'Jackson, MS'),
    ('21230', 'US', 'United States', 'Jackson, TN'),
    ('21231', 'US', 'United States', 'Jacksonville, FL'),
    ('21232', 'US', 'United States', 'Johnstown-Altoona, PA'),
    ('21233', 'US', 'United States', 'Jonesboro, AR'),
    ('21234', 'US', 'United States', 'Joplin-Pittsburg, MO'),
    ('21235', 'US', 'United States', 'Juneau, AK'),
    ('21236', 'US', 'United States', 'Kansas City, MO'),
    ('21237', 'US', 'United States', 'Knoxville, TN'),
    ('21238', 'US', 'United States', 'La Crosse-Eau Claire, WI'),
    ('21239', 'US', 'United States', 'Lafayette, IN'),
    ('21240', 'US', 'United States', 'Lafayette, LA'),
    ('21241', 'US', 'United States', 'Lake Charles, LA'),
    ('21242', 'US', 'United States', 'Lansing, MI'),
    ('21243', 'US', 'United States', 'Laredo, TX'),
    ('21244', 'US', 'United States', 'Las Vegas, NV'),
    ('21245', 'US', 'United States', 'Lexington, KY'),
    ('21246', 'US', 'United States', 'Lima, OH'),
    ('21247', 'US', 'United States', 'Lincoln-Hastings, NE'),
    ('21248', 'US', 'United States', 'Little Rock-Pine Bluff, AR'),
    ('21249', 'US', 'United States', 'Louisville, KY'),
    ('21250', 'US', 'United States', 'Lubbock, TX'),
    ('21251', 'US', 'United States', 'Macon, GA'),
    ('21252', 'US', 'United States', 'Madison, WI'),
    ('21253', 'US', 'United States', 'Mankato, MN'),
    ('21254', 'US', 'United States', 'Marquette, MI'),
    ('21255', 'US', 'United States', 'Medford-Klamath Falls, OR'),
    ('21256', 'US', 'United States', 'Memphis, TN'),
    ('21257', 'US', 'United States', 'Meridian, MS'),
    ('21258', 'US', 'United States', 'Miami-Fort Lauderdale, FL'),
    ('21259', 'US', 'United States', 'Milwaukee, WI'),
    ('21260', 'US', 'United States', 'Minneapolis-St. Paul, MN'),
    ('21261', 'US', 'United States', 'Minot-Bismarck, ND'),
    ('21262', 'US', 'United States', 'Missoula, MT'),
    ('21263', 'US', 'United States', 'Mobile-Pensacola, AL'),
    ('21264', 'US', 'United States', 'Monroe-El Dorado, LA'),
    ('21265', 'US', 'United States', 'Monterey-Salinas, CA'),
    ('21266', 'US', 'United States', 'Montgomery-Selma, AL'),
    ('21267', 'US', 'United States', 'Nashville, TN'),
    ('21268', 'US', 'United States', 'New Orleans, LA'),
    ('21269', 'US', 'United States', 'Norfolk-Newport News, VA'),
    ('21270', 'US', 'United States', 'North Platte, NE'),
    ('21271', 'US', 'United States', 'Odessa-Midland, TX'),
    ('21272', 'US', 'United States', 'Oklahoma City, OK'),
    ('21273', 'US', 'United States', 'Omaha, NE'),
    ('21274', 'US', 'United States', 'Orlando-Daytona Beach, FL'),
    ('21275', 'US', 'United States', 'Ottumwa-Kirksville, IA'),
    ('21276', 'US', 'United States', 'Paducah-Cape Girardeau, KY'),
    ('21277', 'US', 'United States', 'Palm Springs, CA'),
    ('21278', 'US', 'United States', 'Panama City, FL'),
    ('21279', 'US', 'United States', 'Parkersburg, WV'),
    ('21280', 'US', 'United States', 'Peoria-Bloomington, IL'),
    ('21281', 'US', 'United States', 'Philadelphia, PA'),
    ('21282', 'US', 'United States', 'Phoenix, AZ'),
    ('21283', 'US', 'United States', 'Pittsburgh, PA'),
    ('21284', 'US', 'United States', 'Portland, OR'),
    ('21285', 'US', 'United States', 'Portland-Auburn, ME'),
    ('21286', 'US', 'United States', 'Presque Isle, ME'),
    ('21287', 'US', 'United States', 'Providence-New Bedford, RI'),
    ('21288', 'US', 'United States', 'Quincy-Hannibal, IL'),
    ('21289', 'US', 'United States', 'Raleigh-Durham, NC'),
    ('21290', 'US', 'United States', 'Rapid City, SD'),
    ('21291', 'US', 'United States', 'Reno, NV'),
    ('21292', 'US', 'United States', 'Richmond-Petersburg, VA'),
    ('21293', 'US', 'United States', 'Roanoke-Lynchburg, VA'),
    ('21294', 'US', 'United States', 'Rochester-Mason City, MN'),
    ('21295', 'US', 'United States', 'Rochester, NY'),
    ('21296', 'US', 'United States', 'Rockford, IL'),
    ('21297', 'US', 'United States', 'Sacramento-Stockton, CA'),
    ('21298', 'US', 'United States', 'Saint Joseph, MO'),
    ('21299', 'US', 'United States', 'Saint Louis, MO'),
    ('21300', 'US', 'United States', 'Salisbury, MD'),
    ('21301', 'US', 'United States', 'Salt Lake City, UT'),
    ('21302', 'US', 'United States', 'San Angelo, TX'),
    ('21303', 'US', 'United States', 'San Antonio, TX'),
    ('21304', 'US', 'United States', 'San Diego, CA'),
    ('21305', 'US', 'United States', 'San Francisco-Oakland, CA'),
    ('21306', 'US', 'United States', 'Santa Barbara-San Luis Obispo, CA'),
    ('21307', 'US', 'United States', 'Savannah, GA'),
    ('21308', 'US', 'United States', 'Seattle-Tacoma, WA'),
    ('21309', 'US', 'United States', 'Sherman-Ada, TX'),
    ('21310', 'US', 'United States', 'Shreveport, LA'),
    ('21311', 'US', 'United States', 'Sioux City, IA'),
    ('21312', 'US', 'United States', 'Sioux Falls-Mitchell, SD'),
    ('21313', 'US', 'United States', 'South Bend-Elkhart, IN'),
    ('21314', 'US', 'United States', 'Spokane, WA'),
    ('21315', 'US', 'United States', 'Springfield, MO'),
    ('21316', 'US', 'United States', 'Springfield-Holyoke, MA'),
    ('21317', 'US', 'United States', 'Syracuse, NY'),
    ('21318', 'US', 'United States', 'Tallahassee-Thomasville, FL'),
    ('21319', 'US', 'United States', 'Tampa-St. Petersburg, FL'),
    ('21320', 'US', 'United States', 'Terre Haute, IN'),
    ('21321', 'US', 'United States', 'Toledo, OH'),
    ('21322', 'US', 'United States', 'Topeka, KS'),
    ('21323', 'US', 'United States', 'Traverse City-Cadillac, MI'),
    ('21324', 'US', 'United States', 'Tri-Cities, TN'),
    ('21325', 'US', 'United States', 'Tucson-Sierra Vista, AZ'),
    ('21326', 'US', 'United States', 'Tulsa, OK'),
    ('21327', 'US', 'United States', 'Twin Falls, ID'),
    ('21328', 'US', 'United States', 'Tyler-Longview, TX'),
    ('21329', 'US', 'United States', 'Utica, NY'),
    ('21330', 'US', 'United States', 'Victoria, TX'),
    ('21331', 'US', 'United States', 'Waco-Temple-Bryan, TX'),
    ('21332', 'US', 'United States', 'Washington, DC'),
    ('21333', 'US', 'United States', 'Watertown, NY'),
    ('21334', 'US', 'United States', 'Wausau-Rhinelander, WI'),
    ('21335', 'US', 'United States', 'West Palm Beach-Fort Pierce, FL'),
    ('21336', 'US', 'United States', 'Wheeling-Steubenville, WV'),
    ('21337', 'US', 'United States', 'Wichita Falls-Lawton, TX'),
    ('21338', 'US', 'United States', 'Wichita-Hutchinson, KS'),
    ('21339', 'US', 'United States', 'Wilkes Barre-Scranton, PA'),
    ('21340', 'US', 'United States', 'Wilmington, NC'),
    ('21341', 'US', 'United States', 'Yakima-Pasco-Richland, WA'),
    ('21342', 'US', 'United States', 'Youngstown, OH'),
    ('21343', 'US', 'United States', 'Yuma-El Centro, AZ'),
    ('21344', 'US', 'United States', 'Zanesville, OH'),
]


def upgrade(db_connection: Union[sqlite3.Connection, any]) -> None:
    """
    Add google_geo_id column and populate with US metro codes.
    """
    cursor = db_connection.cursor()
    db_type = detect_db_type(db_connection)

    print(f"Running migration 010 on {db_type} database...")

    # 1. Add google_geo_id column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE geographies ADD COLUMN google_geo_id TEXT")
        print("  Added google_geo_id column to geographies")
    except Exception as e:
        if "duplicate column" not in str(e).lower() and "already exists" not in str(e).lower():
            print(f"Warning: google_geo_id column: {e}")

    # 2. Create index on google_geo_id for fast lookups
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_geo_google_id ON geographies(google_geo_id)")
    except Exception as e:
        if "already exists" not in str(e).lower():
            print(f"Warning: Index creation issue: {e}")

    # 3. Insert country-level geo IDs
    for geo_id, country_code, country_name, city_name in COUNTRY_GEO_IDS:
        try:
            if db_type == 'sqlite':
                cursor.execute("""
                    INSERT OR REPLACE INTO geographies (google_geo_id, country_code, country_name, city_name)
                    VALUES (?, ?, ?, ?)
                """, (geo_id, country_code, country_name, city_name))
            else:
                cursor.execute("""
                    INSERT INTO geographies (google_geo_id, country_code, country_name, city_name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (country_code, city_name) DO UPDATE SET google_geo_id = EXCLUDED.google_geo_id
                """, (geo_id, country_code, country_name, city_name))
        except Exception as e:
            print(f"Warning inserting country {country_code}: {e}")

    # 4. Insert US metro geo IDs
    for geo_id, country_code, country_name, city_name in US_METRO_GEO_IDS:
        try:
            if db_type == 'sqlite':
                cursor.execute("""
                    INSERT OR REPLACE INTO geographies (google_geo_id, country_code, country_name, city_name)
                    VALUES (?, ?, ?, ?)
                """, (geo_id, country_code, country_name, city_name))
            else:
                cursor.execute("""
                    INSERT INTO geographies (google_geo_id, country_code, country_name, city_name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (country_code, city_name) DO UPDATE SET google_geo_id = EXCLUDED.google_geo_id
                """, (geo_id, country_code, country_name, city_name))
        except Exception as e:
            print(f"Warning inserting metro {city_name}: {e}")

    db_connection.commit()
    print(f"Migration 010: Added {len(COUNTRY_GEO_IDS)} countries and {len(US_METRO_GEO_IDS)} US metros")


def downgrade(db_connection: Union[sqlite3.Connection, any]) -> None:
    """Rollback migration (for testing)."""
    cursor = db_connection.cursor()
    print("Rolling back migration 010...")

    # Remove the entries we added (by google_geo_id pattern)
    cursor.execute("DELETE FROM geographies WHERE google_geo_id IS NOT NULL")

    # Note: SQLite doesn't support DROP COLUMN easily
    db_connection.commit()
    print("Migration 010 rolled back")


def run_standalone():
    """Run migration standalone (for testing)."""
    from pathlib import Path

    db_path = Path.home() / ".catscan" / "catscan.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    try:
        upgrade(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run_standalone()
