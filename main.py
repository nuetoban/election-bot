import sqlite3
import logging
import os

from dotenv import load_dotenv
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, filters

load_dotenv()

logging.basicConfig(handlers=[logging.FileHandler('log.txt', 'w', 'utf-8')],
                    level=logging.INFO,
                    format='[*] {%(pathname)s:%(lineno)d} %(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_schema():
    with sqlite3.connect("database.sqlite3") as conn:
        c = conn.cursor()

        # Init schema
        c.execute('''
            CREATE TABLE IF NOT EXISTS candidates (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER UNIQUE,
                name     TEXT,
                username TEXT
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS voted (
                id        INTEGER PRIMARY KEY,
                name      TEXT,
                username  TEXT,
                voted_for INTEGER,

                FOREIGN KEY(voted_for) REFERENCES candidates(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id        INTEGER PRIMARY KEY,
                name      TEXT,
                username  TEXT,
                voted_for INTEGER,

                FOREIGN KEY(voted_for) REFERENCES candidates(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS new_chat_members (
                id        INTEGER PRIMARY KEY
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value BOOL
            )
        ''')

        try:
            c.execute('INSERT INTO settings (key, value) VALUES ("active_poll", true)')
        except:
            print('already presented')

def error(update, context):
    print(f'Update "{update}" caused error "{context.error}"')
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def send_poll(update, context):
    if update.message.chat.id != -1001493773956:
        return

    fu = update.message.from_user
    if fu.id != 150804080:
        return
    
    try:
        with sqlite3.connect("database.sqlite3") as conn:
            c = conn.cursor()
            cs = list(c.execute('select * from candidates').fetchall())

        keyboard = [[InlineKeyboardButton(f'{c[0]}. {c[2]} {c[3]}', callback_data=c[0])] for c in cs]

        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('ВЫБЕРИ КАНДИДАТА', reply_markup=reply_markup)
    except Exception as e:
        print(e)

def button(update, context):
    query = update.callback_query

    if query.from_user.id not in ids:
        query.answer(text="Ты не можешь голосовать")
        return 

    with sqlite3.connect("database.sqlite3") as conn:
        c = conn.cursor()
        fu = query.from_user

        try:
            c.execute(
                'INSERT INTO voted (id, name, username, voted_for) VALUES (?, ?, ?, ?)',
                (fu.id, fu.full_name, fu.username, query.data)
            )
        except Exception as e:
            print(e)
            query.answer(text="Ты уже проголосовал!")

    query.answer(text="Ты проголосовал за кандидата {}".format(query.data))

def top(update, context):
    with sqlite3.connect("database.sqlite3") as conn:
        c = conn.cursor()
        cs = list(c.execute('''
            SELECT candidates.name, COUNT(*) AS num
            FROM voted
            JOIN candidates ON candidates.id = voted.voted_for
            GROUP BY voted_for
            ORDER BY num DESC
        ''').fetchall())

    n = 1 
    mes = ''
    for c in cs:
        mes += f'{n}. {c[0]} - {c[1]} голосов\n'
        n += 1

    update.message.reply_text(mes)

def clist(update, context):
    with sqlite3.connect("database.sqlite3") as conn:
        c = conn.cursor()
        cs = list(c.execute('''
            SELECT name
            FROM candidates
        ''').fetchall())

    n = 1 
    mes = ''
    for c in cs:
        mes += f'{n}. {c[0]}\n'
        n += 1

    update.message.reply_text(mes)

def register_poll(update, context):
    if update.message.chat.id != -1001493773956:
        return

    with sqlite3.connect("database.sqlite3") as conn:
        c = conn.cursor()
        active_poll = c.execute('select * from settings where key = "active_poll"').fetchone()[0]
        if not active_poll:
            update.message.reply_text('Регистрация завершена')
            return

    with sqlite3.connect("database.sqlite3") as conn:
        c = conn.cursor()
        try:
            fu = update.message.from_user
            c.execute('''
                INSERT INTO candidates (user_id, name, username)
                VALUES (?, ?, ?)
            ''', (fu.id, fu.full_name, fu.username))
            update.message.reply_text('Теперь ты участвуешь в голосовании! ✅')
        except Exception as e:
            print(e)
            update.message.reply_text('Ты уже участвуешь! 🤬')

def who_voted(update, context):
    with sqlite3.connect("database.sqlite3") as conn:
        c = conn.cursor()
        candidates = list(c.execute('''
            select candidates.id, candidates.name from voted
            join candidates on candidates.id = voted.voted_for
            group by candidates.id order by voted_for;
        '''))

        message = ''
        for ca in candidates:
            c = conn.cursor()
            voted = list(c.execute(f'select * from voted where voted_for = {ca[0]}'))
            message += f'{ca[0]}. {escape(ca[1])}:\n'
            message += ", ".join([f'<a href="tg://user?id={v[0]}">{escape(v[1])}</a>' for v in voted])
            message += '\n\n'

        update.message.reply_text(message, parse_mode=ParseMode.HTML)

def new_chat_members(update, context):
    ncm = update.message.new_chat_members
    for u in ncm:
        c.execute(
            'INSERT INTO new_chat_members (id) VALUES (?)',
            (u.id,)
        )

def stop_reg(update, context):
    fu = update.message.from_user
    if fu.id != 150804080:
        return

    c.execute(
        'INSERT INTO new_chat_members (id) VALUES (?)',
        (u.id)
    )

def main():
    init_schema()

    with open('ids1.txt', 'r') as f:
        ids_raw = f.read()

    global ids
    ids = set([int(i.strip()) for i in ids_raw.split('\n') if i])

    bot_token = os.getenv('BOT_TOKEN')
    updater = Updater(bot_token, use_context=True)

    dp = updater.dispatcher
    dp.bot.set_my_commands([
        ('top', 'Показать рейтинг кандидатов'),
        ('send_poll', 'Отправить опрос (для админов)'),
        ('register_poll', 'Принять участие в опросе'),
        ('who_voted', 'Показать кто голосовал'),
        ('candidates_list', 'Показать список кандидатов'),
    ])

    dp.add_handler(CommandHandler('send_poll', send_poll))
    dp.add_handler(CommandHandler('register_poll', register_poll))
    dp.add_handler(CommandHandler('stop_reg', stop_reg))
    dp.add_handler(CommandHandler('candidates_list', clist))
    dp.add_handler(CommandHandler('top', top))
    dp.add_handler(CommandHandler('who_voted', who_voted))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(filters.Filters.status_update.new_chat_members, new_chat_members))

    dp.add_error_handler(error)

    print('Starting polling')
    updater.start_polling(clean=True)
    updater.idle()


if __name__ == '__main__':
    main()
