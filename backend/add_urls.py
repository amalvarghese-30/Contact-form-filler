import sqlite3

# Connect to database
conn = sqlite3.connect('../data/urls.db')
cursor = conn.cursor()

# URLs to add
urls = [
    'https://www.amazon.com',
    'https://www.microsoft.com',
    'https://www.google.com',
    'https://www.apple.com',
    'https://www.facebook.com',
    'https://www.netflix.com',
    'https://www.spotify.com',
    'https://www.linkedin.com',
    'https://www.twitter.com',
    'https://www.youtube.com',
    'https://www.instagram.com',
    'https://www.github.com',
    'https://www.stackoverflow.com',
    'https://www.medium.com',
    'https://www.dev.to',
    'https://www.airbnb.com',
    'https://www.uber.com',
    'https://www.tesla.com',
    'https://www.paypal.com',
    'https://www.stripe.com',
    'https://www.slack.com',
    'https://www.zoom.us',
    'https://www.figma.com',
    'https://www.canva.com',
    'https://www.notion.so',
    'https://www.trello.com',
    'https://www.asana.com',
    'https://www.docker.com',
    'https://www.aws.amazon.com',
    'https://www.mongodb.com',
]

# Add each URL
added = 0
for url in urls:
    try:
        cursor.execute(
            'INSERT INTO company_urls (url, status) VALUES (?, ?)',
            (url, 'pending')
        )
        added += 1
        print(f'✅ Added: {url}')
    except Exception as e:
        print(f'❌ Error: {url} - {str(e)}')

conn.commit()
conn.close()

print(f'\n✅ Successfully added {added} URLs to database!')
print('🔄 Refresh your dashboard to see them all!')
