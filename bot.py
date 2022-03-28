#!/usr/bin/env python
# pylint: disable=C0116,W0613
from auth import Token
import logging
from logic import *
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

SERVICE, LINK, SIZES, INTERVAL, JOBLIST, SUC_LINK, SUC_INTERVAL, BA_SELECT = range(8)

def alarm(context: CallbackContext) -> None:
    """Send the alarm message, if there is an Update"""
    job = context.job
    was_soldout = []
    is_soldout = []
    try:
        available_sizes = parse_available_sizes(download_zalando_json(job.context.Link))
        if available_sizes != job.context.Stored_Update:
            message = ""

            for size in job.context.Sizes:
                if check_if_soldout(job.context.Stored_Update, size):
                    was_soldout.append(size)
                if check_if_soldout(available_sizes, size):
                    message = message + "\nSize " + size + " not available"
                    is_soldout.append(size)
                else:
                    message = message + "\nSize " + size + " is available!"
            if was_soldout != is_soldout:
                context.bot.send_message(job.context.ChatID, text= "Update for " + job.context.Name + message + "\n" + job.context.Link)
                logger.info('%s Job "%s" found Availability-Update: %s', str(job.context.Service), str(job.context.Name), str(available_sizes))
                
            else:
                logger.info('%s Job "%s" found irrelevant Availability-Update: %s', str(job.context.Service), str(job.context.Name), str(available_sizes))
            job.context.Stored_Update = available_sizes
        else:
            logger.info('%s Job "%s" found no Update. Stored Availability-Update: %s', str(job.context.Service), str(job.context.Name), str(job.context.Stored_Update))
            
    except:
        logger.info("Check not Successful. Try again later.")

def start(update: Update, context: CallbackContext) -> int:
    reply_keyboard = [['🔄 Zalando', '🔄 Simple Update Check', '🔄 Bürgeramt', '🔄 Joblist']]

    update.message.reply_text(
        'Hi! Welcome to the Update Bot\n'
        'Send /cancel to stop talking to me.\n\n'
        'What service do you need?',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select checking Service'
        )
    )

    return SERVICE

def build_menu(buttons,n_cols,header_buttons=None,footer_buttons=None):
  menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
  if header_buttons:
    menu.insert(0, header_buttons)
  if footer_buttons:
    menu.append(footer_buttons)
  return menu

def service(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    logger.info("User %s requested Service: %s", user.first_name, update.message.text)
    context.user_data['service'] = update.message.text

    if update.message.text == "🔄 Zalando":
        sizelist = []
        context.user_data['sizes'] = sizelist
        update.message.reply_text(
            'I see! Please send me the link to the website.',
            reply_markup=ReplyKeyboardRemove(),
        )
        return LINK
    elif update.message.text == "🔄 Joblist":
        keyboard = []
        keyboard_list = []
        for Job in context.job_queue.jobs():
            if update.message.chat_id == Job.context.ChatID:
                keyboard.append(Job.context.Name)
        if keyboard == []:
            update.message.reply_text('No Jobs here, maybe you want to create one?')
            return SERVICE
        keyboard.append("Cancel")        
        update.message.reply_text(
            'Look at all the Jobs! To remove a Job simply select it from the keyboard.',
            reply_markup=ReplyKeyboardMarkup(build_menu(keyboard,n_cols=1), one_time_keyboard=True, resize_keyboard=False, input_field_placeholder='Select Job to remove:'))
        return JOBLIST
    elif update.message.text == "🔄 Simple Update Check":
        update.message.reply_text('Simple Update Check is a basic tool which checks for any ever so small updates on a website.'+
            'You may get "false positives", if the website includes some sort of timestamp.\n\nPlease send me the link to the website.')
        return SUC_LINK
    elif update.message.text == "🔄 Bürgeramt":
        update.message.reply_text('Simple Update Check is a basic tool which checks for any ever so small updates on a website.'+
            'You may get "false positives", if the website includes some sort of timestamp.\n\nPlease send me the link to the website.')
        return BA_SELECT


def joblist(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    for Job in context.job_queue.jobs():
        if update.message.text == Job.context.Name:
            if update.message.chat_id == Job.context.ChatID:
                Job.schedule_removal()
                update.message.reply_text("Job removed")
                logger.info('%s Job "%s" has been removed by User %s', str(Job.context.Service), str(Job.context.Name), user.first_name)
    reply_keyboard = [['🔄 Zalando', '🔄 Simple Update Check', '🔄 Bürgeramt', '🔄 Joblist']]
    update.message.reply_text(
        'Send /cancel to stop talking to me.\n\n'
        'What service do you need?',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select checking Service'
        )
    )
    return SERVICE
"""
Implementation of SUC specific functions 
"""
class SUC_Assignment:
  def __init__(self, ChatID, Service, Name, Link, Stored_Update):
    self.ChatID = ChatID
    self.Service = Service
    self.Name = Name
    self.Link = Link
    self.Stored_Update = Stored_Update

def suc_link(update: Update, context: CallbackContext) -> int:
    """Stores the Link and asks for a location."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    
    logger.info("%s Link received from %s: %s", context.user_data['service'], user.first_name, update.message.text)
    try:
        data = download(update.message.text)
        context.user_data['link'] = update.message.text
        context.user_data['name'] = update.message.text
    except:
        update.message.reply_text("Something has gone terribly wrong. Maybe your link is not valid. Try again.")
        logger.info("Link from %s invalid and failed to download.", user.first_name)
        return LINK
    if data != None:
        update.message.reply_text(
            "I've checked your link and... everything checks out.")
    else:
        update.message.reply_text("Something has gone terribly wrong. There was no content on this website. Maybe your link is not valid. Try again.")
        logger.info("Link from %s invalid and content empty", user.first_name)
        return LINK
    logger.info('%s Link from %s is valid.', context.user_data['service'], user.first_name)
    #update.message.reply_text('Now send me as many Sizes as you want and press /finish if you are done.')
    update.message.reply_text(
        'Okay, Thanks! Now I need your Interval in Seconds',
        reply_markup=ReplyKeyboardMarkup([["3","5","10","30","60","300","600","1800"]], one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select Inteval' ))

    return SUC_INTERVAL


def suc_interval(update: Update, context: CallbackContext) -> int:
    """Stores the info about the user and ends the conversation."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info("Interval from %s: %s", user.first_name, update.message.text)
    try:
        a = SUC_Assignment(
            chat_id,
            context.user_data['service'],
            context.user_data['name'],
            context.user_data['link'],
            "")
        context.job_queue.run_repeating(suc_alarm, int(update.message.text), context=a, name=str(chat_id))
        update.message.reply_text('Searching for updates on "' + context.user_data['link'] + '" every ' + str(update.message.text) + ' seconds.')

    except (IndexError, ValueError):
        update.message.reply_text('There was a problem with your Interval. Please send me the interval in seconds.')
        return INTERVAL
    update.message.reply_text('Thank you! Press /start to start again.', reply_markup=ReplyKeyboardRemove())
    logger.info('Job from %s saved. Searching for updates on "' + context.user_data['link'] + '" every ' + str(update.message.text) + ' seconds.')
    return ConversationHandler.END

def suc_alarm(context: CallbackContext) -> None:
    """Send the alarm message, if there is an Update"""
    job = context.job
    
    try:
        data = download(job.context.Link)
        if data != job.context.Stored_Update:
            context.bot.send_message(job.context.ChatID, text= "Update for " + job.context.Link)
            logger.info('%s Job "%s" found Update.', str(job.context.Service), str(job.context.Link))
            job.context.Stored_Update = data
        else:
            logger.info('%s Job "%s" found no Update.', str(job.context.Service), str(job.context.Link))
            
    except:
        logger.info("Check not Successful. Try again later.")

"""
Implementation of Zalando specific functions 
"""
def link(update: Update, context: CallbackContext) -> int:
    """Stores the Link and asks for a location."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    data = download_zalando_json(update.message.text)
    logger.info("%s Link received from %s: %s", context.user_data['service'], user.first_name, update.message.text)

    try:
        available_sizes = parse_available_sizes(data)
        all_sizes = parse_all_sizes(data)
        soldout_sizes = find_soldout_items(all_sizes, available_sizes)
        context.user_data['link'] = update.message.text
        context.user_data['name'] = str(parse_name(data))
        update.message.reply_text(
            "I've checked your link and... everything checks out.\nThese are the sizes that are potentially available:" + str(all_sizes)+
            "\nThese are the sizes that are currenty sold-out: "+str(soldout_sizes))
    except:
        update.message.reply_text("Something has gone terribly wrong. Maybe your link is not a Zalando link. Try again.")
        logger.info("Link from %s invalid", user.first_name)
        return LINK
    logger.info('%s Link from %s is valid. Name set to "%s"', context.user_data['service'], user.first_name, context.user_data['name'])
    #update.message.reply_text('Now send me as many Sizes as you want and press /finish if you are done.')
    keyboard = all_sizes
    keyboard.append("Done")
    update.message.reply_text(
        'Now send me as many Sizes as you want and press /done if you are done.',
        reply_markup=ReplyKeyboardMarkup(
            [keyboard], one_time_keyboard=False, resize_keyboard=True, input_field_placeholder='Select Size(s)'
        )
    )

    return SIZES

def sizes(update: Update, context: CallbackContext) -> int:
    """Stores the Link and asks for a location."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    
    context.user_data['sizes'].append(update.message.text)
    update.message.reply_text('Okay, got it.')
    logger.info("Size from %s: %s, Sizelist: %s", user.first_name, update.message.text, str(context.user_data['sizes']))
    return SIZES

def sizes_done(update: Update, context: CallbackContext) -> int:
    """Stores the Link and asks for a location."""
    if context.user_data['sizes'] == []:
        update.message.reply_text('I need at least one Size to look for. Try again.')
        return SIZES
    user = update.message.from_user
    chat_id = update.message.chat_id
    update.message.reply_text(
        'Okay, Thanks! Now I need your Interval in Seconds',
        reply_markup=ReplyKeyboardMarkup([["3","5","10","30","60","300","600","1800"]], one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select Inteval' ))
    return INTERVAL

class Assignment:
  def __init__(self, ChatID, Service, Link, Sizes, Name, Stored_Update):
    self.ChatID = ChatID
    self.Service = Service
    self.Link = Link
    self.Sizes = Sizes
    self.Name = Name
    self.Stored_Update = Stored_Update

def interval(update: Update, context: CallbackContext) -> int:
    """Stores the info about the user and ends the conversation."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info("Interval from %s: %s", user.first_name, update.message.text)
    try:
        a = Assignment(
            chat_id,
            context.user_data['service'],
            context.user_data['link'],
            context.user_data['sizes'],
            context.user_data['name'],
            [])
        context.job_queue.run_repeating(alarm, int(update.message.text), context=a, name=str(chat_id))
        update.message.reply_text('Searching for "'+context.user_data['name']+'" in Size(s) ' + str(context.user_data['sizes']) + ' every ' + str(update.message.text) + ' seconds.')

    except (IndexError, ValueError):
        update.message.reply_text('There was a problem with your Interval. Please send me the interval in seconds.')
        return INTERVAL
    update.message.reply_text('Thank you! Press /start to start again.', reply_markup=ReplyKeyboardRemove())
    logger.info('Job from %s saved. Searching for "%s" in Size(s) %s every %s seconds.', user.first_name, context.user_data['name'], str(context.user_data['sizes']), str(update.message.text))
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text(
        'Bye! Press /start to start again.', reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(Token)
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SERVICE: [MessageHandler(Filters.regex('^(🔄 Zalando|🔄 Simple Update Check|🔄 Bürgeramt|🔄 Joblist)$'), service)],
            LINK: [MessageHandler(Filters.text & ~Filters.command, link)],
            SIZES: [CommandHandler("done", sizes_done), MessageHandler(Filters.regex('Done'), sizes_done), MessageHandler(Filters.text, sizes)],
            INTERVAL: [MessageHandler(Filters.text & ~Filters.command, interval)],
            JOBLIST: [MessageHandler(Filters.regex('Cancel'), cancel),MessageHandler(Filters.text & ~Filters.command, joblist)],
            SUC_LINK: [MessageHandler(Filters.text & ~Filters.command, suc_link)],
            SUC_INTERVAL: [MessageHandler(Filters.text & ~Filters.command, suc_interval)],
        },
        fallbacks=[CommandHandler('cancel', cancel),CommandHandler('start', start)],
    )

    dispatcher.add_handler(conv_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()