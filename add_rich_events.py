import json

with open('data/events.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

rich_events = {
    'park': {'coins': 50, 'text': '💎 Рич появился в парке! Он раздаёт золотые билеты! +50 монет и золотой билет.'},
    'forest': {'coins': 60, 'text': '💎 Рич появился в лесу! Он искал грибы, но раздаёт золотые билеты! +60 монет и золотой билет.'},
    'city': {'coins': 70, 'text': '💎 Рич появился в городе! Он угощает всех мороженым и раздаёт золотые билеты! +70 монет и золотой билет.'},
    'beach': {'coins': 80, 'text': '💎 Рич появился на пляже! Он строит замки из песка и раздаёт золотые билеты! +80 монет и золотой билет.'},
    'castle': {'coins': 100, 'text': '💎 Рич появился в замке! Он стал королём на день и раздаёт золотые билеты! +100 монет и золотой билет.'},
    'volcano': {'coins': 120, 'text': '💎 Рич появился у вулкана! Он закалил свой характер и раздаёт золотые билеты! +120 монет и золотой билет.'},
    'space': {'coins': 150, 'text': '💎 Рич появился в космосе! Он прилетел на своей ракете и раздаёт золотые билеты! +150 монет и золотой билет.'}
}

for loc_id, loc_data in rich_events.items():
    if loc_id in data:
        rich_event = {
            'id': f'{loc_id}_rich_appears',
            'type': 'rich',
            'weight': 10,
            'reward': {'coins': loc_data['coins'], 'item': 'golden_ticket'},
            'text': loc_data['text']
        }
        data[loc_id].insert(0, rich_event)

with open('data/events.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('✅ Rich events added to all locations')
