import os
import logging
import random
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackContext, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

from sqlhelper import Base, User, Post, Settings

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
print('[Predlozhka]Initializing database...')

engine = create_engine('sqlite:///database.db')
Base.metadata.create_all(engine)
Session = scoped_session(sessionmaker(bind=engine))

print('[Predlozhka]Initializing Telegram API...')
token = ''
updater = Updater(token, use_context=True)

print('[Predlozhka]Creating temp folder...')
if not os.path.exists('temp'):
    os.makedirs('temp')

print('[Predlozhka]Checking settings...')
session = Session()
settings = session.query(Settings).first()

if not settings:
    settings = Settings(False, None, None)
    session.add(settings)

initialized = settings.initialized
target_channel = settings.target_channel

if initialized:
    if target_channel:
        print('[Predlozhka]Settings...[OK], target_channel: {}'.format(target_channel))
    elif settings.initializer_id:
        print('[Predlozhka][WARN]Bot seems to be initialized, but no target selected. Annoying initializer...')
        updater.bot.send_message(settings.initializer_id, 'Warning! No target channel specified.')
    else:
        print('[Predlozhka][WARN]Bot seems to be initialized, but neither target or initializer specified. '
              'DB maintenance required!')
else:
    print('[Predlozhka][CRITICAL]Bot is not initialized! Waiting for inititalizer...')
session.commit()
session.close()

print('[Predlozhka]Declaring functions and handlers...')


def start(update: Update, context: CallbackContext):
    print('[Predlozhka][start]Start command message triggered')
    db = Session()
    if not db.query(User).filter_by(user_id=update.effective_user.id).first():
        db.add(User(update.effective_user.id))
    update.message.reply_text('Добро пожаловать! Для того чтобы предложить пост, просто отправьте изображение '
                              '(можно с текстом).')
    db.commit()


def initialize(update: Update, context: CallbackContext):
    global initialized, target_channel
    if not initialized:
        db = Session()
        print('[Predlozhka][INFO]Initialize command triggered!')
        initialized = True
        initializer = update.effective_user.id
        parameters = update.message.text.replace('/init ', '').split(';')
        print('[Predlozhka][INFO]Initializing parameters: {}'.format(parameters))
        target_channel = parameters[0]
        settings = db.query(Settings).first()
        settings.initialized = True
        settings.initializer_id = initializer
        settings.target_channel = target_channel
        update.message.reply_text('Bot initialized successfully:\n{}'.format(repr(settings)))
        print('[Predlozhka]User {} selected as admin'.format(parameters[1]))
        target_user = db.query(User).filter_by(user_id=int(parameters[1])).first()
        if target_user:
            target_user.is_admin = True
            update.message.reply_text('User {} is now admin!'.format(parameters[1]))
        else:
            print('[Predlozhka][WARN]User {} does not exists, creating...'.format(parameters[1]))
            update.message.reply_text("Warning! User {} does not exists. "
                                      "I'll create it anyway, but you need to know.".format(parameters[1]))
            db.add(User(user_id=int(parameters[1]), is_admin=True))
        db.commit()
        db.close()


def photo_handler(update: Update, context: CallbackContext):
    print('[Predlozhka][photo_handler]Image accepted, downloading...')
    db = Session()
    photo = update.message.photo[-1].get_file()
    path = 'temp/{}_{}'.format(random.randint(1, 100000000000), photo.file_path.split('/')[-1])
    photo.download(path)

    print('[Predlozhka][photo_handler]Image downloaded, generating post...')
    post = Post(update.effective_user.id, path, update.message.caption)
    db.add(post)
    db.commit()

    print('[Predlozhka][photo_handler]Sending message to admin...')
    buttons = [
        [InlineKeyboardButton('✅', callback_data=json.dumps({'post': post.post_id, 'action': 'accept'})),
         InlineKeyboardButton('❌', callback_data=json.dumps({'post': post.post_id, 'action': 'decline'}))]
    ]
    updater.bot.send_photo(db.query(User).filter_by(is_admin=True).first().user_id, open(post.attachment_path, 'rb'),
                           post.text, reply_markup=InlineKeyboardMarkup(buttons))
    db.close()

    print('[Predlozhka][photo_handler]Sending confirmation to source...')
    update.message.reply_text('Ваш пост отправлен администратору.\nЕсли он будет опубликован - вы получите сообщение.')


def callback_handler(update: Update, context: CallbackContext):
    print('[Predlozhka][callback_handler]Processing admin interaction')
    db = Session()
    if db.query(User).filter_by(user_id=update.effective_user.id).first().is_admin:
        print('[Predlozhka][callback_handler][auth_ring]Authentication successful')
        data = json.loads(update.callback_query.data)
        print('[Predlozhka][callback_handler]Data: {}'.format(data))
        post = db.query(Post).filter_by(post_id=data['post']).first()
        if post:
            print('[Predlozhka][callback_handler]Post found')
            if data['action'] == 'accept':
                print('[Predlozhka][callback_handler]Action: accept')
                updater.bot.send_photo(target_channel, open(post.attachment_path, 'rb'), caption=post.text)
                update.callback_query.answer('✅ Пост успешно отправлен')
                updater.bot.send_message(post.owner_id, 'Предложеный вами пост был опубликован')
            elif data['action'] == 'decline':
                print('[Predlozhka][callback_handler]Action: decline')
                update.callback_query.answer('Пост отклонен')
            print('[Predlozhka][callback_handler]Cleaning up...')
            try:
                os.remove(post.attachment_path)
            except:
                pass
            db.delete(post)
            updater.bot.delete_message(update.callback_query.message.chat_id, update.callback_query.message.message_id)
        else:
            update.callback_query.answer('Ошибка: пост не найден')
    else:
        print('[Predlozhka][callback_handler][auth_ring]Authentication ERROR!')
        update.callback_query.answer('Unauthorized access detected!')
    db.commit()
    db.close()

print('[Predlozhka]All init related stuff done. Waiting for something to happen...')

updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('init', initialize))
updater.dispatcher.add_handler(MessageHandler(Filters.photo, photo_handler))
updater.dispatcher.add_handler(CallbackQueryHandler(callback_handler))

updater.start_polling()
