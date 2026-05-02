import sqlite3
import telebot
import os
from telebot import types
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

def create_db():
    conn = sqlite3.connect("market.db", check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT           
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            name TEXT,
            description TEXT,
            category TEXT, 
            price REAL,
            photo_id TEXT,
            FOREIGN KEY (seller_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close() 


CATEGORIES  = ['Electronics', 'Clothing', 'Book', 'Auto', 'Other']
# Finite-State Machine, FSM) — это модель поведения системы, 
# которая в каждый момент времени 
#  находится только в одном из конечности множества состояний 
user_states = {}
item_info  = {}
search_info = {}

def category_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in CATEGORIES:
        markup.add(types.KeyboardButton(cat))
    return markup

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('Put up for sale'))
    markup.add(types.KeyboardButton('Finding things'))
    return markup

def search_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton('By category'),
        types.KeyboardButton('By keyword'),
    )
    markup.add(types.KeyboardButton('View all advertisements'))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username

    conn = sqlite3.connect('market.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("""INSERT INTO users (id, username) 
                      VALUES (?, ?)""", 
                      (user_id, username))
        conn.commit()
    conn.close()
    bot.send_message(
        message.chat.id,
        'Welcome to the mini-market! Choose an action',
        reply_markup=main_keyboard()
    )



@bot.message_handler(func=lambda message: message.text == '-')
def remove_states(message):
    user_id = message.from_user.id

    if user_id in user_states:
        del user_states[user_id]

    if user_id in item_info:
        del item_info[user_id]

    if user_id in search_info:
        del search_info[user_id]

    bot.send_message(
        message.chat.id,
        'Cancel! Choose an action:',
        reply_markup=main_keyboard()

    )

#! ============= ЛОГИКА ПРОСМОТРА ВЕЩЕЙ ============= 
@bot.message_handler(func=lambda message: message.text == 'Finding things')
def item_search(message):
    """ПОИСК ВЕЩЕЙ, НАЧАЛО"""
    user_id = message.from_user.id 
    user_states[user_id] = 'search_types'
    bot.send_message(message.chat.id, '🔍 Select a search type (or "-" to cancel:', reply_markup=search_keyboard())

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'search_types')
def search_types(message):
    """ОБРАБОТКА ВЫБОРЫ ТИПА ПОИСКА"""
    user_id = message.from_user.id 
    ms = message.text

    if ms == 'By category':
        user_states[user_id] = 'search_category'
        bot.send_message(message.chat.id, 'Select a category:',reply_markup=category_markup())
    elif ms == 'By keyword':
        user_states[user_id] = 'search_keyword'
        bot.send_message(message.chat.id, 'write the keyword (or "-")')
    elif ms == 'View all advertisements':
        conn = sqlite3.connect("market.db", check_same_thread=False)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                items.id, items.name, items.description, items.category,  items.price,
                items.photo_id, items.seller_id, users.username
            FROM items
            JOIN users ON items.seller_id = users.id
            ORDER BY items.id DESC
        """)
        items = cursor.fetchall()
        conn.close()

        if not items: 
            bot.send_message(message.chat.id, '😔 There are no products yet. ', reply_markup=main_keyboard())
            remove_states(message)
            return

        search_info[user_id] = {'items': items, 'index': 0}
        show_one_item(message.chat.id, user_id)
    else:
        bot.send_message(message.chat.id, 'Click on the button to select the searchg type!')

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'search_category')
def search_category(message):
    """SEARCH BY CATEGORY"""
    user_id = message.from_user.id
    category = message.text

    if category not in CATEGORIES:
        bot.send_message(message.chat.id, 'there is no such a category')
        return

    conn = sqlite3.connect("market.db", check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            items.id, items.name, items.description, items.category,  items.price,
            items.photo_id, items.seller_id, users.username
        FROM items
        JOIN users ON items.seller_id = users.id
        WHERE items.category = ?
        ORDER BY items.id DESC
    """, (category,))
    items = cursor.fetchall()
    conn.close()

    if not items: 
        bot.send_message(message.chat.id, '😔 There are no products yet. ', reply_markup=main_keyboard())
        remove_states(message)
        return

    search_info[user_id] = {'items': items, 'index': 0}
    show_one_item(message.chat.id, user_id)


@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'search_keyword')
def search_keyword(message):
    """SEARCH BY KEYWORD"""
    user_id = message.from_user.id
    keyword = message.text

    if len(keyword) < 2:
        bot.send_message(message.chat.id, 'Your word is to small')
        return

    conn = sqlite3.connect("market.db", check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            items.id, items.name, items.description, items.category,  items.price,
            items.photo_id, items.seller_id, users.username
        FROM items
        JOIN users ON items.seller_id = users.id
        WHERE items.name LIKE ?
                   OR items.description LIKE ?
        ORDER BY items.id DESC
    """, (f'%{keyword}%', f"%{keyword}",))
    items = cursor.fetchall()
    conn.close()

    if not items: 
        bot.send_message(message.chat.id, '😔 There are no products yet. ', reply_markup=main_keyboard())
        remove_states(message)
        return

    search_info[user_id] = {'items': items, 'index': 0}
    show_one_item(message.chat.id, user_id)



def show_one_item(chat_id, user_id, id_for_swap=None):
    """Показывает один товар и кнопки перелистывания объявления""" 
    items = search_info[user_id]['items']
    index = search_info[user_id]['index']
    one_item = items[index]
    print(one_item)
    current_info = f"""
📦 Name: {one_item[1]}
📝 Description: {one_item[2]}
💰 Price: {one_item[4]} $
📂 Category: {one_item[3]}
👤 Seller: @{one_item[7]}
    """ 

    kb = types.InlineKeyboardMarkup()
    prev_b = types.InlineKeyboardButton('◀️ Back', callback_data='prev') if index > 0 else None
    next_b = types.InlineKeyboardButton('Next ▶️', callback_data='next') if index < len(items)-1 else None
    exit_b = types.InlineKeyboardButton('Exit ❌', callback_data='exit')

    btns = [b for b in [prev_b, exit_b, next_b] if b is not None]
    kb.row(*btns)

    if id_for_swap:
        try:
            bot.delete_message(chat_id, id_for_swap)
        except:
            pass
        bot.send_photo(chat_id, one_item[5], current_info, reply_markup=kb)
    else:
        bot.send_photo(chat_id, one_item[5], current_info, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    current_index = search_info[user_id]['index']
    message_id = call.message.id

    if data == 'prev' and current_index > 0:
        search_info[user_id]['index'] -= 1
        show_one_item(call.message.chat.id, user_id, message_id)
    elif data == 'next' and current_index < len(search_info[user_id]['items']) - 1:
        search_info[user_id]['index'] += 1
        show_one_item(call.message.chat.id, user_id, message_id)
    elif data == 'exit':
        try:
            bot.delete_message(call.message.chat.id, message_id)
        except:
            pass
        remove_states(call.message)
    bot.answer_callback_query(call.id)







#! ============= ЛОГИКА СОЗДАНИЯ ОБЪЯВЛЕНИЯ ============= 

@bot.message_handler(func=lambda message: message.text == 'Put up for sale')
def sell_start(message):
    """ШАГ1 - НАЧАЛО ПРОЦЕССА ПРОДАЖИ"""
    user_id = message.from_user.id
    user_states[user_id] = 'sell_name'
    item_info[user_id] = {}
    bot.send_message(
        message.chat.id,
        '✏️ Enter the name of the item (or "-" to cancel):'
    )

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'sell_name')
def sell_name(message):
    """ШАГ 2 - ОБРАБОТКА ИМЕНИ, ЗАПРОС ОПИСАНИЯ"""
    user_id = message.from_user.id
    user_states[user_id] = 'sell_description'
    item_info[user_id]['name'] = message.text
    bot.send_message(
        message.chat.id,
        '✏️ Enter the description of the item (or "-" to cancel):'
    )

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'sell_description')
def sell_description(message):
    """ШАГ 3 - ОБРАБОТКА ОПИСАНИЯ, ЗАПРОС КАТЕГОРИИ"""
    user_id = message.from_user.id
    user_states[user_id] = 'sell_category'
    item_info[user_id]['description'] = message.text
    bot.send_message(
        message.chat.id,
        '✏️ Choose the category item (or "-" to cancel):',
        reply_markup=category_markup(),
    )


@bot.message_handler(
    func=lambda message: user_states.get(message.from_user.id) == "sell_category"
)
def sell_category(message):
    """ШАГ 4 - ОБРАБОТКА КАТЕГОРИИ, ЗАПРОС ЦЕНЫ"""
    user_id = message.from_user.id
    if message.text not in CATEGORIES:
        bot.send_message(message.chat.id,
            "There is no such category! Choose from the buttons below.",
        )
        return
    user_states[user_id] = "sell_price"
    item_info[user_id]["category"] = message.text
    bot.send_message(message.chat.id,
        '✏️ Enter the price of the item (or "-" to cancel):',
        reply_markup=main_keyboard(),
    ) 


@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'sell_price')
def sell_price(message):
    """ШАГ 5 - ОБРАБОТКА ЦЕНЫ, ЗАПРОС ФОТО""" 
    user_id = message.from_user.id
    user_states[user_id] = 'sell_photo'
    item_info[user_id]['price'] = message.text
    bot.send_message(
        message.chat.id,
        '📸 Upload a photo of the product (or "-" to cancel): ',
    )

@bot.message_handler(content_types=['photo'],
func=lambda message: user_states.get(message.from_user.id) == 'sell_photo')
def sell_photo(message):
    """ШАГ 6 - ОБРАБОТКА ФОТО, ЗАПРОС ПОДТВЕРЖДЕНИЯ""" 
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    user_states[user_id] = "sell_confirm"
    item_info[user_id]["photo_id"] = photo_id
    data = item_info[user_id]
    current_info = f"""
✅Check your data before publishing:

📦 Name: {data['name']}
📝 Description: {data['description']}
💰 Price: {data['price']} $
📂 Category: {data['category']}
    """ 
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton('Publish'),
        types.KeyboardButton('Start over'),
        types.KeyboardButton('Exit')
    )
    bot.send_photo(
        message.chat.id,
        photo_id,
        current_info
    )
    bot.send_message(message.chat.id, 'Confirm data:', reply_markup=markup)


@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'sell_confirm')
def sell_confirm(message):
    """ШАГ 6 - ОПУБЛИКОВАТЬ ИЛИ ОТМЕНИТЬ""" 
    user_id = message.from_user.id
    ms = message.text
    if ms == 'Publish':
        data=item_info[user_id]
        conn = sqlite3.connect('market.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO items
            (seller_id, name, description, category, price, photo_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, data['name'], data['description'], data['category'], 
            data['price'], data['photo_id']))
        conn.commit()
        conn.close() 

        bot.send_message(
            message.chat.id,
            '✅Product successfully published!: ',
            reply_markup=main_keyboard()
        )
        remove_states(message)
    elif ms == 'Exit':
        bot.send_message(
            message.chat.id,
            'Select an action:',
            reply_markup=main_keyboard()
        )
        remove_states(message)
    elif ms == 'Start over':
        sell_start(message)









create_db()
print('BOT IS ACTIVE')
bot.polling()










































































































































































































































































