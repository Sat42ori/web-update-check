#!/usr/bin/env python
# pylint: disable=C0116,W0613
from auth import *
import logging
import re
import shortuuid
from logic import *
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
    InvalidCallbackData,
    PicklePersistence,
    ContextTypes,
)
import html
import traceback
from telegram.constants import ParseMode
from bs4 import BeautifulSoup

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
service_keyboard = [['🔄 Zalando', '🔄 Simple Update Check', '🔄 Search for ...','🔄 Search in List', '🔄 Joblist']]

SERVICE, LINK, SIZES, INTERVAL, JOBLIST, JOBSELECT, SUC_LINK, SUC_INTERVAL, SFS_LINK, SFS_SEARCHTERM, SFS_INTERVAL, SIL_LINK, SIL_SEARCHTERM, SIL_INTERVAL  = range(14)

class Callback:
  def __init__(self, Operation, Parameter=None):
    self.Operation = Operation
    self.Parameter = Parameter

class Assignment:
  def __init__(self, JobID, ChatID, Service, Interval, Name, Link, Search_For, Stored_Update, Statistics):
    self.JobID = JobID
    self.ChatID = ChatID
    self.Service = Service
    self.Interval = Interval
    self.Name = Name
    self.Link = Link
    self.Search_For = Search_For
    self.Stored_Update = Stored_Update
    self.Statistics = Statistics
  

async def alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message, if there is an Update"""
    job = context.job
    was_soldout = []
    is_soldout = []
    try:
        available_sizes = parse_available_sizes(download_zalando_json(job.data.Link))
        if available_sizes != job.data.Stored_Update:
            message = ""

            for size in job.data.Search_For:
                if check_if_soldout(job.data.Stored_Update, size):
                    was_soldout.append(size)
                if check_if_soldout(available_sizes, size):
                    message = message + "\nSize " + size + " not available"
                    is_soldout.append(size)
                else:
                    message = message + "\nSize " + size + " is available!"
            if was_soldout != is_soldout:
                if job.data.Statistics["count"] >= 1:
                    await context.bot.send_message(job.data.ChatID, text= "Update for " + job.data.Name + message + "\n" + job.data.Link)
                    job.data.Statistics["alarm"] += 1 
                logger.info('%s Job "%s" found Availability-Update: %s', str(job.data.Service), str(job.data.Name), str(available_sizes))
                job.data.Statistics["count"] += 1 
                
            else:
                logger.info('%s Job "%s" found irrelevant Availability-Update: %s', str(job.data.Service), str(job.data.Name), str(available_sizes))
                job.data.Statistics["count"] += 1
            job.data.Stored_Update = available_sizes
        else:
            logger.info('%s Job "%s" found no Update. Stored Availability-Update: %s', str(job.data.Service), str(job.data.Name), str(job.data.Stored_Update))
            job.data.Statistics["count"] += 1
            
    except:
        logger.info("Check not Successful. Try again later.")
        message = (
            f"Check not Successful:\n"
            f"<pre>JobID = {html.escape(str(job.data.JobID))}\n"
            f"Name = {html.escape(str(job.data.Name))}\n"
            f"ChatID = {html.escape(str(job.data.ChatID))}</pre>"
            )
        # Contacting Admin...
        await context.bot.send_message(
            chat_id=Admin, text=message, parse_mode=ParseMode.HTML
        )   

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the initial Message to the user"""
    if Whitelist:
        if await check_userlist(update.message.chat_id,context):
            await update.message.reply_text(
            'Hi! Welcome to the Update Bot\n'
            'Send /cancel to stop talking to me.\n\n'
            'What service do you need?',
            reply_markup=ReplyKeyboardMarkup(
                service_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select checking Service'
            )
            )
            return SERVICE
        elif await check_userlist(update.message.chat_id,context) == False:
            message = (
                f"User {update.message.from_user.full_name} with ID {update.message.chat_id} wants to join\n"
                f"<pre>/admin_join {update.message.chat_id}</pre>\n\n")
            await context.bot.send_message(chat_id=Admin, text=message, parse_mode=ParseMode.HTML)
            await update.message.reply_text('🔒 User not recognized. Contacting Admin... 📲\nPlease stand by for confirmation.')
    else:
        await update.message.reply_text(
            'Hi! Welcome to the Update Bot\n'
            'Send /cancel to stop talking to me.\n\n'
            'What service do you need?',
            reply_markup=ReplyKeyboardMarkup(
                service_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select checking Service'
            )
            )
        return SERVICE
    #await save_to_userlist(update.message.chat_id,context)
    
    

def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    """Helper function to build the next keyboard."""
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

async def save_to_userlist(UserID, context: ContextTypes.DEFAULT_TYPE):
    if context.bot_data.get("userlist") != None:
        if UserID not in context.bot_data["userlist"]:
            context.bot_data["userlist"].append(UserID)
    else:
        context.bot_data["userlist"] = []
    await context.application.persistence.update_bot_data(context.bot_data)

async def check_userlist(UserID, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.bot_data.get("userlist") != None:
        if str(UserID) in context.bot_data["userlist"] or UserID == Admin:
            return True
        else:
            return False 
    else:
        context.bot_data["userlist"] = []
        return False
     

async def save_to_jobstorage(assignment, context: ContextTypes.DEFAULT_TYPE):
    if context.bot_data.get("jobstorage") == None:
        context.bot_data["jobstorage"] = []
    context.bot_data["jobstorage"].append(assignment)
    await context.application.persistence.update_bot_data(context.bot_data)
    

async def delete_from_jobstorage(JobID, context: ContextTypes.DEFAULT_TYPE):
    if context.bot_data.get("jobstorage") != None:
         for assignment in context.bot_data["jobstorage"]:
            if assignment.JobID == JobID:
                context.bot_data["jobstorage"].remove(assignment)
                #await context.application.persistence.flush()
                await context.application.persistence.update_bot_data(context.bot_data)
                

async def service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the user input regarding the selected service"""
    user = update.message.from_user
    logger.info("User %s requested Service: %s", user.full_name, update.message.text)
    context.user_data['service'] = update.message.text

    if update.message.text == "🔄 Zalando":
        sizelist = []
        context.user_data['sizes'] = sizelist
        await update.message.reply_text(
            'I see! Please send me the link to the website.',
            reply_markup=ReplyKeyboardRemove(),
        )

        return LINK
    elif update.message.text == "🔄 Joblist":
        keyboard = []
        keyboard_list = []
        for Job in context.job_queue.jobs():
            if update.message.chat_id == Job.data.ChatID:
                keyboard.append(InlineKeyboardButton(Job.data.Name, callback_data=Callback("select_job",Job.data.JobID)))
        if keyboard == []:
            await update.message.reply_text('No Jobs here, maybe you want to create one? /start')
            return SERVICE
        keyboard.append(InlineKeyboardButton("Cancel", callback_data=Callback("cancel_selection")))
        await update.message.reply_text(
            'Look at all the Jobs! To view details from a Job simply select it below:',
            reply_markup=InlineKeyboardMarkup(build_menu(keyboard,n_cols=1)))
        ReplyKeyboardRemove()
        return JOBLIST
    elif update.message.text == "🔄 Simple Update Check":
        await update.message.reply_text('Simple Update Check is a basic tool which checks for any ever so small updates on a website. '+
            'You may get "false positives", if the website includes some sort of timestamp.\n\nPlease send me the link to the website.')
        return SUC_LINK
    elif update.message.text == "🔄 Search for ...":
        await update.message.reply_text('With "Search for ..." you can limit the query to certain words. '+
            '\n\nPlease send me the link to the website.')
        return SFS_LINK
    elif update.message.text == "🔄 Search in List":
        await update.message.reply_text('With "Search in list" you will be notified of new list entries.'+
            '\n\nPlease send me the link to the website.')
        return SIL_LINK

async def joblist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes the user input regarding the joblist"""
    user = update.message.from_user
    for Job in context.job_queue.jobs():
        if update.message.text == Job.data.Name:
            if update.message.chat_id == Job.data.ChatID:
                await update.message.reply_text(
                    'Details of Job "' + str(Job.data.Name) + '"\n\n'
                    'Job ID: "' + str(Job.data.JobID) + '"\n\n'
                    'Service: ' + str(Job.data.Service) + '\n\n'
                    'Count: ' + str(Job.data.Statistics["count"]) + '\n\n' 
                    '# of Alarms: ' + str(Job.data.Statistics["alarm"]) + '\n\n' )
                logger.info('%s Job "%s" has been selected by User %s', str(Job.data.Service), str(Job.data.Name), user.full_name)
    return SERVICE

def jobdelete(update: Update, context: CallbackContext):
    """Processes the user input to delete a job"""
    user = update.message.from_user
    for Job in context.job_queue.jobs():
        if update.message.text == Job.data.Name:
            if update.message.chat_id == Job.data.ChatID:
                Job.schedule_removal()
                update.message.reply_text("Job removed")
                logger.info('%s Job "%s" has been removed by User %s', str(Job.data.Service), str(Job.data.Name), user.full_name)
    update.message.reply_text(
        'Send /cancel to stop talking to me.\n\n'
        'What service do you need?',
        reply_markup=ReplyKeyboardMarkup(
            service_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select checking Service'
        )
    )
    return SERVICE

"""
Implementation of SUC specific functions 
"""

async def suc_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the Link provided by the user."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info("%s Link received from %s: %s", context.user_data['service'], user.full_name, update.message.text)
    try:
        data = download(update.message.text)
        context.user_data['link'] = update.message.text
        context.user_data['name'] = update.message.text
    except:
        await update.message.reply_text("Something has gone terribly wrong. Maybe your link is not valid. Try again.")
        logger.info("Link from %s invalid and failed to download.", user.full_name)
        return SUC_LINK
    if data != None:
        await update.message.reply_text(
            "I've checked your link and... everything checks out.")
    else:
        await update.message.reply_text("Something has gone terribly wrong. There was no content on this website. Maybe your link is not valid. Try again.")
        logger.info("Link from %s invalid and content empty", user.full_name)
        return SUC_LINK
    logger.info('%s Link from %s is valid.', context.user_data['service'], user.full_name)
    #update.message.reply_text('Now send me as many Sizes as you want and press /finish if you are done.')
    await update.message.reply_text(
        'Okay, Thanks! Now I need your Interval in Seconds',
        reply_markup=ReplyKeyboardMarkup([["3","5","10","30","60","300","600","1800"]], one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select Inteval' ))

    return SUC_INTERVAL

async def suc_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the interval provided by the user, creates a scheduled update and ends the conversation."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info("Interval from %s: %s", user.full_name, update.message.text)
    try:
        temp_interval = int(update.message.text)
        a = Assignment(
            shortuuid.uuid(),
            chat_id,
            context.user_data['service'],
            temp_interval,
            context.user_data['name'],
            context.user_data['link'],
            None,
            "",
            {"count": 0,"alarm": 0}
            )
        context.job_queue.run_repeating(suc_alarm, interval=a.Interval, data=a, name=str(a.JobID))
        await save_to_jobstorage(a, context)
        #b = context.bot_data.get("jobstorage")
        #print(b)
        tmp_msg = 'Searching for updates on "' + context.user_data['link'] + '" every ' + str(update.message.text) + ' seconds.'
        await update.message.reply_text(tmp_msg)

    except (IndexError, ValueError):
        await update.message.reply_text('There was a problem with your Interval. Please send me the interval in seconds.')
        return INTERVAL
    await update.message.reply_text('Thank you! Press /start to start again.', reply_markup=ReplyKeyboardRemove())
    logger.info('Job from %s saved. ' + tmp_msg, user.full_name)
    return ConversationHandler.END

async def suc_alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message, if there is an Update"""
    job = context.job
    
    try:
        current_data = download(job.data.Link)
        if current_data != job.data.Stored_Update:
            if job.data.Statistics["count"] >= 1:
                await context.bot.send_message(job.data.ChatID, text= "Update for " + job.data.Link)
                job.data.Statistics["alarm"] += 1 
            logger.info('%s Job "%s" found Update.', str(job.data.Service), str(job.data.Link))
            job.data.Stored_Update = current_data
            job.data.Statistics["count"] += 1 
            
        else:
            logger.info('%s Job "%s" found no Update.', str(job.data.Service), str(job.data.Link))
            job.data.Statistics["count"] += 1 
            
    except:
        logger.info("Check not Successful. Try again later.")

"""
Implementation of SFS specific functions
"""

async def sfs_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores the Link provided by the user."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    print(chat_id)
    #await update.message.reply_text(context.bot_data["jobstorage"].JobID)
    logger.info("%s Link received from %s: %s", context.user_data['service'], user.full_name, update.message.text)
    try:
        data = download(update.message.text)
        context.user_data['link'] = update.message.text
    except:
        await update.message.reply_text("Something has gone terribly wrong. Maybe your link is not valid. Try again.")
        logger.info("Link from %s invalid and failed to download.", user.full_name)
        return SFS_LINK
    if data != None:
        await update.message.reply_text(
            "I've checked your link and... everything checks out.")
    else:
        await update.message.reply_text("Something has gone terribly wrong. There was no content on this website. Maybe your link is not valid. Try again.")
        logger.info("Link from %s invalid and content empty", user.full_name)
        return SFS_LINK
    logger.info('%s Link from %s is valid.', context.user_data['service'], user.full_name)
    #update.message.reply_text('Now send me as many Sizes as you want and press /finish if you are done.')
    await update.message.reply_text(
        'Great! Now send me the exact term(s) you want to search for. You will be notified if there are any changes concerning your search term (eg. "Out of Stock" or "Add to Shopping Cart")')

    return SFS_SEARCHTERM

async def sfs_searchterm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores the searchterm provided by the user."""
    user = update.message.from_user
    
    context.user_data['Searchterm'] = update.message.text
    context.user_data['name'] = update.message.text + ' @ ' + context.user_data['link']
    logger.info("Searchterm from %s is: %s", user.full_name, update.message.text)
    await update.message.reply_text(
            'Okay, Thanks! Now I need your Interval in Seconds',
            reply_markup=ReplyKeyboardMarkup([["3","5","10","30","60","300","600","1800"]], one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select Inteval' ))
    return SFS_INTERVAL

async def sfs_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the interval provided by the user, creates a scheduled update and ends the conversation."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info("Interval from %s: %s", user.full_name, update.message.text)
    try:
        temp_interval = int(update.message.text)
        a = Assignment(
            shortuuid.uuid(),
            chat_id,
            context.user_data['service'],
            temp_interval,
            context.user_data['name'],
            context.user_data['link'],
            context.user_data['Searchterm'],
            bool,
            {"count": 0,"alarm": 0}
            )
        context.job_queue.run_repeating(sfs_alarm, interval=a.Interval, data=a, name=str(a.JobID))
        await save_to_jobstorage(a, context)
        tmp_msg = 'Searching for updates on "' + context.user_data['Searchterm'] + '" @ ' + context.user_data['link'] + ' every ' + str(update.message.text) + ' seconds.'
        await update.message.reply_text(tmp_msg)

    except (IndexError, ValueError):
        await update.message.reply_text('There was a problem with your Interval. Please send me the interval in seconds.')
        return INTERVAL
    await update.message.reply_text('Thank you! Press /start to start again.', reply_markup=ReplyKeyboardRemove())
    logger.info('Job from %s saved. ' + tmp_msg, user.full_name)
    return ConversationHandler.END

async def sfs_alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message, if there is an Update"""
    job = context.job
    Term_Present = bool
    try:
        data = download(job.data.Link)
        if data != None and job.data.Search_For in data:
            Term_Present = True
        else:
            Term_Present = False
        if Term_Present != job.data.Stored_Update:
            if job.data.Statistics["count"] >= 1:
                await context.bot.send_message(job.data.ChatID, text= "Update for " + job.data.Link)
                job.data.Statistics["alarm"] += 1
            logger.info('%s Job "%s" found an Update.', str(job.data.Service), str(job.data.Link))
            job.data.Stored_Update = Term_Present
            job.data.Statistics["count"] += 1
            
        else:
            logger.info('%s Job "%s" found no Update.', str(job.data.Service), str(job.data.Link))
            job.data.Statistics["count"] += 1
            
    except:
        logger.info("Check not Successful. Try again later.")

"""
Implementation of SIL specific functions
"""

async def sil_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores the Link provided by the user."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    print(chat_id)
    #await update.message.reply_text(context.bot_data["jobstorage"].JobID)
    logger.info("%s Link received from %s: %s", context.user_data['service'], user.full_name, update.message.text)
    try:
        data = download(update.message.text)
        context.user_data['link'] = update.message.text
    except:
        await update.message.reply_text("Something has gone terribly wrong. Maybe your link is not valid. Try again.")
        logger.info("Link from %s invalid and failed to download.", user.full_name)
        return SIL_LINK
    if data != None:
        await update.message.reply_text(
            "I've checked your link and... everything checks out.")
    else:
        await update.message.reply_text("Something has gone terribly wrong. There was no content on this website. Maybe your link is not valid. Try again.")
        logger.info("Link from %s invalid and content empty", user.full_name)
        return SIL_LINK
    logger.info('%s Link from %s is valid.', context.user_data['service'], user.full_name)
    await update.message.reply_text(
        'Great! Now send me the ID of the list. You will be notified if there are any changes to the list.')

    return SIL_SEARCHTERM

async def sil_searchterm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores the searchterm provided by the user."""
    user = update.message.from_user
    
    context.user_data['Searchterm'] = update.message.text
    context.user_data['name'] = update.message.text + ' @ ' + context.user_data['link']
    logger.info("Searchterm from %s is: %s", user.full_name, update.message.text)
    await update.message.reply_text(
            'Okay, Thanks! Now I need your Interval in Seconds',
            reply_markup=ReplyKeyboardMarkup([["3","5","10","30","60","300","600","1800"]], one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select Inteval' ))
    return SIL_INTERVAL

async def sil_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the interval provided by the user, creates a scheduled update and ends the conversation."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info("Interval from %s: %s", user.full_name, update.message.text)
    try:
        temp_interval = int(update.message.text)
        a = Assignment(
            shortuuid.uuid(),
            chat_id,
            context.user_data['service'],
            temp_interval,
            context.user_data['name'],
            context.user_data['link'],
            context.user_data['Searchterm'],
            [],
            {"count": 0,"alarm": 0}
            )
        context.job_queue.run_repeating(sil_alarm, interval=a.Interval, data=a, name=str(a.JobID))
        await save_to_jobstorage(a, context)
        tmp_msg = 'Searching for updates on "' + context.user_data['Searchterm'] + '" @ ' + context.user_data['link'] + ' every ' + str(update.message.text) + ' seconds.'
        await update.message.reply_text(tmp_msg)

    except (IndexError, ValueError):
        await update.message.reply_text('There was a problem with your Interval. Please send me the interval in seconds.')
        return INTERVAL
    await update.message.reply_text('Thank you! Press /start to start again.', reply_markup=ReplyKeyboardRemove())
    logger.info('Job from %s saved. ' + tmp_msg, user.full_name)
    return ConversationHandler.END

async def sil_alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message if a new element is added to the HTML element identified by the given ID or first class occurrence."""
    job = context.job
    try:
        # Download the HTML content from the link
        html_content = download(job.data.Link, True)
        #with open("a.html", 'r', encoding='utf-8') as html_file:
        # html_content = html_file.read()
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try to find an element by ID first
        target_element = soup.find(id=job.data.Search_For)
        
        if not target_element:
            # If no element with the ID was found, try to find the first occurrence of the class
            target_element = soup.find(class_=job.data.Search_For)
        
        if target_element:
            # Get all child elements (direct children) within the target element
            child_elements = target_element.find_all(recursive=False)  # Non-recursive, direct children
            
            # Extract unique content/identifiers of each element (e.g., its HTML or any other identifiable attribute)
            current_element_list = [str(element) for element in child_elements]

            # Remove any timestamps ('ts=[numbers]') from the list
            cleaned_list = []
            for element in current_element_list:
                cleaned_element = re.sub(r'ts=\d+', '', element).strip()
                cleaned_list.append(cleaned_element)
            current_element_list = cleaned_list
        else:
            logger.info("No element found with the specified ID or class.")
            return


        new_elements = set(current_element_list) - set(job.data.Stored_Update)

        if not new_elements:
            logger.info('%s Job "%s" found no new elements.', str(job.data.Service), str(job.data.Link))
        else: 
            if job.data.Statistics["count"] >= 1:
                await context.bot.send_message(
                        job.data.ChatID, 
                        text=f"Update for {job.data.Link}: New element(s) added to the list with ID or class {job.data.Search_For}"
                    )
                job.data.Statistics["alarm"] += 1
                logger.info('%s Job "%s" found an update: New elements added to the list.', str(job.data.Service), str(job.data.Link))
            else:
                logger.info("Initialized element set for the first time.")


        job.data.Stored_Update = current_element_list
        job.data.Statistics["count"] += 1
    except Exception as e:
        logger.info("Check not successful. Error: %s. Try again later.", str(e))


"""
Implementation of Zalando specific functions 
"""

async def link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the Link provided by the user."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    data = download_zalando_json(update.message.text)
    logger.info("%s Link received from %s: %s", context.user_data['service'], user.full_name, update.message.text)

    try:
        available_sizes = parse_available_sizes(data)
        all_sizes = parse_all_sizes(data)
        soldout_sizes = find_soldout_items(all_sizes, available_sizes)
        context.user_data['link'] = update.message.text
        context.user_data['name'] = str(parse_name(data))
        await update.message.reply_text(
            "I've checked your link and... everything checks out.\nThese are the sizes that are potentially available:" + str(all_sizes)+
            "\nThese are the sizes that are currenty sold-out: "+str(soldout_sizes))
    except:
        await update.message.reply_text("Something has gone terribly wrong. Maybe your link is not a Zalando link. Try again.")
        logger.info("Link from %s invalid", user.full_name)
        logger.info("Link from %s invalid", user.full_name)
        return LINK
    logger.info('%s Link from %s is valid. Name set to "%s"', context.user_data['service'], user.full_name, context.user_data['name'])
    #update.message.reply_text('Now send me as many Sizes as you want and press /finish if you are done.')
    keyboard = all_sizes
    keyboard.append("Done")
    await update.message.reply_text(
        'Now send me as many Sizes as you want and press /done if you are done.',
        reply_markup=ReplyKeyboardMarkup(
            [keyboard], one_time_keyboard=False, resize_keyboard=True, input_field_placeholder='Select Size(s)'
        )
    )

    return SIZES

async def sizes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the Sizes provided by the user."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    
    context.user_data['sizes'].append(update.message.text)
    await update.message.reply_text('Okay, got it.')
    logger.info("Size from %s: %s, Sizelist: %s", user.full_name, update.message.text, str(context.user_data['sizes']))
    return SIZES

async def sizes_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Determines if the user input (regarding the sizes) was valid and asks for the interval."""
    if context.user_data['sizes'] == []:
        await update.message.reply_text('I need at least one Size to look for. Try again.')
        return SIZES
    user = update.message.from_user
    chat_id = update.message.chat_id
    await update.message.reply_text(
        'Okay, Thanks! Now I need your Interval in Seconds',
        reply_markup=ReplyKeyboardMarkup([["3","5","10","30","60","300","600","1800"]], one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select Inteval' ))
    return INTERVAL

async def interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the interval provided by the user, creates a scheduled update and ends the conversation."""
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info("Interval from %s: %s", user.full_name, update.message.text)
    try:
        temp_interval = int(update.message.text)
        a = Assignment(
            shortuuid.uuid(),
            chat_id,
            context.user_data['service'],
            temp_interval,
            context.user_data['name'],
            context.user_data['link'],
            context.user_data['sizes'],
            [],
            {"count": 0,"alarm": 0}
            )
        
        context.job_queue.run_repeating(alarm, interval=a.Interval, data=a, name=str(a.JobID))
        await save_to_jobstorage(a, context)
        await update.message.reply_text('Searching for "'+context.user_data['name']+'" in Size(s) ' + str(context.user_data['sizes']) + ' every ' + str(update.message.text) + ' seconds.')

    except (IndexError, ValueError):
        await update.message.reply_text('There was a problem with your Interval. Please send me the interval in seconds.')
        return INTERVAL
    await update.message.reply_text('Thank you! Press /start to start again.', reply_markup=ReplyKeyboardRemove())
    logger.info('Job from %s saved. Searching for "%s" in Size(s) %s every %s seconds.', user.full_name, context.user_data['name'], str(context.user_data['sizes']), str(update.message.text))
    return ConversationHandler.END

async def joblist_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    
   
    await query.answer()
    #query = update.effective_chat
    user = query.from_user
    #print(context.bot_data.get("jobstorage"))
 
    if query.data.Operation == "back_to_joblist":
        keyboard = []
        keyboard_list = []
        for Job in context.job_queue.jobs():
            if user.id == Job.data.ChatID:
                keyboard.append(InlineKeyboardButton(Job.data.Name, callback_data=Callback("select_job",Job.data.JobID)))
        if keyboard == []:
            await query.edit_message_text('No Jobs here, maybe you want to create one?', reply_markup=ReplyKeyboardMarkup(
            service_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select checking Service'))
            return SERVICE
        keyboard.append(InlineKeyboardButton("Cancel", callback_data=Callback("cancel_selection")))
        await query.edit_message_text(
            'Look at all the Jobs! To view details from a Job simply select it below:',
            reply_markup=InlineKeyboardMarkup(build_menu(keyboard,n_cols=1)))
        return JOBLIST
    
    if query.data.Operation  == "select_job":
        for Job in context.job_queue.jobs():
            if query.data.Parameter == Job.data.JobID:
                if user.id == Job.data.ChatID:
                    keyboard = [
                        InlineKeyboardButton("Back to Joblist", callback_data=Callback("back_to_joblist")),
                        InlineKeyboardButton("Delete Job", callback_data=Callback("delete", Job.data.JobID))
                        ]
                    await query.edit_message_text(
                        '⚙️ Details of Job "' + str(Job.data.Name) + '"\n\n'
                        '🗂️ Job ID: "' + str(Job.data.JobID) + '"\n\n'
                        '📠 Service: ' + str(Job.data.Service) + '\n\n'
                        '⏲️ Interval: ' + str(Job.data.Interval) + " Seconds" + '\n\n'
                        '🔁 Count: ' + str(Job.data.Statistics["count"]) + '\n\n' 
                        '🚨 # of Alarms: ' + str(Job.data.Statistics["alarm"]) + '\n\n',
                        reply_markup=InlineKeyboardMarkup(build_menu(keyboard,n_cols=1)))
                    logger.info('%s Job "%s" has been selected by User %s', str(Job.data.Service), str(Job.data.Name), user.full_name)

    if query.data.Operation == "delete":
        for Job in context.job_queue.jobs():
            if query.data.Parameter == Job.data.JobID:
                if user.id == Job.data.ChatID:
                    await delete_from_jobstorage(Job.data.JobID, context)
                    Job.schedule_removal()
                    await query.edit_message_text("Job removed.")
                    logger.info('%s Job "%s" has been removed by User %s', str(Job.data.Service), str(Job.data.Name), user.full_name)
        await query.message.reply_text(
            'Send /cancel to stop talking to me.\n\n'
            'What service do you need?',
            reply_markup=ReplyKeyboardMarkup(
                service_keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder='Select checking Service'
            )
        )
        return SERVICE

    if query.data.Operation  == "cancel_selection":
        logger.info("User %s canceled the conversation.", user.full_name)
        await query.message.reply_text(
        'Bye! Press /start to start again.', reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # await query.answer()
        # CallbackQueries need to be answered, even if no notification to the user is needed
        # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery

    
async def handle_invalid_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Informs the user that the button is no longer available."""
    await update.callback_query.answer()
    await update.effective_message.edit_text(
        "Sorry, I could not process this button click 😕 Please send /start to get a new keyboard."
    )
    #query.edit_message_text(text=f"Selected option: {query.data}")


async def cancel(update: Update, context: CallbackContext):
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.full_name)
    await update.message.reply_text(
        'Bye! Press /start to start again.', reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

async def initialize_queue(application: Application):
    print(application.bot_data.get("jobstorage"))
    if application.bot_data.get("jobstorage") != None:
        logger.info("Initializion started")  
        for assignment in application.bot_data["jobstorage"]:
            if assignment.Service == "🔄 Zalando":
                application.job_queue.run_repeating(alarm, interval=assignment.Interval, data=assignment, name=str(assignment.JobID))
                logger.info("Initialized JobID " + assignment.JobID)
            if assignment.Service == "🔄 Simple Update Check":
                application.job_queue.run_repeating(suc_alarm, interval=assignment.Interval, data=assignment, name=str(assignment.JobID))
                logger.info("Initialized JobID " + assignment.JobID)
            if assignment.Service == "🔄 Search for ...":
                application.job_queue.run_repeating(sfs_alarm, interval=assignment.Interval, data=assignment, name=str(assignment.JobID))
                logger.info("Initialized JobID " + assignment.JobID)
            if assignment.Service == "🔄 Search in List":
                application.job_queue.run_repeating(sil_alarm, interval=assignment.Interval, data=assignment, name=str(assignment.JobID))
                logger.info("Initialized JobID " + assignment.JobID)
    else:
        logger.info("Initializion failed, no jobstorage found")
             
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n"
        f"context.chat_data = {html.escape(str(context.chat_data))}\n\n"
        f"context.user_data = {html.escape(str(context.user_data))}\n\n"
        f"context.bot_data = {html.escape(str(context.bot_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    if len(message) > 4096:
        message = message[0:4080] + "</pre>"
    # Contacting Admin...
    await context.bot.send_message(
        chat_id=Admin, text=message, parse_mode=ParseMode.HTML
    )

async def admin(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.chat_id == Admin:
        message = (
                f"<pre>▫️▫️▫️ HELLO ADMIN ▫️▫️▫️\n\n"
                f"Bot Data\n"
                f"context.bot_data = {html.escape(str(context.bot_data.get('jobstorage')))}\n\n"
                f"Job queue = {html.escape(str(context.job_queue.jobs()))}\n\n"
                f"Userlist = {html.escape(str(context.bot_data.get('userlist')))}</pre>\n\n"
            )
        for assignment in context.bot_data["jobstorage"]:
            message = message + f"<pre>ASSIGNMENT ID = {html.escape(str(assignment.JobID))}\n"
            message = message + f"--> Name: = {html.escape(str(assignment.Name))}\n"
            message = message + f"--> ChatID: = {html.escape(str(assignment.ChatID))}\n"
            a = assignment.Stored_Update
            if len(str(a)) > 100:   
                a = str(a)[0:100]
            message = message + f"--> Stored Update: = {html.escape(str(a))}</pre>\n\n"
        message = message + f"🤖 Admin Commands:\n"
        message = message + f"🔥 Purge data: <pre>/admin_purge [queue/jobstorage/userlist]</pre>\n"
        message = message + f"🗑️ Delete job from queue & jobstorage: <pre>/admin_delete [JobID/ChatID]</pre>\n"
        message = message + f"🆗 Whitelist user:<pre>/admin_join [UserID]</pre>\n"
        message = message + f"💬 Message to user:<pre>/admin_message [UserID/userlist] [Message]</pre>\n"
        if len(message) > 4096:   
                a = str(a)[0:4095]
        await context.bot.send_message(chat_id=Admin, text=message, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text('You are not Admin, disregarding request.')

async def admin_purge(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.chat_id == Admin:
        if len(context.args) >= 1:
            if context.args[0] == "jobstorage":
                context.bot_data["jobstorage"] = []
                await context.application.persistence.update_bot_data(context.bot_data)
                # context.args[0]
                message = (
                        f"<pre>Bot Data Jobstorage purged:</pre>\n"
                        f"<pre>context.bot_data = {html.escape(str(context.bot_data.get('jobstorage')))}</pre>\n\n"
                    )
                await context.bot.send_message(chat_id=Admin, text=message, parse_mode=ParseMode.HTML)
            elif context.args[0] == "queue":
                for Job in context.job_queue.jobs():
                    Job.schedule_removal()
                await update.message.reply_text('Queue deleted.')
            elif context.args[0] == "userlist":
                context.bot_data["userlist"] = []
                await context.application.persistence.update_bot_data(context.bot_data)
                await update.message.reply_text('Userlist deleted.')
            else:
                await update.message.reply_text('Parameter not found')
        else:
            await update.message.reply_text('Parameter not given')
    else:
        await update.message.reply_text('You are not Admin, disregarding request.')

async def admin_delete(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.chat_id == Admin:
        if len(context.args) >= 1:
            for Job in context.job_queue.jobs():
                if context.args[0] == Job.data.JobID:
                    await delete_from_jobstorage(Job.data.JobID, context)
                    Job.schedule_removal()
                    await update.message.reply_text('Deleted: ' + Job.data.JobID )
                    logger.info("Admin deleted JobID " + Job.data.JobID)
                elif context.args[0] == str(Job.data.ChatID):
                    await delete_from_jobstorage(Job.data.JobID, context)
                    Job.schedule_removal()
                    await update.message.reply_text('Deleted via ChatID: ' + Job.data.JobID )
                    logger.info("Admin deleted JobID " + Job.data.JobID)
        else:
            await update.message.reply_text('Parameter not given')
    else:
        await update.message.reply_text('You are not Admin, disregarding request.')

async def admin_message(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.chat_id == Admin:
        if len(context.args) >= 2:
            if context.args[0] == "userlist":
                a = " ".join(context.args[1:])
                for i in context.bot_data["userlist"]:
                    await context.bot.send_message(chat_id=i, text=a)
                    await update.message.reply_text(f'Message sent via Userlist to {i}.')
                    logger.info(f'Admin sent Message to Userlist.')
            else:
                await context.bot.send_message(chat_id=context.args[0], text=" ".join(context.args[1:]))
                await update.message.reply_text(f'Message sent to {context.args[0]}.')
                logger.info(f'Admin sent Message to User {context.args[0]}.')
        else:
            await update.message.reply_text('Parameters not given')
    else:
        await update.message.reply_text('You are not Admin, disregarding request.')

async def admin_join(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.chat_id == Admin:
        if len(context.args) >= 1:
            await save_to_userlist(context.args[0], context)
            await update.message.reply_text(f'User {context.args[0]} added.')
            await context.bot.send_message(chat_id=context.args[0], text="🔓 Account unlocked! Press /start to continue.")
            logger.info(f'Admin added User {context.args[0]}.')
        else:
            await update.message.reply_text('Parameter not given')
    else:
        await update.message.reply_text('You are not Admin, disregarding request.')


def main() -> None:
    """Run the bot."""
    persistence = PicklePersistence(filepath="bot_storage", update_interval=60)
    # Create the Application and pass it your bot's token.
    # Saved queue data can only be restored after the Application was initialized
    application = (
        Application.builder()
        .token(Token)
        .post_init(initialize_queue) 
        .persistence(persistence)
        .arbitrary_callback_data(True)
        .read_timeout(7)
        .get_updates_read_timeout(7)
        .pool_timeout(3)
        .build()
    )



    # Add conversation handler with states
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SERVICE: [MessageHandler(filters.Regex('^(🔄 Zalando|🔄 Simple Update Check|🔄 Search for ...|🔄 Search in List)|🔄 Joblist$'), service)],
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, link)],
            SIZES: [CommandHandler("done", sizes_done), MessageHandler(filters.Regex('Done'), sizes_done), MessageHandler(filters.TEXT, sizes)],
            INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, interval)],
            JOBLIST: [
                CallbackQueryHandler(joblist_menu),
                MessageHandler(filters.Regex('Cancel'), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, joblist)
                ],
            SUC_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, suc_link)],
            SUC_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, suc_interval)],
            SFS_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, sfs_link)],
            SFS_SEARCHTERM: [MessageHandler(filters.TEXT & ~filters.COMMAND, sfs_searchterm)],
            SFS_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, sfs_interval)],
            SIL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, sil_link)],
            SIL_SEARCHTERM: [MessageHandler(filters.TEXT & ~filters.COMMAND, sil_searchterm)],
            SIL_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, sil_interval)],
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   CommandHandler('start', start),
                   CommandHandler('admin', admin),
                   CommandHandler('admin_purge', admin_purge),
                   CommandHandler('admin_delete', admin_delete),
                   CommandHandler('admin_message', admin_message),
                   CommandHandler('admin_join', admin_join)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(
        CallbackQueryHandler(handle_invalid_button, pattern=InvalidCallbackData)
    )
    application.add_error_handler(error_handler)
    
    # Start the Bot
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)
     
    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.


if __name__ == '__main__':
    main()