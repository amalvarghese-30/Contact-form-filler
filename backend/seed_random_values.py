"""

seed_random_values.py

Populate random_value_pool table with 5000 values per field concept

Run once: python seed_random_values.py

"""



import random

import string

import mysql.connector

from datetime import date, timedelta





# Database config

DBCONFIG = {

    "host": "127.0.0.1",

    "port": 3306,

    "user": "root",

    "password": "",

    "database": "form_insights",

}





N_PER_FIELD = 5000





# ---------- Base data (realistic-ish) ----------



FIRST_NAMES = [

    "Aarav", "Vivaan", "Aditya", "Arjun", "Reyansh", "Vihaan", "Shaurya", "Krishna",

    "Ishaan", "Atharv", "Rahul", "Rohan", "Amit", "Siddharth", "Kunal", "Vikram",

    "Priya", "Ananya", "Aadhya", "Diya", "Isha", "Saanvi", "Myra", "Aisha",

    "Neha", "Pooja", "Sakshi", "Shreya", "Nisha", "Riya", "Meera", "Nandini",

    "John", "Michael", "David", "Daniel", "James", "Robert", "William", "Joseph",

    "Sarah", "Emily", "Jessica", "Jennifer", "Amanda", "Michelle", "Lisa", "Karen",

]



LAST_NAMES = [

    "Sharma", "Gupta", "Patel", "Shah", "Kumar", "Singh", "Verma", "Mehta",

    "Reddy", "Rao", "Iyer", "Nair", "Joshi", "Kulkarni", "Bhat", "Menon",

    "Khan", "Ahmed", "Ali", "Hassan", "Ibrahim", "Abdullah",

    "Smith", "Johnson", "Williams", "Brown", "Jones", "Davis", "Miller", "Wilson",

    "Taylor", "Anderson", "Thomas", "Moore", "Jackson", "Martin",

]



COMPANIES = [

    "Tata Consultancy Services", "Infosys", "Wipro", "HCLTech", "Tech Mahindra",

    "Reliance Industries", "Aditya Birla Group", "ICICI Bank", "HDFC Bank",

    "Axis Bank", "Larsen & Toubro", "Mahindra & Mahindra",

    "Flipkart", "Amazon India", "Swiggy", "Zomato", "Paytm", "PhonePe",

    "Google", "Microsoft", "Amazon", "Apple", "Meta", "Adobe", "Atlassian",

]



CITIES_STATES = [

    ("Mumbai", "Maharashtra"),

    ("Pune", "Maharashtra"),

    ("Thane", "Maharashtra"),

    ("Navi Mumbai", "Maharashtra"),

    ("Delhi", "Delhi"),

    ("Bengaluru", "Karnataka"),

    ("Hyderabad", "Telangana"),

    ("Chennai", "Tamil Nadu"),

    ("Kolkata", "West Bengal"),

    ("Ahmedabad", "Gujarat"),

    ("Jaipur", "Rajasthan"),

    ("Lucknow", "Uttar Pradesh"),

    ("Surat", "Gujarat"),

    ("Indore", "Madhya Pradesh"),

]



COUNTRIES = [

    "India", "United States", "United Kingdom", "Canada", "Australia",

    "Germany", "France", "Netherlands", "Singapore", "UAE",

]



SUBJECTS = [

    "Inquiry", "Support Request", "Feedback", "Demo Request", "Partnership",

    "Pricing Request", "Complaint", "Job Application", "General Question",

]



MESSAGES = [

    "Hello, I’m interested in learning more about your services. Please contact me.",

    "Hi, can you share pricing and a brief brochure for your product?",

    "Hello, I need support regarding an issue I’m facing. Please help.",

    "Hi, I would like to request a demo at your earliest convenience.",

    "Hello, I’m interested in a partnership opportunity. Please reach out.",

    "Hi, please share more information about your offerings and next steps.",

]





# ---------- Helpers ----------



def rand_digits(n: int) -> str:

    return "".join(random.choice(string.digits) for _ in range(n))



def rand_letters(n: int) -> str:

    return "".join(random.choice(string.ascii_lowercase) for _ in range(n))



def pick_full_name() -> str:

    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"



def make_email(first: str, last: str) -> str:

    domains = ["gmail.com", "outlook.com", "yahoo.com", "proton.me", "domain.com"]

    local = f"{first}.{last}".lower()

    local = "".join(ch for ch in local if ch.isalnum() or ch == ".")

    suffix = random.choice(["", "", "", str(random.randint(1, 9999))])

    return f"{local}{suffix}@{random.choice(domains)}"



def make_phone() -> str:

    # India-style 10-digit mobile; optionally +91

    first_digit = random.choice(["6", "7", "8", "9"])

    rest = rand_digits(9)

    if random.random() < 0.5:

        return f"+91{first_digit}{rest}"

    return f"{first_digit}{rest}"



def make_zip(country: str) -> str:

    # Mostly India: 6-digit PIN; otherwise 5-digit

    if country == "India":

        return str(random.randint(100000, 999999))

    return str(random.randint(10000, 99999))



def make_dob() -> str:

    # date_of_birth: YYYY-MM-DD, between 1970-01-01 and 2005-12-31

    start = date(1970, 1, 1)

    end = date(2005, 12, 31)

    delta_days = (end - start).days

    d = start + timedelta(days=random.randint(0, delta_days))

    return d.isoformat()



def make_website() -> str:

    bases = ["example.com", "example.org", "mybusiness.in", "startup.io", "company.co"]

    sub = random.choice(["www", "app", "portal", "contact", "support", ""])

    host = random.choice(bases)

    if sub:

        return f"https://{sub}.{host}"

    return f"https://{host}"



def make_address(city: str, state: str) -> str:

    area_words = [

        "Andheri", "Bandra", "Borivali", "Powai", "Vashi", "Kharghar", "Hinjewadi",

        "Koramangala", "Indiranagar", "Gachibowli", "T Nagar", "Salt Lake",

    ]

    road_words = ["Road", "Street", "Avenue", "Lane", "Marg", "Nagar"]

    flat = random.randint(101, 4506)

    bldg = random.choice(["Heights", "Residency", "Apartments", "Tower", "Enclave", "Society"])

    area = random.choice(area_words)

    roadno = random.randint(1, 99)

    road = random.choice(road_words)

    return f"Flat {flat}, {area} {bldg}, {roadno} {road}, {city}, {state}"



def ensure_table(conn) -> None:

    cur = conn.cursor()

    cur.execute(

        """

        CREATE TABLE IF NOT EXISTS random_value_pool (

            id INT AUTO_INCREMENT PRIMARY KEY,

            field_concept VARCHAR(64) NOT NULL,

            value TEXT NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )

        """

    )

    try:

        cur.execute("CREATE INDEX ix_random_value_pool_concept ON random_value_pool(field_concept)")

    except Exception:

        pass

    cur.close()



def insert_values(cur, concept: str, values):

    sql = "INSERT INTO random_value_pool (field_concept, value) VALUES (%s, %s)"

    batch = [(concept, v) for v in values]

    cur.executemany(sql, batch)





# ---------- Main seeding ----------



def build_values() -> dict:

    # Build 5000 rows per concept with realistic cross-field patterns

    values = {k: [] for k in [

        "full_name",

        "first_name",

        "last_name",

        "email",

        "phone",

        "company",

        "subject",

        "message",

        "address",

        "city",

        "state",

        "zip_code",

        "country",

        "website",

        "date_of_birth",

    ]}



    for _ in range(N_PER_FIELD):

        first = random.choice(FIRST_NAMES)

        last = random.choice(LAST_NAMES)

        full = f"{first} {last}"



        city, state = random.choice(CITIES_STATES)

        country = random.choices(

            population=COUNTRIES,

            weights=[70 if c == "India" else 3 for c in COUNTRIES],

            k=1

        )[0]



        # If country isn't India, relax city/state realism

        if country != "India" and random.random() < 0.7:

            city = random.choice(["New York", "London", "Toronto", "Sydney", "Dubai", "Singapore"])

            state = random.choice(["NA", "NA", "NA", "NA", "NA"])



        values["first_name"].append(first)

        values["last_name"].append(last)

        values["full_name"].append(full)

        values["email"].append(make_email(first, last))

        values["phone"].append(make_phone())

        values["company"].append(random.choice(COMPANIES))

        values["subject"].append(random.choice(SUBJECTS))

        values["message"].append(random.choice(MESSAGES))

        values["city"].append(city)

        values["state"].append(state)

        values["country"].append(country)

        values["zip_code"].append(make_zip(country))

        values["address"].append(make_address(city, state))

        values["website"].append(make_website())

        values["date_of_birth"].append(make_dob())



    return values





def seed_database():

    conn = mysql.connector.connect(**DBCONFIG)

    ensure_table(conn)



    cur = conn.cursor()

    try:

        cur.execute("DELETE FROM random_value_pool")

        print("✓ Cleared existing random_value_pool")



        field_data = build_values()



        # Insert per field (5000 each)

        for concept, vals in field_data.items():

            print(f"Inserting {len(vals)} values for '{concept}'...")

            # chunk insert (safer)

            chunk = 1000

            for i in range(0, len(vals), chunk):

                insert_values(cur, concept, vals[i:i+chunk])



        conn.commit()



        cur.execute(

            "SELECT field_concept, COUNT(*) AS cnt "

            "FROM random_value_pool GROUP BY field_concept ORDER BY field_concept"

        )

        rows = cur.fetchall()



        print("\n✓ SEEDING COMPLETE. Summary:")

        total = 0

        for concept, cnt in rows:

            print(f"  {concept}: {cnt} values")

            total += int(cnt)

        print(f"  TOTAL: {total} values")



    except Exception as e:

        conn.rollback()

        print(f"✗ Error: {e}")

        raise

    finally:

        cur.close()

        conn.close()





if __name__ == "__main__":

    random.seed(42)

    print("Starting random value pool seeding...")

    seed_database()




