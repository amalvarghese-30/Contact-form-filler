import sqlite3

DB_PATH = "../data/forms_insights.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # make sure there is a row with id = 1
    cur.execute("SELECT COUNT(*) FROM websites WHERE id = 1")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO websites (id, url, has_captcha, form_found) VALUES (1, ?, 0, 0)",
            ("https://httpbin.org/forms/post",),
        )
    else:
        cur.execute(
            """
            UPDATE websites
            SET url = ?, has_captcha = 0, form_found = 0
            WHERE id = 1
            """,
            ("https://httpbin.org/forms/post",),
        )

    conn.commit()
    conn.close()
    print("✅ website id=1 set to https://httpbin.org/forms/post")

if __name__ == "__main__":
    main()
